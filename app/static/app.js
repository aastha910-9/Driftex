/* DRIFTEX dashboard - views are switched by URL hash (#overview, #product/123 ...) */
const $ = (s, r = document) => r.querySelector(s);
const content = $('#content');
const fmt = Charts.fmt, nf = v => (v == null ? '–' : Math.round(v).toLocaleString());
const cache = {};
const api = async (p, keep) => { if (keep && cache[p]) return cache[p]; const r = await (await fetch(p)).json(); if (keep) cache[p] = r; return r; };
let META = null, liveTimer = null, STATE = { product: null, ptab: 'trend', range: 60, exp: { page: 1, sort: 'interest_28d', dir: 'desc', q: '', category: 'all', trend: 'all', pred: 'all', hide_low: '1' } };

const COL = { blue: '#2f6fed', green: '#14915b', red: '#d1343c', amber: '#d98a0b', navy: '#12284c', gray: '#8a94a9', purple: '#7a52d1' };
const delta = (v, o = {}) => { if (v == null) return ''; const good = o.invert ? v < 0 : v > 0; const cls = Math.abs(v) < 0.5 ? 'flat' : good ? 'up' : 'down'; const ar = v > 0.5 ? '▲' : v < -0.5 ? '▼' : '■'; return `<span class="${cls}">${ar} ${Math.abs(v).toFixed(1)}${o.unit === 'pp' ? ' pp' : '%'}</span>`; };
const trendBadge = t => `<span class="badge ${t === 'Rising' ? 'b-up' : t === 'Declining' ? 'b-down' : t === 'Low volume' ? 'b-warn' : 'b-flat'}">${t}</span>`;
const predBadge = (p, c) => `<span class="badge ${p === 'Increasing' ? 'b-up' : p === 'Decreasing' ? 'b-down' : 'b-flat'}">${p === 'Increasing' ? '▲' : p === 'Decreasing' ? '▼' : '■'} ${p}</span>${c != null ? ` <span class="muted" style="color:var(--muted);font-size:12px">${Math.round(c * 100)}%</span>` : ''}`;
const go = h => { location.hash = h; };
const skuLabel = s => `Product ${s}`;
const setHead = (t, s) => { $('#title').textContent = t; $('#subtitle').textContent = s || ''; };
const loading = () => content.innerHTML = '<div class="spin">Loading…</div>';
const chips = (id, items, active) => `<div class="chips" id="${id}">${items.map(i => `<span class="chip ${active.includes(i.k) ? 'on' : ''}" data-k="${i.k}">${i.c ? `<span class="dot" style="background:${i.c}"></span>` : ''}${i.t}</span>`).join('')}</div>`;

/* ------------------------------------------------------------ router */
const routes = { overview: vOverview, live: vLive, products: vProducts, product: vProduct, categories: vCategories, alerts: vAlerts, model: vModel };
async function route() {
  clearInterval(liveTimer); Charts.clear(); $('#tip').style.opacity = 0;
  const [v, arg] = (location.hash.slice(1) || 'overview').split('/');
  const name = routes[v] ? v : 'overview';
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.v === name));
  loading(); window.scrollTo(0, 0);
  try { await routes[name](arg); } catch (e) { content.innerHTML = `<div class="card">Could not load data: ${e.message}</div>`; console.error(e); }
}
window.addEventListener('hashchange', route);
$('#jump').addEventListener('submit', e => { e.preventDefault(); const v = $('#jumpInput').value.trim(); if (v) go('product/' + v); });

