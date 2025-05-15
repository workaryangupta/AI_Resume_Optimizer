// background.js

// ————————————————————————————————————————————————————————————————
// Configuration
// ————————————————————————————————————————————————————————————————
const CLIENT_ID = '202660636509-gplpehrlas5fsj5p0s69eqdt7b7br7nc.apps.googleusercontent.com';
const SCOPES    = 'https://www.googleapis.com/auth/drive.file';

// ————————————————————————————————————————————————————————————————
// 1) Install hook (for debugging/loading only)
// ————————————————————————————————————————————————————————————————
chrome.runtime.onInstalled.addListener(() => {
  console.log('Background: Resume Tailor installed.');
});

// ————————————————————————————————————————————————————————————————
// 2) OAuth via launchWebAuthFlow
// ————————————————————————————————————————————————————————————————
async function authenticateWithGoogle() {
  const redirectUri = chrome.identity.getRedirectURL();
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: 'token',
    redirect_uri: redirectUri,
    scope: SCOPES,
    include_granted_scopes: 'true'
  });
  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;

  return new Promise((resolve, reject) => {
    chrome.identity.launchWebAuthFlow(
      { url: authUrl, interactive: true },
      callbackUrl => {
        if (chrome.runtime.lastError || !callbackUrl) {
          return reject(chrome.runtime.lastError || new Error('Auth cancelled'));
        }
        // Extract the access_token from the redirect URL fragment
        const hash = new URL(callbackUrl).hash.substring(1);
        const result = Object.fromEntries(new URLSearchParams(hash));
        if (result.error) {
          return reject(new Error(result.error));
        }
        resolve(result.access_token);
      }
    );
  });
}

// ————————————————————————————————————————————————————————————————
// 3) Handle Messages from popup.js
//    Types: UPLOAD, CONVERT, EXPORT
// ————————————————————————————————————————————————————————————————
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      // Always ensure we have an OAuth token first
      const token = await authenticateWithGoogle();

      if (msg.type === 'UPLOAD') {
        // 3A) Upload raw PDF to Drive
        const boundary = '----resume-tailor-boundary';
        const delim    = `--${boundary}\r\n`;
        const close    = `--${boundary}--`;
        const meta     = { name: msg.filename, mimeType: 'application/pdf' };
        const body =
          delim +
          'Content-Type: application/json; charset=UTF-8\r\n\r\n' +
          JSON.stringify(meta) + '\r\n' +
          delim +
          'Content-Type: application/pdf\r\n' +
          'Content-Transfer-Encoding: base64\r\n\r\n' +
          msg.base64 + '\r\n' +
          close;

        const uploadResp = await fetch(
          'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id',
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': `multipart/related; boundary=${boundary}`
            },
            body
          }
        );
        const uploadData = await uploadResp.json();
        if (!uploadData.id) throw new Error('Drive upload failed');
        await chrome.storage.local.set({ driveFileId: uploadData.id });
        return sendResponse({ success: true });
      }

      if (msg.type === 'CONVERT') {
        // 3B) Copy & convert PDF → Google Doc
        const convResp = await fetch(
          `https://www.googleapis.com/drive/v3/files/${msg.driveFileId}/copy?fields=id`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              name: msg.filename.replace(/\.pdf$/i, ''),
              mimeType: 'application/vnd.google-apps.document'
            })
          }
        );
        const convData = await convResp.json();
        if (!convData.id) throw new Error('Conversion failed');
        return sendResponse({ success: true, docId: convData.id });
      }

      if (msg.type === 'EXPORT') {
        // 3C) Export the edited Google Doc back to PDF
        const { driveFileId } = await chrome.storage.local.get('driveFileId');
        const expResp = await fetch(
          `https://www.googleapis.com/drive/v3/files/${driveFileId}/export?mimeType=application/pdf`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!expResp.ok) throw new Error('Export failed');
        const blob = await expResp.blob();
        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = () => {
          const b64 = reader.result.split(',')[1];
          sendResponse({ success: true, pdf: b64 });
        };
        reader.readAsDataURL(blob);
        return; // response via FileReader callback
      }

      // Unknown message type
      sendResponse({ success: false, error: 'Unrecognized message type' });
    } catch (err) {
      console.error('Background error:', err);
      sendResponse({ success: false, error: err.message });
    }
  })();

  return true;  // keep channel open for async sendResponse
});