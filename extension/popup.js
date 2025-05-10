// popup.js

// 1) Auto-Extract Job Details
document.getElementById("autoExtractButton").addEventListener("click", async () => {
  const ta = document.getElementById("jobDescInput");
  ta.value = "⏳ Extracting…";

  // Get the active tab and message the content script
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

// 2) Get Suggestions & Updated PDF
document.getElementById("analyzeButton").addEventListener("click", async () => {
  const resumeFile = document.getElementById("resumeFile").files[0];
  const jobDescText = document.getElementById("jobDescInput").value.trim();

  if (!resumeFile || !jobDescText) {
    alert("Please provide both a resume PDF and job description.");
    return;
  }

  // Show loading states
  const sugDiv = document.getElementById("suggestions");
  const updDiv = document.getElementById("updatedResume");
  sugDiv.textContent = "Processing suggestions…";
  updDiv.textContent = "Processing updated resume PDF…";

  try {
    const formData = new FormData();
    formData.append("resume", resumeFile);
    formData.append("job_description", jobDescText);

    const resp = await fetch("http://localhost:5001/analyze", {
      method: "POST",
      body: formData
    });
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);

    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    // Render suggestions
    sugDiv.textContent = data.suggestions;

    // Render download link for updated PDF
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
