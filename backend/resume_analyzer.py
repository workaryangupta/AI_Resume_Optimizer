# import spacy
# import fitz  # PyMuPDF for extracting text from PDFs
# from collections import Counter
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

# # Load NLP model
# nlp = spacy.load("en_core_web_sm")

# def extract_text_from_pdf(pdf_path):
#     """Extracts text from a PDF file."""
#     doc = fitz.open(pdf_path)
#     text = "\n".join(page.get_text("text") for page in doc)
#     return text

# def extract_skills(text):
#     """Extracts skills and keywords from text using NLP."""
#     doc = nlp(text.lower())
#     skills = [token.text for token in doc if token.pos_ in {"NOUN", "PROPN"}]
#     return Counter(skills).most_common(20)  # Return top 20 keywords

# def calculate_similarity(resume_text, job_text):
#     """Calculates similarity between resume and job description."""
#     vectorizer = TfidfVectorizer()
#     tfidf_matrix = vectorizer.fit_transform([resume_text, job_text])
#     similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
#     return round(similarity * 100, 2)  # Convert to percentage

# def analyze_resume(pdf_path, job_description):
#     """Analyzes resume and compares it with job description."""
#     resume_text = extract_text_from_pdf(pdf_path)
#     resume_skills = extract_skills(resume_text)
#     job_skills = extract_skills(job_description)
#     similarity_score = calculate_similarity(resume_text, job_description)
    
#     missing_skills = [skill for skill, _ in job_skills if skill not in dict(resume_skills)]
    
#     return {
#         "similarity_score": similarity_score,
#         "resume_skills": resume_skills,
#         "job_skills": job_skills,
#         "missing_skills": missing_skills,
#     }

# # Example Usage
# if __name__ == "__main__":
#     pdf_path = "resume.pdf"  # Replace with actual resume path
#     job_description = "We are looking for a software engineer with experience in Python, Flask, and NLP."
    
#     result = analyze_resume(pdf_path, job_description)
#     print("Match Score:", result["similarity_score"], "%")
#     print("Missing Skills:", result["missing_skills"])
