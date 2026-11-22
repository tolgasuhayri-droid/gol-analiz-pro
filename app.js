
let matches = [];

const $ = id => document.getElementById(id);

function escapeHTML(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

function percentage(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const pct = n <= 1 ? n * 100 : n;
  return Math.max(0, Math.min(100, pct));
}

function render() {
  const league = $('league')?.value || '';

  const data = matches.filter(m =>
    !league || m.league === league
  );

  $('status').textContent =
    `${data.length} maç gösteriliyor`;

  $('results').innerHTML = data.map(m => {
    const home = escapeHTML(m.home);
    const away = escapeHTML(m.away);
    const lig = escapeHTML(m.league);

    const markets = [
      ['2,5 ÜST', m.over25],
      ['3,5 ÜST', m.over35],
      ['İY 0,5 ÜST', m.ht_over05],
      ['İY 1,5 ÜST', m.ht_over15]
    ];

    const predictions = markets.map(([name, value]) => {
      const pct = percentage(value);
      return `
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #334155">
          <span>${name}</span>
          <strong>${pct === null ? 'Veri yok' : pct.toFixed(1) + '%'}</strong>
        </div>
      `;
    }).join('');

    return `
      <article class="panel">
        <div class="muted">${lig}</div>
        <h3>${home} - ${away}</h3>
        <div class="muted">Durum: ${escapeHTML(m.status)}</div>
        <div style="margin-top:12px">${predictions}</div>
        <div class="muted" style="margin-top:10px">
          ${escapeHTML(m.analysis_status || '')}
        </div>
      </article>
    `;
  }).join('') || '<p>Maç bulunamadı.</p>';
}

fetch('predictions.json?ts=' + Date.now(), {
  cache: 'no-store'
})
.then(r => {
  if (!r.ok) throw Error('HTTP ' + r.status);
  return r.json();
})
.then(data => {
  matches = Array.isArray(data.matches) ? data.matches : [];

  const leagues = [...new Set(
    matches.map(m => m.league).filter(Boolean)
  )].sort();

  $('league').innerHTML =
    '<option value="">Tüm ligler</option>' +
    leagues.map(l =>
      `<option value="${escapeHTML(l)}">${escapeHTML(l)}</option>`
    ).join('');

  $('league').onchange = render;
  render();
})
.catch(e => {
  $('status').textContent =
    'Veri okunamadı: ' + e.message;
});
