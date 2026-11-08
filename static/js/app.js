/* ============================================================
   Global Pulse — frontend logic (vanilla JS + Chart.js)
   ============================================================ */

const $ = (id) => document.getElementById(id);

const state = {
  city: readPref("city"),
  base: readPref("base") || "EUR",
  days: 30,
  fxSymbol: null,
  coin: "bitcoin",
  charts: {},
};

const COLORS = {
  accent: "#7c5cff",
  cyan: "#22d3ee",
  green: "#34d399",
  amber: "#fbbf24",
  sky: "#38bdf8",
  grid: "rgba(255,255,255,0.06)",
  text: "#8b90b0",
};

const COINS = {
  bitcoin: { symbol: "BTC", color: "#f7931a" },
  ethereum: { symbol: "ETH", color: "#a5a5ff" },
  solana: { symbol: "SOL", color: "#14f195" },
  cardano: { symbol: "ADA", color: "#4d8dff" },
};

/* ---------------- helpers ---------------- */

function readPref(key) {
  try { return localStorage.getItem(`gp:${key}`); } catch { return null; }
}
function savePref(key, value) {
  try { localStorage.setItem(`gp:${key}`, value); } catch { /* storage unavailable */ }
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

let toastTimer;
function toast(message, type = "") {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 3800);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function skeleton(container, count, height = 56) {
  container.replaceChildren(
    ...Array.from({ length: count }, () => {
      const s = el("div", "skeleton");
      s.style.minHeight = `${height}px`;
      return s;
    }),
  );
}

function errorBox(container, message) {
  container.replaceChildren(el("div", "error-box", message));
}

function changeBadge(value, suffix = "") {
  if (value === null || value === undefined) return el("span", "change", "—");
  const up = value >= 0;
  return el("span", `change ${up ? "up" : "down"}`, `${up ? "▲" : "▼"} ${Math.abs(value).toFixed(2)}%${suffix}`);
}

const money = (v, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: v < 1 ? 4 : 2,
  }).format(v);

const compact = (v) => new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);

/* ---------------- charts ---------------- */

Chart.defaults.color = COLORS.text;
Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.font.size = 11;

function gradient(ctx, color) {
  const { chartArea } = ctx.chart;
  if (!chartArea) return "transparent";
  const g = ctx.chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  g.addColorStop(0, `${color}55`);
  g.addColorStop(1, `${color}00`);
  return g;
}

function lineChart(id, labels, data, color, { format = (v) => v, tickFormat = format, maxTicks = 6 } = {}) {
  const existing = state.charts[id];
  if (existing) {
    existing.data.labels = labels;
    existing.data.datasets[0].data = data;
    existing.data.datasets[0].borderColor = color;
    existing.data.datasets[0].backgroundColor = (ctx) => gradient(ctx, color);
    existing.options.plugins.tooltip.callbacks.label = (c) => ` ${format(c.parsed.y)}`;
    existing.options.scales.y.ticks.callback = (v) => tickFormat(v);
    existing.update();
    return;
  }
  state.charts[id] = new Chart($(id), {
    type: "line",
    data: {
      labels,
      datasets: [{
        data,
        borderColor: color,
        backgroundColor: (ctx) => gradient(ctx, color),
        fill: true,
        tension: 0.38,
        borderWidth: 2.2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: color,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1d2140",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          padding: 10,
          displayColors: false,
          callbacks: { label: (c) => ` ${format(c.parsed.y)}` },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: maxTicks,
            maxRotation: 0,
            // Axis shows only the part before the comma ("Nov 2"); tooltips keep the full label.
            callback(value) { return String(this.getLabelForValue(value)).split(",")[0]; },
          },
        },
        y: { grid: { color: COLORS.grid }, border: { display: false }, ticks: { maxTicksLimit: 5, callback: (v) => tickFormat(v) } },
      },
    },
  });
}

/* ---------------- weather icons (inline SVG) ---------------- */

const SUN = '<circle cx="32" cy="32" r="11" fill="#fbbf24"/><g stroke="#fbbf24" stroke-width="3" stroke-linecap="round"><path d="M32 8v6M32 50v6M8 32h6M50 32h6M15 15l4 4M45 45l4 4M15 49l4-4M45 19l4-4"/></g>';
const MOON = '<path d="M40 14a18 18 0 1 0 10 32A16 16 0 0 1 40 14Z" fill="#c7d2fe"/>';
const CLOUD = (fill = "#cbd5e1", y = 0) =>
  `<path transform="translate(0 ${y})" d="M20 48h26a10 10 0 0 0 0-20 14 14 0 0 0-27-2 11 11 0 0 0 1 22Z" fill="${fill}"/>`;
const DROPS = '<g stroke="#38bdf8" stroke-width="3" stroke-linecap="round"><path d="M24 54l-2 6M33 54l-2 6M42 54l-2 6"/></g>';

