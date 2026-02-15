/**
 * Trading Bot Dashboard — WebSocket client with REST fallback
 */

const WS_URL = `ws://${location.host}/ws`;
const API_BASE = `${location.origin}/api`;
const FALLBACK_INTERVAL = 10_000;
const RECONNECT_DELAY = 3_000;

let ws = null;
let fallbackTimer = null;
let logCount = 0;

// ── DOM refs ──
const $ = (id) => document.getElementById(id);
const $wsStatus = $("ws-status");
const $wsLabel = $("ws-label");
const $clock = $("clock");
const $engineState = $("engine-state");
const $exchangeCount = $("exchange-count");
const $strategyCount = $("strategy-count");
const $modeLabel = $("mode-label");
const $connectorList = $("connector-list");
const $balancesBody = $("balances-body");
const $balanceCount = $("balance-count");
const $positionsBody = $("positions-body");
const $positionCount = $("position-count");
const $logEntries = $("log-entries");
const $logCount = $("log-count");

// ── Helpers ──
function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "className") node.className = v;
      else if (k === "style" && typeof v === "object")
        Object.assign(node.style, v);
      else if (k === "textContent") node.textContent = v;
      else node.setAttribute(k, v);
    }
  }
  for (const child of children) {
    if (typeof child === "string") node.appendChild(document.createTextNode(child));
    else if (child) node.appendChild(child);
  }
  return node;
}

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function formatNum(val) {
  if (val === null || val === undefined) return "--";
  const num = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(num)) return String(val);
  if (Math.abs(num) < 1) return num.toFixed(6);
  if (Math.abs(num) < 100) return num.toFixed(4);
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function makeExchangeTag(name) {
  const cls = name.toLowerCase();
  return el("span", { className: `exchange-tag ${cls}`, textContent: name });
}

