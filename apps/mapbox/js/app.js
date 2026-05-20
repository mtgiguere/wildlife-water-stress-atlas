// ─────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────
const MAPBOX_TOKEN = 'pk.eyJ1IjoibXRnaWd1ZXJlIiwiYSI6ImNtcDRnNzl3ejAwajAycG9rb2s1Y2N4NDcifQ.Q72clPC-L8yxVcvrs0LmHA';

const TIER_LABELS = {
  'Loxodonta africana':      'Megafauna',
  'Equus quagga':            'Herbivore',
  'Giraffa camelopardalis':  'Herbivore',
  'Panthera leo':            'Carnivore',
  'Acinonyx jubatus':        'Carnivore',
  'Crocodylus niloticus':    'Indicator',
  'Phoenicopterus roseus':   'Indicator',
  'Hyperolius marmoratus':   'Indicator',
  'Xenopus laevis':          'Indicator',
};

// ─────────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────────
let speciesConfig   = {};
let allFeatures     = [];   // all occurrence features for current species
let currentSpecies  = 'Loxodonta africana';
let currentYear     = 2020;
let currentView     = 'points';
let countryData     = [];   // [{NAME, ISO_A3, year, count}, ...]
let countriesGeoJSON = null;
let mapReady        = false;

// ─────────────────────────────────────────────────────────────────
// MAP INIT
// ─────────────────────────────────────────────────────────────────
mapboxgl.accessToken = MAPBOX_TOKEN;

const map = new mapboxgl.Map({
  container: 'map',
  style: 'mapbox://styles/mapbox/dark-v11',
  center: [20, 0],
  zoom: 3,
  minZoom: 2,
  maxZoom: 12,
  projection: 'mercator',
});

map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');

// ─────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────
function fmt(n) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString();
}

