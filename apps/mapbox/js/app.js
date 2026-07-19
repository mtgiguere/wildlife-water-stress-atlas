// ─────────────────────────────────────────────────────────────────
// app.js
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
  'Hippopotamus amphibius':  'Megafauna',
  'Syncerus caffer':         'Herbivore',
};

// Stress level color palette
// low = green, moderate = yellow, high = red, fallback = cyan
const STRESS_COLORS = {
  low:      '#00C87A',
  moderate: '#FFB800',
  high:     '#FF5A3C',
  fallback: '#00C4FF',
};

// Mapbox match expression — maps stress_level property to color
const STRESS_COLOR_EXPR = [
  'match', ['get', 'stress_level'],
  'low',      STRESS_COLORS.low,
  'moderate', STRESS_COLORS.moderate,
  'high',     STRESS_COLORS.high,
  STRESS_COLORS.fallback,
];

// Dim slate — reserved for genuine no-data / no-coverage (Phase D confidence
// layer). NOT used for a real zero-stress value: a 0 reads green so the animal
// stays visible (see stressRamp / the threat ramps below).
const ROAD_THREAT_NONE = '#2A4050';

// Road threat color ramp — continuous 0–1 road_threat_score. 0 = green (low /
// no threat) so every occurrence is visible; threat reads as the shift to red.
const ROAD_THREAT_COLOR_EXPR = [
  'interpolate', ['linear'], ['get', 'road_threat_score'],
  0,    STRESS_COLORS.low,
  0.33, STRESS_COLORS.moderate,
  0.66, STRESS_COLORS.high,
  1,    STRESS_COLORS.high,
];

// Settlement threat color ramp — same green→red threat semantics as roads,
// keyed on settlement_threat_score. Shown in the SETTLEMENTS view.
const SETTLEMENT_THREAT_COLOR_EXPR = [
  'interpolate', ['linear'], ['get', 'settlement_threat_score'],
  0,    STRESS_COLORS.low,
  0.33, STRESS_COLORS.moderate,
  0.66, STRESS_COLORS.high,
  1,    STRESS_COLORS.high,
];

// Settlement context points (cities & towns) — a warm violet, distinct from
// the amber road backbone and the blue water network.
const SETTLEMENT_POINT_COLOR = '#C08BE0';

// Stress color ramp keyed on any 0–1 stress property. The STRESS view colors by
// stress_aggregate (cumulative) by default; the per-stressor toggle recolors the
// same points by a single stressor's contribution (stress_water/roads/settlements).
function stressRamp(valueExpr) {
  return [
    'interpolate', ['linear'], valueExpr,
    // 0 = green (not dark slate): the animal is ALWAYS visible; stress reads as the
    // shift toward red. Grey is reserved for genuine no-data/coverage (Phase D),
    // never for a real zero-stress value.
    0,    STRESS_COLORS.low,
    0.33, STRESS_COLORS.moderate,
    0.66, STRESS_COLORS.high,
    1,    STRESS_COLORS.high,
  ];
}
function stressColorBy(prop) { return stressRamp(['get', prop]); }
const STRESS_AGGREGATE_COLOR_EXPR = stressColorBy('stress_aggregate');

// The per-occurrence stressor contributions that make up the cumulative
// (noisy-OR) total. These are REBUILT per selected species from its stressor
// list (buildStressorControls) — not hardcoded — so the controls reflect whatever
// stressors a plugin declares. `let` because they're reassigned on species change.
let STRESSOR_PROPS = ['stress_water', 'stress_roads', 'stress_settlements'];
let SCENARIO_LABELS = { stress_water: 'Water', stress_roads: 'Roads', stress_settlements: 'Settlements' };
// Which stressors are included in the live cumulative re-aggregation (a scenario),
// and each stressor's weight in [0,1] (a mitigation knob; 0 == excluded).
let scenarioEnabled = { stress_water: true, stress_roads: true, stress_settlements: true };
let scenarioWeight = { stress_water: 1, stress_roads: 1, stress_settlements: 1 };

