/* =========================================
   AQI Forecaster — Frontend Dashboard JS
   ========================================= */

const API = "";  // same-origin; set to "http://localhost:5000" if separate

let map;
let markers = {};
let detailChart = null;
let distChart = null;
let activeCity = null;
let currentTab = "history";

// ── AQI helpers ───────────────────────────

const HEALTH_ADVICE = {
  "Good":         "Air quality is satisfactory. Enjoy outdoor activities.",
  "Satisfactory": "Air quality is acceptable. Unusually sensitive people should consider reducing prolonged outdoor exertion.",
  "Moderate":     "Members of sensitive groups may experience health effects. General public is less likely to be affected.",
  "Poor":         "Everyone may begin to experience health effects. Sensitive groups should limit outdoor exertion.",
  "Very Poor":    "Health warnings of emergency conditions. The entire population is likely to be affected.",
  "Severe":       "Health alert: everyone may experience more serious health effects. Avoid all outdoor exertion.",
};

function aqiColor(aqi) {
  if (aqi <= 50)  return "#00e400";
  if (aqi <= 100) return "#ffff00";
  if (aqi <= 200) return "#ff7e00";
  if (aqi <= 300) return "#ff0000";
  if (aqi <= 400) return "#8f3f97";
  return "#7e0023";
}

function aqiCategory(aqi) {
  if (aqi <= 50)  return "Good";
  if (aqi <= 100) return "Satisfactory";
  if (aqi <= 200) return "Moderate";
  if (aqi <= 300) return "Poor";
  if (aqi <= 400) return "Very Poor";
  return "Severe";
}

function markerSize(aqi) {
  // Scale bubble size by AQI severity
  const base = 36;
  return base + Math.round((aqi / 500) * 24);
}

// ── Map Initialization ─────────────────────

function initMap() {
  map = L.map("map", {
    center: [22.5, 82.5],
    zoom: 5,
    zoomControl: true,
    attributionControl: true,
  });

  // Dark tile layer
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {
      attribution: '© <a href="https://www.openstreetmap.org">OpenStreetMap</a> © <a href="https://carto.com">CARTO</a>',
      maxZoom: 18, minZoom: 4,
    }
  ).addTo(map);

  map.zoomControl.setPosition("bottomright");
}

// ── Markers ───────────────────────────────

