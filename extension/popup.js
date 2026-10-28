const $ = (id) => document.getElementById(id);

function human(n) {
  if (!n || n < 0) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

async function refreshStatus() {
  const s = await chrome.runtime.sendMessage({ type: "fetchly-status" });
  $("dot").classList.toggle("on", !!s.alive);
  $("statusText").textContent = s.alive ? "Fetchly is running" : "Fetchly is not running — start Fetchly";
  $("enabled").checked = s.enabled;
  $("port").value = s.port;
}

async function loadMedia() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  const res = await chrome.runtime.sendMessage({ type: "fetchly-get-media", tabId: tab.id });
  const items = (res && res.items) || [];
  const box = $("media");
  if (!items.length) return;
  box.innerHTML = "";
  items.forEach((m, i) => {
    const row = document.createElement("div");
    row.className = "media";
    const name = document.createElement("span");
    const what = m.kind === "hls" ? "Streaming video (HLS)" :
      `${(m.mime || "").startsWith("audio/") ? "Audio" : "Video"} ${m.ext || ""} ${human(m.size)}`;
    name.textContent = `${i + 1}. ${what}`;
    name.title = m.url;
    const b = document.createElement("button");
    b.textContent = "Download";
    b.onclick = async () => {
      const r = await chrome.runtime.sendMessage({ type: "fetchly-download-media", item: m, tabId: tab.id,
        pageUrl: tab.url, title: tab.title });
      b.textContent = r && r.ok ? "Sent ✓" : "Failed";
    };
    row.append(name, b);
    box.appendChild(row);
  });
}

$("enabled").addEventListener("change", (e) => chrome.storage.local.set({ enabled: e.target.checked }));
$("port").addEventListener("change", async (e) => {
  const p = parseInt(e.target.value, 10);
  if (p >= 1024 && p <= 65535) {
    await chrome.storage.local.set({ port: p });
    refreshStatus();
  }
});

refreshStatus();
loadMedia();