// Cumulative stress as a LIVE Mapbox expression: noisy-OR (1 − ∏(1−wᵢ·sᵢ)) over
// the ENABLED stressors, read straight from each feature's per-stressor
// properties and scaled by the scenario weight wᵢ. A missing/null stressor
// coerces to 0 → factor (1−0)=1 → excluded (honest coverage); weight 0 does the
// same. This lets STRESS "Total" recolor instantly on any toggle/slider change,
// with no data mutation. Matches the Python engine's noisy-OR.
function scenarioAggExpr() {
  const factors = STRESSOR_PROPS
    .filter(p => scenarioEnabled[p])
    .map(p => ['-', 1, ['*', scenarioWeight[p], ['to-number', ['get', p]]]]);
  if (factors.length === 0) return ['literal', 0];
  const product = factors.length === 1 ? factors[0] : ['*', ...factors];
  return ['-', 1, product];
}

// JS twin of scenarioAggExpr, for the tooltip (feature props are in hand there).
function scenarioAggregate(props) {
  const vals = STRESSOR_PROPS
    .filter(p => scenarioEnabled[p])
    .map(p => (props[p] == null ? null : scenarioWeight[p] * props[p]))
    .filter(v => v != null);
  if (!vals.length) return 0;
  return 1 - vals.reduce((prod, v) => prod * (1 - v), 1);
}

// Legend/tooltip label for the cumulative total, noting any excluded stressors.
function scenarioLabel() {
  const excluded = STRESSOR_PROPS.filter(p => !scenarioEnabled[p]).map(p => SCENARIO_LABELS[p]);
  return excluded.length ? `Cumulative stress (excl. ${excluded.join(', ')})` : 'Cumulative stress';
}

// Which stress property the STRESS view currently colors by.
let currentStressBy = 'stress_aggregate';

// A stressor id → display label (title-cased; underscores → spaces). A proper
// display name lives in the stressor-type plugins; title-casing the id is the JIT
// choice until that's surfaced to the frontend.
function titleCase(id) {
  return id.replace(/_/g, ' ').replace(/\b\w/, c => c.toUpperCase());
}

// Build the STRESS-view controls (colour-by + scenario) from the SELECTED
// species' stressor list — so the UI reflects whatever stressors a plugin
// declares (finishes the "stressor-driven frontend" goal), instead of a
// hardcoded Water/Roads/Settlements set. Called on species change. Event
// handling is delegated to the containers, so rebuilding the DOM is safe.
function buildStressorControls(species) {
  const cfg = speciesConfig[species] || {};
  const ids = Array.isArray(cfg.stressors) ? cfg.stressors.map(s => s.stressor_id) : [];

  STRESSOR_PROPS   = ids.map(id => `stress_${id}`);
  SCENARIO_LABELS  = Object.fromEntries(ids.map(id => [`stress_${id}`, titleCase(id)]));
  scenarioEnabled  = Object.fromEntries(STRESSOR_PROPS.map(p => [p, true]));
  scenarioWeight   = Object.fromEntries(STRESSOR_PROPS.map(p => [p, 1]));
  currentStressBy  = 'stress_aggregate';

  // Colour-by: Total (cumulative) + one button per stressor.
  const colorby = document.getElementById('stress-colorby');
  colorby.querySelectorAll('.stressby-btn').forEach(b => b.remove());
  const total = document.createElement('button');
  total.className = 'stressby-btn active';
  total.dataset.prop = 'stress_aggregate';
  total.textContent = 'Total';
  colorby.appendChild(total);
  ids.forEach(id => {
    const b = document.createElement('button');
    b.className = 'stressby-btn';
    b.dataset.prop = `stress_${id}`;
    b.textContent = titleCase(id);
    colorby.appendChild(b);
  });

  // Scenario: one include/exclude button + weight slider per stressor.
  const scenario = document.getElementById('stress-scenario');
  scenario.querySelectorAll('.scenario-row').forEach(r => r.remove());
  ids.forEach(id => {
    const prop = `stress_${id}`;
    const label = titleCase(id);
    const row = document.createElement('div');
    row.className = 'scenario-row';
    row.innerHTML = `
      <button class="scenario-btn active" data-prop="${prop}" aria-pressed="true">${label}</button>
      <input class="scenario-weight" type="range" min="0" max="100" step="5" value="100" data-prop="${prop}" aria-label="${label} weight" />
      <span class="scenario-weight-val" data-prop="${prop}">100%</span>
    `;
    scenario.appendChild(row);
  });
}

