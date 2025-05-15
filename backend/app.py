import io
import os
import re
import base64
import logging
from typing import List

from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
from sentence_transformers import SentenceTransformer, util
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ─── Flask App Setup ──────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# ─── Configuration ────────────────────────────────────────────────────────────

# MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
MODEL_NAME = "google/flan-t5-small"
DEJAVU_TTF = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")

# ─── Load Embedding Model ────────────────────────────────────────────────────

logging.info(f"Loading embedding model {MODEL_NAME}")
try:
    embedding_model = SentenceTransformer(MODEL_NAME)
    logging.info("✅ Model loaded successfully")
except Exception as e:
    logging.error("❌ Failed to load model: %s", e)
    raise

# ─── Helpers: PDF Extraction & Generation ─────────────────────────────────────

def extract_text_from_pdf(pdf_file) -> str:
    """Extract all text from an uploaded PDF."""
    reader = PyPDF2.PdfReader(pdf_file)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()

def generate_pdf_from_text(text: str) -> bytes:
    """
    Convert plain text into a PDF in-memory, using DejaVuSans for Unicode support.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 40

    # Register and select font
    if os.path.isfile(DEJAVU_TTF):
        pdfmetrics.registerFont(TTFont("DejaVuSans", DEJAVU_TTF))
        c.setFont("DejaVuSans", 12)
    else:
        logging.warning("DejaVuSans.ttf not found, using Helvetica")
        c.setFont("Helvetica", 12)

    textobj = c.beginText(margin, height - margin)
    textobj.setLeading(14)
    for line in text.splitlines():
        textobj.textLine(line)
    c.drawText(textobj)
    c.showPage()
    c.save()

    buf.seek(0)
    return buf.read()

# ─── Helpers: Suggestion Logic ────────────────────────────────────────────────

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

def parse_bullet_points(text: str) -> List[str]:
    """
    Split job description into meaningful bullets, skipping headings.
    """
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

def cluster_job_bullets(bullets: List[str], threshold: float = 0.8) -> List[str]:
    """
    Cluster similar bullets via embeddings; return one representative per cluster.
    """
    embeddings = embedding_model.encode(bullets, convert_to_tensor=True)
    reps = []
    clusters = []

    for i, emb in enumerate(embeddings):
        placed = False
        for rep_idx in reps:
            sim = float(util.pytorch_cos_sim(embeddings[rep_idx], emb))
            if sim >= threshold:
                placed = True
                break
        if not placed:
            reps.append(i)

    return [bullets[i] for i in reps]

def generate_suggestions_with_clustering(
    resume_text: str,
    job_description: str,
    threshold: float = 0.35,
    cluster_threshold: float = 0.8
) -> str:
    """
    1) Parse & dedupe bullets
    2) Compare vs resume via embeddings
    3) Return formatted suggestion string
    """
    bullets = parse_bullet_points(job_description)
    if not bullets:
        return "No job bullets detected in the description."

    deduped = cluster_job_bullets(bullets, threshold=cluster_threshold)
    job_emb = embedding_model.encode(deduped, convert_to_tensor=True)
    resume_lines = [l for l in resume_text.splitlines() if l.strip()]
    resume_emb = embedding_model.encode(resume_lines, convert_to_tensor=True)

    missing = []
    for i, b in enumerate(deduped):
        score = float(util.pytorch_cos_sim(job_emb[i], resume_emb).max())
        if score < threshold:
            missing.append(b)

    if not missing:
        return "✅ Your resume already covers most points from the job description!"

    out = ["Consider adding the following keywords/points:\n"]
    out += [f"• {m}\n" for m in missing]
    return "".join(out).strip()

# ─── Flask Routes ─────────────────────────────────────────────────────────────

@app.route('/extract_resume', methods=['POST'])
def extract_resume():
    """Extract text from uploaded PDF → return JSON."""
    if 'resume' not in request.files:
        return jsonify(error="No resume file provided."), 400
    try:
        text = extract_text_from_pdf(request.files['resume'])
        return jsonify(resume_text=text)
    except Exception as e:
        logging.error("extract_resume error: %s", e)
        return jsonify(error=str(e)), 500

@app.route('/analyze', methods=['POST'])
def analyze_resume():
    """
    Accepts resume_text or PDF + job_description.
    Returns {"suggestions": "..."}.
    """
    # get resume text
    resume_text = request.form.get('resume_text', '').strip()
    if not resume_text and 'resume' in request.files:
        resume_text = extract_text_from_pdf(request.files['resume'])
    if not resume_text:
        return jsonify(error="No resume provided."), 400

    # get job description
    job_desc = request.form.get('job_description', '').strip()
    if not job_desc:
        return jsonify(error="Job description is required."), 400

    try:
        sugg = generate_suggestions_with_clustering(resume_text, job_desc)
        return jsonify(suggestions=sugg)
    except Exception as e:
        logging.error("analyze error: %s", e)
        return jsonify(error=str(e)), 500

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf_endpoint():
    """Convert posted text → PDF (base64)."""
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify(error="No text provided."), 400
    try:
        pdf_bytes = generate_pdf_from_text(text)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        return jsonify(pdf=pdf_b64)
    except Exception as e:
        logging.error("generate_pdf error: %s", e)
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    # Local dev server
    app.run(debug=True, host="0.0.0.0", port=5001)