function getOccurrenceFile(scientificName) {
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/occurrences_gbif_${slug}.geojson`;
}

function filterByYear(features, year) {
  return features.filter(f => f.properties.year === year);
}

function updateStats(yearFeatures) {
  document.getElementById('stat-year-count').textContent = fmt(yearFeatures.length);
  document.getElementById('stat-total-count').textContent = fmt(allFeatures.length);
  document.getElementById('covid-note').style.display = currentYear === 2020 ? 'block' : 'none';
}

// ─────────────────────────────────────────────────────────────────
// TOOLTIP
// ─────────────────────────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');

function showTooltip(e, props) {
  const cfg = speciesConfig[currentSpecies] || {};
  tooltip.innerHTML = `
    <strong>${cfg.emoji || ''} ${props.species || cfg.common_name || currentSpecies}</strong><br>
    Year: ${props.year || '—'}
  `;
  tooltip.style.display = 'block';
  moveTooltip(e);
}

function moveTooltip(e) {
  const x = e.originalEvent.clientX;
  const y = e.originalEvent.clientY;
  tooltip.style.left = (x + 14) + 'px';
  tooltip.style.top  = (y - 10) + 'px';
}

function hideTooltip() {
  tooltip.style.display = 'none';
}

// ─────────────────────────────────────────────────────────────────
// YEAR SLIDER
// ─────────────────────────────────────────────────────────────────
function getYearRange(features) {
  if (!features.length) return { min: 1800, max: 2024 };
  const years = features.map(f => f.properties.year).filter(Boolean);
  return { min: Math.min(...years), max: Math.max(...years) };
}

function applyYearFilter(year) {
  currentYear = year;
  document.getElementById('year-display').textContent = year;

  const yearFeatures = filterByYear(allFeatures, year);

  if (map.getSource('occurrences')) {
    map.getSource('occurrences').setData({
      type: 'FeatureCollection',
      features: yearFeatures,
    });
  }

  updateStats(yearFeatures);
  if (currentView === 'countries') applyCountryView(year);
}

document.getElementById('year-slider').addEventListener('input', e => {
  applyYearFilter(parseInt(e.target.value));
});

// ─────────────────────────────────────────────────────────────────
// AUTOPLAY
// ─────────────────────────────────────────────────────────────────
let playInterval = null;
let playSpeed    = 400;

document.querySelectorAll('.speed-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    playSpeed = parseInt(btn.dataset.ms);
    if (playInterval) {
      stopPlay();
      startPlay();
    }
  });
});

function startPlay() {
  const slider = document.getElementById('year-slider');
  document.getElementById('play-btn').textContent = '⏸ PAUSE';
  playInterval = setInterval(() => {
    let next = parseInt(slider.value) + 1;
    if (next > parseInt(slider.max)) next = parseInt(slider.min);
    slider.value = next;
    applyYearFilter(next);
  }, playSpeed);
}

function stopPlay() {
  clearInterval(playInterval);
  playInterval = null;
  document.getElementById('play-btn').textContent = '▶ PLAY';
}

document.getElementById('play-btn').addEventListener('click', () => {
  if (playInterval) stopPlay();
  else startPlay();
});

// ─────────────────────────────────────────────────────────────────
// SPECIES
// ─────────────────────────────────────────────────────────────────
function buildSpeciesGrid(config) {
  const grid = document.getElementById('species-grid');
  grid.innerHTML = '';

  Object.entries(config).forEach(([sci, cfg]) => {
    const btn = document.createElement('button');
    btn.className = 'species-btn';
    btn.dataset.species = sci;
    btn.innerHTML = `
      <span class="species-emoji">${cfg.emoji || '🐾'}</span>
      <span class="species-info">
        <span class="species-common">${cfg.common_name}</span>
        <span class="species-scientific">${sci}</span>
      </span>
      <span class="species-tier">${TIER_LABELS[sci] || ''}</span>
    `;
    btn.addEventListener('click', () => loadSpecies(sci));
    grid.appendChild(btn);
  });
}

async function loadSpecies(scientificName) {
  currentSpecies = scientificName;

  // Update active button
  document.querySelectorAll('.species-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.species === scientificName);
  });

  // Update legend label
  const cfg = speciesConfig[scientificName] || {};
  document.getElementById('legend-species-label').textContent =
    `${cfg.emoji || ''} ${cfg.common_name || scientificName} occurrences`;

  // Fetch GeoJSON
  const url = getOccurrenceFile(scientificName);
  let geojson;
  try {
    const res = await fetch(url);
    geojson = await res.json();
  } catch (e) {
    console.warn('Could not load occurrences for', scientificName, e);
    geojson = { type: 'FeatureCollection', features: [] };
  }

  allFeatures = geojson.features;

  // Update year slider range
  const { min, max } = getYearRange(allFeatures);
  const slider = document.getElementById('year-slider');
  slider.min   = min;
  slider.max   = max;

  // Clamp current year to valid range
  const clampedYear = Math.max(min, Math.min(max, currentYear));
  slider.value = clampedYear;

  document.getElementById('year-range-labels').innerHTML =
    `<span>${min}</span><span>${max}</span>`;

  applyYearFilter(clampedYear);

  await loadCountryData(scientificName);
  if (currentView === 'countries') applyCountryView(clampedYear);
}

// ─────────────────────────────────────────────────────────────────
// COUNTRY CHOROPLETH
// ─────────────────────────────────────────────────────────────────
function getCountryFile(scientificName) {
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/country_counts_gbif_${slug}.geojson`;
}

async function loadCountryData(scientificName) {
  const url = getCountryFile(scientificName);
  try {
    const res = await fetch(url);
    countryData = await res.json();
  } catch(e) {
    console.warn('Could not load country data for', scientificName, e);
    countryData = [];
  }
}

function getCountryGeoJSONForYear(year) {
  if (!countriesGeoJSON) return { type: 'FeatureCollection', features: [] };

  const yearCounts = {};
  countryData
    .filter(d => d.year === year)
    .forEach(d => { yearCounts[d.ISO_A3] = d.count; });

  const maxCount = Math.max(...Object.values(yearCounts), 1);

  return {
    type: 'FeatureCollection',
    features: countriesGeoJSON.features.map(f => ({
      ...f,
      properties: {
        ...f.properties,
        count:     yearCounts[f.properties.ISO_A3] || 0,
        intensity: (yearCounts[f.properties.ISO_A3] || 0) / maxCount,
      }
    }))
  };
}

async function initCountriesGeoJSON() {
  if (countriesGeoJSON) return;
  try {
    const res = await fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson');
    countriesGeoJSON = await res.json();
  } catch(e) {
    console.warn('Could not load countries GeoJSON', e);
  }
}

function applyCountryView(year) {
  if (!map.getSource('countries')) return;
  map.getSource('countries').setData(getCountryGeoJSONForYear(year));
}

