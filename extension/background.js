// Fetchly — background service worker.
// 1) Takes over browser downloads of the configured file types and sends them to Fetchly.
// 2) Detects video/audio streams on pages and offers a "Download with Fetchly" button.
// 3) Adds right-click menus: download link, download all links, download selected links.

const DEFAULTS = { port: 7614, enabled: true };
const DEFAULT_TYPES = ("3GP 7Z AAC ACE AIF APK ARJ ASF AVI BIN BZ2 DEB DMG DOCX EXE FLAC FLV GZ GZIP IMG ISO LZH M4A " +
  "M4V MKV MOV MP3 MP4 MPA MPE MPEG MPG MSI MSU OGG OGV OPUS PDF PKG PPS PPT PPTX QT R0* R1* RA RAR RM RMVB RPM SEA " +
  "SIT SITX TAR TGZ TIF TIFF WAV WEBM WMA WMV XLSX XZ Z ZIP ZST").split(" ");

let fetchly = { alive: false, types: DEFAULT_TYPES, minSizeKB: 0, appEnabled: true, checked: 0 };
const bypass = new Map(); // url -> expiry time; downloads we deliberately leave to the browser

// ---------------------------------------------------------------- helpers
async function settings() {
  return { ...DEFAULTS, ...(await chrome.storage.local.get(DEFAULTS)) };
}

async function api(path, body) {
  const { port } = await settings();
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 3000);
  try {
    const res = await fetch(`http://127.0.0.1:${port}${path}`, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json", "X-Fetchly-Client": "extension" },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

async function ping(force = false) {
  if (!force && Date.now() - fetchly.checked < 4000) return fetchly.alive;
  try {
    const info = await api("/ping");
    fetchly = { alive: true, types: info.types || DEFAULT_TYPES, minSizeKB: info.minSizeKB || 0,
            appEnabled: info.enabled !== false, checked: Date.now() };
  } catch (e) {
    fetchly.alive = false;
    fetchly.checked = Date.now();
  }
  updateIcon();
  return fetchly.alive;
}

function updateIcon() {
  chrome.action.setTitle({ title: fetchly.alive ? "Fetchly is running" : "Fetchly is not running" });
}

function extOf(name) {
  const clean = (name || "").split(/[?#]/)[0];
  const base = clean.split(/[\\/]/).pop();
  const i = base.lastIndexOf(".");
  return i > 0 ? base.slice(i + 1).toUpperCase() : "";
}

function matchesTypes(name) {
  const e = extOf(name);
  if (!e) return false;
  return fetchly.types.some((t) => {
    t = String(t).trim().toUpperCase().replace(/^\./, "");
    return t.endsWith("*") ? e.startsWith(t.slice(0, -1)) : e === t;
  });
}

async function cookieHeader(url) {
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch (e) {
    return "";
  }
}

function isBypassed(url) {
  const t = bypass.get(url);
  if (t && t > Date.now()) return true;
  bypass.delete(url);
  return false;
}

async function sendToFetchly(url, extra = {}) {
  const payload = {
    url,
    referrer: extra.referrer || "",
    filename: extra.filename || "",
    fileSize: extra.fileSize || -1,
    mime: extra.mime || "",
    kind: extra.kind || "",
    title: extra.title || "",
    cookies: await cookieHeader(url),
    userAgent: navigator.userAgent,
  };
  await api("/download", payload);
}

// ---------------------------------------------------------------- download takeover
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  takeOver(item)
    .then((taken) => { if (!taken) suggest(); })
    .catch(() => suggest());
  return true; // we answer asynchronously
});

async function takeOver(item) {
  const s = await settings();
  if (!s.enabled) return false;
  const url = item.finalUrl || item.url;
  if (!/^https?:/i.test(url) || isBypassed(url) || isBypassed(item.url)) return false;
  if (item.byExtensionId && item.byExtensionId === chrome.runtime.id) return false;
  const name = (item.filename || "").split(/[\\/]/).pop();
  if (!(await ping())) return false;
  if (!fetchly.appEnabled) return false;
  if (!matchesTypes(name) && !matchesTypes(url)) return false;
  if (fetchly.minSizeKB > 0 && item.fileSize > 0 && item.fileSize < fetchly.minSizeKB * 1024) return false;

  try {
    await chrome.downloads.cancel(item.id);
    chrome.downloads.erase({ id: item.id });
  } catch (e) { /* already gone */ }
  try {
    await sendToFetchly(url, { referrer: item.referrer, filename: name, fileSize: item.fileSize, mime: item.mime });
  } catch (e) {
    // Fetchly vanished in the meantime: let the browser do it after all.
    bypass.set(url, Date.now() + 60000);
    chrome.downloads.download({ url });
  }
  return true;
}

// ---------------------------------------------------------------- context menus
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "fetchly-link", title: "Download with Fetchly", contexts: ["link", "video", "audio", "image"] });
    chrome.contextMenus.create({ id: "fetchly-selected", title: "Download selected links with Fetchly", contexts: ["selection"] });
    chrome.contextMenus.create({ id: "fetchly-all", title: "Download all links with Fetchly", contexts: ["page"] });
  });
  chrome.alarms.create("fetchly-ping", { periodInMinutes: 0.5 });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("fetchly-ping", { periodInMinutes: 0.5 });
  ping(true);
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "fetchly-ping") ping(true); });

