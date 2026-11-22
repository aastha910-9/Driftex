/* Chart helpers built on Chart.js (loaded from the CDN in index.html). Same small API used by app.js. */
const Charts = (() => {
  let live = [];
  const fmt = v => v == null ? '–' : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : Math.abs(v) >= 1e4 ? (v / 1e3).toFixed(1) + 'k' : Math.round(v * 10) / 10 === Math.round(v) ? Math.round(v).toLocaleString() : (Math.round(v * 10) / 10).toLocaleString();
  const dlabel = s => new Date(s + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

  function line(el, o) {
    const cv = document.createElement('canvas');
    el.innerHTML = ''; el.style.position = 'relative'; el.style.height = (o.height || 300) + 'px'; el.appendChild(cv);
    const ds = [];
    if (o.band) {
      ds.push({ label: '_low', data: o.band.lo, borderWidth: 0, pointRadius: 0, fill: false });
      ds.push({ label: '80% range', data: o.band.hi, borderWidth: 0, pointRadius: 0, backgroundColor: 'rgba(47,111,237,.13)', fill: '-1' });
    }
    o.series.forEach(s => ds.push({
      label: s.name, data: s.data, borderColor: s.color, backgroundColor: s.color + '22', borderWidth: s.width || 2.2,
      borderDash: s.dash ? [6, 5] : [], pointRadius: 0, pointHoverRadius: 4, tension: 0.25, fill: !!s.area, spanGaps: false
    }));
    const labels = o.labels.map((l, i) => dlabel(l) + (o.fcFrom != null && i >= o.fcFrom ? ' (forecast)' : ''));
    const marker = {
      id: 'marker', afterDatasetsDraw(c) {
        (o.markers || []).forEach(m => {
          const x = c.scales.x.getPixelForValue(m.i), { top, bottom } = c.chartArea, g = c.ctx;
          g.save(); g.strokeStyle = '#9aa6bd'; g.setLineDash([3, 4]); g.beginPath(); g.moveTo(x, top); g.lineTo(x, bottom); g.stroke();
          g.setLineDash([]); g.fillStyle = '#7a859b'; g.font = '11px sans-serif'; g.fillText(m.text, x + 5, top + 12); g.restore();
        });
      }
    };
    const chart = new Chart(cv, {
      type: 'line', data: { labels, datasets: ds }, plugins: [marker],
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: o.series.length > 1, position: 'top', align: 'end', labels: { usePointStyle: true, boxWidth: 8, filter: i => i.text !== '_low' && i.text !== '80% range' } },
          tooltip: { filter: i => i.dataset.label !== '_low', callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.parsed.y)}` } }
        },
        scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } }, y: { beginAtZero: true, grid: { color: '#e8ecf3' }, ticks: { callback: v => fmt(v) } } }
      }
    });
    live.push(chart);
  }

  /* sparkline placeholder; call mountSparks(container) after inserting the HTML */
  const spark = (vals, color = '#2f6fed') => `<canvas class="spark" width="110" height="30" data-c="${color}" data-v='${JSON.stringify(vals || [])}'></canvas>`;
  function mountSparks(root) {
    root.querySelectorAll('canvas.spark').forEach(cv => {
      const v = JSON.parse(cv.dataset.v);
      live.push(new Chart(cv, {
        type: 'line', data: { labels: v.map((_, i) => i), datasets: [{ data: v, borderColor: cv.dataset.c, borderWidth: 1.8, pointRadius: 0, tension: .3 }] },
        options: { responsive: false, animation: false, events: [], plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
      }));
    });
  }
  function clear() { live.forEach(c => { try { c.destroy(); } catch (e) { } }); live = []; }
  return { line, spark, mountSparks, fmt, clear, dlabel };
})();
