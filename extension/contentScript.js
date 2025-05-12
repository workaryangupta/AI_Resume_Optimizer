// contentScript.js

/**
 * 1) Try to find a heading (h1–h6) whose text contains
 *    any of our KEYWORDS (case-insensitive).
 * 2) If found, scrape all <p> and <ul>/<ol> that follow until
 *    the next heading.
 * 3) Otherwise, pick the <ul> or <ol> with the most <li> items.
 * 4) Otherwise, pick the <div> whose children <p> count is highest.
 */

function extractJobDescription() {
  const KEYWORDS = [
    "Job Description", 
    "Key Responsibilities", 
    "Responsibilities", 
    "Requirements", 
    "Minimum Requirements", 
    "Qualifications", 
    "Desired Skills", 
    "What we are looking for", 
    "Role Overview" 
  ].map(k => k.toLowerCase());

  // 1) Heading match (h1–h6)
  const heading = Array.from(
    document.querySelectorAll("h1,h2,h3,h4,h5,h6")
  ).find(h => {
    const txt = h.innerText.trim().toLowerCase();
    return KEYWORDS.some(kw => txt.includes(kw));
  });

  if (heading) {
    let blocks = [];
    let sib = heading.nextElementSibling;
    while (sib && !/^H[1-6]$/.test(sib.tagName)) {
      if (sib.tagName === "P") {
        blocks.push(sib.innerText.trim());
      } else if (["UL", "OL"].includes(sib.tagName)) {
        blocks.push(
          Array.from(sib.querySelectorAll("li"))
            .map(li => "• " + li.innerText.trim())
            .join("\n")
        );
      }
      sib = sib.nextElementSibling;
    }
    const text = blocks.join("\n\n").trim();
    if (text) return text;
  }

  // 2) Fallback: the biggest list (<ul> or <ol>)
  const lists = Array.from(document.querySelectorAll("ul,ol"));
  let bestList = null, maxItems = 0;
  for (const lst of lists) {
    const count = lst.querySelectorAll("li").length;
    if (count > maxItems) {
      maxItems = count;
      bestList = lst;
    }
  }
  if (bestList && maxItems >= 3) {
    return Array.from(bestList.querySelectorAll("li"))
      .map(li => "• " + li.innerText.trim())
      .join("\n");
  }

  // 3) Fallback: the <div> with the most <p> children
  const ps = Array.from(document.querySelectorAll("p"));
  let bestParent = null, maxPs = 0;
  for (const p of ps) {
    const parent = p.parentElement;
    if (parent) {
      const count = parent.querySelectorAll("p").length;
      if (count > maxPs) {
        maxPs = count;
        bestParent = parent;
      }
    }
  }
  if (bestParent && maxPs >= 3) {
    return Array.from(bestParent.querySelectorAll("p"))
      .map(p => p.innerText.trim())
      .join("\n\n");
  }

  // Nothing found
  return "";
}

chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
  if (msg.action === "extractJD") {
    sendResponse({ jobDescription: extractJobDescription() });
  }
  return true;
});

