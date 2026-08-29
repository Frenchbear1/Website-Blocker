const parameters = new URLSearchParams(location.search);
const domain = parameters.get("domain") || "this website";
const domainLabel = document.getElementById("domain");
const statusLabel = document.getElementById("status");
domainLabel.textContent = domain;

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
  sendHeartbeat({type: "lumaguard-heartbeat", domain, active: false}, (result) => {
    if (!result || !result.ok) {
      statusLabel.textContent = "LumaGuard isn’t reachable. Make sure the desktop app is running.";
    } else if (!result.blocked) {
      location.href = `https://${domain}`;
    } else {
      statusLabel.textContent = "The daily limit is still active.";
    }
  });
}

document.getElementById("check").addEventListener("click", checkAgain);
document.getElementById("back").addEventListener("click", () => history.back());