// ── Clock ──
function updateClock() {
  $clock.textContent = new Date().toLocaleTimeString("en-US", { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Logging ──
function addLog(tag, message) {
  const time = new Date().toLocaleTimeString("en-US", { hour12: false });
  const entry = el("div", { className: "log-entry" },
    el("span", { className: "log-time", textContent: time }),
    el("span", { className: "log-tag", textContent: tag }),
    el("span", { textContent: message })
  );
  $logEntries.appendChild(entry);
  logCount++;
  $logCount.textContent = String(logCount);
  $logEntries.scrollTop = $logEntries.scrollHeight;

  while ($logEntries.children.length > 100) {
    $logEntries.removeChild($logEntries.firstChild);
  }
}

// ── Render ──
function renderStatus(data) {
  const status = data.status || data;
  $engineState.textContent = status.running ? "RUNNING" : "IDLE";
  $exchangeCount.textContent = String((status.connected_exchanges || []).length);
  $strategyCount.textContent = String((status.strategies || []).length);
  $modeLabel.textContent = status.dry_run ? "DRY RUN" : "LIVE";
  $modeLabel.style.color = status.dry_run ? "var(--accent-amber)" : "var(--accent-red)";
}

function renderConnectors(exchanges) {
  clearChildren($connectorList);
  if (!exchanges || exchanges.length === 0) {
    $connectorList.appendChild(
      el("div", { className: "empty-state" },
        el("div", { className: "icon", textContent: "~" }),
        "No connectors active"
      )
    );
    return;
  }
  for (const name of exchanges) {
    $connectorList.appendChild(
      el("div", { className: "connector-item" },
        el("div", { className: "connector-dot" }),
        el("span", { className: "connector-name", textContent: name })
      )
    );
  }
}

function renderBalances(balances) {
  clearChildren($balancesBody);
  if (!balances || Object.keys(balances).length === 0) {
    $balancesBody.appendChild(
      el("tr", {},
        el("td", { colspan: "5", className: "empty-state", textContent: "No balance data" })
      )
    );
    $balanceCount.textContent = "0 assets";
    return;
  }

  let count = 0;
  for (const [exchange, items] of Object.entries(balances)) {
    for (const b of items) {
      count++;
      const row = el("tr", { className: "data-flash" },
        el("td", {}, makeExchangeTag(exchange)),
        el("td", { style: { fontWeight: "600" }, textContent: b.currency }),
        el("td", { textContent: formatNum(b.free) }),
        el("td", { textContent: formatNum(b.used) }),
        el("td", { style: { color: "var(--text-primary)", fontWeight: "500" }, textContent: formatNum(b.total) })
      );
      $balancesBody.appendChild(row);
    }
  }

  $balanceCount.textContent = `${count} asset${count !== 1 ? "s" : ""}`;
}

function renderPositions(positions) {
  clearChildren($positionsBody);
  if (!positions || Object.keys(positions).length === 0) {
    $positionsBody.appendChild(
      el("tr", {},
        el("td", { colspan: "7", className: "empty-state", textContent: "No open positions" })
      )
    );
    $positionCount.textContent = "0 open";
    return;
  }

  let count = 0;
  for (const [exchange, items] of Object.entries(positions)) {
    for (const p of items) {
      count++;
      const pnlVal = parseFloat(p.unrealized_pnl);
      const pnlClass = pnlVal >= 0 ? "pnl-positive" : "pnl-negative";
      const pnlSign = pnlVal >= 0 ? "+" : "";

      const row = el("tr", { className: "data-flash" },
        el("td", {}, makeExchangeTag(exchange)),
        el("td", { style: { fontWeight: "600" }, textContent: p.symbol }),
        el("td", { className: `side-${p.side}`, textContent: p.side.toUpperCase() }),
        el("td", { textContent: formatNum(p.quantity) }),
        el("td", { textContent: formatNum(p.entry_price) }),
        el("td", { textContent: formatNum(p.current_price) }),
        el("td", { className: pnlClass, style: { fontWeight: "600" }, textContent: `${pnlSign}${formatNum(p.unrealized_pnl)}` })
      );
      $positionsBody.appendChild(row);
    }
  }

  $positionCount.textContent = `${count} open`;
}

function handleUpdate(data) {
  if (data.status) renderStatus(data);
  if (data.status?.connected_exchanges) renderConnectors(data.status.connected_exchanges);
  if (data.balances) renderBalances(data.balances);
  if (data.positions) renderPositions(data.positions);
}

// ── WebSocket ──
function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    $wsStatus.className = "status-dot connected";
    $wsLabel.textContent = "live";
    addLog("WS", "Connected to server");
    clearInterval(fallbackTimer);
    fallbackTimer = null;
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleUpdate(data);
    } catch (e) {
      addLog("ERR", "Failed to parse message");
    }
  };

  ws.onclose = () => {
    $wsStatus.className = "status-dot disconnected";
    $wsLabel.textContent = "offline";
    addLog("WS", "Disconnected, retrying...");
    startFallback();
    setTimeout(connectWS, RECONNECT_DELAY);
  };

  ws.onerror = () => {
    ws.close();
  };
}

// ── REST Fallback ──
async function fetchREST() {
  try {
    const [statusRes, balancesRes, positionsRes] = await Promise.all([
      fetch(`${API_BASE}/status`),
      fetch(`${API_BASE}/balances`),
      fetch(`${API_BASE}/positions`),
    ]);

    const status = await statusRes.json();
    const balances = await balancesRes.json();
    const positions = await positionsRes.json();

    renderStatus(status);
    renderConnectors(status.connected_exchanges || []);
    renderBalances(balances);
    renderPositions(positions);
  } catch {
    addLog("HTTP", "REST fetch failed");
  }
}

function startFallback() {
  if (fallbackTimer) return;
  fallbackTimer = setInterval(fetchREST, FALLBACK_INTERVAL);
  fetchREST();
}

// ── Init ──
addLog("SYS", "Dashboard loaded");
connectWS();
