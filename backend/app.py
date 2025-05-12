import logging
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
from sentence_transformers import SentenceTransformer, util

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# ─── Load embedding model ───────────────────────────────────────────────────────
logging.info("Loading embedding model…")
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# ─── Helper Functions ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_file) -> str:
    """
    Read all pages from a PDF and return the extracted text.
    """
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text.strip()
    except Exception as e:
        logging.error("Error extracting text from PDF: %s", e)
        raise

def parse_bullet_points(text: str) -> list[str]:
    """
    Split the job description into meaningful lines/bullets,
    skipping known headings and empty lines.
    """
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
        line = line.strip()
        if not line or line in HEADINGS:
            continue
        if re.match(r'^[A-Z][A-Za-z0-9\s&/]+:\s*$', line):
            continue
        for sym in BULLET_SYMBOLS:
            if line.startswith(sym):
                line = line[len(sym):].strip()
                break
        if line:
            bullets.append(line)
    return bullets

def cluster_job_bullets(bullets: list[str],
                        embedding_model: SentenceTransformer,
                        threshold: float = 0.8) -> list[str]:
    """
    Cluster similar bullets via semantic embeddings and
    return one representative per cluster.
    """
    embeddings = embedding_model.encode(bullets, convert_to_tensor=True)
    clusters: list[tuple[int, list[int]]] = []

    for i, emb in enumerate(embeddings):
        placed = False
        for rep_idx, idxs in clusters:
            sim = float(util.pytorch_cos_sim(embeddings[rep_idx], emb))
            if sim >= threshold:
                idxs.append(i)
                placed = True
                break
        if not placed:
            clusters.append((i, [i]))

    return [bullets[rep] for rep, _ in clusters]

def generate_suggestions_with_clustering(resume_text: str,
                                         job_description: str,
                                         embedding_model: SentenceTransformer,
                                         threshold: float = 0.35,
                                         cluster_threshold: float = 0.8) -> str:
    """
    1) Parse & dedupe job bullets
    2) Compare against resume lines via embeddings
    3) Return a formatted suggestion string
    """
    raw = parse_bullet_points(job_description)
    if not raw:
        return "No job bullets detected in the description."

    deduped = cluster_job_bullets(raw, embedding_model, threshold=cluster_threshold)

    job_emb = embedding_model.encode(deduped, convert_to_tensor=True)
    resume_lines = [l for l in resume_text.splitlines() if l.strip()]
    resume_emb = embedding_model.encode(resume_lines, convert_to_tensor=True)

    missing = []
    for i, bullet in enumerate(deduped):
        sim_scores = util.pytorch_cos_sim(job_emb[i], resume_emb)
        best = float(sim_scores.max())
        if best < threshold:
            missing.append(bullet)

    if not missing:
        return "✅ Your resume already covers most points from the job description!"

    # Format output
    output = "Consider adding the following keywords/points:\n\n"
    for b in missing:
        output += f"• {b}\n\n"
    return output.strip()


# ─── API Endpoints ──────────────────────────────────────────────────────────────

@app.route('/extract_resume', methods=['POST'])
def extract_resume():
    """Extract text from the uploaded PDF and return it."""
    if 'resume' not in request.files:
        return jsonify(error="No resume file provided."), 400
    try:
        text = extract_text_from_pdf(request.files['resume'])
        return jsonify(resume_text=text)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/analyze', methods=['POST'])
def analyze_resume():
    """
    Accept either:
      • resume_text in form data (preferred), or
      • a PDF file under 'resume'
    Plus job_description in form data.
    Return only the suggestions.
    """
    # 1) Get resume text
    resume_text = request.form.get('resume_text', '').strip()
    if not resume_text:
        if 'resume' not in request.files:
            return jsonify(error="No resume provided."), 400
        resume_text = extract_text_from_pdf(request.files['resume'])

    # 2) Get job description
    job_desc = request.form.get('job_description', '').strip()
    if not job_desc:
        return jsonify(error="Job description is required."), 400

    # 3) Generate suggestions
    sugg = generate_suggestions_with_clustering(
        resume_text,
        job_desc,
        embedding_model=embedding_model
    )

    return jsonify(suggestions=sugg)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
