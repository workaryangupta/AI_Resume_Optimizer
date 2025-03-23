document.getElementById("tailorButton").addEventListener("click", async () => {
  const resumeFile = document.getElementById("resumeFile").files[0];
  const jobDescText = document.getElementById("jobDescInput").value.trim();

  if (!resumeFile || !jobDescText) {
    alert("Please provide a resume PDF file and the job description.");
    return;
  }

  // Display loading messages
  document.getElementById("suggestions").textContent = "Processing suggestions...";
  document.getElementById("updatedResume").textContent = "Processing updated resume PDF...";

  try {
    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('job_description', jobDescText);

    const response = await fetch("http://localhost:5001/analyze", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }

    document.getElementById("suggestions").textContent = data.suggestions;

    // Create a download link for the updated PDF
    if (data.updated_resume_pdf) {
      const link = document.createElement('a');
      link.href = 'data:application/pdf;base64,' + data.updated_resume_pdf;
      link.download = 'updated_resume.pdf';
      link.textContent = 'Download Updated Resume PDF';
      const updatedResumeDiv = document.getElementById("updatedResume");
      updatedResumeDiv.innerHTML = '';
      updatedResumeDiv.appendChild(link);
    } else {
      document.getElementById("updatedResume").textContent = "No updated resume generated.";
    }
  } catch (error) {
    console.error("Error:", error);
    document.getElementById("suggestions").textContent = "Error: " + error.message;
    document.getElementById("updatedResume").textContent = "Error: " + error.message;
  }
});
