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

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

###############################################################################
# 1. Load or initialize local NLP models
###############################################################################

# (A) For rewriting with a local language model (Flan-T5)
MODEL_NAME = "google/flan-t5-base"  # smaller than "large" or "xl"
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

def generate_suggestions(resume_text, job_description):
    """
    Identify top keywords from the job description that are missing
    or underrepresented in the resume. Return a human-readable string
    of suggestions.
    """
    documents = [resume_text, job_description]
    try:
        tfidf_matrix = vectorizer.fit_transform(documents)
        feature_names = vectorizer.get_feature_names_out()

        resume_tfidf = tfidf_matrix[0].toarray()[0]
        job_tfidf = tfidf_matrix[1].toarray()[0]

        differences = []
        for i, word in enumerate(feature_names):
            diff = job_tfidf[i] - resume_tfidf[i]
            if diff > 0:
                differences.append((word, diff))

        differences.sort(key=lambda x: x[1], reverse=True)
        top_missing = [word for word, diff in differences[:10]]  # top 10

        if not top_missing:
            return "Your resume already covers the key terms from the job description."

        suggestion_str = (
            "Consider incorporating or emphasizing the following terms/skills "
            "from the job description:\n- " + "\n- ".join(top_missing)
        )
        return suggestion_str
    except Exception as e:
        logging.error("Error generating suggestions: " + str(e))
        return "Could not generate suggestions."

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
        suggestions = generate_suggestions(resume_text, job_description)
        logging.info("Generated suggestions.")

        # 5) Rewrite the resume text locally using Flan-T5
        updated_resume_text = rewrite_text(resume_text, suggestions)
        logging.info("Rewrote resume text using local T5 model.")

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
