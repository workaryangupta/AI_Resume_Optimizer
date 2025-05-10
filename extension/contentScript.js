// contentScript.js

/**
 * Heuristic extraction:
 *  1) Find the first heading (h1–h4) containing
 *     one of our KEYWORDS.
 *  2) Collect subsequent <p> and <ul>/<ol> blocks
 *     until the next heading.
 */
function extractJobDescription() {
    const KEYWORDS = [
      "Job Description",
      "Key Responsibilities",
      "Responsibilities",
      "Requirements",
      "Qualifications",
      "Desired Skills",
      "What we are looking for",
      "Role Overview"
    ];
  
    // 1) Find matching heading
    const heading = Array.from(document.querySelectorAll("h1,h2,h3,h4"))
      .find(h => KEYWORDS.some(k => h.innerText.includes(k)));
    if (!heading) return "";
  
    // 2) Gather siblings until the next heading
    let textBlocks = [];
    let sib = heading.nextElementSibling;
    while (sib && !/^H[1-4]$/.test(sib.tagName)) {
      if (sib.tagName === "P") {
        textBlocks.push(sib.innerText.trim());
      } else if (["UL", "OL"].includes(sib.tagName)) {
        textBlocks.push(
          Array.from(sib.querySelectorAll("li"))
            .map(li => "• " + li.innerText.trim())
            .join("\n")
        );
      }
      sib = sib.nextElementSibling;
    }
  
    return textBlocks.join("\n\n").trim();
  }
  
  // Listen for messages from popup.js
  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.action === "extractJD") {
      sendResponse({ jobDescription: extractJobDescription() });
    }
    return true;
  });
  