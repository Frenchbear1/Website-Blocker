const extensionApi = globalThis.browser || globalThis.chrome;
let redirecting = false;
let warningHost = null;
let previousOverflow = "";

function sendHeartbeat(message, callback) {
  if (globalThis.browser) {
    browser.runtime.sendMessage(message).then(callback).catch(() => {});
  } else {
    chrome.runtime.sendMessage(message, (result) => {
      if (!chrome.runtime.lastError) callback(result);
    });
  }
}

function checkLimit() {
  if (redirecting || warningHost || document.visibilityState !== "visible" || !document.hasFocus()) return;
  const domain = location.hostname.replace(/^www\./i, "").toLowerCase();
  if (!domain || !domain.includes(".")) return;
  sendHeartbeat({type: "website-blocker-heartbeat", domain, active: true}, (result) => {
    if (!result) return;
    if (result.blocked) {
      redirectToBlockPage(domain);
      return;
    }
    if (result.notice) showWarning(result.notice, domain, result.accent_color);
  });
}

function redirectToBlockPage(domain) {
  redirecting = true;
  const destination = extensionApi.runtime.getURL(`blocked.html?domain=${encodeURIComponent(domain)}`);
  location.replace(destination);
}

function dismissWarning() {
  if (!warningHost) return;
  warningHost.remove();
  warningHost = null;
  document.documentElement.style.overflow = previousOverflow;
  window.setTimeout(checkLimit, 500);
}

