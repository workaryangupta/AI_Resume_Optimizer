// popup.js

// Helpers to get/set the base resume
function getStoredResume() {
  return new Promise(res =>
    chrome.storage.local.get(['resumeText', 'resumeFileName'], obj =>
      res({ text: obj.resumeText||'', name: obj.resumeFileName||'' })
    )
  );
}
function setStoredResume(text, name) {
  return new Promise(res =>
    chrome.storage.local.set({ resumeText: text, resumeFileName: name }, res)
  );
}

// Initialize: show upload vs. stored vs. editor
async function initUI() {
  const { text, name } = await getStoredResume();
  const uploadSec = document.getElementById('uploadSection');
  const storedSec = document.getElementById('storedWrapper');
  const editorSec = document.getElementById('editorSection');
  const resumeFileNameEl = document.getElementById('resumeFileName');

  if (name && text) {
    uploadSec.style.display = 'none';
    storedSec.style.display = 'flex';
    resumeFileNameEl.textContent = name;
    document.getElementById('editor').innerText = text;
    editorSec.style.display = 'block';
  } else {
    uploadSec.style.display = 'block';
    storedSec.style.display = 'none';
    editorSec.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', initUI);

// 1) Upload & store base resume
document.getElementById('resumeFile').addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('resumeChooserText').textContent = file.name;

  try {
    const fd = new FormData(); fd.append('resume', file);
    const resp = await fetch('http://localhost:5001/extract_resume',{ method:'POST', body:fd });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { resume_text } = await resp.json();
    await setStoredResume(resume_text, file.name);
    alert('✅ Base resume uploaded and stored!');
    initUI();
  } catch (err) {
    console.error(err);
    alert('Error extracting resume: ' + err.message);
  }
});

// 2) Change base resume
document.getElementById('changeResumeButton').addEventListener('click', () => {
  chrome.storage.local.remove(['resumeText','resumeFileName'], () => {
    document.getElementById('resumeFile').value = '';
    document.getElementById('resumeChooserText').textContent = 'No file chosen';
    initUI();
  });
});

// 3) Toolbar formatting
document.getElementById('toolbar').addEventListener('click', e => {
  const cmd = e.target.dataset.cmd;
  if (cmd) document.execCommand(cmd, false, null);
});

// 4) Download edited resume (one-off, does NOT overwrite base)
document.getElementById('downloadEdited').addEventListener('click', async () => {
  const text = document.getElementById('editor').innerText.trim();
  if (!text) return alert('Please upload and edit your resume before downloading.');

  try {
    const fd = new FormData(); fd.append('text', text);
    const resp = await fetch('http://localhost:5001/generate_pdf',{ method:'POST', body:fd });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { pdf, error } = await resp.json();
    if (error) throw new Error(error);

    const a = document.createElement('a');
    a.href = 'data:application/pdf;base64,' + pdf;
    a.download = 'edited_resume.pdf';
    a.click();
  } catch (err) {
    console.error(err);
    alert('Error generating PDF: ' + err.message);
  }
});

// 5) Auto-extract JD
document.getElementById('autoExtract').addEventListener('click', async () => {
  const ta = document.getElementById('jobDescInput');
  ta.value = '⏳ Extracting…';
  const [tab] = await chrome.tabs.query({ active:true, currentWindow:true });
  chrome.tabs.sendMessage(tab.id, { action:'extractJD' }, res => {
    if (res?.jobDescription) ta.value = res.jobDescription;
    else {
      ta.value = '';
      alert('Auto-extract failed. Please paste manually.');
    }
  });
});

// 6) Get Suggestions on edited text
document.getElementById('getSuggestions').addEventListener('click', async () => {
  const resumeText = document.getElementById('editor').innerText.trim();
  const jobDesc = document.getElementById('jobDescInput').value.trim();
  if (!resumeText) return alert('Please upload your base resume first.');
  if (!jobDesc)    return alert('Please provide a job description.');

  const sugDiv = document.getElementById('suggestions');
  sugDiv.textContent = 'Processing suggestions…';
  try {
    const fd = new FormData();
    fd.append('resume_text', resumeText);
    fd.append('job_description', jobDesc);
    const resp = await fetch('http://localhost:5001/analyze',{ method:'POST', body:fd });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { suggestions, error } = await resp.json();
    if (error) throw new Error(error);
    sugDiv.textContent = suggestions;
  } catch (err) {
    console.error(err);
    sugDiv.textContent = 'Error: ' + err.message;
  }
});
