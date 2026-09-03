const popupApi = globalThis.browser || globalThis.chrome;
const title = document.getElementById("title");
const detail = document.getElementById("detail");
const status = document.getElementById("status");
const statusText = status.querySelector("b");
const checkButton = document.getElementById("check");
const brandIcon = document.getElementById("brandIcon");
const accentNames = new Set(["violet", "rose", "mint", "blue", "amber"]);

function applyAppearance(result) {
  if (!result) return;
  const accent = accentNames.has(result.accent) ? result.accent : "violet";
  const color = /^#[0-9a-f]{6}$/i.test(result.accent_color || "") ? result.accent_color : "#8b7cff";
  document.documentElement.style.setProperty("--accent", color);
  document.documentElement.style.setProperty("--accent-hover", color);
  brandIcon.src = `icons/${accent}-32.png`;
}

function sendStatus(callback) {
  if (globalThis.browser) {
    browser.runtime.sendMessage({type: "website-blocker-status"}).then(callback).catch(() => callback(null));
  } else {
    chrome.runtime.sendMessage({type: "website-blocker-status"}, (result) => {
      callback(chrome.runtime.lastError ? null : result);
    });
  }
}

function render(result) {
  applyAppearance(result);
  checkButton.disabled = false;
  status.className = "status";
  if (result && result.ok && result.connected) {
    title.textContent = "Connected";
    detail.textContent = "Focused website counting is ready.";
    status.classList.add("connected");
    statusText.textContent = "Desktop app connected";
  } else {
    title.textContent = "Desktop app not found";
    detail.textContent = "Start Website Blocker, then check again. Whole-browser limits do not need this companion.";
    status.classList.add("offline");
    statusText.textContent = "Not connected";
  }
}

function check() {
  checkButton.disabled = true;
  title.textContent = "Checking connection…";
  detail.textContent = "Looking for the Website Blocker desktop app.";
  status.className = "status waiting";
  statusText.textContent = "Checking";
  sendStatus(render);
}

checkButton.addEventListener("click", check);
check();
