const extensionApi = globalThis.browser || globalThis.chrome;
const toolbarApi = extensionApi.action || extensionApi.browserAction;
const accents = new Set(["violet", "rose", "mint", "blue", "amber"]);

function applyAppearance(payload) {
  if (!payload || !toolbarApi) return payload;
  const accent = accents.has(payload.accent) ? payload.accent : "violet";
  toolbarApi.setIcon({
    path: {
      16: `icons/${accent}-16.png`,
      32: `icons/${accent}-32.png`,
      48: `icons/${accent}-48.png`,
      128: `icons/${accent}-128.png`
    }
  });
  return payload;
}

function browserName() {
  const agent = navigator.userAgent.toLowerCase();
  if (agent.includes("edg/")) return "edge";
  if (agent.includes("vivaldi")) return "vivaldi";
  if (agent.includes("opr/")) return "opera";
  if (agent.includes("firefox/")) return "firefox";
  if (navigator.brave) return "brave";
  return "chrome";
}

function postToWebsiteBlocker(path, payload) {
  return fetch(`http://127.0.0.1:17843${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Website-Blocker-Companion": "1"
    },
    body: JSON.stringify({browser: browserName(), ...payload})
  }).then((response) => response.json());
}

function reportPresence() {
  return postToWebsiteBlocker("/presence", {})
    .then(applyAppearance)
    .catch(() => ({ok: false, connected: false, unavailable: true}));
}

extensionApi.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) return false;
  if (message.type === "website-blocker-status") {
    reportPresence().then(sendResponse);
    return true;
  }
  if (message.type === "website-blocker-decision") {
    postToWebsiteBlocker("/decision", {
        domain: message.domain,
        action: message.action
    })
      .then(applyAppearance)
      .then((payload) => sendResponse(payload))
      .catch(() => sendResponse({ok: false, blocked: false, unavailable: true}));
    return true;
  }
  if (message.type !== "website-blocker-heartbeat") return false;
  postToWebsiteBlocker("/heartbeat", {
    domain: message.domain,
    active: message.active !== false
  })
    .then(applyAppearance)
    .then((payload) => sendResponse(payload))
    .catch(() => sendResponse({ok: false, blocked: false, unavailable: true}));
  return true;
});

extensionApi.runtime.onInstalled.addListener(() => {
  extensionApi.alarms.create("website-blocker-presence", {periodInMinutes: 1});
  reportPresence();
});
extensionApi.runtime.onStartup.addListener(reportPresence);
extensionApi.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "website-blocker-presence") reportPresence();
});
extensionApi.alarms.create("website-blocker-presence", {periodInMinutes: 1});
reportPresence();
