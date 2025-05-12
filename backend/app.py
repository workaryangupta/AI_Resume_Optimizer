import io
import os
import base64
import logging
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2

# Import sentence_transformers directly (no need for patching in newer versions)
from sentence_transformers import SentenceTransformer, util

# Use ReportLab for PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# ─── Load embedding model ───────────────────────────────────────────────────────
logging.info("Loading embedding model...")
try:
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    logging.info("Model loaded successfully")
except Exception as e:
    logging.error("Failed to load model: %s", e)
    raise

# ─── Helper: Extract text from PDF ──────────────────────────────────────────────
def extract_text_from_pdf(pdf_file) -> str:
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text.strip()
    except Exception as e:
        logging.error("Error extracting text from PDF: %s", e)
        raise

# ─── Helper: Generate PDF from plain text using ReportLab ────────────────────────
def generate_pdf_from_text(text: str) -> bytes:
    buffer = io.BytesIO()
    width, height = A4
    margin = 40  # points margin

    c = canvas.Canvas(buffer, pagesize=A4)

    # Register DejaVuSans for Unicode support
    font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    if os.path.isfile(font_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
        c.setFont("DejaVuSans", 12)
    else:
        logging.warning(f"DejaVuSans.ttf not found at {font_path}; using Helvetica fallback.")
        c.setFont("Helvetica", 12)

    textobj = c.beginText()
    textobj.setTextOrigin(margin, height - margin)
    textobj.setLeading(14)

    for line in text.split("\n"):
        textobj.textLine(line)

    c.drawText(textobj)
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()

# ─── Suggestion logic ──────────────────────────────────────────────────────────
def parse_bullet_points(text: str) -> list[str]:
    HEADINGS = {
        "Key Responsibilities",
        "Required Skills & Qualifications",
        "Must-Have Skills",
        "Good-to-Have Skills",
        "About the Role",
        "Job Description",
        "Minimum Qualifications"
    }
    BULLET_SYMBOLS = ("•", "✅", "-", "✔", "▶")

    bullets = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s in HEADINGS:
            continue
        if re.match(r'^[A-Z][A-Za-z0-9\s&/]+:\s*$', s):
            continue
        for sym in BULLET_SYMBOLS:
            if s.startswith(sym):
                s = s[len(sym):].strip()
                break
        if s:
            bullets.append(s)
    return bullets

def cluster_job_bullets(bullets: list[str], threshold: float = 0.8) -> list[str]:
    embeddings = embedding_model.encode(bullets, convert_to_tensor=True)
    clusters: list[tuple[int, list[int]]] = []

    for i, emb in enumerate(embeddings):
        placed = False
        for rep_idx, idxs in clusters:
            if float(util.pytorch_cos_sim(embeddings[rep_idx], emb)) >= threshold:
                idxs.append(i)
                placed = True
                break
        if not placed:
            clusters.append((i, [i]))
    return [bullets[rep] for rep, _ in clusters]

def generate_suggestions_with_clustering(
    resume_text: str,
    job_description: str,
    threshold: float = 0.35,
    cluster_threshold: float = 0.8
) -> str:
    raw = parse_bullet_points(job_description)
    if not raw:
        return "No job bullets detected in the description."

    deduped = cluster_job_bullets(raw, threshold=cluster_threshold)
    job_emb = embedding_model.encode(deduped, convert_to_tensor=True)
    resume_lines = [l for l in resume_text.splitlines() if l.strip()]
    resume_emb = embedding_model.encode(resume_lines, convert_to_tensor=True)

    missing = []
    for i, b in enumerate(deduped):
        best = float(util.pytorch_cos_sim(job_emb[i], resume_emb).max())
        if best < threshold:
            missing.append(b)

    if not missing:
        return "✅ Your resume already covers most points from the job description!"
    out = "Consider adding the following keywords/points:\n\n"
    out += "\n\n".join(f"• {m}" for m in missing)
    return out

# ─── API Endpoints ──────────────────────────────────────────────────────────────
@app.route('/extract_resume', methods=['POST'])
def extract_resume():
    if 'resume' not in request.files:
        return jsonify(error="No resume file provided."), 400
    try:
        text = extract_text_from_pdf(request.files['resume'])
        return jsonify(resume_text=text)
    except Exception as e:
        logging.error("Error in extract_resume: %s", e)
        return jsonify(error=str(e)), 500

@app.route('/analyze', methods=['POST'])
def analyze_resume():
    resume_text = request.form.get('resume_text', '').strip()
    if not resume_text and 'resume' in request.files:
        resume_text = extract_text_from_pdf(request.files['resume'])
    if not resume_text:
        return jsonify(error="No resume provided."), 400

    job_desc = request.form.get('job_description', '').strip()
    if not job_desc:
        return jsonify(error="Job description is required."), 400

    try:
        sugg = generate_suggestions_with_clustering(resume_text, job_desc)
        return jsonify(suggestions=sugg)
    except Exception as e:
        logging.error("Error in analyze: %s", e)
        return jsonify(error=str(e)), 500

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify(error="No text provided."), 400
    try:
        pdf_bytes = generate_pdf_from_text(text)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        return jsonify(pdf=pdf_b64)
    except Exception as e:
        logging.error("Error in generate_pdf: %s", e)
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)