function showWarning(notice, domain, accentValue) {
  if (warningHost) return;
  endSession();
  previousOverflow = document.documentElement.style.overflow;
  document.documentElement.style.overflow = "hidden";

  warningHost = document.createElement("div");
  warningHost.setAttribute("data-website-blocker-warning", "");
  const shadow = warningHost.attachShadow({mode: "open"});
  const accent = /^#[0-9a-f]{6}$/i.test(accentValue || "") ? accentValue : "#8b7cff";
  shadow.innerHTML = `
    <style>
      :host {
        all: initial !important;
        position: fixed !important;
        inset: 0 !important;
        z-index: 2147483647 !important;
        display: block !important;
        font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif !important;
      }
      * { box-sizing: border-box; }
      .scrim {
        width: 100%; height: 100%; display: grid; place-items: center; padding: 24px;
        color: #f4f3fa; background: rgba(7, 8, 13, .66);
        -webkit-backdrop-filter: blur(12px) saturate(.72);
        backdrop-filter: blur(12px) saturate(.72);
        animation: website-blocker-fade .18s ease-out both;
      }
      .card {
        width: min(490px, 100%); padding: 26px; overflow: hidden;
        border: 1px solid #3b3d4d; border-radius: 22px;
        background: linear-gradient(145deg, #171927, #11131c);
        box-shadow: 0 28px 90px rgba(0, 0, 0, .62);
        animation: website-blocker-rise .22s cubic-bezier(.2, .8, .2, 1) both;
      }
      .top { display: flex; gap: 15px; align-items: flex-start; }
      .mark {
        flex: 0 0 50px; height: 50px; display: grid; place-items: center;
        color: ${accent}; background: #211f32; border: 1px solid ${accent};
        border-radius: 15px; font-size: 25px; font-weight: 850;
      }
      .eyebrow { margin: 2px 0 5px; color: ${accent}; font-size: 10px; font-weight: 850; letter-spacing: 1.7px; }
      h1 { margin: 0; color: #f4f3fa; font-size: 21px; line-height: 1.2; letter-spacing: -.25px; }
      .body { margin: 18px 0 8px; color: #bebecb; font-size: 14px; line-height: 1.55; }
      .choice { margin: 0; color: #9293a4; font-size: 12px; line-height: 1.5; }
      .actions { display: flex; justify-content: flex-end; gap: 9px; margin-top: 23px; }
      button {
        appearance: none; border: 1px solid #3b3d4d; border-radius: 11px;
        padding: 10px 16px; color: #f4f3fa; background: #202230;
        font: 700 12px "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
        cursor: pointer; transition: transform .14s ease, background .14s ease, border-color .14s ease;
      }
      button:hover { background: #292b3a; transform: translateY(-1px); }
      button:focus-visible { outline: 3px solid ${accent}66; outline-offset: 2px; }
      button.primary { color: #0a0b12; background: ${accent}; border-color: ${accent}; }
      button.primary:hover { filter: brightness(1.1); }
      button.block:hover { color: #ff9daf; border-color: #ff7a90; background: #2b1820; }
      button:disabled { opacity: .6; cursor: wait; transform: none; }
      .status { min-height: 17px; margin: 12px 0 -4px; color: #ff9daf; font-size: 11px; text-align: right; }
      @keyframes website-blocker-fade { from { opacity: 0; } to { opacity: 1; } }
      @keyframes website-blocker-rise { from { opacity: 0; transform: translateY(10px) scale(.985); } to { opacity: 1; transform: none; } }
      @media (prefers-color-scheme: light) {
        .scrim { color: #20212a; background: rgba(235, 237, 244, .68); }
        .card { background: linear-gradient(145deg, #fff, #f8f7fc); border-color: #d1d4de; box-shadow: 0 28px 90px rgba(50, 53, 67, .24); }
        h1 { color: #20212a; } .body { color: #4f5260; } .choice { color: #6b6e7b; }
        button { color: #20212a; background: #eceef4; border-color: #c9cdd8; }
        button:hover { background: #e2e5ed; }
        button.primary { color: #fff; background: #8b7cff; border-color: #8b7cff; }
        button.block:hover { color: #c83854; background: #fff0f3; border-color: #e87f94; }
      }
      @media (max-width: 520px) {
        .card { padding: 22px; border-radius: 18px; }
        .actions { flex-direction: column-reverse; }
        button { width: 100%; }
      }
    </style>
    <section class="scrim" role="dialog" aria-modal="true" aria-labelledby="website-blocker-title" aria-describedby="website-blocker-detail">
      <div class="card">
        <div class="top">
          <div class="mark" aria-hidden="true">!</div>
          <div><p class="eyebrow">WEBSITE BLOCKER TIME LIMIT</p><h1 id="website-blocker-title"></h1></div>
        </div>
        <p class="body" id="website-blocker-detail"></p>
        <p class="choice">Dismiss to keep browsing, or turn this into a strict block until tomorrow.</p>
        <div class="actions">
          <button class="block" type="button">Block for today</button>
          <button class="primary" type="button">Dismiss warning</button>
        </div>
        <p class="status" aria-live="polite"></p>
      </div>
    </section>`;

  shadow.getElementById("website-blocker-title").textContent = notice.title || "Time-limit warning";
  shadow.getElementById("website-blocker-detail").textContent = notice.detail || `${domain} reached its daily allowance.`;
  const dismiss = shadow.querySelector("button.primary");
  const block = shadow.querySelector("button.block");
  const status = shadow.querySelector(".status");
  dismiss.addEventListener("click", dismissWarning);
  block.addEventListener("click", () => {
    block.disabled = true;
    dismiss.disabled = true;
    block.textContent = "Blocking...";
    sendHeartbeat({type: "website-blocker-decision", action: "block_today", domain}, (result) => {
      if (result && result.blocked) {
        redirectToBlockPage(domain);
        return;
      }
      status.textContent = "Website Blocker could not apply the block. Make sure the desktop app is running.";
      block.disabled = false;
      dismiss.disabled = false;
      block.textContent = "Block for today";
    });
  });
  document.documentElement.appendChild(warningHost);
  window.setTimeout(() => dismiss.focus(), 0);
}

function endSession() {
  const domain = location.hostname.replace(/^www\./i, "").toLowerCase();
  if (domain && domain.includes(".")) {
    sendHeartbeat({type: "website-blocker-heartbeat", domain, active: false}, () => {});
  }
}

checkLimit();
setInterval(checkLimit, 3000);
window.addEventListener("blur", endSession);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") endSession();
});