function weatherIcon(icon, isDay = true) {
  const body = {
    clear: isDay ? SUN : MOON,
    partly: `<g transform="translate(-6 -8) scale(.8)">${isDay ? SUN : MOON}</g>${CLOUD("#e2e8f0", 4)}`,
    cloudy: `${CLOUD("#64748b", -6)}${CLOUD("#cbd5e1", 4)}`,
    fog: `${CLOUD("#94a3b8", -6)}<g stroke="#94a3b8" stroke-width="3" stroke-linecap="round"><path d="M14 52h36M20 58h28"/></g>`,
    drizzle: `${CLOUD("#94a3b8", -4)}<g stroke="#38bdf8" stroke-width="3" stroke-linecap="round"><path d="M26 52v4M38 52v4"/></g>`,
    rain: `${CLOUD("#94a3b8", -4)}${DROPS}`,
    snow: `${CLOUD("#cbd5e1", -4)}<g fill="#e0f2fe"><circle cx="24" cy="56" r="2.5"/><circle cx="33" cy="58" r="2.5"/><circle cx="42" cy="56" r="2.5"/></g>`,
    storm: `${CLOUD("#64748b", -4)}<path d="M34 46l-6 9h6l-4 8 10-11h-6l4-6Z" fill="#fbbf24"/>`,
  }[icon] || CLOUD();
  return `<svg viewBox="0 0 64 64" style="fill:none;stroke:none">${body}</svg>`;
}

/* ---------------- weather ---------------- */

async function loadWeather(city = state.city) {
  const query = city ? `?city=${encodeURIComponent(city)}` : "";
  const data = await api(`/api/weather${query}`);
  state.city = data.location.name;
  savePref("city", state.city);
  renderWeather(data);
  return data;
}

function renderWeather({ location, current, hourly, daily }) {
  $("w-location").textContent = `${location.name}${location.country ? ", " + location.country : ""}`;
  $("w-temp").textContent = Math.round(current.temperature);
  $("w-desc").textContent = current.description;
  $("w-feels").textContent = `${Math.round(current.feels_like)}°C`;
  $("w-hum").textContent = `${current.humidity}%`;
  $("w-wind").textContent = `${Math.round(current.wind_speed)} km/h`;
  $("w-time").textContent = current.time.slice(11, 16);
  $("w-icon").innerHTML = weatherIcon(current.icon, current.is_day);

  lineChart(
    "weather-chart",
    hourly.time.map((t) => t.slice(11, 16)),
    hourly.temperature,
    COLORS.sky,
    { format: (v) => `${Math.round(v)}°`, maxTicks: 8 },
  );

  $("w-daily").replaceChildren(
    ...daily.map((d, i) => {
      const card = el("div", "day");
      card.title = d.description;
      const name = i === 0 ? "Today" : new Date(`${d.date}T12:00`).toLocaleDateString("en", { weekday: "short" });
      card.append(el("div", "name", name));
      card.insertAdjacentHTML("beforeend", weatherIcon(d.icon, true));
      const temps = el("div");
      temps.append(el("span", "hi", `${Math.round(d.max)}°`), el("span", "lo", `${Math.round(d.min)}°`));
      card.append(temps);
      return card;
    }),
  );
}

/* ---------------- currency ---------------- */

async function loadCurrencies() {
  const currencies = await api("/api/currencies");
  const select = $("fx-base");
  select.replaceChildren(
    ...Object.entries(currencies).map(([code, name]) => {
      const opt = el("option", "", code);
      opt.value = code;
      opt.title = name;
      return opt;
    }),
  );
  if (!(state.base in currencies)) state.base = "EUR";
  select.value = state.base;
}

async function loadRates() {
  const data = await api(`/api/rates?base=${state.base}&days=${state.days}`);
  const symbols = Object.keys(data.rates);
  if (!symbols.includes(state.fxSymbol)) state.fxSymbol = symbols[0];
  renderRates(data);
  return data;
}

function renderRates(data) {
  $("fx-date").textContent = `Updated ${data.date}`;
  const tiles = Object.entries(data.rates).map(([code, value]) => {
    const tile = el("button", `tile${code === state.fxSymbol ? " active" : ""}`);
    tile.type = "button";
    tile.append(el("div", "code", `${data.base} → ${code}`), el("div", "value", value.toFixed(4)), changeBadge(data.change_pct[code], ` · ${state.days}D`));
    tile.addEventListener("click", () => {
      state.fxSymbol = code;
      renderRates(data);
    });
    return tile;
  });
  $("fx-tiles").replaceChildren(...tiles);

  const { dates, series } = data.history;
  lineChart(
    "fx-chart",
    dates.map((d) => new Date(`${d}T12:00`).toLocaleDateString("en", { month: "short", day: "numeric" })),
    series[state.fxSymbol],
    COLORS.green,
    { format: (v) => Number(v).toFixed(4) },
  );
}

/* ---------------- crypto ---------------- */

