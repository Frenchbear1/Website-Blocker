const parameters = new URLSearchParams(location.search);
const domain = parameters.get("domain") || "this website";
const reason = parameters.get("reason") || "time_limit";
const domainLabel = document.getElementById("domain");
const titleLabel = document.getElementById("blocked-title");
const reasonLabel = document.getElementById("blocked-reason");
const noteLabel = document.getElementById("blocked-note");
const statusLabel = document.getElementById("status");
domainLabel.textContent = domain;
if (reason === "site_rule") {
  titleLabel.textContent = "This site is on your blocked list.";
  reasonLabel.textContent = "is blocked by a site rule in the desktop app.";
  noteLabel.textContent = "Remove it from Blocked sites, then check again.";
} else {
  titleLabel.textContent = "That’s enough for today.";
  reasonLabel.textContent = "has reached the daily time allowance you chose.";
  noteLabel.textContent = "Time resets automatically at local midnight on an active day.";
}

function sendHeartbeat(message, callback) {
  if (globalThis.browser) {
    browser.runtime.sendMessage(message).then(callback).catch(() => callback(null));
  } else {
    chrome.runtime.sendMessage(message, (result) => {
      if (chrome.runtime.lastError) callback(null);
      else callback(result);
    });
  }
}

function checkAgain() {
  statusLabel.textContent = "Checking your allowance…";
  sendHeartbeat({type: "website-blocker-heartbeat", domain, active: false}, (result) => {
    if (!result || !result.ok) {
      statusLabel.textContent = "Website Blocker isn’t reachable. Make sure the desktop app is running.";
    } else if (!result.blocked) {
      location.href = `https://${domain}`;
    } else if (result.block_reason === "site_rule") {
      statusLabel.textContent = "This site is still on your blocked sites list.";
    } else {
      statusLabel.textContent = "The daily limit is still active.";
    }
  });
}

document.getElementById("check").addEventListener("click", checkAgain);
document.getElementById("back").addEventListener("click", () => history.back());