function showPointsView() {
  currentView = 'points';
  map.setLayoutProperty('occurrences-dot',  'visibility', 'visible');
  map.setLayoutProperty('occurrences-glow', 'visibility', 'visible');
  if (map.getLayer('countries-fill'))   map.setLayoutProperty('countries-fill',   'visibility', 'none');
  if (map.getLayer('countries-stroke')) map.setLayoutProperty('countries-stroke', 'visibility', 'none');
  if (map.getLayer('clusters'))      map.setLayoutProperty('clusters',      'visibility', 'visible');
  if (map.getLayer('cluster-count')) map.setLayoutProperty('cluster-count', 'visibility', 'visible');
  stopPlay();
}

function showCountriesView() {
  currentView = 'countries';
  map.setLayoutProperty('occurrences-dot',  'visibility', 'none');
  map.setLayoutProperty('occurrences-glow', 'visibility', 'none');
  if (map.getLayer('countries-fill'))   map.setLayoutProperty('countries-fill',   'visibility', 'visible');
  if (map.getLayer('countries-stroke')) map.setLayoutProperty('countries-stroke', 'visibility', 'visible');
  if (map.getLayer('clusters'))      map.setLayoutProperty('clusters',      'visibility', 'none');
  if (map.getLayer('cluster-count')) map.setLayoutProperty('cluster-count', 'visibility', 'none');
  applyCountryView(currentYear);
  stopPlay();
}

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (btn.dataset.view === 'points') showPointsView();
    else showCountriesView();
  });
});

async function initCountryLayers() {
  await initCountriesGeoJSON();
  if (!countriesGeoJSON) return;

  map.addSource('countries', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: 'countries-fill',
    type: 'fill',
    source: 'countries',
    layout: { visibility: 'none' },
    paint: {
      'fill-color': [
        'interpolate', ['linear'], ['get', 'intensity'],
        0,    'rgba(0,196,255,0)',
        0.01, 'rgba(0,196,255,0.1)',
        0.25, 'rgba(0,196,255,0.35)',
        0.5,  'rgba(0,196,255,0.6)',
        1,    'rgba(0,196,255,0.85)',
      ],
      'fill-opacity': 0.8,
    },
  });

  map.addLayer({
    id: 'countries-stroke',
    type: 'line',
    source: 'countries',
    layout: { visibility: 'none' },
    paint: {
      'line-color': '#00C4FF',
      'line-width': 0.5,
      'line-opacity': 0.4,
    },
  });

  // Tooltip for country view
  map.on('mouseenter', 'countries-fill', e => {
    const props = e.features[0].properties;
    if (!props.count) return;
    map.getCanvas().style.cursor = 'pointer';
    const cfg = speciesConfig[currentSpecies] || {};
    tooltip.innerHTML = `
      <strong>${props.NAME}</strong><br>
      ${cfg.emoji || ''} ${props.count.toLocaleString()} records<br>
      <span style="color:var(--text-muted)">Year: ${currentYear}</span>
    `;
    tooltip.style.display = 'block';
    moveTooltip(e);
  });

  map.on('mousemove', 'countries-fill', e => {
    const props = e.features[0].properties;
    if (!props.count) {
      hideTooltip();
      return;
    }
    const cfg = speciesConfig[currentSpecies] || {};
    tooltip.innerHTML = `
      <strong>${props.NAME}</strong><br>
      ${cfg.emoji || ''} ${props.count.toLocaleString()} records<br>
      <span style="color:var(--text-muted)">Year: ${currentYear}</span>
    `;
    tooltip.style.display = 'block';
    moveTooltip(e);
  });

  map.on('mouseleave', 'countries-fill', () => {
    map.getCanvas().style.cursor = '';
    hideTooltip();
  });
}

// ─────────────────────────────────────────────────────────────────
// TREND CHART
// ─────────────────────────────────────────────────────────────────
function getCountryTimeSeries(iso) {
  return countryData
    .filter(d => d.ISO_A3 === iso)
    .sort((a, b) => a.year - b.year);
}