async function loadCrypto() {
  const coins = await api("/api/crypto");
  renderCrypto(coins);
  await loadCoinHistory(state.coin);
  return coins;
}

function renderCrypto(coins) {
  const items = coins.map((c) => {
    const meta = COINS[c.id] || { symbol: c.id.slice(0, 3).toUpperCase(), color: COLORS.accent };
    const li = el("li");
    const btn = el("button", `coin${c.id === state.coin ? " active" : ""}`);
    btn.type = "button";
    btn.dataset.coin = c.id;

    const avatar = el("span", "coin-avatar", meta.symbol[0]);
    avatar.style.background = meta.color;

    const info = el("div");
    info.append(el("div", "coin-name", `${c.id[0].toUpperCase()}${c.id.slice(1)}`), el("div", "coin-cap", `${meta.symbol} · MCap $${compact(c.market_cap)}`));

    const price = el("div", "coin-price");
    price.append(el("div", "", money(c.price)), changeBadge(c.change_24h, " 24h"));

    btn.append(avatar, info, price);
    btn.addEventListener("click", () => {
      state.coin = c.id;
      document.querySelectorAll(".coin").forEach((b) => b.classList.toggle("active", b.dataset.coin === c.id));
      loadCoinHistory(c.id).catch((e) => toast(e.message, "error"));
    });
    li.append(btn);
    return li;
  });
  $("crypto-list").replaceChildren(...items);
}

async function loadCoinHistory(coin) {
  const data = await api(`/api/crypto/${coin}/history?days=7`);
  const meta = COINS[coin] || { color: COLORS.amber, symbol: coin };
  $("crypto-chart-title").textContent = `${meta.symbol} · 7-day price (USD)`;
  lineChart(
    "crypto-chart",
    data.timestamps.map((t) =>
      new Date(t).toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
    ),
    data.prices,
    meta.color,
    {
      format: (v) => money(v),
      tickFormat: (v) => (v >= 1000 ? `$${compact(v)}` : money(v)),
      maxTicks: 7,
    },
  );
}

/* ---------------- telegram ---------------- */

async function loadStatus() {
  const health = await api("/api/health");
  const chip = $("tg-status");
  chip.textContent = health.telegram_enabled ? "connected" : "not configured";
  chip.className = `status-chip ${health.telegram_enabled ? "on" : "off"}`;
  $("tg-send").disabled = !health.telegram_enabled;
  if (!health.telegram_enabled) $("tg-send").title = "Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env";
  if (!state.city) state.city = health.default_city;
}

async function sendDigest() {
  const btn = $("tg-send");
  btn.disabled = true;
  try {
    const res = await api("/api/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city: state.city, base: state.base }),
    });
    const preview = $("tg-preview");
    preview.textContent = res.preview.replace(/<[^>]+>/g, "");
    preview.hidden = false;
    toast("Digest sent to Telegram ✓", "success");
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

/* ---------------- orchestration ---------------- */

async function loadAll() {
  const btn = $("refresh-btn");
  btn.classList.add("spinning");
  const tasks = [
    ["Weather", loadWeather(), (m) => errorBox($("w-daily"), m)],
    ["Exchange rates", loadRates(), (m) => errorBox($("fx-tiles"), m)],
    ["Crypto", loadCrypto(), (m) => errorBox($("crypto-list"), m)],
  ];
  const results = await Promise.allSettled(tasks.map((t) => t[1]));
  results.forEach((r, i) => {
    if (r.status === "rejected") {
      const [name, , onError] = tasks[i];
      onError(r.reason.message);
      toast(`${name}: ${r.reason.message}`, "error");
    }
  });
  btn.classList.remove("spinning");
  $("last-updated").textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function bindEvents() {
  $("city-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const city = $("city-input").value.trim();
    if (city.length < 2) return;
    try {
      await loadWeather(city);
      $("city-input").value = "";
      $("city-input").blur();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $("fx-base").addEventListener("change", (e) => {
    state.base = e.target.value;
    savePref("base", state.base);
    loadRates().catch((err) => toast(err.message, "error"));
  });

  $("fx-range").addEventListener("click", (e) => {
    const days = Number(e.target.dataset.days);
    if (!days || days === state.days) return;
    state.days = days;
    document.querySelectorAll("#fx-range button").forEach((b) => b.classList.toggle("active", b === e.target));
    loadRates().catch((err) => toast(err.message, "error"));
  });

  $("refresh-btn").addEventListener("click", loadAll);
  $("tg-send").addEventListener("click", sendDigest);
}

async function init() {
  skeleton($("fx-tiles"), 5, 78);
  skeleton($("crypto-list"), 4);
  skeleton($("w-daily"), 7, 90);
  bindEvents();

  await loadStatus().catch(() => {});
  loadCurrencies().catch(() => {});
  await loadAll();

  setInterval(loadAll, 5 * 60 * 1000); // auto-refresh every 5 minutes
}

init();
