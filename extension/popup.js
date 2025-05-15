// 1) Storage Helpers
function getStoredResume() {
  return new Promise(res =>
    chrome.storage.local.get(
      ['resumeText', 'resumeFileName', 'driveFileId'],
      obj => res({
        text: obj.resumeText || '',
        name: obj.resumeFileName || '',
        driveFileId: obj.driveFileId || ''
      })
    )
  );
}

function setStoredResume(text, name) {
  return new Promise(res =>
    chrome.storage.local.set({ resumeText: text, resumeFileName: name }, res)
  );
}


// 2) UI Init: toggle sections
async function initUI() {
  const { text, name } = await getStoredResume();
  document.getElementById('uploadSection').style.display  = (name && text) ? 'none' : 'block';
  document.getElementById('storedWrapper').style.display = (name && text) ? 'flex' : 'none';
  document.getElementById('keywordCard').style.display   = 'none';
  document.getElementById('suggestionCard').style.display= 'none';
  if (name && text) {
    document.getElementById('resumeFileName').textContent = name;
  }
}
document.addEventListener('DOMContentLoaded', initUI);


// 3) Upload & Extract Resume
document.getElementById('resumeFile').addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('resumeChooserText').textContent = file.name;

  // 3A) Extract via Flask
  try {
    const form = new FormData();
    form.append('resume', file);
    const resp = await fetch('http://localhost:5001/extract_resume', {
      method: 'POST',
      body: form
    });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { resume_text } = await resp.json();
    await setStoredResume(resume_text, file.name);
  } catch (err) {
    return alert('Extraction error: ' + err.message);
  }

  // 3B) Read PDF and message background to UPLOAD to Drive
  const reader = new FileReader();
  reader.onload = () => {
    const base64 = reader.result.split(',')[1];
    chrome.runtime.sendMessage(
      { type: 'UPLOAD', filename: file.name, base64 },
      reply => {
        alert(reply.success ? '✅ Uploaded to Drive!' : '❌ Drive upload failed: ' + reply.error);
        initUI();
      }
    );
  };
  reader.readAsDataURL(file);
});


// 4) Change Base Resume
document.getElementById('changeResumeButton').addEventListener('click', () => {
  chrome.storage.local.remove(['resumeText','resumeFileName','driveFileId'], () => {
    document.getElementById('resumeChooserText').textContent = 'No file chosen';
    initUI();
  });
});


// 5) Auto-Extract Job Description
document.getElementById('autoExtract').addEventListener('click', async () => {
  const ta = document.getElementById('jobDescInput');
  ta.value = '⏳ Extracting…';
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { action: 'extractJD' }, res => {
    if (res?.jobDescription) ta.value = res.jobDescription;
    else {
      ta.value = '';
      alert('Auto-extract failed');
    }
  });
});


// 6) Get Suggestions & show cards
document.getElementById('getSuggestions').addEventListener('click', async () => {
  const { text: resumeText } = await getStoredResume();
  const jobDesc = document.getElementById('jobDescInput').value.trim();
  if (!resumeText) return alert('Please upload your resume first.');
  if (!jobDesc)    return alert('Please provide the job description.');

  const kc = document.getElementById('keywordCard');
  const sc = document.getElementById('suggestionCard');
  kc.style.display = sc.style.display = 'block';

  // loading state
  document.getElementById('cardText').textContent = 'Analyzing…';
  document.getElementById('suggestionList').innerHTML = '<li>Analyzing…</li>';
  document.getElementById('cardGauge').style.setProperty('--pct', 0);

  try {
    const fd = new FormData();
    fd.append('resume_text', resumeText);
    fd.append('job_description', jobDesc);
    const resp = await fetch('http://localhost:5001/analyze', {
      method: 'POST',
      body: fd
    });
    if (!resp.ok) throw new Error(`Server ${resp.status}`);
    const { suggestions } = await resp.json();

    // parse missing bullets
    const missing = suggestions
      .split('\n')
      .filter(l => l.trim().startsWith('•'))
      .map(l => l.trim().slice(1).trim());

    // count JD bullets
    const total = jobDesc
      .split('\n')
      .filter(l => /^([•\-✔▶])/.test(l.trim()))
      .length;
    const matched = Math.max(total - missing.length, 0);
    const pct = total > 0 ? Math.round((matched / total) * 100) : 0;

    // update Keyword Match card
    document.getElementById('cardStatus').textContent =
      pct < 50 ? 'Needs Work' : pct < 80 ? 'Good' : 'Excellent';
    document.getElementById('cardText').textContent =
      `Your resume has ${matched} out of ${total} (${pct}%) keywords that appear in the job description.`;
    document.getElementById('cardGauge').style.setProperty('--pct', pct);

    // render missing list
    const ul = document.getElementById('suggestionList');
    if (missing.length) {
      ul.innerHTML = missing.map(it => `<li>${it}</li>`).join('');
    } else {
      ul.innerHTML = '<li>None — your resume covers all keywords! 🎉</li>';
    }
  } catch (err) {
    console.error("Suggestion error:", err);
    document.getElementById('cardText').textContent = 'Error: ' + err.message;
    document.getElementById('suggestionList').innerHTML = `<li>Error: ${err.message}</li>`;
  }
});


// 7) Convert → Google Doc & open
document.getElementById('editResumeBtn').addEventListener('click', async () => {
  const { driveFileId, name } = await getStoredResume();
  if (!driveFileId) return alert('Please upload your resume first.');

  chrome.runtime.sendMessage(
    { type: 'CONVERT', driveFileId, filename: name },
    resp => {
      if (resp.success) {
        chrome.tabs.create({
          url: `https://docs.google.com/document/d/${resp.docId}/edit`
        });
      } else {
        alert('Conversion failed: ' + resp.error);
      }
    }
  );
});


// 8) Export edited Google Doc → PDF
document.getElementById('downloadEditedBtn').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'EXPORT' }, resp => {
    if (resp.success && resp.pdf) {
      const a = document.createElement('a');
      a.href = 'data:application/pdf;base64,' + resp.pdf;
      a.download = 'Edited_Resume.pdf';
      a.click();
    } else {
      alert('Export failed: ' + resp.error);
    }
  });
});