// ─────────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────────
let speciesConfig    = {};
let allFeatures      = [];   // all occurrence features for current species
let allThreatFeatures = [];  // all road-threat features for current species
let allSettlementFeatures = [];  // all settlement-threat features for current species
let allAggregateFeatures = [];   // all cumulative-stress features for current species
let currentSpecies   = 'Loxodonta africana';
// Default to the last FULL calendar year; loadSpeciesData() then clamps this to
// the data's actual range, so the effective default = min(latest year in data,
// currentYear − 1). (Was hardcoded 2020 — the anomalous COVID-dip year.)
let currentYear      = new Date().getFullYear() - 1;
let currentView      = 'points';
let countryData      = [];   // [{NAME, ISO_A3, year, count}, ...]
let countriesGeoJSON = null;
let mapReady         = false;

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

function getStressFile(scientificName) {
  // Load stress score GeoJSON — occurrences enriched with distance_m,
  // stress_score (0-1), and stress_level (low/moderate/high)
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/stress_scores_gbif_${slug}.geojson`;
}

function getThreatFile(scientificName) {
  // Load road threat GeoJSON — occurrences enriched with distance_to_road_m,
  // road_class, and road_threat_score (0-1). May not exist for every species.
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/road_threats_gbif_${slug}.geojson`;
}

