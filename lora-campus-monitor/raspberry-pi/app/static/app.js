// Shared dashboard helpers and a small dependency-free canvas line chart
// (no CDN needed: the dashboard works on a LAN without internet).

function refreshMs() {
  return Math.max(5, Number(document.body.dataset.refresh || 15)) * 1000;
}

async function fetchJSON(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fmt(v, digits) {
  return v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(digits);
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function fmtAge(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
  return `${Math.floor(s / 86400)} d ${Math.floor((s % 86400) / 3600)} h`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setState(id, ok, okText, badText) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = ok ? okText : badText;
  el.className = 'value ' + (ok ? 'good' : 'bad');
}

function metric(label, value, unit, digits) {
  return `<div class="metric"><div class="label">${label}</div><div class="mval">${fmt(value, digits)} <span class="unit">${unit}</span></div></div>`;
}

function formatTimestamps() {
  document.querySelectorAll('.ts[data-ts]').forEach(el => { el.textContent = fmtTime(el.dataset.ts); });
}

function drawLineChart(canvas, points, key, unit, hours) {
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 300;
  const cssHeight = Number(canvas.getAttribute('height')) || 180;
  canvas.style.height = cssHeight + 'px';
  canvas.width = cssWidth * dpr;
  canvas.height = cssHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const css = getComputedStyle(document.body);
  const lineColor = css.getPropertyValue('--accent').trim() || '#2563eb';
  const gridColor = css.getPropertyValue('--grid').trim() || '#e5e7eb';
  const textColor = css.getPropertyValue('--muted').trim() || '#6b7280';

  const data = points
    .filter(p => p[key] !== null && p[key] !== undefined)
    .map(p => ({ t: new Date(p.received_at).getTime(), v: Number(p[key]) }));

  ctx.font = '11px system-ui, sans-serif';
  ctx.fillStyle = textColor;
  if (data.length === 0) {
    ctx.textAlign = 'center';
    ctx.fillText('No data in this period', cssWidth / 2, cssHeight / 2);
    return;
  }

  const pad = { l: 48, r: 10, t: 10, b: 24 };
  const w = cssWidth - pad.l - pad.r;
  const h = cssHeight - pad.t - pad.b;
  const tMax = Date.now();
  const tMin = tMax - hours * 3600 * 1000;
  let vMin = Math.min(...data.map(d => d.v));
  let vMax = Math.max(...data.map(d => d.v));
  if (vMin === vMax) { vMin -= 1; vMax += 1; }
  const margin = (vMax - vMin) * 0.08;
  vMin -= margin; vMax += margin;

  const x = t => pad.l + ((t - tMin) / (tMax - tMin)) * w;
  const y = v => pad.t + (1 - (v - vMin) / (vMax - vMin)) * h;

  ctx.strokeStyle = gridColor;
  ctx.lineWidth = 1;
  const step = (vMax - vMin) / 4;
  const decimals = step >= 10 ? 0 : step >= 1 ? 1 : step >= 0.1 ? 2 : 3;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (let i = 0; i <= 4; i++) {
    const v = vMin + step * i;
    const yy = y(v);
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(pad.l + w, yy); ctx.stroke();
    ctx.fillText(v.toFixed(decimals), pad.l - 6, yy);
  }

  ctx.textBaseline = 'top';
  for (let i = 0; i <= 4; i++) {
    const t = tMin + ((tMax - tMin) * i) / 4;
    const d = new Date(t);
    const label = hours > 48
      ? d.toLocaleDateString([], { month: 'short', day: 'numeric' })
      : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    ctx.textAlign = i === 0 ? 'left' : i === 4 ? 'right' : 'center';
    ctx.fillText(label, x(t), pad.t + h + 6);
  }

  // Break the line where the gap is much larger than the typical spacing.
  const spacing = data.length > 1 ? (data[data.length - 1].t - data[0].t) / (data.length - 1) : 0;
  const maxGap = Math.max(spacing * 5, 5 * 60 * 1000);
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  data.forEach((d, i) => {
    const gap = i > 0 && d.t - data[i - 1].t > maxGap;
    if (i === 0 || gap) ctx.moveTo(x(d.t), y(d.v)); else ctx.lineTo(x(d.t), y(d.v));
  });
  ctx.stroke();
  if (data.length < 60) {
    ctx.fillStyle = lineColor;
    data.forEach(d => { ctx.beginPath(); ctx.arc(x(d.t), y(d.v), 2, 0, 2 * Math.PI); ctx.fill(); });
  }

  const last = data[data.length - 1];
  ctx.fillStyle = textColor;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText(`latest ${last.v.toFixed(Math.abs(last.v) < 100 ? 2 : 0)} ${unit}`, pad.l + 6, pad.t + 2);
}