/* ------------------------------------------------------------ overview */
async function vOverview() {
  const [s, m] = [await api('/api/summary?n=120'), META];
  setHead('Executive Overview', 'Company-wide customer behaviour. Last 7 days compared with the previous 7 days.');
  const K = s.kpi;
  const cards = [['Page visits', K.visits], ['Searches', K.searches], ['Add to cart', K.carts], ['Cart removals', K.removes, 1], ['Purchases', K.buys], ['Cart → purchase', K.conversion]];
  const tc = s.trend_counts, tt = (tc.Rising || 0) + (tc.Stable || 0) + (tc.Declining || 0) || 1;
  content.innerHTML = `
  <div class="grid g6">${cards.map(([l, k, inv]) => `<div class="card kpi"><div class="l">${l}</div><div class="v mono">${k.unit === 'pp' ? k.value + '%' : nf(k.value)}</div><div class="d">${delta(k.change, { invert: inv, unit: k.unit })} <span class="flat">vs prev. 7 days</span></div></div>`).join('')}</div>
  <div class="grid g21" style="margin-top:18px">
    <div class="card"><div class="card-h"><div><h3>Company activity trend</h3><div class="sub">Daily events across the whole website</div></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">${chips('ov-m', [{ k: 'visits', t: 'Page visits', c: COL.blue }, { k: 'searches', t: 'Searches', c: COL.purple }, { k: 'carts', t: 'Add to cart', c: COL.amber }, { k: 'buys', t: 'Purchases', c: COL.green }], ['visits', 'buys'])}
      ${chips('ov-r', [{ k: 30, t: '30D' }, { k: 60, t: '60D' }, { k: 120, t: 'All' }], [60])}</div></div>
      <div id="ov-chart"></div></div>
    <div class="card funnel"><h3>Customer funnel · last 7 days</h3><div class="sub">From visit to purchase</div>
      ${[['Page visits', s.funnel.visits, COL.blue], ['Added to cart', s.funnel.carts, COL.amber], ['Purchased', s.funnel.buys, COL.green]].map(([l, v, c]) => `<div class="f"><div class="top"><span>${l}</span><b class="mono">${nf(v)}</b></div><div class="bar"><span style="width:${Math.max(4, v / s.funnel.visits * 100)}%;background:${c}"></span></div></div>`).join('')}
      <div class="note" style="margin-top:16px">${(s.funnel.carts / s.funnel.visits * 100).toFixed(1)}% of visits end in an add-to-cart; ${(s.funnel.buys / s.funnel.carts * 100).toFixed(1)}% of carts convert to purchases.</div></div>
  </div>
  <div class="grid g3" style="margin-top:18px">
    <div class="card"><h3>Product portfolio health</h3><div class="sub">${tt} active products · current 7-day trend</div>
      <div class="bar" style="height:16px"><span style="width:${(tc.Rising || 0) / tt * 100}%;background:${COL.green}"></span><span style="width:${(tc.Stable || 0) / tt * 100}%;background:#c9d1e0"></span><span style="width:${(tc.Declining || 0) / tt * 100}%;background:${COL.red}"></span></div>
      <div class="legend"><span><i style="background:${COL.green}"></i>Rising ${tc.Rising || 0}</span><span><i style="background:#c9d1e0"></i>Stable ${tc.Stable || 0}</span><span><i style="background:${COL.red}"></i>Declining ${tc.Declining || 0}</span></div>
      <div class="sub" style="margin:18px 0 8px">Model outlook for the next 7 days</div>
      ${['Increasing', 'Stable', 'Decreasing'].map(k => `<div class="row"><div class="k">${k}</div><div class="bar"><span style="width:${(s.pred_counts[k] || 0) / tt * 100}%;background:${k === 'Increasing' ? COL.green : k === 'Decreasing' ? COL.red : '#aab3c5'}"></span></div><div class="p mono">${s.pred_counts[k] || 0}</div></div>`).join('')}</div>
    <div class="card"><h3>Fastest rising products</h3><div class="sub">Interest change · last 7 days</div>${moverList(s.top_rising)}</div>
    <div class="card"><h3>Fastest declining products</h3><div class="sub">Interest change · last 7 days</div>${moverList(s.top_declining)}</div>
  </div>`;
  let sel = ['visits', 'buys'], rng = 60;
  const colors = { visits: COL.blue, searches: COL.purple, carts: COL.amber, buys: COL.green }, names = { visits: 'Page visits', searches: 'Searches', carts: 'Add to cart', buys: 'Purchases' };
  const draw = () => { const rows = s.series.slice(-rng); $('#ov-chart').innerHTML = ''; Charts.clear(); Charts.line($('#ov-chart'), { height: 310, labels: rows.map(r => r.date), series: sel.map(k => ({ name: names[k], color: colors[k], data: rows.map(r => r[k]), area: sel.length === 1 })) }); };
  bindChips('#ov-m', k => { sel = sel.includes(k) ? sel.filter(x => x !== k) : [...sel, k]; if (!sel.length) sel = [k]; return sel; }, draw);
  bindChips('#ov-r', k => { rng = +k; return [rng]; }, draw);
  bindLinks(); draw();
}
function moverList(rows) {
  if (!rows.length) return '<div class="sub">No products meet the threshold.</div>';
  return rows.map(r => `<div class="list-item" data-go="product/${r.sku}"><div><div class="t">${skuLabel(r.sku)}</div><div class="m">Category ${r.category} · ${nf(r.interest_7d)} interest</div></div><div style="text-align:right"><b>${delta(r.change_7d)}</b><div class="m">Next 7d: ${r.pred_label}</div></div></div>`).join('');
}
function bindChips(sel, on, cb) {
  const root = $(sel);
  root.addEventListener('click', e => { const c = e.target.closest('.chip'); if (!c) return; const act = on(c.dataset.k).map(String); root.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', act.includes(x.dataset.k))); cb(); });
}
function bindLinks() { content.querySelectorAll('[data-go]').forEach(e => e.addEventListener('click', () => go(e.dataset.go))); }

/* ------------------------------------------------------------ live monitor */
async function vLive() {
  const L = await api('/api/live');
  setHead('Live Monitor', 'Streams the event log day by day, exactly as a production system would receive it.');
  content.innerHTML = `
  <div class="note" style="margin-bottom:16px">Replay mode: the last ${L.dates.length} days of the dataset are streamed one day at a time. In production the same dashboard would be fed by the company's live event stream.</div>
  <div class="card hdr-card" style="margin-bottom:18px"><div><div class="big"><span class="pulse" id="pl"></span><span id="ldate">—</span></div><div class="meta" id="lprog"></div></div>
    <div class="pill-row"><button id="lplay">❚❚ Pause</button><button class="ghost" id="lrestart">↺ Restart</button>${chips('lspeed', [{ k: 1, t: '1×' }, { k: 2, t: '2×' }, { k: 4, t: '4×' }], [1])}</div></div>
  <div class="grid g4" id="ltiles"></div>
  <div class="grid g2" style="margin-top:18px"><div class="card"><h3>Page visits</h3><div class="sub">Company-wide, live</div><div id="lc1"></div></div><div class="card"><h3>Add to cart &amp; purchases</h3><div class="sub">Company-wide, live</div><div id="lc2"></div></div></div>
  <div class="grid g2" style="margin-top:18px"><div class="card"><h3 class="up">▲ Products gaining interest</h3><div class="sub">Today vs. their trailing 7-day average</div><div class="feed" id="lup"></div></div><div class="card"><h3 class="down">▼ Products losing interest</h3><div class="sub">Today vs. their trailing 7-day average</div><div class="feed" id="ldn"></div></div></div>`;
  let i = 0, speed = 1, playing = true, hist = [], busy = false;
  const tile = (l, k, inv) => { const c = hist[hist.length - 1], p = hist[hist.length - 2]; const ch = p ? (c[k] - p[k]) / p[k] * 100 : null; return `<div class="card kpi"><div class="l">${l}</div><div class="v mono">${nf(c[k])}</div><div class="d">${ch == null ? '<span class="flat">first day</span>' : delta(ch, { invert: inv }) + ' <span class="flat">vs previous day</span>'}</div></div>`; };
  const feedHtml = (r, up, d) => `<div class="ev" data-go="product/${r.sku}"><div style="flex:1"><div class="t" style="font-weight:600;color:var(--navy)">${skuLabel(r.sku)} <span class="muted" style="color:var(--muted);font-weight:400">· cat ${r.category}</span></div><div class="m" style="font-size:12px;color:var(--muted)">${Charts.dlabel(d)} · ${nf(r.now)} vs avg ${nf(r.baseline)}</div></div><b class="${up ? 'up' : 'down'}">${up ? '▲' : '▼'} ${Math.abs(r.change)}%</b></div>`;
  const render = () => {
    $('#ltiles').innerHTML = tile('Page visits', 'visits') + tile('Add to cart', 'carts') + tile('Cart removals', 'removes', 1) + tile('Purchases', 'buys');
    const lab = hist.map(h => h.date);
    Charts.clear();
    Charts.line($('#lc1'), { height: 230, labels: lab, series: [{ name: 'Page visits', color: COL.blue, data: hist.map(h => h.visits), area: 1 }] });
    Charts.line($('#lc2'), { height: 230, labels: lab, series: [{ name: 'Add to cart', color: COL.amber, data: hist.map(h => h.carts) }, { name: 'Purchases', color: COL.green, data: hist.map(h => h.buys) }] });
  };
  const tick = async () => {
    if (busy || !playing) return; busy = true;
    if (i >= L.dates.length) { playing = false; $('#lplay').textContent = '▶ Play'; $('#pl').classList.add('off'); busy = false; return; }
    const d = L.dates[i], r = await api('/api/live/day?date=' + d);
    hist.push({ date: d, ...r.company }); i++;
    $('#ldate').textContent = new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    $('#lprog').textContent = `Day ${i} of ${L.dates.length}`;
    render();
    $('#lup').insertAdjacentHTML('afterbegin', r.up.map(x => feedHtml(x, 1, d)).join('')); $('#ldn').insertAdjacentHTML('afterbegin', r.down.map(x => feedHtml(x, 0, d)).join(''));
    ['#lup', '#ldn'].forEach(s => { const f = $(s); while (f.children.length > 40) f.lastChild.remove(); });
    content.querySelectorAll('.ev:not([data-b])').forEach(e => { e.dataset.b = 1; e.addEventListener('click', () => go(e.dataset.go)); });
    busy = false;
  };
  const start = () => { clearInterval(liveTimer); liveTimer = setInterval(tick, 1500 / speed); };
  $('#lplay').onclick = () => { playing = !playing; $('#lplay').textContent = playing ? '❚❚ Pause' : '▶ Play'; $('#pl').classList.toggle('off', !playing); if (playing && i >= L.dates.length) { i = 0; hist = []; $('#lup').innerHTML = $('#ldn').innerHTML = ''; } };
  $('#lrestart').onclick = () => { i = 0; hist = []; $('#lup').innerHTML = $('#ldn').innerHTML = ''; playing = true; $('#lplay').textContent = '❚❚ Pause'; $('#pl').classList.remove('off'); tick(); };
  bindChips('#lspeed', k => { speed = +k; start(); return [k]; }, () => { });
  start(); tick();
}

/* ------------------------------------------------------------ product explorer */
async function vProducts() {
  setHead('Product Explorer', 'Every product with its current trend, forecast and model prediction. Click a row to analyse it.');
  const E = STATE.exp;
  content.innerHTML = `<div class="card">
    <div class="filters"><input id="fq" placeholder="Search product ID" value="${E.q}" style="width:170px">
      <select id="fc"><option value="all">All categories</option>${META.categories.map(c => `<option value="${c}" ${E.category == c ? 'selected' : ''}>Category ${c}</option>`).join('')}</select>
      <select id="ft">${['all', 'Rising', 'Stable', 'Declining'].map(v => `<option value="${v}" ${E.trend === v ? 'selected' : ''}>${v === 'all' ? 'Current trend: all' : v}</option>`).join('')}</select>
      <select id="fp">${['all', 'Increasing', 'Stable', 'Decreasing'].map(v => `<option value="${v}" ${E.pred === v ? 'selected' : ''}>${v === 'all' ? 'Predicted next 7d: all' : 'Predicted: ' + v}</option>`).join('')}</select>
      <label style="color:var(--muted)"><input type="checkbox" id="fl" ${E.hide_low === '1' ? 'checked' : ''}> Hide low-volume products</label></div>
    <div class="tw" id="ptable"></div></div>`;
  const load = async () => {
    const qs = new URLSearchParams({ ...E, size: 15 }); const r = await api('/api/products?' + qs);
    const th = (k, l, n) => `<th class="s ${n ? 'n' : ''}" data-s="${k}">${l}${E.sort === k ? (E.dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>`;
    $('#ptable').innerHTML = `<table><thead><tr>${th('sku', 'Product')}${th('category', 'Category')}${th('interest_7d', 'Interest 7d', 1)}${th('change_7d', 'Δ 7 days', 1)}${th('change_28d', 'Δ 28 days', 1)}${th('conversion_28d', 'Conversion', 1)}<th>Current trend</th>${th('confidence', 'Next 7 days (model)')}${th('fc_change_pct', 'Forecast Δ', 1)}</tr></thead><tbody>
      ${r.rows.map(p => `<tr class="link" data-go="product/${p.sku}"><td><b>${skuLabel(p.sku)}</b></td><td>${p.category}</td><td class="n mono">${nf(p.interest_7d)}</td><td class="n">${delta(p.change_7d)}</td><td class="n">${delta(p.change_28d)}</td><td class="n mono">${p.conversion_28d}%</td><td>${trendBadge(p.trend)}</td><td>${predBadge(p.pred_label, p.confidence)}</td><td class="n">${delta(p.fc_change_pct)}</td></tr>`).join('') || '<tr><td colspan="9" style="padding:30px;text-align:center;color:var(--muted)">No products match these filters.</td></tr>'}</tbody></table>
      <div class="pager"><span>${r.total.toLocaleString()} products · page ${r.page} of ${Math.max(1, Math.ceil(r.total / r.size))}</span><span><button class="ghost" id="pp" ${r.page <= 1 ? 'disabled' : ''}>← Previous</button> <button class="ghost" id="pn" ${r.page * r.size >= r.total ? 'disabled' : ''}>Next →</button></span></div>`;
    bindLinks();
    $('#ptable').querySelectorAll('th.s').forEach(h => h.onclick = () => { const k = h.dataset.s; E.dir = E.sort === k && E.dir === 'desc' ? 'asc' : 'desc'; E.sort = k; E.page = 1; load(); });
    $('#pp').onclick = () => { E.page--; load(); }; $('#pn').onclick = () => { E.page++; load(); };
  };
  const on = (id, key, f = v => v) => $(id).addEventListener('change', e => { E[key] = f(e.target.type === 'checkbox' ? (e.target.checked ? '1' : '0') : e.target.value); E.page = 1; load(); });
  on('#fc', 'category'); on('#ft', 'trend'); on('#fp', 'pred'); on('#fl', 'hide_low');
  let t; $('#fq').addEventListener('input', e => { clearTimeout(t); t = setTimeout(() => { E.q = e.target.value.trim(); E.page = 1; load(); }, 250); });
  load();
}

/* ------------------------------------------------------------ product analysis */
async function vProduct(arg) {
  const sku = arg || STATE.product;
  if (!sku) {
    setHead('Product Analysis', 'Select a product to analyse its behaviour, forecast and risk signals.');
    const top = await api('/api/products?size=12&hide_low=1&sort=interest_28d', 1);
    content.innerHTML = `<div class="card"><h3>Choose a product</h3><div class="sub">Type a product ID in the box at the top right, or pick one of the most active products.</div><div class="grid g3">${top.rows.map(p => `<div class="list-item card" style="box-shadow:none" data-go="product/${p.sku}"><div><div class="t">${skuLabel(p.sku)}</div><div class="m">Category ${p.category} · ${nf(p.interest_28d)} interest (28d)</div></div>${trendBadge(p.trend)}</div>`).join('')}</div></div>`;
    return bindLinks();
  }
  STATE.product = sku;
  const d = await api(`/api/product/${sku}?days=120`);
  if (d.error) { setHead('Product Analysis'); content.innerHTML = `<div class="card"><h3>Product ${sku} not found</h3><div class="sub">Only the most active products are modelled (top ${META.n_products.toLocaleString()}). Try another ID from the Product Explorer.</div></div>`; return; }
  const st = d.stats;
  setHead(skuLabel(sku), `Category ${st.category} · Price tier ${st.price} · Rank #${st.rank} of ${META.n_products} by 28-day interest · #${d.category_rank.rank} of ${d.category_rank.of} in its category`);
  const sum = (a, k) => a.reduce((s, r) => s + r[k], 0), L7 = d.daily.slice(-7), P7 = d.daily.slice(-14, -7);
  const sig = (k, inv) => ({ cur: sum(L7, k), prev: sum(P7, k), ch: sum(P7, k) ? (sum(L7, k) - sum(P7, k)) / sum(P7, k) * 100 : 0, inv });
  const hasV = META.has_product_views;
  content.innerHTML = `
  <div class="card hdr-card" style="margin-bottom:18px"><div><div class="pill-row">${trendBadge(st.trend)} ${predBadge(st.pred_label, st.confidence)} ${Math.abs(st.z_latest) >= 3 ? `<span class="badge b-warn">${st.z_latest > 0 ? 'Spike' : 'Drop'} today (z ${st.z_latest > 0 ? '+' : ''}${st.z_latest})</span>` : ''}</div>
    <div class="meta" style="margin-top:10px">Interest index (last 7 days): <b class="mono">${nf(st.interest_7d)}</b> &nbsp; ${delta(st.change_7d)} vs previous 7 days &nbsp;·&nbsp; 28-day change ${delta(st.change_28d)}</div></div>
    <div class="pill-row"><button class="ghost" id="pprev">← Previous</button><button class="ghost" id="pnext">Next →</button></div></div>
  <div class="tabs"><a data-t="trend">Trend &amp; Behaviour</a><a data-t="forecast">Forecast &amp; Prediction</a><a data-t="signals">Behaviour Signals</a></div>
  <div id="pbody"></div>`;
  $('#pprev').onclick = () => go('product/' + (+sku - 1)); $('#pnext').onclick = () => go('product/' + (+sku + 1));
  const tabs = {
    trend() {
      const kp = [['Add to cart · 7d', sig('carts')], ['Purchases · 7d', sig('buys')], ['Cart removals · 7d', sig('removes', 1)], [hasV ? 'Page views · 7d' : 'Page views', hasV ? sig('views') : null], ['Conversion · 28d', { cur: st.conversion_28d + '%', ch: null }]];
      $('#pbody').innerHTML = `<div class="grid g6" style="grid-template-columns:repeat(5,1fr)">${kp.map(([l, s]) => `<div class="card kpi"><div class="l">${l}</div><div class="v mono">${s ? (typeof s.cur === 'number' ? nf(s.cur) : s.cur) : 'n/a'}</div><div class="d">${s ? (s.ch == null ? '<span class="flat">cart → purchase</span>' : delta(s.ch, { invert: s.inv }) + ' <span class="flat">vs prev. 7d</span>') : '<span class="flat">not in dataset</span>'}</div></div>`).join('')}</div>
      <div class="card" style="margin-top:18px"><div class="card-h"><div><h3>Customer behaviour over time</h3><div class="sub">Daily activity for this product. Dotted line = EWMA smoothed interest.</div></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">${chips('pm', [{ k: 'interest', t: 'Interest index', c: COL.blue }, { k: 'carts', t: 'Add to cart', c: COL.amber }, { k: 'buys', t: 'Purchases', c: COL.green }, { k: 'removes', t: 'Removals', c: COL.red }], ['interest', 'carts'])}${chips('pr', [{ k: 30, t: '30D' }, { k: 60, t: '60D' }, { k: 120, t: '120D' }], [STATE.range])}</div></div><div id="pc"></div></div>
      ${hasV ? '' : '<div class="note warn" style="margin-top:18px">Product-level page views are not available: in the Synerise <b>page_visit</b> file visits are stored per page URL, not per product ID. Interest is therefore built from add-to-cart, purchase and removal events. If your file has a product column, set <code>PAGE_VISIT_SKU_COL</code> in config.py and views will be included automatically.</div>'}`;
      let sel = ['interest', 'carts'], names = { interest: 'Interest index', carts: 'Add to cart', buys: 'Purchases', removes: 'Removals' }, cols = { interest: COL.blue, carts: COL.amber, buys: COL.green, removes: COL.red };
      const draw = () => { const r = d.daily.slice(-STATE.range); Charts.clear(); const s = sel.map(k => ({ name: names[k], color: cols[k], data: r.map(x => x[k]), area: sel.length === 1 })); if (sel.includes('interest')) s.push({ name: 'EWMA (7d)', color: COL.navy, data: r.map(x => x.ewma), dash: 1, width: 1.8 }); Charts.line($('#pc'), { height: 340, labels: r.map(x => x.date), series: s }); };
      bindChips('#pm', k => { sel = sel.includes(k) ? sel.filter(x => x !== k) : [...sel, k]; if (!sel.length) sel = [k]; return sel; }, draw);
      bindChips('#pr', k => { STATE.range = +k; return [k]; }, draw); draw();
    },
    forecast() {
      const wk = d.weekly.slice(-14), fc = d.forecast, nW = wk.length, labels = wk.map(w => w.week_start).concat(fc.map(f => f.week_start));
      const act = wk.map(w => w.interest).concat(fc.map(() => null)), pr = wk.map((w, i) => i === nW - 1 ? w.interest : null).concat(fc.map(f => f.mean));
      const lo = wk.map((w, i) => i === nW - 1 ? w.interest : null).concat(fc.map(f => f.lo)), hi = wk.map((w, i) => i === nW - 1 ? w.interest : null).concat(fc.map(f => f.hi));
      const pb = (l, p, c) => `<div class="row"><div class="k" style="width:90px">${l}</div><div class="bar" style="height:12px"><span style="width:${p * 100}%;background:${c}"></span></div><div class="p mono">${(p * 100).toFixed(0)}%</div></div>`;
      $('#pbody').innerHTML = `<div class="grid g21"><div class="card"><h3>Weekly interest forecast · next ${fc.length} weeks</h3><div class="sub">Solid = actual weekly interest · dashed = forecast · shaded = 80% range</div><div id="fcc"></div></div>
        <div class="card"><h3>Model prediction · next 7 days</h3><div class="sub">${META.best_model}, probability of each outcome</div>${pb('Increase', st.p_up, COL.green)}${pb('Stable', st.p_stable, '#aab3c5')}${pb('Decrease', st.p_down, COL.red)}
        <div style="margin:16px 0 4px">${predBadge(st.pred_label, st.confidence)}</div><div class="sub">An <i>increase</i> or <i>decrease</i> means more than ±20% versus the average of the last 4 weeks.</div>
        ${st.low_volume ? '<div class="note warn">Low-volume product: predictions are less reliable.</div>' : ''}</div></div>
        <div class="grid g2" style="margin-top:18px"><div class="card"><h3>Forecast table</h3><div class="sub">Expected weekly interest index</div><table><thead><tr><th>Week starting</th><th class="n">Forecast</th><th class="n">Low</th><th class="n">High</th></tr></thead><tbody>${fc.map(f => `<tr><td>${Charts.dlabel(f.week_start)}</td><td class="n mono"><b>${nf(f.mean)}</b></td><td class="n mono">${nf(f.lo)}</td><td class="n mono">${nf(f.hi)}</td></tr>`).join('')}</tbody></table></div>
        <div class="card"><h3>Business insights</h3><div class="sub">Generated automatically from the signals above</div>${d.insights.map(i => `<div class="insight">${i}</div>`).join('')}</div></div>`;
      Charts.line($('#fcc'), { height: 320, labels, fcFrom: nW, band: { lo, hi }, markers: [{ i: nW - 1, text: 'today' }], series: [{ name: 'Actual', color: COL.blue, data: act, area: 1 }, { name: 'Forecast', color: COL.amber, data: pr, dash: 1 }] });
    },
    signals() {
      const S = [['Page views', hasV ? sig('views') : null, 'Attention on the product'], ['Add to cart', sig('carts'), 'Purchase intention'], ['Cart removals', sig('removes', 1), 'Hesitation / interest drop'], ['Purchases', sig('buys'), 'Actual demand']];
      const cv = x => x.carts ? x.buys / x.carts * 100 : 0; const c1 = cv({ carts: sum(L7, 'carts'), buys: sum(L7, 'buys') }), c0 = cv({ carts: sum(P7, 'carts'), buys: sum(P7, 'buys') });
      const rd = (s, inv) => { if (!s) return '<span class="badge b-flat">n/a</span>'; const ch = inv ? -s.ch : s.ch; return ch > 10 ? '<span class="badge b-up">Strengthening</span>' : ch < -10 ? '<span class="badge b-down">Weakening</span>' : '<span class="badge b-flat">Steady</span>'; };
      const rows = S.map(([n, s, m]) => `<tr><td><b>${n}</b></td><td class="n mono">${s ? nf(s.cur) : '–'}</td><td class="n mono">${s ? nf(s.prev) : '–'}</td><td class="n">${s ? delta(s.ch, { invert: s.inv }) : '–'}</td><td>${m}</td><td>${rd(s, s && s.inv)}</td></tr>`).join('') +
        `<tr><td><b>Conversion rate</b></td><td class="n mono">${c1.toFixed(1)}%</td><td class="n mono">${c0.toFixed(1)}%</td><td class="n">${delta(c1 - c0, { unit: 'pp' })}</td><td>Purchase effectiveness</td><td>${rd({ ch: c1 - c0 })}</td></tr>`;
      $('#pbody').innerHTML = `<div class="card"><h3>Behaviour signals · last 7 days vs previous 7 days</h3><div class="sub">How each behaviour is changing and what it indicates for this product</div><div class="tw"><table><thead><tr><th>Behaviour</th><th class="n">Last 7 days</th><th class="n">Previous 7 days</th><th class="n">Change</th><th>What it indicates</th><th>Reading</th></tr></thead><tbody>${rows}</tbody></table></div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><h3>Statistical drift check</h3><div class="sub">Daily interest vs its own 28-day baseline (Z-score)</div><div id="zc"></div></div>
      <div class="card"><h3>Weekly interest</h3><div class="sub">Last 14 weeks</div><div id="wc"></div></div></div>`;
      const r = d.daily.slice(-60); Charts.line($('#zc'), { height: 250, labels: r.map(x => x.date), series: [{ name: 'Z-score', color: COL.purple, data: r.map(x => Math.max(-6, Math.min(6, x.z))), area: 1 }] });
      const w = d.weekly.slice(-14); Charts.line($('#wc'), { height: 250, labels: w.map(x => x.week_start), series: [{ name: 'Weekly interest', color: COL.blue, data: w.map(x => x.interest), area: 1 }] });
    }
  };
  const show = t => { STATE.ptab = t; document.querySelectorAll('.tabs a').forEach(a => a.classList.toggle('on', a.dataset.t === t)); Charts.clear(); tabs[t](); };
  document.querySelectorAll('.tabs a').forEach(a => a.onclick = () => show(a.dataset.t)); show(STATE.ptab);
}

/* ------------------------------------------------------------ categories */
async function vCategories() {
  setHead('Category Insights', 'Interest aggregated by product category. Click a category to list its products.');
  const r = await api('/api/categories');
  content.innerHTML = `<div class="card"><div class="tw"><table><thead><tr><th>Category</th><th class="n">Products</th><th class="n">Interest 7d</th><th class="n">Δ 7 days</th><th class="n">Δ 28 days</th><th>Last 8 weeks</th><th class="n">Rising</th><th class="n">Declining</th></tr></thead><tbody>
  ${r.rows.map(c => `<tr class="link" data-cat="${c.category}"><td><b>Category ${c.category}</b></td><td class="n">${c.products}</td><td class="n mono">${nf(c.interest_7d)}</td><td class="n">${delta(c.change_7d)}</td><td class="n">${delta(c.change_28d)}</td><td>${Charts.spark(c.spark, c.change_28d >= 0 ? COL.green : COL.red)}</td><td class="n up">${c.rising}</td><td class="n down">${c.declining}</td></tr>`).join('')}</tbody></table></div></div>`;
  Charts.mountSparks(content);
  content.querySelectorAll('[data-cat]').forEach(e => e.onclick = () => { STATE.exp.category = e.dataset.cat; STATE.exp.page = 1; go('products'); });
}

/* ------------------------------------------------------------ alerts */
async function vAlerts() {
  setHead('Alerts & Anomalies', 'Products whose daily interest deviates sharply from their own recent baseline (EWMA + Z-score).');
  let kind = 'all';
  content.innerHTML = `<div class="grid g3"><div class="card kpi"><div class="l">Spikes (21 days)</div><div class="v up" id="as">–</div></div><div class="card kpi"><div class="l">Drops (21 days)</div><div class="v down" id="ad">–</div></div><div class="card kpi"><div class="l">Detection rule</div><div class="v" style="font-size:16px;margin-top:12px">|Z| ≥ threshold vs 28-day baseline</div></div></div>
  <div class="card" style="margin-top:18px"><div class="card-h"><div><h3>Latest alerts</h3></div>${chips('ak', [{ k: 'all', t: 'All' }, { k: 'Spike', t: 'Spikes' }, { k: 'Drop', t: 'Drops' }], ['all'])}</div><div class="tw" id="atab"></div></div>`;
  const load = async () => {
    const r = await api('/api/alerts?kind=' + kind); $('#as').textContent = r.total_spikes; $('#ad').textContent = r.total_drops;
    $('#atab').innerHTML = `<table><thead><tr><th>Date</th><th>Product</th><th>Category</th><th>Alert</th><th class="n">Interest that day</th><th class="n">Normal level</th><th class="n">Z-score</th></tr></thead><tbody>${r.rows.map(a => `<tr class="link" data-go="product/${a.sku}"><td>${Charts.dlabel(a.date)}</td><td><b>${skuLabel(a.sku)}</b></td><td>${a.category}</td><td><span class="badge ${a.direction === 'Spike' ? 'b-up' : 'b-down'}">${a.direction === 'Spike' ? '▲ Spike' : '▼ Drop'}</span></td><td class="n mono">${nf(a.interest)}</td><td class="n mono">${nf(a.baseline)}</td><td class="n mono">${a.z > 0 ? '+' : ''}${a.z}</td></tr>`).join('') || '<tr><td colspan="7" style="padding:30px;text-align:center;color:var(--muted)">No alerts of this type.</td></tr>'}</tbody></table>`; bindLinks();
  };
  bindChips('#ak', k => { kind = k; return [k]; }, load); load();
}

/* ------------------------------------------------------------ model & methodology */
async function vModel() {
  const r = await api('/api/model'), ds = r.dataset, best = r.models[r.best_model];
  setHead('Model & Methodology', 'How the predictions are produced, how accurate they are, and what data they use.');
  content.innerHTML = `<div class="tabs"><a data-t="perf">Performance</a><a data-t="method">Methodology</a><a data-t="data">Data & Pipeline</a></div><div id="mb"></div>`;
  const pct = v => (v * 100).toFixed(1) + '%';
  const tabs = {
    perf() {
      const names = Object.keys(r.models), mx = 1;
      const cm = best.confusion, cls = ['Decreasing', 'Stable', 'Increasing'], rs = cm.map(x => x.reduce((a, b) => a + b, 0));
      $('#mb').innerHTML = `<div class="grid g4"><div class="card kpi"><div class="l">Selected model</div><div class="v" style="font-size:20px;margin-top:12px">${r.best_model}</div></div><div class="card kpi"><div class="l">Accuracy (hold-out weeks)</div><div class="v">${pct(best.accuracy)}</div></div><div class="card kpi"><div class="l">Macro F1</div><div class="v">${pct(best.macro_f1)}</div></div><div class="card kpi"><div class="l">Naive baseline accuracy</div><div class="v">${pct(r.baseline.accuracy)}</div><div class="d flat">"last week's direction continues"</div></div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><h3>Model comparison</h3><div class="sub">Macro-F1 on unseen, later weeks</div>${names.map(n => `<div class="row"><div class="k" style="width:130px">${n}</div><div class="bar" style="height:14px"><span style="width:${r.models[n].macro_f1 / mx * 100}%;background:${n === r.best_model ? COL.blue : '#b4c3e0'}"></span></div><div class="p mono">${pct(r.models[n].macro_f1)}</div></div>`).join('')}<div class="row"><div class="k" style="width:130px">Naive baseline</div><div class="bar" style="height:14px"><span style="width:${r.baseline.macro_f1 * 100}%;background:#d5dae5"></span></div><div class="p mono">${pct(r.baseline.macro_f1)}</div></div></div>
      <div class="card"><h3>What drives the prediction</h3><div class="sub">Random Forest feature importance</div>${r.feature_importance.slice(0, 7).map(f => `<div class="row"><div class="k" style="width:150px;font-size:12.5px">${f.feature}</div><div class="bar"><span style="width:${f.importance / r.feature_importance[0].importance * 100}%;background:${COL.navy}"></span></div><div class="p mono">${(f.importance * 100).toFixed(0)}%</div></div>`).join('')}</div></div>
      <div class="card" style="margin-top:18px"><h3>Confusion matrix · ${r.best_model}</h3><div class="sub">Rows = what actually happened, columns = what the model predicted (share of each row)</div><table class="cm" style="max-width:560px"><thead><tr><th></th>${cls.map(c => `<th>Pred. ${c}</th>`).join('')}</tr></thead><tbody>${cm.map((row, i) => `<tr><th style="text-align:left">Actual ${cls[i]}</th>${row.map((v, j) => { const p = rs[i] ? v / rs[i] : 0; return `<td style="background:rgba(${i === j ? '20,145,91' : '209,52,60'},${(0.08 + p * (i === j ? .55 : .7)).toFixed(2)})">${(p * 100).toFixed(0)}%<div style="font-weight:400;font-size:11px;color:var(--muted)">${v.toLocaleString()}</div></td>`; }).join('')}</tr>`).join('')}</tbody></table></div>`;
    },
    method() {
      $('#mb').innerHTML = `<div class="grid g2"><div class="card"><h3>1 · Interest index</h3><div class="sub">One number per product per day</div><p style="line-height:1.6">Interest = ${ds.weights.views}×page views + ${ds.weights.carts}×add-to-cart + ${ds.weights.buys}×purchases. Cart removals are tracked separately as a hesitation signal. Stronger actions carry more weight.</p></div>
      <div class="card"><h3>2 · Drift detection</h3><div class="sub">Z-score + EWMA</div><p style="line-height:1.6">Each product's daily interest is compared with its own previous 28 days. A Z-score beyond the threshold raises a spike or drop alert; a 7-day EWMA smooths the signal for the charts.</p></div>
      <div class="card"><h3>3 · Prediction target</h3><div class="sub">Will interest rise, fall or stay stable next week?</div><p style="line-height:1.6">Label = next week's interest compared with the average of the last 4 weeks: <b>Increasing</b> (above +${ds.change_threshold * 100}%), <b>Decreasing</b> (below −${ds.change_threshold * 100}%), otherwise <b>Stable</b>.</p></div>
      <div class="card"><h3>4 · No data leakage</h3><div class="sub">Features use only the past</div><p style="line-height:1.6">Features come from weeks up to <i>t</i>; the label comes from week <i>t+1</i>. Training and testing are split by time: models learn from earlier weeks and are scored on later, unseen weeks, with a one-week gap.</p></div>
      <div class="card"><h3>5 · Models</h3><div class="sub">Compared automatically</div><p style="line-height:1.6">Logistic Regression, Random Forest and XGBoost (when installed). The best macro-F1 on the hold-out weeks is selected, then refitted on all labelled history and applied to the latest week.</p></div>
      <div class="card"><h3>6 · Forecast</h3><div class="sub">Next 4 weeks</div><p style="line-height:1.6">Damped-trend exponential smoothing on weekly interest, with an 80% range from historical forecast errors.</p></div></div>
      <div class="card" style="margin-top:18px"><h3>Features used</h3><div class="pill-row" style="margin-top:8px">${ds.features.map(f => `<span class="badge b-blue">${f}</span>`).join('')}</div></div>`;
    },
    data() {
      const lbl = ds.label_distribution_train;
      $('#mb').innerHTML = `<div class="grid g3"><div class="card kpi"><div class="l">Products modelled</div><div class="v">${ds.products_modelled.toLocaleString()}</div></div><div class="card kpi"><div class="l">Period</div><div class="v" style="font-size:17px;margin-top:12px">${ds.date_from} → ${ds.date_to}</div><div class="d flat">${ds.days} days · ${ds.weeks} weeks</div></div><div class="card kpi"><div class="l">Training / test rows</div><div class="v">${ds.train_rows.toLocaleString()} / ${ds.test_rows.toLocaleString()}</div></div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><h3>Pipeline</h3><div class="sub">From raw Synerise files to dashboard</div>
        ${[['add_to_cart · remove_from_cart · product_buy', 'Daily counts per product and per customer'], ['page_visit', 'Company-wide daily traffic' + (ds.has_product_views ? ' and product views' : ' (stored per URL, not per product)')], ['search_query', 'Daily search volume (queries are anonymised vectors)'], ['product_properties', 'Category and price tier per product'], ['Feature engineering → Models → Forecast', 'Weekly panel, leakage-free labels, time-based validation'], ['Dashboard', 'Company view, product view, alerts, live monitor']].map(([a, b], i) => `<div class="insight"><div><b>${a}</b><div class="m" style="color:var(--muted);font-size:12.5px">${b}</div></div></div>`).join('')}</div>
      <div class="card"><h3>Dataset notes</h3><div class="sub">Important for interpreting the results</div><div class="insight">Training weeks: ${ds.train_weeks}</div><div class="insight">Test weeks: ${ds.test_weeks}</div><div class="insight">Training label mix: ${Object.entries(lbl).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(' · ')}</div><div class="insight">Product names and search text are anonymised in Synerise, so products are shown by ID and category.</div><div class="insight">Price changes, stock and promotions are not in the dataset; they can influence interest and are not modelled.</div></div></div>`;
    }
  };
  const show = t => { document.querySelectorAll('.tabs a').forEach(a => a.classList.toggle('on', a.dataset.t === t)); tabs[t](); };
  document.querySelectorAll('.tabs a').forEach(a => a.onclick = () => show(a.dataset.t)); show('perf');
}

/* ------------------------------------------------------------ boot */
(async () => {
  META = await api('/api/meta');
  $('#asof').innerHTML = `<span class="pulse"></span>Data up to ${META.date_to}`;
  route();
})();