function getSettlementFile(scientificName) {
  // Load settlement threat GeoJSON — occurrences enriched with
  // distance_to_settlement_m, settlement_class, and settlement_threat_score.
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/settlement_threats_gbif_${slug}.geojson`;
}

function getAggregateStressFile(scientificName) {
  // Load cumulative-stress GeoJSON — occurrences enriched with per-stressor
  // scores (stress_water/roads/settlements) and stress_aggregate (0-1).
  const slug = scientificName.toLowerCase().replace(' ', '_');
  return `data/stress_gbif_${slug}.geojson`;
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

function stressLevelLabel(level) {
  if (level === 'low')      return `<span style="color:${STRESS_COLORS.low}">● LOW</span>`;
  if (level === 'moderate') return `<span style="color:${STRESS_COLORS.moderate}">● MODERATE</span>`;
  if (level === 'high')     return `<span style="color:${STRESS_COLORS.high}">● HIGH</span>`;
  return '—';
}

function showTooltip(e, props) {
  const cfg = speciesConfig[currentSpecies] || {};
  const distKm = props.distance_m ? (props.distance_m / 1000).toFixed(1) + ' km' : '—';
  tooltip.innerHTML = `
    <strong>${cfg.emoji || ''} ${props.species || cfg.common_name || currentSpecies}</strong><br>
    Year: ${props.year || '—'}<br>
    Distance to water: ${distKm}<br>
    Stress: ${stressLevelLabel(props.stress_level)}
  `;
  tooltip.style.display = 'block';
  moveTooltip(e);
}

function threatLevelLabel(score) {
  if (score >= 0.66) return `<span style="color:${STRESS_COLORS.high}">● HIGH</span>`;
  if (score >= 0.33) return `<span style="color:${STRESS_COLORS.moderate}">● MODERATE</span>`;
  if (score > 0)     return `<span style="color:${STRESS_COLORS.low}">● LOW</span>`;
  return `<span style="color:var(--text-muted)">● NONE</span>`;
}

function showThreatTooltip(e, props) {
  const cfg = speciesConfig[currentSpecies] || {};
  const distKm = props.distance_to_road_m != null ? (props.distance_to_road_m / 1000).toFixed(1) + ' km' : '—';
  const score  = props.road_threat_score != null ? props.road_threat_score.toFixed(2) : '—';
  tooltip.innerHTML = `
    <strong>${cfg.emoji || ''} ${props.species || cfg.common_name || currentSpecies}</strong><br>
    Year: ${props.year || '—'}<br>
    Nearest road: ${props.road_class || '—'}<br>
    Distance to road: ${distKm}<br>
    Road threat: ${threatLevelLabel(props.road_threat_score || 0)} (${score})
  `;
  tooltip.style.display = 'block';
  moveTooltip(e);
}

function showSettlementTooltip(e, props) {
  const cfg = speciesConfig[currentSpecies] || {};
  const distKm = props.distance_to_settlement_m != null ? (props.distance_to_settlement_m / 1000).toFixed(1) + ' km' : '—';
  const score  = props.settlement_threat_score != null ? props.settlement_threat_score.toFixed(2) : '—';
  tooltip.innerHTML = `
    <strong>${cfg.emoji || ''} ${props.species || cfg.common_name || currentSpecies}</strong><br>
    Year: ${props.year || '—'}<br>
    Nearest settlement: ${props.settlement_class || '—'}<br>
    Distance to settlement: ${distKm}<br>
    Settlement threat: ${threatLevelLabel(props.settlement_threat_score || 0)} (${score})
  `;
  tooltip.style.display = 'block';
  moveTooltip(e);
}

function pct(v) {
  return v == null ? '—' : Math.round(v * 100) + '%';
}

function showAggregateStressTooltip(e, props) {
  const cfg = speciesConfig[currentSpecies] || {};
  // The per-stressor breakdown is the whole point of cumulative (not worst-wins)
  // aggregation — you can see which stressors drive the total. Excluded stressors
  // (scenario off) are struck through and don't count toward the shown total.
  const agg = scenarioAggregate(props);
  const part = (p) => {
    const s = `${SCENARIO_LABELS[p].toLowerCase()} ${pct(props[p])}`;
    return scenarioEnabled[p] ? s : `<span style="opacity:0.4; text-decoration:line-through">${s}</span>`;
  };
  tooltip.innerHTML = `
    <strong>${cfg.emoji || ''} ${props.species || cfg.common_name || currentSpecies}</strong><br>
    Year: ${props.year || '—'}<br>
    ${scenarioLabel()}: ${threatLevelLabel(agg)} (${pct(agg)})<br>
    <span style="opacity:0.75">· ${part('stress_water')} · ${part('stress_roads')} · ${part('stress_settlements')}</span>
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

  if (map.getSource('threats')) {
    map.getSource('threats').setData({
      type: 'FeatureCollection',
      features: filterByYear(allThreatFeatures, year),
    });
  }

  if (map.getSource('settlement-threats')) {
    map.getSource('settlement-threats').setData({
      type: 'FeatureCollection',
      features: filterByYear(allSettlementFeatures, year),
    });
  }

  if (map.getSource('stress-aggregate')) {
    map.getSource('stress-aggregate').setData({
      type: 'FeatureCollection',
      features: filterByYear(allAggregateFeatures, year),
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
// Group species by realm (data-driven → scales as species plugins are added;
// a flat list doesn't). Preferred order first, then any unknown realms.
const REALM_ORDER = ['terrestrial', 'freshwater', 'marine'];
const REALM_LABELS = { terrestrial: 'Terrestrial', freshwater: 'Freshwater', marine: 'Marine' };

function buildSpeciesGrid(config) {
  const grid = document.getElementById('species-grid');
  grid.innerHTML = '';

  const byRealm = {};
  Object.entries(config).forEach(([sci, cfg]) => {
    const realm = cfg.realm || 'other';
    (byRealm[realm] ||= []).push([sci, cfg]);
  });
  const realms = [
    ...REALM_ORDER.filter(r => byRealm[r]),
    ...Object.keys(byRealm).filter(r => !REALM_ORDER.includes(r)),
  ];

  realms.forEach(realm => {
    const header = document.createElement('div');
    header.className = 'species-group-label';
    header.dataset.realm = realm;
    header.textContent = REALM_LABELS[realm] || realm;
    grid.appendChild(header);

    byRealm[realm].forEach(([sci, cfg]) => {
      const btn = document.createElement('button');
      btn.className = 'species-btn';
      btn.dataset.species = sci;
      btn.dataset.search = `${cfg.common_name} ${sci}`.toLowerCase();  // for filtering
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
  });
}

// Type-to-filter the species list; scales to many plugins. Hides non-matching
// buttons and any realm header left with no visible members.
function filterSpecies(query) {
  const q = query.trim().toLowerCase();
  const grid = document.getElementById('species-grid');
  grid.querySelectorAll('.species-btn').forEach(btn => {
    btn.style.display = !q || btn.dataset.search.includes(q) ? '' : 'none';
  });
  grid.querySelectorAll('.species-group-label').forEach(header => {
    let sib = header.nextElementSibling;
    let anyVisible = false;
    while (sib && sib.classList.contains('species-btn')) {
      if (sib.style.display !== 'none') { anyVisible = true; break; }
      sib = sib.nextElementSibling;
    }
    header.style.display = anyVisible ? '' : 'none';
  });
}

document.getElementById('species-search').addEventListener('input', e => filterSpecies(e.target.value));

async function loadSpecies(scientificName) {
  currentSpecies = scientificName;

  // Rebuild the STRESS-view controls from this species' stressor list, and
  // re-apply the Total coloring if the STRESS view is open.
  buildStressorControls(scientificName);
  if (currentView === 'stress') setStressColorBy('stress_aggregate');

  // Update active button
  document.querySelectorAll('.species-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.species === scientificName);
  });

  // Update legend label
  const cfg = speciesConfig[scientificName] || {};
  document.getElementById('legend-species-label').textContent =
    `${cfg.emoji || ''} ${cfg.common_name || scientificName} occurrences`;

  // Fetch stress score GeoJSON — occurrences enriched with stress_level
  const url = getStressFile(scientificName);
  let geojson;
  try {
    const res = await fetch(url);
    geojson = await res.json();
  } catch (e) {
    console.warn('Could not load stress scores for', scientificName, e);
    geojson = { type: 'FeatureCollection', features: [] };
  }

  allFeatures = geojson.features;

  // Fetch road threat GeoJSON — same occurrences enriched with road_threat_score.
  // Not every species necessarily has an export yet, so fail soft to empty.
  try {
    const tres = await fetch(getThreatFile(scientificName));
    const tgeo = await tres.json();
    allThreatFeatures = tgeo.features || [];
  } catch (e) {
    console.warn('Could not load road threats for', scientificName, e);
    allThreatFeatures = [];
  }

  // Fetch settlement threat GeoJSON — same occurrences enriched with
  // settlement_threat_score. Fail soft to empty if not yet exported.
  try {
    const sres = await fetch(getSettlementFile(scientificName));
    const sgeo = await sres.json();
    allSettlementFeatures = sgeo.features || [];
  } catch (e) {
    console.warn('Could not load settlement threats for', scientificName, e);
    allSettlementFeatures = [];
  }

  // Fetch cumulative-stress GeoJSON — occurrences with stress_aggregate + the
  // per-stressor breakdown. Fail soft to empty if not yet exported.
  try {
    const ares = await fetch(getAggregateStressFile(scientificName));
    const ageo = await ares.json();
    allAggregateFeatures = ageo.features || [];
  } catch (e) {
    console.warn('Could not load cumulative stress for', scientificName, e);
    allAggregateFeatures = [];
  }

  // Fly to Africa on species switch
  map.flyTo({ center: [20, 0], zoom: 3, duration: 1200 });

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

function setVisibility(layerId, visible) {
  if (map.getLayer(layerId)) {
    map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
  }
}

// Legend sections follow the active view: water-stress for POINTS/COUNTRIES,
// road-threat for ROADS, settlement-threat for SETTLEMENTS.
function updateLegend() {
  const isThreats = currentView === 'threats';
  const isSettlements = currentView === 'settlements';
  const isStress = currentView === 'stress';
  document.getElementById('legend-stress').style.display = isThreats || isSettlements || isStress ? 'none' : 'flex';
  document.getElementById('legend-threat').style.display = isThreats ? 'flex' : 'none';
  document.getElementById('legend-settlement').style.display = isSettlements ? 'flex' : 'none';
  document.getElementById('legend-aggregate').style.display = isStress ? 'flex' : 'none';
  document.getElementById('stress-colorby').style.display = isStress ? 'flex' : 'none';
  document.getElementById('stress-scenario').style.display = isStress ? 'flex' : 'none';
}

// Per-stressor toggle: recolor the STRESS dots by any single stressor's
// contribution (or the cumulative total), so you can see WHICH stressor drives
// the pattern — the map-layer form of the tooltip breakdown.
function setStressColorBy(prop) {
  currentStressBy = prop;
  // "Total" uses the live scenario expression (defaults to the full noisy-OR);
  // a single stressor colors by its own property (scenario doesn't apply there).
  const expr = prop === 'stress_aggregate' ? stressRamp(scenarioAggExpr()) : stressColorBy(prop);
  ['stress-aggregate-dot', 'stress-aggregate-glow'].forEach(id => {
    if (map.getLayer(id)) map.setPaintProperty(id, 'circle-color', expr);
  });
  document.querySelectorAll('.stressby-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.prop === prop));
  const label = document.getElementById('legend-aggregate-label');
  // Label derives from the stressor id (title-cased): "Water stress", etc.
  if (label) label.textContent = prop === 'stress_aggregate' ? scenarioLabel() : `${SCENARIO_LABELS[prop] || 'Stress'} stress`;
}

// Controls are rebuilt per species (buildStressorControls), so listeners are
// DELEGATED to the containers rather than bound to individual (transient) buttons.
document.getElementById('stress-colorby').addEventListener('click', e => {
  const btn = e.target.closest('.stressby-btn');
  if (btn) setStressColorBy(btn.dataset.prop);
});

// Scenario include/exclude — toggle a stressor in/out of the cumulative total and
// re-aggregate live (only affects the "Total" coloring).
document.getElementById('stress-scenario').addEventListener('click', e => {
  const btn = e.target.closest('.scenario-btn');
  if (!btn) return;
  const prop = btn.dataset.prop;
  scenarioEnabled[prop] = !scenarioEnabled[prop];
  btn.classList.toggle('active', scenarioEnabled[prop]);
  btn.setAttribute('aria-pressed', String(scenarioEnabled[prop]));
  if (currentStressBy === 'stress_aggregate') setStressColorBy('stress_aggregate');
});

// Weight sliders — scale a stressor's contribution (0% == excluded), live.
document.getElementById('stress-scenario').addEventListener('input', e => {
  const slider = e.target.closest('.scenario-weight');
  if (!slider) return;
  const prop = slider.dataset.prop;
  scenarioWeight[prop] = Number(slider.value) / 100;
  const valSpan = document.querySelector(`.scenario-weight-val[data-prop="${prop}"]`);
  if (valSpan) valSpan.textContent = `${slider.value}%`;
  if (currentStressBy === 'stress_aggregate') setStressColorBy('stress_aggregate');
});

// Hide every view-specific data layer. Each show*View() then re-enables only
// the layers it needs — keeps the four views mutually exclusive without each
// one having to remember every other view's layers.
function hideAllDataLayers() {
  [
    'occurrences-dot', 'occurrences-glow', 'clusters', 'cluster-count',
    'countries-fill', 'countries-stroke',
    'roads-backbone-line', 'threats-dot', 'threats-glow',
    'settlements-points-layer', 'settlement-threats-dot', 'settlement-threats-glow',
    'stress-aggregate-dot', 'stress-aggregate-glow',
  ].forEach(id => setVisibility(id, false));
}

function showPointsView() {
  currentView = 'points';
  hideAllDataLayers();
  setVisibility('occurrences-dot',  true);
  setVisibility('occurrences-glow', true);
  setVisibility('clusters',         true);
  setVisibility('cluster-count',    true);
  updateLegend();
  stopPlay();
}

function showCountriesView() {
  currentView = 'countries';
  hideAllDataLayers();
  setVisibility('countries-fill',   true);
  setVisibility('countries-stroke', true);
  applyCountryView(currentYear);
  updateLegend();
  stopPlay();
}

function showThreatsView() {
  currentView = 'threats';
  hideAllDataLayers();
  setVisibility('roads-backbone-line', true);
  setVisibility('threats-dot',      true);
  setVisibility('threats-glow',     true);
  updateLegend();
  stopPlay();
}

function showSettlementsView() {
  currentView = 'settlements';
  hideAllDataLayers();
  setVisibility('settlements-points-layer', true);
  setVisibility('settlement-threats-dot',   true);
  setVisibility('settlement-threats-glow',  true);
  updateLegend();
  stopPlay();
}

function showStressView() {
  currentView = 'stress';
  hideAllDataLayers();
  setVisibility('stress-aggregate-dot',  true);
  setVisibility('stress-aggregate-glow', true);
  // Apply the current colour-by (Total uses the live scenario noisy-OR expression)
  // so the view is consistent from the moment it opens, before any toggle click.
  setStressColorBy(currentStressBy);
  updateLegend();
  stopPlay();
}

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if      (btn.dataset.view === 'points')      showPointsView();
    else if (btn.dataset.view === 'countries')   showCountriesView();
    else if (btn.dataset.view === 'settlements') showSettlementsView();
    else if (btn.dataset.view === 'stress')      showStressView();
    else                                         showThreatsView();
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

  // Glow layer — soft halo color-coded by stress level
  map.addLayer({
    id: 'occurrences-glow',
    type: 'circle',
    source: 'occurrences',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius':  8,
      'circle-color':   STRESS_COLOR_EXPR,
      'circle-opacity': 0.15,
      'circle-blur':    1,
    },
  });

  // Dot layer — solid point color-coded by stress level
  map.addLayer({
    id: 'occurrences-dot',
    type: 'circle',
    source: 'occurrences',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius':         3.5,
      'circle-color':          STRESS_COLOR_EXPR,
      'circle-opacity':        0.85,
      'circle-stroke-width':   0.5,
      'circle-stroke-color':   '#FFFFFF',
      'circle-stroke-opacity': 0.3,
    },
  });

  // ── Backbone road network ─────────────────────────────────────
  // Simplified motorway/trunk/primary lines — drawn beneath the threat
  // points so a red occurrence is visibly "next to a road". Amber, to read
  // distinctly from the blue water network. Shown only in the ROADS view.
  map.addSource('roads-backbone', {
    type: 'geojson',
    data: 'data/roads_backbone.geojson',
    buffer: 64,
    tolerance: 0.5,
  });

  map.addLayer({
    id: 'roads-backbone-line',
    type: 'line',
    source: 'roads-backbone',
    layout: { visibility: 'none', 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color':   '#F2A93B',
      'line-width':   ['interpolate', ['linear'], ['zoom'], 3, 1.4, 6, 2.2, 11, 4],
      // Roads are context, occurrences are the subject. Keep the network faint
      // at the continental overview (where 137k segments would otherwise drown
      // the points) and let it firm up as you zoom in for precise reference.
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.28, 5, 0.5, 8, 0.85],
    },
  });

  // ── Road threat source + layers ───────────────────────────────
  // Same occurrence points, colored by road_threat_score instead of stress.
  // Not clustered — clustering would hide the per-point threat color.
  map.addSource('threats', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: 'threats-glow',
    type: 'circle',
    source: 'threats',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':  8,
      'circle-color':   ROAD_THREAT_COLOR_EXPR,
      'circle-opacity': 0.15,
      'circle-blur':    1,
    },
  });

  map.addLayer({
    id: 'threats-dot',
    type: 'circle',
    source: 'threats',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':         3.5,
      'circle-color':          ROAD_THREAT_COLOR_EXPR,
      'circle-opacity':        0.85,
      'circle-stroke-width':   0.5,
      'circle-stroke-color':   '#FFFFFF',
      'circle-stroke-opacity': 0.3,
    },
  });

  map.on('mouseenter', 'threats-dot', e => {
    map.getCanvas().style.cursor = 'pointer';
    showThreatTooltip(e, e.features[0].properties);
  });
  map.on('mousemove', 'threats-dot', e => {
    moveTooltip(e);
  });
  map.on('mouseleave', 'threats-dot', () => {
    map.getCanvas().style.cursor = '';
    hideTooltip();
  });

  // ── Settlement points (cities & towns) ────────────────────────
  // Context layer for the SETTLEMENTS view — the city/town points the threat
  // is measured against. Violet, to read distinctly from amber roads and blue
  // water. Analytics score against ALL settlement classes; only city/town paint.
  map.addSource('settlements-points', {
    type: 'geojson',
    data: 'data/settlements_points.geojson',
    buffer: 64,
    tolerance: 0.5,
  });

  map.addLayer({
    id: 'settlements-points-layer',
    type: 'circle',
    source: 'settlements-points',
    layout: { visibility: 'none' },
    paint: {
      // Cities read larger than towns; both firm up as you zoom in.
      'circle-radius': [
        'interpolate', ['linear'], ['zoom'],
        3, ['match', ['get', 'settlement_class'], 'city', 3, 1.5],
        8, ['match', ['get', 'settlement_class'], 'city', 7, 4],
      ],
      'circle-color':          SETTLEMENT_POINT_COLOR,
      'circle-opacity':        ['interpolate', ['linear'], ['zoom'], 3, 0.35, 6, 0.6, 9, 0.85],
      'circle-stroke-width':   0.5,
      'circle-stroke-color':   '#FFFFFF',
      'circle-stroke-opacity': 0.25,
    },
  });

  // ── Settlement threat source + layers ─────────────────────────
  // Same occurrence points, colored by settlement_threat_score. Not clustered.
  map.addSource('settlement-threats', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: 'settlement-threats-glow',
    type: 'circle',
    source: 'settlement-threats',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':  8,
      'circle-color':   SETTLEMENT_THREAT_COLOR_EXPR,
      'circle-opacity': 0.15,
      'circle-blur':    1,
    },
  });

  map.addLayer({
    id: 'settlement-threats-dot',
    type: 'circle',
    source: 'settlement-threats',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':         3.5,
      'circle-color':          SETTLEMENT_THREAT_COLOR_EXPR,
      'circle-opacity':        0.85,
      'circle-stroke-width':   0.5,
      'circle-stroke-color':   '#FFFFFF',
      'circle-stroke-opacity': 0.3,
    },
  });

  map.on('mouseenter', 'settlement-threats-dot', e => {
    map.getCanvas().style.cursor = 'pointer';
    showSettlementTooltip(e, e.features[0].properties);
  });
  map.on('mousemove', 'settlement-threats-dot', e => {
    moveTooltip(e);
  });
  map.on('mouseleave', 'settlement-threats-dot', () => {
    map.getCanvas().style.cursor = '';
    hideTooltip();
  });

  // ── Cumulative stress source + layers (STRESS view) ───────────
  // Occurrences colored by stress_aggregate — the noisy-OR of ALL stressors.
  map.addSource('stress-aggregate', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: 'stress-aggregate-glow',
    type: 'circle',
    source: 'stress-aggregate',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':  8,
      'circle-color':   STRESS_AGGREGATE_COLOR_EXPR,
      'circle-opacity': 0.15,
      'circle-blur':    1,
    },
  });

  map.addLayer({
    id: 'stress-aggregate-dot',
    type: 'circle',
    source: 'stress-aggregate',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius':         3.5,
      'circle-color':          STRESS_AGGREGATE_COLOR_EXPR,
      'circle-opacity':        0.85,
      'circle-stroke-width':   0.5,
      'circle-stroke-color':   '#FFFFFF',
      'circle-stroke-opacity': 0.3,
    },
  });

  map.on('mouseenter', 'stress-aggregate-dot', e => {
    map.getCanvas().style.cursor = 'pointer';
    showAggregateStressTooltip(e, e.features[0].properties);
  });
  map.on('mousemove', 'stress-aggregate-dot', e => {
    moveTooltip(e);
  });
  map.on('mouseleave', 'stress-aggregate-dot', () => {
    map.getCanvas().style.cursor = '';
    hideTooltip();
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