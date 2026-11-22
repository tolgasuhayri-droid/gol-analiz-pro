
let matches = [];

const $ = id => document.getElementById(id);

function render() {
  const league = $('league').value;

  const data = matches.filter(m =>
    !league || m.league === league
  );

  $('status').textContent =
    `${data.length} maç gösteriliyor`;

  $('results').innerHTML = data.map(m => {
    const home = escapeHTML(m.home);
    const away = escapeHTML(m.away);
    const lig = escapeHTML(m.league);

    return `
      <article class="panel">
        <div class="muted">${lig}</div>
        <h3>${home} - ${away}</h3>
        <div class="muted">
          Durum: ${escapeHTML(m.status)}
        </div>
      </article>
    `;
  }).join('') || '<p>Maç bulunamadı.</p>';
}

function escapeHTML(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

fetch('predictions.json?ts=' + Date.now(), {
  cache: 'no-store'
})
.then(r => {
  if (!r.ok) throw Error('HTTP ' + r.status);
  return r.json();
})
.then(data => {
  matches = Array.isArray(data) ? data : [];

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
