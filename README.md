🤖 AI Resume Optimizer
An AI-powered Chrome extension that tailors resumes to job descriptions using NLP

🧠 Overview
AI Resume Optimizer is a Chrome extension built to simplify and automate the resume-tailoring process for job seekers.
It extracts job descriptions from career portals, compares them with a user’s resume using advanced NLP models, and provides actionable improvement suggestions to enhance ATS (Applicant Tracking System) compatibility.
The tool integrates securely with Google Drive and Google Docs via OAuth, allowing users to edit and export and edit resumes according to the suggestions effortlessly.

🚀 Key Features
- Job Description Extraction – Automatically extracts job postings from websites.
- Semantic Resume Analysis – Uses Sentence-BERT (SBERT) for contextual similarity comparison.
- AI Recommendations – Generates improvement suggestions using Flan-T5 Transformer.
- Visual Feedback – Displays a gauge meter showing keyword match and similarity percentage.
- Cloud-Based Backend – Built on Flask, deployed via Google Cloud Run (Currently not functional)
- Secure Integration – Google OAuth for Drive-based resume upload, edit, and export.
- Manual Editing in Google Docs – Edit AI suggestions while preserving formatting.


System Architecture:
<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/40600834-03e0-458f-ac99-4a42ac7313e1" />


How to use
1. Clone the Repository
  git clone https://github.com/<your-username>/AI-Resume-Optimizer.git
  cd AI-Resume-Optimizer

2. Backend Setup
  pip install -r requirements.txt
  python app.py

3. Chrome Extension Setup
  Go to chrome://extensions/
  Enable Developer mode
  Click Load unpacked
  Select the project’s extension/ folder
  The extension will appear in your toolbar — ready to use ✅


🧠 How It Works
  Upload Resume (PDF) → Extracted text is analyzed by backend.
  Auto Extract Job Description → Captures job data from career pages.
  AI Comparison → SBERT + Flan-T5 generate contextual keyword insights.
  Get Suggestions → Shows missing keywords, ATS alignment score, and recommendations.
  Edit in Google Docs → Modify and export as PDF seamlessly.

📸 Screenshots
<img width="2048" height="1165" alt="image" src="https://github.com/user-attachments/assets/55fdcbe9-30a3-452d-9f16-44709b3b99f5" />
<img width="736" height="1208" alt="image" src="https://github.com/user-attachments/assets/3de87267-a356-44c8-a519-b136a7401b27" />
<img width="722" height="1194" alt="image" src="https://github.com/user-attachments/assets/3e27414b-6dc7-4871-a5f0-260830d62ab9" />
<img width="2048" height="1163" alt="image" src="https://github.com/user-attachments/assets/e1ee0324-4f60-4628-8cd8-cd6239e33169" />


👨‍💻 Author
Aryan Gupta



