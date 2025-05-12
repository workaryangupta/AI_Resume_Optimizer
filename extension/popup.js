// popup.js

// Helper: get stored resume data
function getStoredResume() {
  return new Promise(resolve => {
    chrome.storage.local.get(['resumeText', 'resumeFileName'], res => {
      resolve({
        text: res.resumeText || '',
        name: res.resumeFileName || ''
      });
    });
  });
}

// Helper: show/hide UI based on whether we have a resume
async function initResumeUI() {
  const { name } = await getStoredResume();
  const uploadW = document.getElementById('uploadWrapper');
  const storedW = document.getElementById('storedWrapper');
  if (name) {
    // We have a stored resume
    document.getElementById('resumeFileName').textContent = name;
    uploadW.style.display = 'none';
    storedW.style.display = 'flex';
  } else {
    // No resume yet
    uploadW.style.display = 'block';
    storedW.style.display = 'none';
  }
}

// 1) On popup load, adjust UI
document.addEventListener('DOMContentLoaded', initResumeUI);

// 2) When the user selects a PDF, extract & store it
document.getElementById('resumeFile').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Show chosen filename immediately
  document.getElementById('resumeChooserText').textContent = file.name;

  // Call backend to extract text
  const fd = new FormData();
  fd.append('resume', file);
  try {
    const resp = await fetch('http://localhost:5001/extract_resume', {
      method: 'POST',
      body: fd
    });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { resume_text } = await resp.json();
    // Store both text and filename
    chrome.storage.local.set({
      resumeText: resume_text,
      resumeFileName: file.name
    }, () => {
      initResumeUI(); // switch UI to “stored” view
      alert('✅ Resume uploaded and stored!');
    });
  } catch (err) {
    console.error(err);
    alert('Error extracting resume text: ' + err.message);
  }
});

// 3) “Change” button: clear stored resume and reset UI
document.getElementById('changeResumeButton').addEventListener('click', () => {
  chrome.storage.local.remove(['resumeText','resumeFileName'], () => {
    document.getElementById('resumeFile').value = '';
    document.getElementById('resumeChooserText').textContent = 'No file chosen';
    initResumeUI();
  });
});

// 4) Auto-Extract Job Details (unchanged)
document.getElementById("autoExtractButton").addEventListener("click", async () => {
  const ta = document.getElementById("jobDescInput");
  ta.value = "⏳ Extracting…";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { action: "extractJD" }, (res) => {
    if (res?.jobDescription) {
      ta.value = res.jobDescription;
    } else {
      ta.value = "";
      alert("Auto-extract failed. Please paste manually.");
    }
  });
});

// 5) Get Suggestions & Updated PDF, using stored resumeText
document.getElementById("analyzeButton").addEventListener("click", async () => {
  const jobDesc = document.getElementById("jobDescInput").value.trim();
  const { text: resumeText } = await getStoredResume();

  if (!resumeText) {
    alert("Please upload your resume PDF first.");
    return;
  }
  if (!jobDesc) {
    alert("Please provide a job description.");
    return;
  }

  const sugDiv = document.getElementById("suggestions");
  const updDiv = document.getElementById("updatedResume");
  sugDiv.textContent = "Processing suggestions…";
  updDiv.textContent = "Processing updated resume PDF…";

  try {
    const fd = new FormData();
    fd.append("resume_text", resumeText);
    fd.append("job_description", jobDesc);

    const resp = await fetch("http://localhost:5001/analyze", {
      method: "POST",
      body: fd
    });
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    sugDiv.textContent = data.suggestions;
    if (data.updated_resume_pdf) {
      const link = document.createElement("a");
      link.href = "data:application/pdf;base64," + data.updated_resume_pdf;
      link.download = "updated_resume.pdf";
      link.textContent = "Download Updated Resume PDF";
      updDiv.innerHTML = "";
      updDiv.appendChild(link);
    } else {
      updDiv.textContent = "No updated resume generated.";
    }
  } catch (err) {
    console.error(err);
    sugDiv.textContent = "Error: " + err.message;
    updDiv.textContent = "Error: " + err.message;
  }
});
