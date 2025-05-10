import os
import io
import base64
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2

# Use fpdf2 (same import name "from fpdf import FPDF", but install "fpdf2")
from fpdf import FPDF

# NLP + ML libraries
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer, util

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

###############################################################################
# 1. Load or initialize local NLP models
###############################################################################

# (A) For rewriting with a local language model (Flan-T5)
MODEL_NAME = "google/flan-t5-small"  # smaller model than "base"
logging.info("Loading local model and tokenizer. This may take a while on first run...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# (B) For generating suggestions with TF-IDF
vectorizer = TfidfVectorizer(stop_words="english")

###############################################################################
# 2. Helper Functions
###############################################################################

def extract_text_from_pdf(pdf_file):
    """
    Extract all text from a PDF file using PyPDF2.
    """
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logging.error("Error extracting text from PDF: " + str(e))
        raise

    
# Initialize a local embedding model once (outside the function).
# "all-MiniLM-L6-v2" is a small, fast model for semantic similarity.
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

import re

def parse_bullet_points(text: str):
    """
    Split the job description into bullet points or meaningful lines,
    skipping known headings and ignoring empty lines.
    """

    # Common headings we want to skip
    HEADINGS = {
        "Key Responsibilities",
        "Required Skills & Qualifications",
        "Must-Have Skills",
        "Good-to-Have Skills",
        "About the Role",
        "Required Skills & Qualifications",
        "Agile & Collaboration",  # example
        "Job Description",        # example
    }

    # Bullet symbols or prefixes we look for
    BULLET_SYMBOLS = ("•", "✅", "-", "✔", "▶")

    bullet_points = []
    
    # Split text by line
    lines = text.splitlines()
    
    for line in lines:
        # Strip whitespace
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # If the entire line matches a known heading, skip it
        if line in HEADINGS:
            continue
        
        # Optionally, skip lines that look like headings (heuristic: short lines ending with ':')
        # e.g. "Key Responsibilities:", "Required Skills:"
        if re.match(r'^[A-Z][A-Za-z0-9\s&/]+:\s*$', line):
            continue
        
        # Check if the line starts with a bullet symbol
        # If yes, remove it and any trailing space
        for sym in BULLET_SYMBOLS:
            if line.startswith(sym):
                # remove the symbol
                line = line[len(sym):].strip()
                break  # no need to check other symbols
        
        # After trimming bullet symbols, skip if it’s now empty
        if not line:
            continue

        # At this point, we have a legitimate bullet/line
        bullet_points.append(line)
    
    return bullet_points


def cluster_job_bullets(bullets, embedding_model, threshold=0.8):
    """
    Naive approach to cluster similar bullets using sentence embeddings.
    Returns a list of representative bullets, one per cluster.
    """
    # Embed all bullets once
    bullet_embeddings = embedding_model.encode(bullets, convert_to_tensor=True)
    
    clusters = []  # list of (rep_index, [indices in cluster])
    representative_bullets = []

    for i, bullet in enumerate(bullets):
        added_to_cluster = False

        for cluster_rep_idx, cluster_indices in clusters:
            # Compare to the representative bullet of this cluster
            rep_embedding = bullet_embeddings[cluster_rep_idx]
            current_embedding = bullet_embeddings[i]
            sim = float(util.pytorch_cos_sim(rep_embedding, current_embedding))

            if sim >= threshold:
                # Belongs to this cluster
                cluster_indices.append(i)
                added_to_cluster = True
                break
        
        if not added_to_cluster:
            # Create a new cluster with this bullet as the representative
            clusters.append((i, [i]))

    # Build the final list of representative bullets
    for (rep_idx, idx_list) in clusters:
        # Optionally, pick the "longest bullet" or the first bullet as the rep.
        # Here, we just pick the first bullet in the cluster.
        representative_bullets.append(bullets[rep_idx])

    return representative_bullets



def generate_suggestions_with_clustering(resume_text, job_description, embedding_model, threshold=0.5, cluster_threshold=0.8):
    """
    1) Parse & cluster job bullets to remove duplicates.
    2) Check coverage vs. resume lines.
    """
    # 1) Parse bullets
    raw_bullets = parse_bullet_points(job_description)
    if not raw_bullets:
        return "No job bullets found in the description."

    # 2) Cluster bullets to remove near-duplicates
    deduped_bullets = cluster_job_bullets(raw_bullets, embedding_model, threshold=cluster_threshold)
    
    # 3) Embed the deduped bullets & resume lines
    job_embeddings = embedding_model.encode(deduped_bullets, convert_to_tensor=True)
    resume_lines = [l.strip() for l in resume_text.split('\n') if l.strip()]
    resume_embeddings = embedding_model.encode(resume_lines, convert_to_tensor=True)

    missing_bullets = []
    for i, bullet in enumerate(deduped_bullets):
        sims = util.pytorch_cos_sim(job_embeddings[i], resume_embeddings)
        best_score = float(sims.max())

        if best_score < threshold:
            missing_bullets.append(bullet)

    if not missing_bullets:
        return "Your resume already covers most points from the job description!"

    # 4) Convert missing bullets to actionable suggestions
    suggestions = []
    for bullet in missing_bullets:
        suggestions.append(bullet)

    # Format the final suggestions
    final_text = "Consider the following improvements:\n\n"
    for s in suggestions:
        final_text += f"• {s}\n\n"

    return final_text.strip()

def rewrite_text(original_text, suggestions):
    """
    Use a local T5-based model to rewrite the original_text
    by incorporating the suggestions.
    """
    try:
        prompt = (
            "Rewrite the following resume text by incorporating these suggestions. "
            "Ensure the final version is coherent, professional, and well-structured.\n\n"
            f"Resume Text:\n{original_text}\n\n"
            f"Suggestions:\n{suggestions}\n\n"
            "Refined Resume:"
        )

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
        outputs = model.generate(**inputs, max_new_tokens=300, temperature=0.7)
        refined_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return refined_text.strip()
    except Exception as e:
        logging.error("Error rewriting text: " + str(e))
        return original_text  # fallback: return original if rewriting fails

def generate_pdf_from_text(text):
    """
    Convert plain text into a PDF file in memory using fpdf2 with a Unicode-capable font.
    Return the raw PDF bytes.
    """
    try:
        # Create the PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Register and set a TTF font that supports Unicode (e.g., DejaVuSans.ttf).
        # Make sure DejaVuSans.ttf is in the same folder as this script.
        pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        pdf.set_font("DejaVu", "", 12)

        # Write text line by line
        for line in text.split('\n'):
            pdf.multi_cell(0, 10, line)

        # Output to an in-memory buffer
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)
        return pdf_output.read()

    except Exception as e:
        logging.error("Error generating PDF: " + str(e))
        raise

