
let matches = [];
let selectedMarket = "over25";

const $ = id => document.getElementById(id);

const markets = [
  { id: "o25", key: "over25", label: "2,5 ÜST" },
  { id: "o35", key: "over35", label: "3,5 ÜST" },
  { id: "ht05", key: "ht_over05", label: "İY 0,5 ÜST" },
  { id: "ht15", key: "ht_over15", label: "İY 1,5 ÜST" }
];

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}

function probability(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const n = Number(value);

  if (!Number.isFinite(n) || n < 0 || n > 100) {
    return null;
  }

  return n <= 1 ? n * 100 : n;
}

function formatProbability(value) {
  const pct = probability(value);
  return pct === null ? "Veri yok" : pct.toFixed(1) + "%";
}

function setupMarkets() {
  const tabs = document.querySelector(".tabs");

  if (!tabs) return;

  // Mevcut iki butonu koru, ilk yari seceneklerini ekle.
  markets.slice(2).forEach(market => {
    if (!$(market.id)) {
      const button = document.createElement("button");
      button.id = market.id;
      button.textContent = market.label;
      tabs.appendChild(button);
    }
  });

  tabs.style.flexWrap = "wrap";

  markets.forEach(market => {
    const button = $(market.id);
    if (!button) return;

    button.style.flexBasis = "40%";

    button.onclick = () => {
      selectedMarket = market.key;
      updateButtons();
      render();
    };
  });

  updateButtons();
}

function updateButtons() {
  markets.forEach(market => {
    const button = $(market.id);
    if (button) {
      button.classList.toggle(
        "active",
        market.key === selectedMarket
      );
    }
  });
}

function render() {
  const league = $("league")?.value || "";
  const minimum = Number($("cut")?.value ?? 50);

  if ($("cutLabel")) {
    $("cutLabel").textContent = minimum + "%";
  }

  const filtered = matches
    .filter(match => !league || match.league === league)
    .filter(match => {
      const pct = probability(match[selectedMarket]);
      return pct !== null && pct >= minimum;
    })
    .sort((a, b) =>
      probability(b[selectedMarket]) -
      probability(a[selectedMarket])
    );

  $("status").textContent =
    `${filtered.length} / ${matches.length} maç gösteriliyor`;

  $("results").innerHTML = filtered.map(match => {
    const selectedPct = probability(match[selectedMarket]);

    const rows = markets.map(market => {
      const pct = probability(match[market.key]);
      const highlighted = market.key === selectedMarket;

      return `
        <div style="
          display:flex;
          justify-content:space-between;
          gap:12px;
          padding:9px 0;
          border-bottom:1px solid #334155;
          ${highlighted ? "color:#66dfb4;" : ""}
        ">
          <span>${market.label}</span>
          <strong>${formatProbability(match[market.key])}</strong>
        </div>
      `;
    }).join("");

    const strong = selectedPct >= 70;

    return `
      <article class="panel">
        <div class="muted">
          ${escapeHTML(match.league)}
        </div>

        <h3>
          ${escapeHTML(match.home)} -
          ${escapeHTML(match.away)}
        </h3>

        <div class="muted">
          Durum: ${escapeHTML(match.status)}
        </div>

        <div style="
          display:flex;
          justify-content:space-between;
          align-items:center;
          margin-top:14px;
          gap:10px;
        ">
          <strong>
            ${markets.find(m => m.key === selectedMarket)?.label}
          </strong>

          <span class="score">
            ${selectedPct.toFixed(1)}%
          </span>
        </div>

        ${strong ? `
          <div style="
            color:#66dfb4;
            font-size:13px;
            margin-top:6px;
          ">
            Yüksek model olasılığı
          </div>
        ` : ""}

        <div class="bar">
          <div class="fill" style="
            width:${selectedPct}%;
          "></div>
        </div>

        <div style="margin-top:14px">
          ${rows}
        </div>

        <div class="muted" style="margin-top:10px">
          ${escapeHTML(match.analysis_status || "")}
        </div>
      </article>
    `;
  }).join("") || `
    <article class="panel">
      <p>Bu filtreye uygun maç bulunamadı.</p>
      <div class="muted">
        Minimum olasılığı düşürmeyi deneyebilirsin.
      </div>
    </article>
  `;
}

setupMarkets();

if ($("cut")) {
  $("cut").oninput = render;
}

if ($("league")) {
  $("league").onchange = render;
}

fetch("predictions.json?ts=" + Date.now(), {
  cache: "no-store"
})
.then(response => {
  if (!response.ok) {
    throw new Error("HTTP " + response.status);
  }
  return response.json();
})
.then(data => {
  matches = Array.isArray(data.matches)
    ? data.matches
    : [];

  const leagues = [...new Set(
    matches.map(m => m.league).filter(Boolean)
  )].sort();

  $("league").innerHTML =
    '<option value="">Tüm ligler</option>' +
    leagues.map(league => `
      <option value="${escapeHTML(league)}">
        ${escapeHTML(league)}
      </option>
    `).join("");

  if ($("updated") && data.updated_at) {
    const date = new Date(data.updated_at);
    $("updated").textContent =
      Number.isNaN(date.getTime())
        ? ""
        : "Son güncelleme: " + date.toLocaleString("tr-TR");
  }

  render();
})
.catch(error => {
  $("status").textContent =
    "Veriler yüklenemedi: " + error.message;
});