function showTrendChart(iso, name) {
  const series = getCountryTimeSeries(iso);
  if (!series.length) return;

  document.getElementById('trend-title').textContent = name.toUpperCase();

  const slope = series[0].slope;
  const r2    = series[0].r2;
  const trend = series[0].trend;

  const badge = document.getElementById('trend-badge');
  badge.textContent = trend.toUpperCase();
  badge.className   = `trend-badge ${trend}`;

  document.getElementById('trend-r2-full').textContent =
    `slope: ${slope.toFixed(2)} rec/yr · r²: ${r2.toFixed(2)}`;

  // Draw chart
  const canvas = document.getElementById('trend-canvas');
  const ctx    = canvas.getContext('2d');
  canvas.width  = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  const years  = series.map(d => d.year);
  const counts = series.map(d => d.count);
  const minY   = 0;
  const maxY   = Math.max(...counts, 1);
  const minX   = Math.min(...years);
  const maxX   = Math.max(...years);

  const pad = { top: 10, right: 20, bottom: 24, left: 36 };
  const w   = canvas.width  - pad.left - pad.right;
  const h   = canvas.height - pad.top  - pad.bottom;

  const toX = x => pad.left + ((x - minX) / (maxX - minX || 1)) * w;
  const toY = y => pad.top  + (1 - (y - minY) / (maxY - minY || 1)) * h;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth   = 1;
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    const y = pad.top + t * h;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + w, y); ctx.stroke();
  });

  // X axis labels
  ctx.fillStyle  = 'rgba(90,122,138,0.8)';
  ctx.font       = '10px DM Sans';
  ctx.textAlign  = 'center';
  years.filter((_, i) => i % Math.ceil(years.length / 6) === 0).forEach(yr => {
    ctx.fillText(yr, toX(yr), canvas.height - 4);
  });

  // Y axis labels
  ctx.textAlign = 'right';
  [0, 0.5, 1].forEach(t => {
    const val = Math.round(minY + t * (maxY - minY));
    ctx.fillText(val, pad.left - 4, pad.top + (1 - t) * h + 4);
  });

  // Data line
  ctx.strokeStyle = 'rgba(0,196,255,0.8)';
  ctx.lineWidth   = 2;
  ctx.beginPath();
  series.forEach((d, i) => {
    if (i === 0) ctx.moveTo(toX(d.year), toY(d.count));
    else         ctx.lineTo(toX(d.year), toY(d.count));
  });
  ctx.stroke();

  // Data points
  ctx.fillStyle = 'rgba(0,196,255,1)';
  series.forEach(d => {
    ctx.beginPath();
    ctx.arc(toX(d.year), toY(d.count), 3, 0, Math.PI * 2);
    ctx.fill();
  });

  // Trend line
  const intercept = series[0].slope * minX + (counts[0] - series[0].slope * years[0]);
  const y1 = series[0].slope * minX + intercept;
  const y2 = series[0].slope * maxX + intercept;

  ctx.strokeStyle = trend === 'increasing' ? 'rgba(0,196,255,0.4)' :
                    trend === 'declining'  ? 'rgba(255,90,60,0.6)' :
                                            'rgba(255,255,255,0.2)';
  ctx.lineWidth   = 1.5;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(toX(minX), toY(Math.max(minY, y1)));
  ctx.lineTo(toX(maxX), toY(Math.max(minY, y2)));
  ctx.stroke();
  ctx.setLineDash([]);

  document.getElementById('trend-panel').classList.add('visible');
}

// Trend panel close button
document.getElementById('trend-close').addEventListener('click', () => {
  document.getElementById('trend-panel').classList.remove('visible');
});

// Country click → trend chart
map.on('click', 'countries-fill', e => {
  const props = e.features[0].properties;
  if (!props.count) return;
  showTrendChart(props.ISO_A3, props.NAME);
});

// ─────────────────────────────────────────────────────────────────
// DRAGGABLE TREND MODAL
// ─────────────────────────────────────────────────────────────────
(function() {
  const panel  = document.getElementById('trend-panel');
  const header = document.getElementById('trend-header');
  let dragging = false, startX, startY, startLeft, startTop;

  header.addEventListener('mousedown', e => {
    if (e.target === document.getElementById('trend-close')) return;
    dragging  = true;
    startX    = e.clientX;
    startY    = e.clientY;
    startLeft = panel.offsetLeft;
    startTop  = panel.offsetTop;
    header.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    panel.style.left = Math.max(0, startLeft + dx) + 'px';
    panel.style.top  = Math.max(0, startTop  + dy) + 'px';
  });

  document.addEventListener('mouseup', () => {
    dragging = false;
    header.style.cursor = 'grab';
  });
})();