###############################################################################
# 3. Flask Endpoint
###############################################################################

@app.route('/analyze', methods=['POST'])
def analyze_resume():
    try:
        # 1) Get the PDF file from the request
        if 'resume' not in request.files:
            return jsonify({"error": "No resume file provided."}), 400
        resume_file = request.files['resume']

        # 2) Get job description from the form data
        job_description = request.form.get("job_description", "").strip()
        if not job_description:
            return jsonify({"error": "Job description is required."}), 400

        # 3) Extract text from the uploaded PDF
        resume_text = extract_text_from_pdf(resume_file)
        if not resume_text:
            return jsonify({"error": "Could not extract text from resume PDF."}), 400

        logging.info("Extracted resume text for analysis.")

        # 4) Generate suggestions (classical NLP with TF-IDF)
        # suggestions = generate_suggestions(resume_text, job_description)
        suggestions = generate_suggestions_with_clustering(
                            resume_text,
                            job_description,
                            embedding_model=embedding_model,   # same global model
                            threshold=0.35,                     # coverage threshold
                            cluster_threshold=0.8              # bullet clustering threshold
                        )
        logging.info("Generated suggestions.")

        # 5) Rewrite the resume text locally using Flan-T5
        logging.info("About to rewrite resume text.")
        updated_resume_text = rewrite_text(resume_text, suggestions)
        logging.info("Rewrite finished.")

        # 6) Convert the updated text into a PDF with full Unicode support
        pdf_data = generate_pdf_from_text(updated_resume_text)
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
        logging.info("Generated updated resume PDF.")

        return jsonify({
            "suggestions": suggestions,
            "updated_resume_pdf": pdf_base64
        })

    except Exception as e:
        logging.error(f"Error processing the request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # For production, consider running behind a WSGI server (gunicorn) and using HTTPS
    # For local testing:
    app.run(debug=True, host="0.0.0.0", port=5001)
