const $ = s => document.querySelector(s);
let timer;

/* ---------- map ---------- */
const map = L.map('map', {worldCopyJump: true, minZoom: 1}).setView([25, 10], 2);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 18
}).addTo(map);

const pinIcon = L.divIcon({
  className: '', html: '<div class="pin"></div>', iconSize: [14, 14], iconAnchor: [7, 7]
});
let pin = null, night = null;

function setPin(lat, lon) {
  if (pin) pin.setLatLng([lat, lon]);
  else pin = L.marker([lat, lon], {icon: pinIcon, keyboard: false}).addTo(map);
}

async function drawNight() {
  try {
    const t = await (await fetch('/api/terminator')).json();
    const ring = t.points.concat([[t.pole, 180], [t.pole, -180]]);
    if (night) night.setLatLngs(ring);
    else night = L.polygon(ring, {
      stroke: false, fillColor: '#05070C', fillOpacity: .55, interactive: false
    }).addTo(map);
    night.bringToBack();
  } catch (e) { /* the map is still perfectly usable without it */ }
}

map.on('click', async e => {
  const hint = $('#maphint');
  hint.className = 'maphint busy';
  hint.textContent = 'Finding the nearest town...';
  setPin(e.latlng.lat, e.latlng.lng);
  try {
    const r = await fetch('/api/reverse', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({lat: e.latlng.lat, lon: e.latlng.lng})
    });
    const p = await r.json();
    hint.className = 'maphint';
    hint.textContent = p.snapped
      ? 'Nearest town: ' + p.label
      : p.label + ' \u2014 nothing named nearby, using the coordinates';
    await choose(p);
  } catch (err) {
    hint.className = 'maphint';
    hint.textContent = 'Could not look that spot up. Try again, or use the search.';
  }
});

/* ---------- panel ---------- */
async function status() {
  const s = await (await fetch('/api/status')).json();
  const lamp = $('#lamp');
  lamp.style.setProperty('--lamp', s.color || '#8896A6');
  lamp.style.setProperty('--sky', s.sky || '#FFFFFF');
  lamp.style.setProperty('--sky-a', s.sky_alpha ?? 0);
  lamp.style.setProperty('--dim', s.dim ?? 1);
  lamp.className = 'lamp ' + (s.anim || 'steady');

  $('#cond').textContent = s.condition || 'Pick a place';
  $('#place').textContent = s.place || 'nowhere yet';
  $('#figs').textContent = s.temperature == null
    ? '' : `${s.temperature}\u00b0C \u00b7 wind ${s.wind} km/h \u00b7 cloud ${s.cloud}%`;
  $('#clock').innerHTML = s.time ? `${s.time} <span>${s.phase}</span>` : '';
  $('#sunline').textContent = s.sunline || '';
  $('#note').textContent = s.bulbs
    ? `${s.bulbs} bulb${s.bulbs > 1 ? 's' : ''} following along`
    : 'Preview only \u2014 no bulbs connected';

  if (s.lat != null) setPin(s.lat, s.lon);
}

async function choose(p) {
  await fetch('/api/place', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(p)
  });
  $('#q').value = '';
  $('#results').innerHTML = '';
  setPin(p.lat, p.lon);
  if (map.getZoom() < 4) map.flyTo([p.lat, p.lon], 5, {duration: 1.1});
  else map.panTo([p.lat, p.lon]);
  setTimeout(status, 400);
}

function rows(list) {
  const ul = $('#results');
  ul.innerHTML = '';
  list.forEach(p => {
    const li = document.createElement('li');
    const b = document.createElement('button');
    // textContent throughout: a place name from a third party never becomes markup
    b.textContent = p.name + ' ';
    const co = document.createElement('span');
    co.className = 'co';
    co.textContent = p.country || '';
    b.appendChild(co);
    b.onclick = () => choose({label: p.label, lat: p.lat, lon: p.lon});
    li.appendChild(b);
    ul.appendChild(li);
  });
}

$('#q').addEventListener('input', e => {
  clearTimeout(timer);
  const q = e.target.value.trim();
  if (q.length < 2) { $('#results').innerHTML = ''; return; }
  timer = setTimeout(async () => {
    rows(await (await fetch('/api/search?q=' + encodeURIComponent(q))).json());
  }, 300);
});

(async () => {
  const presets = await (await fetch('/api/presets')).json();
  const chips = $('#chips');
  presets.forEach(p => {
    const b = document.createElement('button');
    b.textContent = p.label;
    b.onclick = () => choose(p);
    chips.appendChild(b);
  });
})();

status();
setInterval(status, 5000);
drawNight();
setInterval(drawNight, 120000);