// ─────────────────────────────────────────────────────────────────
// MAP LOAD — ADD LAYERS + BOOTSTRAP
// ─────────────────────────────────────────────────────────────────
map.on('load', async () => {

  // ── Water layer ──────────────────────────────────────────────
  map.addSource('water', {
    type: 'geojson',
    data: 'data/water.geojson',
    buffer: 64,
    tolerance: 0.5,
  });

  map.addLayer({
    id: 'water-lines',
    type: 'line',
    source: 'water',
    filter: ['==', ['geometry-type'], 'LineString'],
    paint: {
      'line-color': '#00B4FF',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.6, 6, 2],
      'line-opacity': 0.7,
    },
  });

  map.addLayer({
    id: 'water-polygons-fill',
    type: 'fill',
    source: 'water',
    filter: ['any',
      ['==', ['geometry-type'], 'Polygon'],
      ['==', ['geometry-type'], 'MultiPolygon'],
    ],
    paint: {
      'fill-color': '#00B4FF',
      'fill-opacity': 0.20,
    },
  });

  map.addLayer({
    id: 'water-polygons-stroke',
    type: 'line',
    source: 'water',
    filter: ['any',
      ['==', ['geometry-type'], 'Polygon'],
      ['==', ['geometry-type'], 'MultiPolygon'],
    ],
    paint: {
      'line-color': '#00B4FF',
      'line-width': 0.8,
      'line-opacity': 0.5,
    },
  });

  // ── Occurrences source + layers ───────────────────────────────
  map.addSource('occurrences', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    cluster: true,
    clusterMaxZoom: 6,
    clusterRadius: 40,
  });

  map.addLayer({
    id: 'clusters',
    type: 'circle',
    source: 'occurrences',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': [
        'step', ['get', 'point_count'],
        '#00C4FF', 50,
        '#0090CC', 200,
        '#005F88'
      ],
      'circle-radius': [
        'step', ['get', 'point_count'],
        14, 50,
        20, 200,
        26
      ],
      'circle-opacity': 0.85,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#FFFFFF',
      'circle-stroke-opacity': 0.3,
    },
  });

  map.addLayer({
    id: 'cluster-count',
    type: 'symbol',
    source: 'occurrences',
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
      'text-size': 12,
    },
    paint: {
      'text-color': '#ffffff',
    },
  });

  map.addLayer({
    id: 'occurrences-glow',
    type: 'circle',
    source: 'occurrences',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius':  8,
      'circle-color':   '#00C4FF',
      'circle-opacity': 0.15,
      'circle-blur':    1,
    },
  });

  map.addLayer({
    id: 'occurrences-dot',
    type: 'circle',
    source: 'occurrences',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius':        3.5,
      'circle-color':         '#00C4FF',
      'circle-opacity':       0.85,
      'circle-stroke-width':  0.5,
      'circle-stroke-color':  '#FFFFFF',
      'circle-stroke-opacity':0.3,
    },
  });

  // ── Occurrence tooltip events ─────────────────────────────────
  map.on('mouseenter', 'occurrences-dot', e => {
    map.getCanvas().style.cursor = 'pointer';
    showTooltip(e, e.features[0].properties);
  });
  map.on('mousemove', 'occurrences-dot', e => {
    moveTooltip(e);
  });
  map.on('mouseleave', 'occurrences-dot', () => {
    map.getCanvas().style.cursor = '';
    hideTooltip();
  });

  // ── Cluster click → zoom in ───────────────────────────────────
  map.on('click', 'clusters', e => {
    const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] });
    const clusterId = features[0].properties.cluster_id;
    map.getSource('occurrences').getClusterExpansionZoom(clusterId, (err, zoom) => {
      if (err) return;
      map.easeTo({ center: features[0].geometry.coordinates, zoom });
    });
  });
  map.on('mouseenter', 'clusters', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'clusters', () => { map.getCanvas().style.cursor = ''; });

  // ── Country layers ────────────────────────────────────────────
  await initCountryLayers();
  await loadCountryData(currentSpecies);
  mapReady = true;

  // ── Load species config + initial species ─────────────────────
  try {
    const res = await fetch('data/species_config.json');
    speciesConfig = await res.json();
  } catch (e) {
    console.warn('Could not load species_config.json', e);
  }

  buildSpeciesGrid(speciesConfig);
  await loadSpecies(currentSpecies);

  if (currentView === 'countries') applyCountryView(currentYear);
  else await loadCountryData(currentSpecies);

  // ── Hide loading screen ───────────────────────────────────────
  const loading = document.getElementById('loading');
  loading.classList.add('hidden');
  setTimeout(() => loading.remove(), 700);
});