async function needFetchly(tabId) {
  if (await ping(true)) return true;
  notifyTab(tabId, "Fetchly is not running. Start Fetchly and try again.");
  return false;
}

function notifyTab(tabId, text) {
  if (tabId >= 0) chrome.tabs.sendMessage(tabId, { type: "fetchly-toast", text }, { frameId: 0 }).catch(() => {});
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const tabId = tab ? tab.id : -1;
  if (!(await needFetchly(tabId))) return;
  if (info.menuItemId === "fetchly-link") {
    const url = info.linkUrl || info.srcUrl;
    if (url && /^https?:/i.test(url)) await sendToFetchly(url, { referrer: info.pageUrl });
    else notifyTab(tabId, "This link can't be downloaded by Fetchly.");
    return;
  }
  const selectedOnly = info.menuItemId === "fetchly-selected";
  const [res] = await chrome.scripting.executeScript({
    target: { tabId },
    args: [selectedOnly],
    func: (selectedOnly) => {
      const sel = window.getSelection();
      const out = [];
      const push = (url, text) => { if (url && /^https?:/i.test(url)) out.push({ url, text: (text || "").trim().slice(0, 200) }); };
      document.querySelectorAll("a[href]").forEach((a) => {
        if (!selectedOnly || (sel && sel.containsNode(a, true))) push(a.href, a.textContent);
      });
      if (!selectedOnly) {
        document.querySelectorAll("video[src], audio[src], video source[src], audio source[src]").forEach((m) => push(m.src, "media"));
      }
      return out;
    },
  });
  const links = (res && res.result) || [];
  if (!links.length) return notifyTab(tabId, "No links found.");
  await api("/batch", { links, pageUrl: tab.url, cookies: await cookieHeader(tab.url), userAgent: navigator.userAgent });
});