function createAQIIcon(aqi, cityName) {
  const color = aqiColor(aqi);
  const size  = markerSize(aqi);
  const fs    = size > 50 ? 14 : 12;
  const cityShort = cityName.length > 7 ? cityName.substring(0, 6) + "…" : cityName;

  return L.divIcon({
    className: "aqi-marker",
    html: `
      <div class="aqi-bubble" style="
        width:${size}px; height:${size}px;
        background:${color};
        box-shadow: 0 0 ${size/2}px ${color}55;
      ">
        <span class="b-val" style="font-size:${fs}px; color:${parseInt(color.slice(1),16) > 0x888888 ? '#000' : '#fff'}">${aqi}</span>
        <span class="b-city" style="font-size:7px; color:${parseInt(color.slice(1),16) > 0x888888 ? '#0004' : '#fff8'}">${cityShort}</span>
      </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function placeMarkers(cities) {
  // Remove old markers
  Object.values(markers).forEach(m => map.removeLayer(m));
  markers = {};

  cities.forEach(city => {
    const icon = createAQIIcon(city.aqi, city.city);
    const marker = L.marker([city.latitude, city.longitude], { icon, zIndexOffset: city.aqi })
      .addTo(map);

    marker.on("click", () => selectCity(city.city, city.state));
    marker.bindTooltip(`
      <div style="font-family:Inter,sans-serif;min-width:120px">
        <strong style="font-size:13px">${city.city}</strong><br>
        <span style="color:#9aa3b8;font-size:11px">${city.state}</span><br>
        <span style="font-size:18px;font-weight:700;color:${city.color || aqiColor(city.aqi)}">${city.aqi}</span>
        <span style="font-size:10px;color:#9aa3b8"> AQI · ${city.category}</span>
      </div>`, { direction: "top", offset: [0, -10] });

    markers[city.city] = marker;
  });
}

// ── Data Loading ───────────────────────────

async function loadCities() {
  try {
    const res  = await fetch(`${API}/api/cities`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    placeMarkers(data.data);
    updateRankings(data.data);
    updateHeaderStats(data.data);
    updateDistChart(data.data);
    document.getElementById("last-updated").textContent = new Date().toLocaleTimeString("en-IN");
  } catch (err) {
    showToast("⚠️ Failed to load city data: " + err.message, "error");
  }
}

function updateHeaderStats(cities) {
  const avg  = Math.round(cities.reduce((s, c) => s + c.aqi, 0) / cities.length);
  const worst = cities.reduce((a, b) => b.aqi > a.aqi ? b : a);
  document.getElementById("nat-avg-val").textContent = avg;
  document.getElementById("nat-avg-val").style.color = aqiColor(avg);
  document.getElementById("worst-city-val").textContent = `${worst.city} (${worst.aqi})`;
  document.getElementById("worst-city-val").style.color = aqiColor(worst.aqi);
}

function updateRankings(cities) {
  const sorted = [...cities].sort((a, b) => b.aqi - a.aqi);
  const list = document.getElementById("ranking-list");
  list.innerHTML = sorted.map((c, i) => `
    <div class="rank-item ${activeCity === c.city ? 'active' : ''}"
         onclick="selectCity('${c.city}', '${c.state}')">
      <span class="rank-num">${i + 1}</span>
      <span class="rank-dot" style="background:${c.color || aqiColor(c.aqi)}"></span>
      <span class="rank-name" title="${c.city}">${c.city}</span>
      <span class="rank-aqi" style="color:${c.color || aqiColor(c.aqi)}">${c.aqi}</span>
    </div>
  `).join("");
}

function updateDistChart(cities) {
  const cats = {};
  const colors = {
    "Good": "#00e400", "Satisfactory": "#ffff00", "Moderate": "#ff7e00",
    "Poor": "#ff0000", "Very Poor": "#8f3f97", "Severe": "#7e0023"
  };
  cities.forEach(c => { cats[c.category] = (cats[c.category] || 0) + 1; });

  const labels = Object.keys(cats);
  const values = Object.values(cats);
  const bgColors = labels.map(l => colors[l] || "#888");

  const ctx = document.getElementById("dist-chart").getContext("2d");
  if (distChart) distChart.destroy();
  distChart = new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: bgColors, borderWidth: 1, borderColor: "#111520" }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#9aa3b8", font: { size: 9 }, padding: 6, boxWidth: 10 }
        }
      },
    }
  });
}

// ── City Detail Panel ──────────────────────

async function selectCity(cityName, stateStr) {
  activeCity = cityName;
  document.getElementById("panel-placeholder").style.display = "none";
  document.getElementById("panel-content").style.display = "block";
  document.getElementById("detail-city-name").textContent = cityName;
  document.getElementById("detail-city-state").textContent = stateStr || "";

  // Reset charts
  if (detailChart) { detailChart.destroy(); detailChart = null; }

  // Fly map to city
  if (markers[cityName]) {
    const latlng = markers[cityName].getLatLng();
    map.flyTo(latlng, 8, { animate: true, duration: 0.8 });
  }

  // Load current data
  try {
    const res  = await fetch(`${API}/api/city/${encodeURIComponent(cityName)}/current`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    const aqi = data.aqi.value;
    const color = aqiColor(aqi);
    const cat = aqiCategory(aqi);

    // Big display
    document.getElementById("aqi-number").textContent = aqi;
    document.getElementById("aqi-circle").style.background = color;
    document.getElementById("aqi-circle").style.boxShadow = `0 0 30px ${color}44`;
    document.getElementById("aqi-category").textContent = cat;
    document.getElementById("aqi-category").style.background = color + "33";
    document.getElementById("aqi-category").style.color = color;
    document.getElementById("health-advice").textContent = HEALTH_ADVICE[cat] || "";

    // Pollutants
    document.getElementById("p-pm25").textContent = data.aqi.pm25;
    document.getElementById("p-pm10").textContent = data.aqi.pm10;
    document.getElementById("p-no2").textContent  = data.aqi.no2;
    document.getElementById("p-so2").textContent  = data.aqi.so2;
    document.getElementById("p-co").textContent   = data.aqi.co;
    document.getElementById("p-o3").textContent   = data.aqi.o3;

    // Weather
    document.getElementById("wx-temp").textContent  = `${data.weather.temperature}°C`;
    document.getElementById("wx-hum").textContent   = `${data.weather.humidity}%`;
    document.getElementById("wx-wind").textContent  = `${data.weather.wind_speed} m/s`;
    document.getElementById("wx-vis").textContent   = `${data.weather.visibility} km`;
  } catch (e) {
    showToast("⚠️ Could not load city data", "error");
  }

  // Default to history tab
  switchTab("history");

  // Highlight rank list
  document.querySelectorAll(".rank-item").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".rank-item").forEach(el => {
    if (el.querySelector(".rank-name")?.textContent.includes(cityName)) el.classList.add("active");
  });
}

function closePanel() {
  activeCity = null;
  document.getElementById("panel-placeholder").style.display = "flex";
  document.getElementById("panel-content").style.display = "none";
  if (detailChart) { detailChart.destroy(); detailChart = null; }
}

// ── Tabs ───────────────────────────────────

function switchTab(tab) {
  currentTab = tab;
  document.getElementById("tab-history").classList.toggle("active", tab === "history");
  document.getElementById("tab-forecast").classList.toggle("active", tab === "forecast");
  document.getElementById("forecast-table-wrapper").style.display = tab === "forecast" ? "block" : "none";

  if (tab === "history") loadHistoryChart();
  else loadForecastChart();
}

async function loadHistoryChart() {
  if (!activeCity) return;
  try {
    const res  = await fetch(`${API}/api/city/${encodeURIComponent(activeCity)}/history?days=30`);
    const data = await res.json();
    if (!data.success) return;

    const labels = data.data.map(d => d.date.slice(5));  // MM-DD
    const values = data.data.map(d => d.aqi);
    const maxVals = data.data.map(d => d.aqi_max);
    const minVals = data.data.map(d => d.aqi_min);
    const bgColors = values.map(v => aqiColor(v) + "44");

    renderDetailChart(labels, values, maxVals, minVals, bgColors, "30-Day AQI History");
  } catch (e) { console.error(e); }
}

async function loadForecastChart() {
  if (!activeCity) return;
  try {
    const res  = await fetch(`${API}/api/city/${encodeURIComponent(activeCity)}/forecast?days=7`);
    const data = await res.json();
    if (!data.success) return;

    const fc = data.forecasts;
    const labels  = fc.map(d => d.date.slice(5));
    const values  = fc.map(d => d.predicted_aqi);
    const uppers  = fc.map(d => d.confidence_upper);
    const lowers  = fc.map(d => d.confidence_lower);
    const bgColors = values.map(v => aqiColor(v) + "44");

    renderDetailChart(labels, values, uppers, lowers, bgColors, `7-Day Forecast (${data.model})`);

    // Fill table
    const tbody = document.getElementById("forecast-tbody");
    tbody.innerHTML = fc.map(f => `
      <tr>
        <td>${f.date}</td>
        <td style="font-weight:700;color:${f.color || aqiColor(f.predicted_aqi)}">${f.predicted_aqi}</td>
        <td><span class="fc-cat" style="background:${f.color || aqiColor(f.predicted_aqi)}">${f.category}</span></td>
        <td style="color:#5a6380">${f.confidence_lower}–${f.confidence_upper}</td>
      </tr>
    `).join("");
  } catch (e) { console.error(e); }
}

function renderDetailChart(labels, values, highs, lows, bgColors, title) {
  const ctx = document.getElementById("detail-chart").getContext("2d");
  if (detailChart) { detailChart.destroy(); detailChart = null; }

  detailChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "AQI",
          data: values,
          borderColor: values.map(v => aqiColor(v)),
          backgroundColor: bgColors,
          segment: {
            borderColor: ctx => aqiColor(values[ctx.p1DataIndex] || 100),
          },
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: false,
        },
        {
          label: "Upper CI",
          data: highs,
          borderColor: "rgba(255,255,255,0.1)",
          backgroundColor: "rgba(59,130,246,0.08)",
          borderWidth: 1, borderDash: [3, 3],
          pointRadius: 0, fill: "+1", tension: 0.4,
        },
        {
          label: "Lower CI",
          data: lows,
          borderColor: "rgba(255,255,255,0.1)",
          backgroundColor: "rgba(59,130,246,0.08)",
          borderWidth: 1, borderDash: [3, 3],
          pointRadius: 0, fill: false, tension: 0.4,
        },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 400 },
      plugins: {
        legend: { display: false },
        title: { display: true, text: title, color: "#9aa3b8", font: { size: 10 } },
        tooltip: {
          backgroundColor: "#181d2e",
          borderColor: "#1f263a",
          borderWidth: 1,
          titleColor: "#f0f2f7",
          bodyColor: "#9aa3b8",
          callbacks: {
            label: ctx => ` AQI: ${ctx.parsed.y} — ${aqiCategory(ctx.parsed.y)}`,
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#5a6380", font: { size: 9 }, maxTicksLimit: 10 },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          ticks: { color: "#5a6380", font: { size: 9 } },
          grid: { color: "rgba(255,255,255,0.04)" },
          min: 0, max: 500,
        }
      }
    }
  });
}

// ── Toast ──────────────────────────────────

function showToast(msg, type = "info") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.background = type === "error" ? "#450a0a" : "#111520";
  el.style.borderColor = type === "error" ? "#ef4444" : "rgba(255,255,255,0.07)";
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3200);
}

// ── Train Models ───────────────────────────

async function triggerTraining() {
  try {
    showToast("⚙️ Model training started in background...");
    const res = await fetch(`${API}/api/train`, { method: "POST" });
    const data = await res.json();
    showToast(data.success ? "✅ " + data.message : "❌ " + data.error,
              data.success ? "info" : "error");
  } catch (e) {
    showToast("❌ Could not start training: " + e.message, "error");
  }
}

// ── Auto-refresh ───────────────────────────

function startAutoRefresh(intervalMs = 60_000) {
  setInterval(async () => {
    await loadCities();
    if (activeCity && currentTab === "history") loadHistoryChart();
  }, intervalMs);
}

// ── Bootstrap ─────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  initMap();
  await loadCities();
  startAutoRefresh(60_000);
});
