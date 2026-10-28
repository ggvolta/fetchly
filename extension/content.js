// Fetchly — floating "Download with Fetchly" button over videos on the page.
(() => {
  if (window.__fetchlyInjected) return;
  window.__fetchlyInjected = true;

  let items = [];
  let host, root, btn, menu, toast, hidden = false, timer = null;

  function human(n) {
    if (!n || n < 0) return "";
    const u = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
  }

  function build() {
    if (host) return;
    host = document.createElement("div");
    host.style.cssText = "position:fixed;z-index:2147483647;top:0;left:0;width:0;height:0;";
    root = host.attachShadow({ mode: "closed" });
    root.innerHTML = `
      <style>
        :host { all: initial; }
        .wrap { position: fixed; font: 13px/1.3 "Segoe UI", system-ui, sans-serif; }
        .btn { display:flex; align-items:center; gap:6px; background:#1D2058; color:#fff; border:0;
               border-radius:6px; padding:6px 10px 6px 8px; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.35);
               font:inherit; font-weight:600; white-space:nowrap; }
        .btn:hover { background:#2A2E7A; }
        .x { margin-left:4px; opacity:.75; font-weight:400; padding:0 2px; }
        .x:hover { opacity:1; }
        .menu { position:absolute; top:100%; right:0; margin-top:4px; background:#fff; color:#1f2933;
                border-radius:6px; box-shadow:0 4px 16px rgba(0,0,0,.3); min-width:300px; max-width:460px;
                padding:4px 0; display:none; }
        .menu.open { display:block; }
        .item { padding:7px 12px; cursor:pointer; display:flex; justify-content:space-between; gap:12px; }
        .item:hover { background:#e3f0fd; }
        .k { color:#5c6b7a; font-size:12px; white-space:nowrap; }
        .t { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .toast { position:fixed; right:16px; bottom:16px; background:#263238; color:#fff; padding:10px 14px;
                 border-radius:6px; box-shadow:0 2px 10px rgba(0,0,0,.4); display:none; max-width:360px; }
      </style>
      <div class="wrap" id="wrap">
        <button class="btn" id="btn">
          <svg width="16" height="16" viewBox="0 0 16 16"><path fill="#FFB33A" d="M6 1h4v6h3l-5 6-5-6h3z"/><rect fill="#FFB33A" x="2" y="14" width="12" height="1.6" rx=".8"/></svg>
          <span id="lbl">Download this video</span><span class="x" id="x" title="Hide">✕</span>
        </button>
        <div class="menu" id="menu"></div>
      </div>
      <div class="toast" id="toast"></div>`;
    btn = root.getElementById("btn");
    menu = root.getElementById("menu");
    toast = root.getElementById("toast");
    btn.addEventListener("click", (e) => {
      if (e.composedPath().includes(root.getElementById("x"))) {
        hidden = true;
        root.getElementById("wrap").style.display = "none";
        return;
      }
      if (items.length === 1) download(items[0]);
      else menu.classList.toggle("open");
    });
    document.documentElement.appendChild(host);
    timer = setInterval(position, 500);
    window.addEventListener("scroll", position, { passive: true });
    window.addEventListener("resize", position);
  }

  function label(m) {
    if (m.kind === "hls") return ["Streaming video (HLS)", "M3U8"];
    const type = (m.mime || "").startsWith("audio/") ? "Audio" : "Video";
    return [`${type} ${m.ext || ""}`.trim(), human(m.size)];
  }

  function render() {
    build();
    if (hidden) return;
    root.getElementById("wrap").style.display = items.length ? "block" : "none";
    root.getElementById("lbl").textContent =
      items.length > 1 ? `Download this video (${items.length})` : "Download this video";
    menu.innerHTML = "";
    items.forEach((m, i) => {
      const [t, k] = label(m);
      const row = document.createElement("div");
      row.className = "item";
      row.innerHTML = `<span class="t"></span><span class="k"></span>`;
      row.firstChild.textContent = `${i + 1}. ${t}`;
      row.lastChild.textContent = k;
      row.title = m.url;
      row.addEventListener("click", () => { menu.classList.remove("open"); download(m); });
      menu.appendChild(row);
    });
    position();
  }

  function bestVideo() {
    let best = null, area = 0;
    for (const v of document.querySelectorAll("video")) {
      const r = v.getBoundingClientRect();
      const a = r.width * r.height;
      if (a > area && r.width > 120 && r.height > 80 && r.bottom > 0 && r.top < innerHeight) { best = r; area = a; }
    }
    return best;
  }

  function position() {
    if (!root || hidden || !items.length) return;
    const wrap = root.getElementById("wrap");
    const r = bestVideo();
    if (r) {
      wrap.style.top = Math.max(4, r.top + 8) + "px";
      wrap.style.left = "";
      wrap.style.right = Math.max(4, innerWidth - r.right + 8) + "px";
      wrap.style.bottom = "";
    } else {
      wrap.style.top = "";
      wrap.style.right = "16px";
      wrap.style.bottom = "16px";
    }
  }

  function showToast(text) {
    build();
    toast.textContent = text;
    toast.style.display = "block";
    clearTimeout(showToast.t);
    showToast.t = setTimeout(() => (toast.style.display = "none"), 3500);
  }

  function download(m) {
    chrome.runtime.sendMessage(
      { type: "fetchly-download-media", item: m, pageUrl: location.href, title: document.title },
      (res) => { if (res && res.ok) showToast("Sent to Fetchly"); }
    );
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "fetchly-media") {
      items = msg.items || [];
      render();
    } else if (msg.type === "fetchly-toast") {
      showToast(msg.text);
    }
  });

  // Alt+click on a link = let the browser download it itself (same as IDM)
  document.addEventListener("click", (e) => {
    if (!e.altKey) return;
    const a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (a && /^https?:/i.test(a.href)) chrome.runtime.sendMessage({ type: "fetchly-bypass", url: a.href }, () => void chrome.runtime.lastError);
  }, true);

  // pick up media detected before this script loaded
  chrome.runtime.sendMessage({ type: "fetchly-get-media" }, (res) => {
    if (chrome.runtime.lastError) return;
    if (res && res.items && res.items.length) { items = res.items; render(); }
  });
})();