// ---------------------------------------------------------------- media (video grabber)
const MEDIA_EXT = /\.(mp4|m4v|webm|mkv|mov|flv|avi|wmv|3gp|mp3|m4a|aac|ogg|oga|opus|wav|flac)(\?|#|$)/i;

function mediaKey(tabId) { return "media_" + tabId; }

async function getMedia(tabId) {
  const k = mediaKey(tabId);
  const o = await chrome.storage.session.get(k);
  return o[k] || [];
}

async function setMedia(tabId, list) {
  await chrome.storage.session.set({ [mediaKey(tabId)]: list });
  chrome.action.setBadgeBackgroundColor({ color: "#3D42C9", tabId }).catch(() => {});
  chrome.action.setBadgeText({ text: list.length ? String(list.length) : "", tabId }).catch(() => {});
}

chrome.webRequest.onHeadersReceived.addListener(
  (d) => {
    if (d.tabId < 0 || d.statusCode >= 400) return;
    const h = {};
    for (const x of d.responseHeaders || []) h[x.name.toLowerCase()] = x.value || "";
    const ct = (h["content-type"] || "").toLowerCase().split(";")[0].trim();
    const url = d.url;
    let path = "";
    try { path = new URL(url).pathname; } catch (e) { return; }
    if (/googlevideo\.com|\.youtube\.com/i.test(url)) return; // YouTube uses split streams (see README)
    if (/\.(ts|m4s|aac\?.*seg|key)(\?|$)/i.test(path) || ct === "video/mp2t") return; // HLS/DASH fragments
    let kind = null;
    if (ct.includes("mpegurl") || /\.m3u8$/i.test(path)) kind = "hls";
    else if (ct.startsWith("video/") || ct.startsWith("audio/")) kind = "file";
    else if (ct === "application/octet-stream" && MEDIA_EXT.test(path)) kind = "file";
    if (!kind) return;
    let size = -1;
    const cr = h["content-range"];
    if (cr && /\/(\d+)$/.test(cr)) size = parseInt(cr.match(/\/(\d+)$/)[1], 10);
    else if (h["content-length"]) size = parseInt(h["content-length"], 10);
    if (kind === "file" && size > 0 && size < 300 * 1024) return; // ignore tiny clips/beacons
    recordMedia(d.tabId, { url, kind, size, mime: ct, ext: extOf(path) || (kind === "hls" ? "M3U8" : "") });
  },
  { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other", "object"] },
  ["responseHeaders"]
);

const recordQueue = new Map();
async function recordMedia(tabId, m) {
  // serialize per tab so storage writes don't race
  const prev = recordQueue.get(tabId) || Promise.resolve();
  const next = prev.then(async () => {
    const list = await getMedia(tabId);
    const key = m.url.replace(/([?&])(range|bytestart|byteend)=[^&]*/gi, "$1");
    if (list.some((x) => x.key === key)) return;
    if (m.kind === "hls" && list.filter((x) => x.kind === "hls").length >= 6) return;
    list.push({ ...m, key, time: Date.now() });
    await setMedia(tabId, list);
    chrome.tabs.sendMessage(tabId, { type: "fetchly-media", items: list }, { frameId: 0 }).catch(() => {});
  });
  recordQueue.set(tabId, next.catch(() => {}));
}

chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading" && info.url) setMedia(tabId, []);
});
chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(mediaKey(tabId)));

// ---------------------------------------------------------------- messages from content script / popup
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    if (msg.type === "fetchly-download-media") {
      const tabId = sender.tab ? sender.tab.id : msg.tabId;
      if (!(await needFetchly(tabId))) return reply({ ok: false });
      const m = msg.item;
      const title = (msg.title || "video").replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);
      const ext = m.kind === "hls" ? "ts" : (m.ext || "mp4").toLowerCase();
      await sendToFetchly(m.url, { referrer: msg.pageUrl, filename: m.kind === "hls" ? "" : `${title}.${ext}`,
        fileSize: m.size, mime: m.mime, kind: m.kind === "hls" ? "hls" : "http", title });
      reply({ ok: true });
    } else if (msg.type === "fetchly-get-media") {
      const tabId = msg.tabId || (sender.tab && sender.tab.id);
      reply({ items: await getMedia(tabId) });
    } else if (msg.type === "fetchly-bypass") {
      bypass.set(msg.url, Date.now() + 30000);
      reply({ ok: true });
    } else if (msg.type === "fetchly-status") {
      await ping(true);
      reply({ alive: fetchly.alive, ...(await settings()) });
    }
  })().catch((e) => reply({ ok: false, error: String(e) }));
  return true;
});

ping(true);
