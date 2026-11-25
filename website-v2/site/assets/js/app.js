/* 智农宝 · 农业数据工作台
   单页应用：hash 路由 + 本机数据 + 全部离线可用。
   数据来源：site/data/*.json（由本机比赛工作簿导出，SHA-256 见 source_manifest.json） */
(function () {
  'use strict';

  /* ============================================================
     0. 基础工具
     ============================================================ */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = Chart.esc;
  const fmt = Chart.fmt;
  const isNum = Chart.isNum;

  const view = $('#view');
  const sidebar = $('#sidebar');
  const crumb = $('#crumb');

  const TITLES = {
    '/': '总览', '/data': '数据总览', '/map': '省域分布', '/compare': '区域对比',
    '/crop-data': '作物指标', '/macro': '宏观与劳动力', '/forecast': '趋势预测',
    '/model': '模型与图表', '/datasets': '数据集目录', '/features': '功能与恢复进度',
    '/about': '恢复说明', '/farming-cost': '种植成本测算', '/data-upload': 'CSV 数据导入',
    '/gov-dashboard': '区域工作台',
    '/smart-plan': '种植防亏损', '/predict': '产量与价格预测', '/digital-farm': '数字农田生态',
    '/presentation': '项目与答辩', '/recovery': '数据备份与恢复'
  };

  const METRICS = [
    { id: 'agriShare', label: '第一产业占GDP比重', short: '一产占比', field: '第一产业占GDP比重(%)', unit: '%', digits: 1, agg: 'ratio', note: '第一产业GDP ÷ 总GDP，用合计值计算' },
    { id: 'agriGdp', label: '第一产业GDP', short: '一产GDP', field: '第一产业GDP(亿元)', unit: '亿元', digits: 1, agg: 'sum', note: '省级记录直接求和' },
    { id: 'gdp', label: '地区生产总值', short: '总GDP', field: '总GDP(亿元)', unit: '亿元', digits: 0, agg: 'sum', note: '省级记录直接求和' },
    { id: 'gdpPer', label: '人均GDP', short: '人均GDP', field: '人均GDP(元)', unit: '元', digits: 0, agg: 'perCapita', note: 'GDP合计 ÷ 人口合计' },
    { id: 'income', label: '农村居民人均可支配收入', short: '农村收入', field: '农村居民人均可支配收入(元)', unit: '元', digits: 0, agg: 'mean', note: '省级算术平均，未按人口加权' },
    { id: 'pop', label: '常住人口', short: '人口', field: '常住人口(万人)', unit: '万人', digits: 1, agg: 'sum', note: '省级记录直接求和' },
    { id: 'agriIncome', label: '农村居民人均第一产业收入(估算)', short: '一产收入', field: '农村居民人均第一产业收入估算(元)', unit: '元', digits: 0, agg: 'mean', note: '原工作簿的估算列，非统计口径' }
  ];
  const metricOf = id => METRICS.find(m => m.id === id) || METRICS[0];

  const REGIONS = ['东部', '中部', '西部', '东北'];
  const CROP_IMPUTED_FROM = 2022;

  /* 生成确定性演示序列：从 base*(1-drift) 线性增长到 base，加小幅正弦扰动 */
  function refSeq(base, drift, n, seed) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const t = n <= 1 ? 1 : i / (n - 1);
      const trend = base * (1 - drift) + base * drift * t;
      const wobble = Math.sin(i * 1.7 + seed) * base * 0.03;
      out.push(Math.round((trend + wobble) * 10) / 10);
    }
    return out;
  }

  /* 作物参考数据：单产/价格/成本为演示用参考值，非官方统计口径 */
  const AGRI_REF = {
    note: '作物单产、价格、成本为演示用参考值，非官方统计口径，仅供测算与决策演示。',
    histYears: 10,
    crops: [
      { name: '水稻', yield: 480, price: 2.8, cost: 1450, img: 'crop-rice.jpg', region: '南方主产区', season: '5—10 月', desc: '需水量大，适合水源充足、积温较高的平原或梯田。' },
      { name: '小麦', yield: 390, price: 2.6, cost: 900, img: 'hero-farm.jpg', region: '北方冬麦区', season: '10—6 月', desc: '耐旱耐寒，适合温带平原，需注意春季倒春寒。' },
      { name: '玉米', yield: 550, price: 2.4, cost: 1000, img: 'crop-corn.jpg', region: '东北/黄淮海', season: '4—9 月', desc: '适应性强、产量高，需注意灌浆期水分供给。' },
      { name: '大豆', yield: 160, price: 5.2, cost: 650, img: 'crop-corn.jpg', region: '东北产区', season: '5—10 月', desc: '固氮养地，单产较低，适合轮作与豆制品加工。' },
      { name: '花生', yield: 300, price: 6.5, cost: 1100, img: 'crop-orchard.jpg', region: '黄淮海/长江流域', season: '4—9 月', desc: '经济价值高，需沙壤土与充足光照。' },
      { name: '籽棉', yield: 280, price: 7.0, cost: 1500, img: 'hero-farm.jpg', region: '新疆棉区', season: '4—10 月', desc: '喜光喜温，需注意虫害与后期脱叶采收。' },
      { name: '设施蔬菜', yield: 5200, price: 2.2, cost: 6200, img: 'crop-greenhouse.jpg', region: '城郊设施农业', season: '周年', desc: '投入高、产出高，需控温控湿与精细管理。' },
      { name: '苹果', yield: 2400, price: 4.5, cost: 3600, img: 'crop-orchard.jpg', region: '黄土高原/环渤海', season: '多年生', desc: '多年生果树，前期投入大，盛果期回报稳定。' }
    ]
  };
  AGRI_REF.crops.forEach((c, i) => {
    c.yieldHist = refSeq(c.yield, 0.12, AGRI_REF.histYears, i + 1);
    c.priceHist = refSeq(c.price, 0.15, AGRI_REF.histYears, i + 7);
  });
  const cropOf = name => AGRI_REF.crops.find(c => c.name === name) || AGRI_REF.crops[0];

  /* 数字农田生态模拟数据（本地演示，不代表真实测量） */
  const FARM_SIM = {
    note: '数字农田生态数据为本地模拟演示值，用于展示系统能力，不代表真实田间测量。',
    farm: { name: '南钛示范农场', plots: 24, area: 1560, unit: '亩', cropKinds: 8, devices: 36 },
    weather: { temp: 26.4, humidity: 68, rainfall: 2.4, wind: 3.2, light: 48200, soilTemp: 22.1 },
    soil: { n: 82, p: 45, k: 120, ph: 6.5, organic: 2.8, moisture: 46 },
    growth: { healthy: 72, attention: 21, critical: 7 },
    four: [
      { key: '苗情', icon: 'i-leaf', val: '长势良好', pct: 86, status: 'ok', note: '叶面积指数正常，分蘖均匀' },
      { key: '墒情', icon: 'i-cloud', val: '适宜', pct: 72, status: 'ok', note: '土壤含水率处于适宜区间' },
      { key: '虫情', icon: 'i-info', val: '轻度', pct: 38, status: 'warn', note: '发现少量蚜虫，建议 3 日内防治' },
      { key: '灾情', icon: 'i-shield', val: '无预警', pct: 8, status: 'ok', note: '近期无气象灾害预警' }
    ],
    devices: [
      { name: '田间气象站', type: '气象', online: true },
      { name: '土壤墒情仪 #1', type: '土壤', online: true },
      { name: '土壤墒情仪 #2', type: '土壤', online: true },
      { name: '虫情测报灯', type: '植保', online: true },
      { name: '高清球机 #1', type: '监控', online: true },
      { name: '高清球机 #2', type: '监控', online: false },
      { name: '水肥一体机', type: '设备', online: true },
      { name: '智能灌溉阀 #3', type: '设备', online: false }
    ],
    tasks: [
      { date: '11-03', name: '冬小麦播种', done: true },
      { date: '11-05', name: '灌区补水', done: false },
      { date: '11-08', name: '叶面追肥', done: false },
      { date: '11-12', name: '虫情普查', done: false }
    ]
  };
  /* 24h 气温演示序列（凌晨低、午后高） */
  FARM_SIM.weather24 = Array.from({ length: 24 }, (_, h) => Math.round((20 + 7 * Math.sin(((h - 6) / 24) * Math.PI * 2) + (Math.sin(h * 3.1) * 0.8)) * 10) / 10);
  const imgUrl = file => 'assets/img/' + file;

  const store = {
    get(key, fallback) {
      try { const raw = localStorage.getItem('zn.' + key); return raw == null ? fallback : JSON.parse(raw); }
      catch (e) { return fallback; }
    },
    set(key, value) { try { localStorage.setItem('zn.' + key, JSON.stringify(value)); } catch (e) { /* 无痕模式忽略 */ } }
  };

  /* ============================================================
     1. 数据层
     ============================================================ */
  const app = {
    dashboard: null, crops: null, tableIndex: null, charts: null, sourceManifest: null,
    rows: [], years: [], provinces: [], byYear: new Map(), byProvince: new Map(),
    tables: new Map(), coreOnly: false
  };

  const CORE_FILES = {
    dashboard: 'dashboard.json', crops: 'crops.json', tableIndex: 'table_index.json',
    charts: 'chart_manifest.json', sourceManifest: 'source_manifest.json'
  };

  async function loadData() {
    const core = window.__ZN_CORE__ || {};
    for (const key of Object.keys(CORE_FILES)) {
      let value = null;
      if (location.protocol !== 'file:') {
        try {
          const response = await fetch('data/' + CORE_FILES[key], { cache: 'no-cache' });
          if (response.ok) value = await response.json();
        } catch (e) { /* 退回内嵌数据 */ }
      }
      if (!value) { value = core[key] || null; app.coreOnly = true; }
      if (!value) throw new Error('缺少数据文件 data/' + CORE_FILES[key]);
      app[key] = value;
    }
    buildIndex();
  }

  function buildIndex() {
    app.rows = app.dashboard.panel.rows || [];
    app.years = (app.dashboard.years || []).slice().sort((a, b) => a - b);
    app.provinces = (app.dashboard.provinces || []).slice().sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'));
    app.byYear = new Map();
    app.byProvince = new Map();
    app.rows.forEach(row => {
      const year = row['年份'];
      const province = row['省份'];
      if (!app.byYear.has(year)) app.byYear.set(year, []);
      app.byYear.get(year).push(row);
      if (!app.byProvince.has(province)) app.byProvince.set(province, []);
      app.byProvince.get(province).push(row);
    });
    app.byProvince.forEach(list => list.sort((a, b) => a['年份'] - b['年份']));
  }

  const latestYear = () => app.years[app.years.length - 1];
  const rowsOfYear = year => app.byYear.get(Number(year)) || [];
  const rowsOfProvince = name => app.byProvince.get(name) || [];
  const recordCount = () => app.rows.length;

  /* 地区聚合：按指标性质选择求和 / 比值 / 人均 / 平均 */
  function aggregate(rows, metric) {
    const m = typeof metric === 'string' ? metricOf(metric) : metric;
    const gdp = rows.reduce((s, r) => s + (Number(r['总GDP(亿元)']) || 0), 0);
    const agri = rows.reduce((s, r) => s + (Number(r['第一产业GDP(亿元)']) || 0), 0);
    const pop = rows.reduce((s, r) => s + (Number(r['常住人口(万人)']) || 0), 0);
    if (m.agg === 'sum') return rows.reduce((s, r) => s + (Number(r[m.field]) || 0), 0);
    if (m.agg === 'ratio') return gdp ? (agri / gdp) * 100 : null;
    if (m.agg === 'perCapita') return pop ? (gdp / pop) * 10000 : null;
    const values = rows.map(r => r[m.field]).filter(isNum);
    return values.length ? values.reduce((s, v) => s + v, 0) / values.length : null;
  }

  /* 逐年计算某指标的合计/比值序列 */
  function aggregateSeries(metricId, filterFn) {
    const m = metricOf(metricId);
    return app.years.map(year => {
      const rows = rowsOfYear(year).filter(filterFn || (() => true));
      return rows.length ? aggregate(rows, m) : null;
    });
  }

  /* 空值统计：任一面板指标为空的记录条数 */
  function recordsWithGaps(rows) {
    return rows.filter(row => METRICS.some(m => row[m.field] == null)).length;
  }

  /* 复合增长率（按首末年份） */
  function cagr(first, last, span) {
    if (!isNum(first) || !isNum(last) || first <= 0 || !span) return null;
    return (Math.pow(last / first, 1 / span) - 1) * 100;
  }

  /* ============================================================
     2. 通用 UI 组件
     ============================================================ */
  function pageHead(title, subtitle, actions) {
    return `<div class="page-head"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>` +
      (actions ? `<div class="page-actions">${actions}</div>` : '') + `</div>`;
  }

  function kpiCard(item) {
    return `<div class="kpi${item.accent ? ' accent' : ''}">` +
      `<div class="kpi-label">${esc(item.label)}</div>` +
      `<div class="kpi-value">${item.value}${item.unit ? `<span class="unit">${esc(item.unit)}</span>` : ''}</div>` +
      (item.note ? `<div class="kpi-note">${esc(item.note)}</div>` : '') + `</div>`;
  }

  function kpiGrid(items) { return `<div class="kpi-grid">${items.map(kpiCard).join('')}</div>`; }

  function listBars(items, unit, digits) {
    if (!items.length) return '<div class="empty">没有数据</div>';
    const max = Math.max(...items.map(i => Math.abs(i.value) || 0)) || 1;
    return `<div class="list">${items.map(item => `<div class="list-row">
      <span class="name" title="${esc(item.label)}">${esc(item.label)}</span>
      <span class="bar"><span style="width:${Math.max(1, Math.abs(item.value) / max * 100).toFixed(1)}%"></span></span>
      <span class="val">${fmt(item.value, digits == null ? 1 : digits)}${esc(unit || '')}</span>
    </div>`).join('')}</div>`;
  }

  function statusTag(text, kind) { return `<span class="status ${kind}">${esc(text)}</span>`; }

  /* 表格组件：排序 / 分页 / 汇总 / 每页条数 */
  class DataTable {
    constructor(host, config) {
      this.host = host;
      this.columns = config.columns;
      this.pageSize = config.pageSize || 50;
      this.emptyText = config.empty || '没有符合条件的记录';
      this.summary = config.summary || null;
      this.rows = [];
      this.page = 0;
      this.sort = config.sort || null;
      this.host.innerHTML = this.shell();
      this.tbody = $('[data-body]', host);
      this.bind();
    }

    shell() {
      return `<div class="table-meta"><span data-count></span><span data-summary></span>
        <span style="margin-left:auto"></span>
        <select class="control" data-size aria-label="每页条数">${[20, 50, 100, 200].map(n => `<option value="${n}"${n === this.pageSize ? ' selected' : ''}>${n} 条/页</option>`).join('')}</select></div>
        <div class="table-wrap"><table class="data-table"><thead><tr>${this.columns.map((c, i) =>
          `<th data-col="${i}" class="${c.sortable === false ? '' : 'sortable'}" style="text-align:${c.align === 'num' ? 'right' : 'left'}">${esc(c.label)}<span class="sort-arrow">↕</span></th>`).join('')}</tr></thead>
          <tbody data-body></tbody></table></div>
        <div class="pagination"><button class="button secondary" type="button" data-prev>上一页</button><span data-pages></span><button class="button secondary" type="button" data-next>下一页</button></div>`;
    }

    bind() {
      $$('th.sortable', this.host).forEach(th => {
        th.addEventListener('click', () => {
          const index = Number(th.dataset.col);
          const key = this.columns[index].sortKey || index;
          if (this.sort && this.sort.key === key) this.sort.dir = -this.sort.dir;
          else this.sort = { key, dir: 1, index };
          this.page = 0;
          this.update();
        });
      });
      $('[data-prev]', this.host).addEventListener('click', () => { this.page = Math.max(0, this.page - 1); this.update(); });
      $('[data-next]', this.host).addEventListener('click', () => { this.page = Math.min(this.pageCount() - 1, this.page + 1); this.update(); });
      $('[data-size]', this.host).addEventListener('change', event => { this.pageSize = Number(event.target.value); this.page = 0; this.update(); });
    }

    setRows(rows) { this.rows = rows; this.page = 0; this.update(); return this; }

    sortedRows() {
      const rows = this.rows.slice();
      if (!this.sort) return rows;
      const column = this.columns[this.sort.index];
      const dir = this.sort.dir;
      return rows.sort((a, b) => {
        const va = column.value(a), vb = column.value(b);
        if (isNum(va) && isNum(vb)) return (va - vb) * dir;
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        return String(va).localeCompare(String(vb), 'zh-Hans-CN') * dir;
      });
    }

    pageCount() { return Math.max(1, Math.ceil(this.rows.length / this.pageSize)); }

    update() {
      const all = this.sortedRows();
      const pages = this.pageCount();
      this.page = Math.min(this.page, pages - 1);
      const slice = all.slice(this.page * this.pageSize, this.page * this.pageSize + this.pageSize);

      this.tbody.innerHTML = slice.length ? slice.map((row, i) => `<tr>${this.columns.map(column => {
        const value = column.value(row);
        const align = column.align === 'num' ? ' class="num"' : '';
        const text = column.render
          ? column.render(row, value)
          : column.plain
            ? esc(value == null || value === '' ? '—' : String(value))
            : (isNum(value) ? fmt(value, column.digits) : (value == null || value === '' ? '<span class="null">—</span>' : esc(value)));
        return `<td${align}>${text}</td>`;
      }).join('')}</tr>`).join('') : `<tr><td colspan="${this.columns.length}" class="empty">${esc(this.emptyText)}</td></tr>`;

      $('[data-count]', this.host).textContent = `${this.rows.length.toLocaleString('zh-CN')} 条记录`;
      $('[data-summary]', this.host).innerHTML = this.summary ? this.summary(all) : '';
      $('[data-pages]', this.host).textContent = `${this.page + 1} / ${pages}`;
      $('[data-prev]', this.host).disabled = this.page === 0;
      $('[data-next]', this.host).disabled = this.page >= pages - 1;
      $$('th', this.host).forEach((th, i) => {
        const arrow = $('.sort-arrow', th);
        if (!arrow) return;
        const active = this.sort && this.sort.index === i;
        arrow.textContent = active ? (this.sort.dir > 0 ? '▲' : '▼') : '↕';
        if (active) th.setAttribute('aria-sort', this.sort.dir > 0 ? 'ascending' : 'descending');
        else th.removeAttribute('aria-sort');
      });
    }
  }

  /* CSV 导出：BOM + 防公式注入 */
  function downloadCSV(rows, filename) {
    if (!rows.length) { toast('没有可导出的数据', 'error'); return; }
    const safe = rows.map(row => row.map(value => (typeof value === 'string' && /^[=+@\-\t]/.test(value) ? "'" + value : value)));
    const csv = '\ufeff' + Papa.unparse(safe);
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename.endsWith('.csv') ? filename : filename + '.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast(`已导出 ${filename}`);
  }

  function toast(message, kind) {
    const node = document.createElement('div');
    node.className = 'toast' + (kind === 'error' ? ' error' : '');
    node.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#${kind === 'error' ? 'i-info' : 'i-check'}"/></svg><span>${esc(message)}</span>`;
    $('#toasts').appendChild(node);
    setTimeout(() => { node.style.opacity = '0'; node.style.transform = 'translateY(4px)'; }, 2600);
    setTimeout(() => node.remove(), 3000);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('已复制到剪贴板');
    } catch (e) {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      try { document.execCommand('copy'); toast('已复制到剪贴板'); }
      catch (err) { toast('复制失败，请手动选择', 'error'); }
      area.remove();
    }
  }

  /* 灯箱 */
  function openLightbox(src, title) {
    const box = $('#lightbox');
    $('#lightbox-img').src = src;
    $('#lightbox-img').alt = title || '';
    $('#lightbox-title').textContent = title || '';
    const link = $('#lightbox-download');
    link.href = src;
    link.setAttribute('download', (title || 'chart') + '.png');
    box.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    $('#lightbox').hidden = true;
    $('#lightbox-img').src = '';
    document.body.style.overflow = '';
  }

  const chartUrl = file => 'assets/charts/' + encodeURIComponent(file);

  /* ============================================================
     3. 页面
     ============================================================ */

  /* 3.1 总览 */
  function overviewPage() {
    const year = latestYear();
    const rows = rowsOfYear(year);
    const shareSeries = aggregateSeries('agriShare');
    const top = rows.slice().sort((a, b) => (b['第一产业GDP(亿元)'] || 0) - (a['第一产业GDP(亿元)'] || 0)).slice(0, 8)
      .map(r => ({ label: r['省份'], value: r['第一产业GDP(亿元)'] }));
    const incomeTop = rows.slice().sort((a, b) => (b['农村居民人均可支配收入(元)'] || 0) - (a['农村居民人均可支配收入(元)'] || 0)).slice(0, 6)
      .map(r => ({ label: r['省份'], value: r['农村居民人均可支配收入(元)'] }));
    const missing = recordsWithGaps(app.rows);
    const charts = app.charts.slice(0, 2);

    view.innerHTML =
      `<section class="hero hero-photo rise" style="background-image:url('${imgUrl('hero-farm.jpg')}')">
        <div class="hero-kicker"><svg class="icon" aria-hidden="true"><use href="#i-leaf"/></svg> 智慧农业 · 数字农田 · AI 预测</div>
        <h1>智农宝 <span class="grad-text">农业大脑</span></h1>
        <p class="hero-sub">从 31 省农业经济大数据，到种植防亏损决策与数字农田生态，为农户、合作社与政策研究者提供离线、可复现的一站式智慧农业工作台。</p>
        <div class="hero-stats">
          <div class="hero-stat"><b>${app.provinces.length}</b><span>省级地区</span></div>
          <div class="hero-stat"><b>${app.years.length}</b><span>年份跨度</span></div>
          <div class="hero-stat"><b>${recordCount().toLocaleString('zh-CN')}</b><span>面板记录</span></div>
          <div class="hero-stat"><b>${AGRI_REF.crops.length}</b><span>作物模型</span></div>
          <div class="hero-stat"><b>${app.tableIndex.length}</b><span>源工作簿</span></div>
        </div>
        <div class="hero-actions">
          <a class="button light" href="#/smart-plan"><svg class="icon" aria-hidden="true"><use href="#i-shield"/></svg>种植防亏损</a>
          <a class="button" href="#/digital-farm"><svg class="icon" aria-hidden="true"><use href="#i-layers"/></svg>数字农田生态</a>
          <a class="button" href="#/predict"><svg class="icon" aria-hidden="true"><use href="#i-chart"/></svg>产量价格预测</a>
        </div>
      </section>` +
      `<div class="section-bar"><h2>核心能力</h2></div>
      <div class="prod-grid">
        <a class="prod-card" href="#/smart-plan" style="background-image:url('${imgUrl('crop-greenhouse.jpg')}')">
          <span class="prod-tag">AI 决策</span>
          <b>种植防亏损决策</b>
          <span>输入作物与面积，自动测算保本价、预期利润与风险等级，给出种植建议。</span>
          <svg class="icon prod-arrow" aria-hidden="true"><use href="#i-arrow"/></svg>
        </a>
        <a class="prod-card" href="#/digital-farm" style="background-image:url('${imgUrl('farm-digital.jpg')}')">
          <span class="prod-tag">数字孪生</span>
          <b>数字农田生态大屏</b>
          <span>四情监测、气象、土壤墒情、长势分区与设备状态一屏总览。</span>
          <svg class="icon prod-arrow" aria-hidden="true"><use href="#i-arrow"/></svg>
        </a>
        <a class="prod-card" href="#/predict" style="background-image:url('${imgUrl('crop-rice.jpg')}')">
          <span class="prod-tag">AI 预测</span>
          <b>产量与价格预测</b>
          <span>基于作物历史参考序列做趋势外推，辅助择机种植与销售。</span>
          <svg class="icon prod-arrow" aria-hidden="true"><use href="#i-arrow"/></svg>
        </a>
      </div>` +
      `<div class="section-bar"><h2>核心数据速览</h2><div class="page-actions"><button class="button secondary" id="overview-export">导出面板 CSV</button></div></div>` +
      `<div class="note">本工作台由本机比赛资料重建，<strong>不是 Manus 原站源码</strong>。页面计算全部使用原工作簿数值，未做外部统计源复核。</div>` +
      kpiGrid([
        { label: '覆盖省级地区', value: app.provinces.length, unit: '个', note: '原表省份口径' },
        { label: '面板年份跨度', value: app.years.length, unit: '年', note: `${app.years[0]}–${year}` },
        { label: `${year} 年第一产业GDP`, value: fmt(aggregate(rows, 'agriGdp'), 0), unit: '亿元', note: '省级记录求和' },
        { label: `${year} 年第一产业占比`, value: fmt(aggregate(rows, 'agriShare'), 1), unit: '%', note: '合计值计算', accent: true },
        { label: `较 ${app.years[0]} 年占比变化`, value: fmt((aggregate(rowsOfYear(year), 'agriShare') - aggregate(rowsOfYear(app.years[0]), 'agriShare')), 1), unit: '个百分点', note: '首末年直接相减' }
      ]) +
      `<div class="two-cols">
        <section class="panel">
          <div class="panel-head"><h2>全国第一产业占GDP比重</h2><span class="subtle">省级合计计算 · ${app.years.length} 年</span></div>
          <div id="ov-chart"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>${year} 年第一产业GDP 前 8 省份</h2><span class="subtle">亿元</span></div>
          ${listBars(top, '', 0)}
          <div class="chart-note">条长为同榜内相对值，非全国占比。</div>
          <div class="panel-head" style="margin-top:14px"><h2>农村居民人均可支配收入 前 6</h2></div>
          ${listBars(incomeTop, '元', 0)}
        </section>
      </div>` +
      `<div class="section-bar"><h2>数据质量速览</h2><a class="file-link" href="#/about">查看口径说明</a></div>
      <div class="grid-3">
        <div class="panel"><div class="kpi-label">面板缺失指标单元</div><div class="kpi-value">${missing.toLocaleString('zh-CN')}<span class="unit">条记录含空值</span></div><div class="kpi-note">9 个指标字段逐条检查，空值在原表中即存在</div></div>
        <div class="panel"><div class="kpi-label">宏观宽表缺失</div><div class="kpi-value">${app.dashboard.macro.rows.filter(r => Object.values(r).some(v => v == null)).length}<span class="unit">/ ${app.dashboard.macro.rows.length} 行</span></div><div class="kpi-note">2000 年前后多项指标未填报，保留原值</div></div>
        <div class="panel"><div class="kpi-label">作物指标推算年份</div><div class="kpi-value">${CROP_IMPUTED_FROM}${app.crops ? ' 起' : ''}<span class="unit">需核验</span></div><div class="kpi-note">该段数值可能由增长率补齐，不作官方实测</div></div>
      </div>` +
      `<div class="section-bar"><h2>快捷入口</h2></div>
      <div class="workflow-links">
        ${[['数据总览', '#/data', '按年份筛选、排序、导出'],
        ['省域分布', '#/map', '切换指标查看 31 省差异'],
        ['区域对比', '#/compare', '最多四省同图对照'],
        ['趋势预测', '#/forecast', '在线回归外推，标注拟合优度'],
        ['数据集目录', '#/datasets', `${app.tableIndex.length} 份工作簿逐表预览`],
        ['恢复说明', '#/about', '已找到 / 未找到的边界']].map(([name, url, detail]) =>
        `<a href="${url}"><div><strong>${name}</strong><span>${detail}</span></div><svg class="icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>`).join('')}
      </div>` +
      `<div class="section-bar"><h2>研究成果图</h2><a class="file-link" href="#/model">全部 ${app.charts.length} 张</a></div>
      <div class="image-grid">${charts.map(c => `<figure class="image-card"><button type="button" data-open-chart="${esc(c.file)}" data-title="${esc(c.name)}"><img src="${chartUrl(c.file)}" alt="${esc(c.name)}" loading="lazy"></button><figcaption>${esc(c.name)}</figcaption></figure>`).join('')}</div>`;

    Chart.mount($('#ov-chart'), { series: [{ name: '一产占比', values: shareSeries }], labels: app.years.map(String), unit: '%', digits: 1, area: true, height: 300 });
    const exportRows = [['省份', '大区', '年份', ...METRICS.map(m => m.label)]];
    rows.forEach(row => exportRows.push([row['省份'], row['大区'], row['年份'], ...METRICS.map(m => row[m.field])]));
    $('#overview-export').onclick = () => downloadCSV(exportRows, `智农宝_${year}年面板`);
    bindChartOpeners();
  }

  /* 3.2 数据总览 */
  function dataPage() {
    const initialState = { year: latestYear(), regions: [], query: '' };
    view.innerHTML = pageHead('数据总览', '按年份、大区与关键词查阅原工作簿的省级记录',
      `<button class="button secondary" id="data-export">导出筛选结果 CSV</button><button class="button secondary" id="data-copy">复制为表格</button>`) +
      `<div class="note">所有数值为<strong>原工作簿拷贝值</strong>，单位随列名。排序与合计只在本页重算，不改写数据。</div>
      <div class="filters">
        <select class="control" id="f-year" aria-label="年份">${app.years.slice().reverse().map(y => `<option value="${y}">${y} 年</option>`).join('')}</select>
        <div class="chips" id="f-regions">${REGIONS.map(r => `<button class="chip" type="button" data-region="${r}" aria-pressed="false">${r}</button>`).join('')}</div>
        <input class="control grow" id="f-query" placeholder="搜索省份名称" aria-label="搜索省份">
        <button class="button ghost" type="button" id="f-reset">重置</button>
      </div>
      <div id="data-table"></div>`;

    const columns = [
      { label: '省份', value: r => r['省份'], align: 'text' },
      { label: '大区', value: r => r['大区'] },
      { label: '年份', value: r => r['年份'], align: 'num', plain: true },
      { label: '总GDP(亿元)', value: r => r['总GDP(亿元)'], align: 'num', digits: 0 },
      { label: '人均GDP(元)', value: r => r['人均GDP(元)'], align: 'num', digits: 0 },
      { label: '第一产业GDP(亿元)', value: r => r['第一产业GDP(亿元)'], align: 'num', digits: 1 },
      { label: '一产占GDP比重(%)', value: r => r['第一产业占GDP比重(%)'], align: 'num', digits: 1 },
      { label: '常住人口(万人)', value: r => r['常住人口(万人)'], align: 'num', digits: 1 },
      { label: '农村居民人均可支配收入(元)', value: r => r['农村居民人均可支配收入(元)'], align: 'num', digits: 0 },
      { label: '一产收入估算(元)', value: r => r['农村居民人均第一产业收入估算(元)'], align: 'num', digits: 0 }
    ];

    const table = new DataTable($('#data-table'), {
      columns, pageSize: 50, sort: { key: 5, dir: -1, index: 5 },
      summary: rows => {
        const gdp = rows.reduce((s, r) => s + (Number(r['总GDP(亿元)']) || 0), 0);
        const agri = rows.reduce((s, r) => s + (Number(r['第一产业GDP(亿元)']) || 0), 0);
        return `合计 总GDP ${fmt(gdp, 0)} 亿元 · 一产GDP ${fmt(agri, 0)} 亿元 · 一产占比 ${fmt(gdp ? agri / gdp * 100 : null, 1)}%`;
      }
    });

    let current = [];
    const refresh = () => {
      const year = Number($('#f-year').value);
      const query = $('#f-query').value.trim();
      current = rowsOfYear(year)
        .filter(r => !initialState.regions.length || initialState.regions.includes(r['大区']))
        .filter(r => !query || String(r['省份']).includes(query));
      table.setRows(current);
    };

    $('#f-year').value = String(initialState.year);
    $('#f-year').addEventListener('change', refresh);
    $('#f-query').addEventListener('input', refresh);
    $('#f-reset').addEventListener('click', () => {
      initialState.regions = [];
      $$('#f-regions .chip').forEach(chip => chip.setAttribute('aria-pressed', 'false'));
      $('#f-query').value = '';
      $('#f-year').value = String(latestYear());
      refresh();
    });
    $$('#f-regions .chip').forEach(chip => chip.addEventListener('click', () => {
      const region = chip.dataset.region;
      const on = chip.getAttribute('aria-pressed') === 'true';
      chip.setAttribute('aria-pressed', on ? 'false' : 'true');
      initialState.regions = on ? initialState.regions.filter(x => x !== region) : initialState.regions.concat(region);
      refresh();
    }));
    $('#data-export').addEventListener('click', () => {
      const head = ['省份', '大区', '年份', ...METRICS.map(m => m.label)];
      downloadCSV([head, ...current.map(r => [r['省份'], r['大区'], r['年份'], ...METRICS.map(m => r[m.field])])],
        `智农宝_${$('#f-year').value}年_省级面板`);
    });
    $('#data-copy').addEventListener('click', () => {
      const lines = [['省份', '大区', '年份', '总GDP(亿元)', '第一产业GDP(亿元)', '一产占比(%)'].join('\t')]
        .concat(current.map(r => [r['省份'], r['大区'], r['年份'], r['总GDP(亿元)'], r['第一产业GDP(亿元)'], r['第一产业占GDP比重(%)']].join('\t')));
      copyText(lines.join('\n'));
    });
    refresh();
  }

  /* 3.3 省域分布（矩阵热力图，不使用地理边界） */
  function mapPage() {
    const savedMetric = store.get('mapMetric', 'agriShare');
    view.innerHTML = pageHead('省域分布', '按指标查看 31 个省级地区的相对位置（矩阵布局，不使用行政边界）',
      `<select class="control" id="m-metric">${METRICS.map(m => `<option value="${m.id}">${m.label}</option>`).join('')}</select>`) +
      `<div class="note">颜色深浅表示同一年份内该指标的<strong>相对高低</strong>，不代表地理邻近或面积。点击省份卡片进入详情。</div>
      <div class="panel">
        <div class="slider-row"><span id="m-year-label"></span><input type="range" id="m-year" min="0" max="${app.years.length - 1}" value="${app.years.length - 1}" step="1" aria-label="年份滑块"><span class="subtle" id="m-range">${app.years[0]}–${latestYear()}</span></div>
        <div class="chart-note" id="m-scale"></div>
      </div>
      <div id="m-content"></div>`;

    $('#m-metric').value = metricOf(savedMetric).id;
    const draw = () => {
      const metric = metricOf($('#m-metric').value);
      const year = app.years[Number($('#m-year').value)];
      store.set('mapMetric', metric.id);
      $('#m-year-label').textContent = year + ' 年';
      const rows = rowsOfYear(year);
      const numerator = metric.agg === 'ratio'
        ? rows.map(r => ({ row: r, value: r[metric.field] }))
        : rows.map(r => ({ row: r, value: r[metric.field] }));
      const values = numerator.map(x => x.value).filter(isNum);
      const min = Math.min(...values), max = Math.max(...values);
      $('#m-scale').textContent = `色阶：${fmt(min, metric.digits)}${metric.unit}（浅）→ ${fmt(max, metric.digits)}${metric.unit}（深）· ${metric.note}`;
      $('#m-content').innerHTML = REGIONS.map(region => {
        const items = numerator.filter(x => x.row['大区'] === region)
          .sort((a, b) => (b.value || -Infinity) - (a.value || -Infinity));
        if (!items.length) return '';
        return `<div class="section-bar"><h2>${region}地区</h2><span class="subtle">${items.length} 个省级地区</span></div>
        <div class="province-grid">${items.map(({ row, value }) => {
          const t = isNum(value) && max > min ? (value - min) / (max - min) : 0.5;
          const light = 94 - t * 42;
          const color = t > 0.62 ? '#ffffff' : '#16281f';
          return `<a class="province-tile" href="#/province/${encodeURIComponent(row['省份'])}" style="background:hsl(145 38% ${light.toFixed(1)}%);border-top-color:hsl(148 45% ${(52 - t * 22).toFixed(0)}%)">
            <strong style="color:${color}">${esc(row['省份'])}</strong>
            <span style="color:${color};opacity:.82">${fmt(value, metric.digits)}${esc(metric.unit)}</span>
            <span class="tile-bar"><span style="width:${(t * 100).toFixed(0)}%;background:#2f7d4f"></span></span>
          </a>`;
        }).join('')}</div>`;
      }).join('');
    };
    $('#m-metric').addEventListener('change', draw);
    $('#m-year').addEventListener('input', draw);
    draw();
  }

  /* 3.4 区域对比（最多 4 省 + 指标切换） */
  function comparePage() {
    const metric = metricOf(store.get('compareMetric', 'agriShare'));
    const saved = store.get('compareProvinces', ['广东', '河南', '黑龙江']);
    const picked = saved.filter(p => app.provinces.includes(p)).slice(0, 4);
    const initial = picked.length ? picked : ['广东', '河南'];

    view.innerHTML = pageHead('区域对比', '同一指标下最多四个省级地区对照，附最新年份差值与年均增速',
      `<select class="control" id="c-metric">${METRICS.map(m => `<option value="${m.id}">${m.label}</option>`).join('')}</select>
       <button class="button secondary" id="c-export">导出对比表 CSV</button>`) +
      `<div class="note">年均增速按“首末年复合增长率”计算（CAGR），只用于趋势比较；不代表官方增速口径。</div>
      <div class="filters" id="c-pickers"></div>
      <section class="panel"><div class="panel-head"><h2 id="c-title"></h2><span class="subtle" id="c-sub"></span></div><div id="c-chart"></div></section>
      <div class="section-bar"><h2>最新年份对照</h2><span class="subtle" id="c-year"></span></div>
      <div id="c-table"></div>`;

    $('#c-metric').value = metric.id;
    let slots = [initial[0] || '', initial[1] || '', initial[2] || '', initial[3] || ''];
    const colors = Chart.PALETTE;
    const pickedList = () => Array.from(new Set(slots.filter(Boolean)));

    const renderPickers = () => {
      $('#c-pickers').innerHTML = [0, 1, 2, 3].map(index => `<select class="control" data-slot="${index}" aria-label="省份 ${index + 1}">
        <option value="">${index < 2 ? '（请选择省份）' : '（不选）'}</option>
        ${app.provinces.map(p => `<option value="${esc(p)}"${slots[index] === p ? ' selected' : ''}>${esc(p)}</option>`).join('')}
      </select>`).join('') + `<button class="button ghost" type="button" id="c-reset">重置选择</button>`;
      $$('#c-pickers select').forEach(select => select.addEventListener('change', () => {
        slots[Number(select.dataset.slot)] = select.value;
        /* 同一个省份不能重复占用两个位置 */
        const owner = slots.indexOf(select.value);
        if (select.value && owner !== Number(select.dataset.slot)) slots[owner] = '';
        renderPickers();
        draw();
      }));
      $('#c-reset').addEventListener('click', () => { slots = ['广东', '河南', '', '']; renderPickers(); draw(); });
    };

    const draw = () => {
      const m = metricOf($('#c-metric').value);
      const selected = pickedList();
      store.set('compareMetric', m.id);
      store.set('compareProvinces', selected);
      const series = selected.map((name, index) => {
        const rows = rowsOfProvince(name);
        const lookup = new Map(rows.map(r => [r['年份'], r[m.field]]));
        return { name, values: app.years.map(y => (isNum(lookup.get(y)) ? lookup.get(y) : null)), color: colors[index % colors.length] };
      });
      $('#c-title').textContent = m.label + ' 历年对比';
      $('#c-sub').textContent = `${selected.length} 个省份 · ${app.years[0]}–${latestYear()} · 单位 ${m.unit}`;
      if (series.length) Chart.mount($('#c-chart'), { series, labels: app.years.map(String), unit: m.unit, digits: m.digits, height: 340 });
      else $('#c-chart').innerHTML = '<div class="empty">请至少选择一个省份</div>';

      const year = latestYear();
      $('#c-year').textContent = `${year} 年 · ${m.note}`;
      const head = ['省份', '大区', m.label + `(${m.unit})`, '与全省均值差', '首末年变化', '年均增速(%)'];
      const allRows = rowsOfYear(year);
      const mean = aggregate(allRows, m);
      const body = selected.map(name => {
        const row = rowsOfYear(year).find(r => r['省份'] === name);
        const rows = rowsOfProvince(name);
        const first = rows[0] ? rows[0][m.field] : null;
        const last = row ? row[m.field] : null;
        const span = rows.length > 1 ? rows[rows.length - 1]['年份'] - rows[0]['年份'] : 0;
        return [name, row ? row['大区'] : '—', last, isNum(last) && isNum(mean) ? last - mean : null,
          isNum(last) && isNum(first) ? last - first : null, cagr(first, last, span)];
      });
      const grid = `<div class="table-wrap"><table class="data-table"><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
        <tbody>${body.map(row => `<tr>${row.map((value, i) => `<td class="${i === 0 ? '' : 'num'}">${isNum(value) ? fmt(value, i === 5 ? 2 : m.digits) : (value == null ? '<span class="null">—</span>' : esc(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
      $('#c-table').innerHTML = grid;
      $('#c-export').onclick = () => downloadCSV([head, ...body], `智农宝_对比_${m.short}_${year}`);
    };

    $('#c-metric').addEventListener('change', draw);
    renderPickers();
    draw();
  }

  /* 3.5 省份详情 */
  function provincePage(name) {
    const rows = rowsOfProvince(name);
    if (!rows.length) return notFound(`没有省份“${name}”的记录`);
    const last = rows[rows.length - 1];
    const year = last['年份'];
    const metric = metricOf(store.get('provinceMetric', 'agriShare'));
    const rankRows = rowsOfYear(year).slice().sort((a, b) => (b[metric.field] || -Infinity) - (a[metric.field] || -Infinity));
    const rank = rankRows.findIndex(r => r['省份'] === name) + 1;
    const first = rows[0];
    const growth = cagr(first[metric.field], last[metric.field], last['年份'] - first['年份']);

    view.innerHTML = pageHead(`${name} · 农业经济`, `${rows[0]['年份']}–${year} 年 · ${last['大区']}地区 · 共 ${rows.length} 条年度记录`,
      `<a class="button secondary" href="#/map">返回省域分布</a><button class="button secondary" id="p-export">导出该省 CSV</button>`) +
      kpiGrid([
        { label: '最新年份', value: year, note: '原表最后一条记录' },
        { label: '第一产业GDP', value: fmt(last['第一产业GDP(亿元)'], 1), unit: '亿元', note: `全国第 ${rankRows.filter(r => (r['第一产业GDP(亿元)'] || 0) > (last['第一产业GDP(亿元)'] || 0)).length + 1} 位` },
        { label: '第一产业占比', value: fmt(last['第一产业占GDP比重(%)'], 1), unit: '%', note: '总GDP 口径', accent: true },
        { label: '农村居民人均可支配收入', value: fmt(last['农村居民人均可支配收入(元)'], 0), unit: '元', note: '原表值' },
        { label: '人均GDP', value: fmt(last['人均GDP(元)'], 0), unit: '元', note: '原表值' }
      ]) +
      `<div class="filters"><select class="control" id="p-metric">${METRICS.map(m => `<option value="${m.id}">${m.label}</option>`).join('')}</select>
        <span class="subtle" id="p-metric-note"></span></div>
      <section class="panel"><div class="panel-head"><h2 id="p-title"></h2><span class="subtle" id="p-sub"></span></div><div id="p-chart"></div></section>
      <div class="section-bar"><h2>主要指标走势</h2><span class="subtle">迷你趋势图 · 纵轴自适应</span></div>
      <div class="grid-3" id="p-sparks"></div>
      <div class="section-bar"><h2>${year} 年同指标排名</h2><span class="subtle">共 ${rankRows.length} 个省级地区 · 当前第 ${rank} 位</span></div>
      <div id="p-rank"></div>`;

    $('#p-metric').value = metric.id;

    const sparkCards = () => METRICS.slice(0, 6).map(m => {
      const values = rows.map(r => r[m.field]);
      const lastValue = values[values.length - 1];
      return `<div class="panel"><div class="kpi-label">${esc(m.short)}</div>
        <div class="kpi-value">${fmt(lastValue, m.digits)}<span class="unit">${esc(m.unit)}</span></div>
        ${Chart.spark(values, { color: '#2f7d4f', height: 44 })}
        <div class="kpi-note">${rows[0]['年份']}–${year} · 最新值</div></div>`;
    }).join('');

    const draw = () => {
      const m = metricOf($('#p-metric').value);
      store.set('provinceMetric', m.id);
      $('#p-metric-note').textContent = m.note;
      $('#p-title').textContent = `${name} · ${m.label}`;
      $('#p-sub').textContent = `单位 ${m.unit} · 年均增速 ${fmt(cagr(rows[0][m.field], last[m.field], last['年份'] - rows[0]['年份']), 2)}%`;
      Chart.mount($('#p-chart'), {
        series: [{ name: m.label, values: rows.map(r => r[m.field]) }],
        labels: rows.map(r => String(r['年份'])), unit: m.unit, digits: m.digits, area: true, height: 320
      });
      const ranked = rowsOfYear(year).slice().sort((a, b) => (b[m.field] || -Infinity) - (a[m.field] || -Infinity));
      $('#p-rank').innerHTML = listBars(ranked.map(r => ({ label: r['省份'], value: r[m.field] })), m.unit, m.digits);
    };

    $('#p-export').addEventListener('click', () => {
      const head = ['年份', ...METRICS.map(m => m.label)];
      downloadCSV([head, ...rows.map(r => [r['年份'], ...METRICS.map(m => r[m.field])])], `智农宝_${name}_面板`);
    });
    $('#p-sparks').innerHTML = sparkCards();
    $('#p-metric').addEventListener('change', draw);
    draw();
  }

  /* 3.6 作物指标 */
  function cropPage() {
    if (!app.crops) { view.innerHTML = pageHead('作物指标', '数据缺失') + '<div class="empty">未找到 crops.json</div>'; return; }
    const provinces = Object.keys(app.crops.provinces).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'));
    const defaultProvince = store.get('cropProvince', '广东');
    const startProvince = provinces.includes(defaultProvince) ? defaultProvince : provinces[0];
    const indicatorsOf = province => Object.keys(app.crops.provinces[province].indicators);

    view.innerHTML = pageHead('作物指标', `${provinces.length} 个省级地区 · 播种面积与作物结构`, `<button class="button secondary" id="cr-export">导出该指标 CSV</button>`) +
      `<div class="note warning">${esc(app.crops.warning || '历史工作簿原值，可能含插值或推算。')} 图中 ${CROP_IMPUTED_FROM} 年及以后以色带标出，请勿直接当作官方实测值。</div>
      <div class="filters">
        <select class="control" id="cr-province" aria-label="省份">${provinces.map(p => `<option value="${esc(p)}"${p === startProvince ? ' selected' : ''}>${esc(p)}</option>`).join('')}</select>
        <select class="control" id="cr-indicator" aria-label="指标"></select>
        <input class="control grow" id="cr-province-search" placeholder="筛选省份下拉（输入后回车）" aria-label="筛选省份">
      </div>
      <div class="chips" id="cr-peers"></div>
      <section class="panel" style="margin-top:12px"><div class="panel-head"><h2 id="cr-title"></h2><span class="subtle" id="cr-source"></span></div><div id="cr-chart"></div></section>
      <div class="section-bar"><h2>原值明细</h2><span class="subtle">按年份倒序</span></div>
      <div id="cr-table"></div>`;

    let peers = store.get('cropPeers', []).filter(p => provinces.includes(p)).slice(0, 3);
    let table = null;
    const colors = Chart.PALETTE;

    const setIndicators = () => {
      const province = $('#cr-province').value;
      const list = indicatorsOf(province);
      const keep = $('#cr-indicator').value;
      $('#cr-indicator').innerHTML = list.map(name => `<option value="${esc(name)}"${name === keep ? ' selected' : ''}>${esc(name)}</option>`).join('');
      if (!list.includes(keep)) $('#cr-indicator').value = list[0];
    };

    const drawPeers = () => {
      const current = $('#cr-province').value;
      const available = provinces.filter(p => p !== current && !peers.includes(p));
      $('#cr-peers').innerHTML = `<span class="subtle">叠加对比：</span>` +
        (peers.length
          ? peers.map(p => `<button class="chip" type="button" data-remove="${esc(p)}" aria-pressed="true">${esc(p)} ×</button>`).join('')
          : '<span class="subtle">可在同一指标下叠加最多 3 个省份</span>') +
        (peers.length < 3
          ? `<select class="control" id="cr-add" aria-label="添加对比省份"><option value="">＋ 添加省份对比</option>${available.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join('')}</select>`
          : '');
      $$('#cr-peers [data-remove]').forEach(chip => chip.addEventListener('click', () => {
        peers = peers.filter(item => item !== chip.dataset.remove);
        store.set('cropPeers', peers);
        drawPeers();
        draw();
      }));
      const adder = $('#cr-add');
      if (adder) adder.addEventListener('change', () => {
        if (!adder.value) return;
        peers = peers.concat(adder.value).slice(-3);
        store.set('cropPeers', peers);
        drawPeers();
        draw();
      });
    };

    const draw = () => {
      const province = $('#cr-province').value;
      const indicator = $('#cr-indicator').value;
      const source = app.crops.provinces[province];
      store.set('cropProvince', province);
      const names = [province].concat(peers.filter(p => p !== province));
      const series = names.map((name, index) => {
        const data = app.crops.provinces[name];
        const values = (data.indicators[indicator] || []);
        const points = data.years.map((y, i) => [y, isNum(values[i]) ? values[i] : null])
          .filter(p => p[0] != null).sort((a, b) => a[0] - b[0]);
        return { name, points };
      }).filter(s => s.points.length);
      const years = Array.from(new Set(series.flatMap(s => s.points.map(p => p[0])))).sort((a, b) => a - b);
      const chartSeries = series.map((s, index) => {
        const lookup = new Map(s.points);
        return { name: s.name, values: years.map(y => (isNum(lookup.get(y)) ? lookup.get(y) : null)), color: colors[index % colors.length] };
      });
      const imputedFrom = years.findIndex(y => y >= CROP_IMPUTED_FROM);
      $('#cr-title').textContent = indicator;
      $('#cr-source').textContent = source.file || '';
      Chart.mount($('#cr-chart'), {
        series: chartSeries, labels: years.map(String), digits: 2, height: 340,
        bands: imputedFrom >= 0 ? [{ from: imputedFrom, to: years.length - 1, label: '可能含推算' }] : []
      });

      const values = source.indicators[indicator] || [];
      const rows = source.years.map((y, i) => [y, isNum(values[i]) ? values[i] : null, y >= CROP_IMPUTED_FROM ? '待核验：可能含推算' : '原表值（未独立核验）'])
        .sort((a, b) => b[0] - a[0]);
      if (!table) {
        table = new DataTable($('#cr-table'), {
          columns: [
            { label: '年份', value: r => r[0], align: 'num', plain: true },
            { label: indicator, value: r => r[1], align: 'num', digits: 2 },
            { label: '核验状态', value: r => r[2], render: (row, value) => statusTag(value.startsWith('待核验') ? '可能含推算' : '原表值', value.startsWith('待核验') ? 'warn' : 'ok') }
          ], pageSize: 20
        });
      }
      table.columns[1].label = indicator;
      table.host.querySelector('thead th:nth-child(2)').firstChild.textContent = indicator;
      table.setRows(rows);
      $('#cr-export').onclick = () => downloadCSV([['年份', indicator, '核验状态'], ...rows], `智农宝_${province}_${indicator}`);
    };

    $('#cr-province').addEventListener('change', () => {
      peers = peers.filter(item => item !== $('#cr-province').value);
      setIndicators(); drawPeers(); draw();
    });
    $('#cr-indicator').addEventListener('change', draw);
    $('#cr-province-search').addEventListener('change', event => {
      const query = event.target.value.trim();
      if (!query) return;
      const hit = provinces.find(p => p.includes(query));
      if (hit) { $('#cr-province').value = hit; setIndicators(); drawPeers(); draw(); toast(`已切换到 ${hit}`); }
      else toast('没有匹配的省份', 'error');
      event.target.value = '';
    });
    setIndicators();
    drawPeers();
    draw();
  }

  /* 3.7 宏观与劳动力 */
  function macroPage() {
    const macro = app.dashboard.macro;
    const headers = macro.headers.filter(h => h !== '年份');
    const saved = store.get('macroMetrics', headers.slice(3, 6)).filter(h => headers.includes(h)).slice(0, 4);
    const selected = saved.length ? saved : headers.slice(0, 3);
    const rows = macro.rows.slice().sort((a, b) => a['年份'] - b['年份']);

    view.innerHTML = pageHead('宏观与劳动力', `${macro.rows.length} 行年度宽表 · ${headers.length} 个指标`, `<button class="button secondary" id="mc-export">导出所选指标 CSV</button>`) +
      `<div class="note warning">原表存在大量空值，且个别年份的数值与年份存在明显不匹配（例如 2000 年出现偏高的收入值）。这里<strong>保留原值不自动纠正</strong>，正式报告引用前请逐年核对来源。</div>
      <div class="chips" id="mc-chips"></div>
      <section class="panel" style="margin-top:12px"><div class="panel-head"><h2>指标走势</h2><span class="subtle">缺失年份断线表示原表为空</span></div><div id="mc-chart"></div></section>
      <div class="section-bar"><h2>宽表原值</h2><span class="subtle">空值以 — 标记</span></div>
      <div id="mc-table"></div>`;

    let picked = selected.slice();
    let table = null;

    const draw = () => {
      store.set('macroMetrics', picked);
      $('#mc-chips').innerHTML = headers.map(h => `<button class="chip" type="button" data-key="${esc(h)}" aria-pressed="${picked.includes(h)}">${esc(h)}</button>`).join('');
      $$('#mc-chips .chip').forEach(chip => chip.addEventListener('click', () => {
        const key = chip.dataset.key;
        if (picked.includes(key)) picked = picked.filter(x => x !== key);
        else if (picked.length >= 4) { toast('最多同时显示 4 个指标', 'error'); return; }
        else picked = picked.concat(key);
        draw();
      }));
      const series = picked.map((key, index) => ({
        name: key, values: rows.map(r => (isNum(r[key]) ? r[key] : null)), color: Chart.PALETTE[index % Chart.PALETTE.length]
      }));
      if (series.length) Chart.mount($('#mc-chart'), { series, labels: rows.map(r => String(r['年份'])), height: 340, digits: 2 });
      else $('#mc-chart').innerHTML = '<div class="empty">请选择至少一个指标</div>';

      const data = rows.slice().sort((a, b) => b['年份'] - a['年份']);
      if (!table) {
        table = new DataTable($('#mc-table'), {
          columns: [
            { label: '年份', value: r => r['年份'], align: 'num', plain: true },
            ...headers.map(h => ({ label: h, value: r => r[h], align: 'num', digits: 2 }))
          ], pageSize: 50, sort: { key: 0, dir: -1, index: 0 }
        });
      }
      table.setRows(data);
      $('#mc-export').onclick = () => downloadCSV([['年份', ...(picked.length ? picked : headers)], ...data.map(r => [r['年份'], ...(picked.length ? picked : headers).map(h => r[h])])], '智农宝_宏观指标');
    };

    draw();
  }

  /* 3.8 趋势预测（在线回归外推，明确标注为演示算法） */
  function forecastPage() {
    const metric = metricOf(store.get('forecastMetric', 'agriShare'));
    const startProvince = store.get('forecastProvince', '广东');
    const horizonDefault = store.get('forecastHorizon', 5);
    const lastYear = latestYear();

    view.innerHTML = pageHead('趋势预测', '基于历史序列的在线回归外推（演示算法，非原站 SARIMA 模型）',
      `<button class="button secondary" id="fc-export">导出预测表 CSV</button>`) +
      `<div class="note warning">本页在你本地浏览器里用最小二乘法现算，<strong>不是</strong>比赛项目里保存的 SARIMA/分类模型输出。R² 为样本内拟合优度，样本点少时容易虚高，预测结果不可作为决策依据。</div>
      <div class="filters">
        <select class="control" id="fc-province" aria-label="省份">${app.provinces.map(p => `<option value="${esc(p)}"${p === startProvince ? ' selected' : ''}>${esc(p)}</option>`).join('')}</select>
        <select class="control" id="fc-metric" aria-label="指标">${METRICS.map(m => `<option value="${m.id}">${m.label}</option>`).join('')}</select>
        <select class="control" id="fc-method" aria-label="方法">
          <option value="linear">线性回归（最小二乘）</option>
          <option value="log">指数趋势（对数线性）</option>
        </select>
        <div class="slider-row" style="flex:1 1 240px"><span>外推</span><input type="range" id="fc-horizon" min="1" max="10" step="1" value="${horizonDefault}" aria-label="外推年数"><span id="fc-horizon-label">${horizonDefault} 年</span></div>
      </div>
      <div class="kpi-grid" id="fc-kpis"></div>
      <div id="fc-warn"></div>
      <section class="panel"><div class="panel-head"><h2 id="fc-title"></h2><span class="subtle" id="fc-sub"></span></div><div id="fc-chart"></div></section>
      <div class="section-bar"><h2>逐年预测值</h2><span class="subtle">含历史拟合值与未来外推值</span></div>
      <div id="fc-table"></div>
      <div class="section-bar"><h2>原项目预测图</h2><span class="subtle">比赛项目保存的图像，不是本页输出</span></div>
      <div class="image-grid">${app.charts.filter(c => /^C1[12]_/.test(c.name)).map(c => `<figure class="image-card"><button type="button" data-open-chart="${esc(c.file)}" data-title="${esc(c.name)}"><img src="${chartUrl(c.file)}" alt="${esc(c.name)}" loading="lazy"></button><figcaption>${esc(c.name)}</figcaption></figure>`).join('')}</div>`;

    $('#fc-province').value = startProvince;
    $('#fc-metric').value = metric.id;

    const draw = () => {
      const province = $('#fc-province').value;
      const m = metricOf($('#fc-metric').value);
      const method = $('#fc-method').value;
      const horizon = Number($('#fc-horizon').value);
      store.set('forecastProvince', province);
      store.set('forecastMetric', m.id);
      store.set('forecastHorizon', horizon);
      $('#fc-horizon-label').textContent = horizon + ' 年';

      const rows = rowsOfProvince(province).filter(r => isNum(r[m.field]));
      const points = rows.map(r => [r['年份'], r[m.field]]);
      const model = method === 'log' ? Chart.fitLog(points) : Chart.fit(points);
      if (!model || points.length < 3) {
        $('#fc-kpis').innerHTML = '';
        $('#fc-chart').innerHTML = '<div class="empty">该省份此指标的有效年份不足 3 个，无法拟合</div>';
        $('#fc-table').innerHTML = '';
        return;
      }

      const futureYears = Array.from({ length: horizon }, (_, i) => lastYear + i + 1);
      const labels = points.map(p => String(p[0])).concat(futureYears.map(String));
      const history = points.map(p => p[1]).concat(futureYears.map(() => null));
      const fitted = points.map(p => model.predict(p[0])).concat(futureYears.map(y => model.predict(y)));
      const future = points.map(() => null).concat(futureYears.map(y => model.predict(y)));

      $('#fc-kpis').innerHTML = [
        { label: '拟合样本', value: points.length, unit: '年', note: `${points[0][0]}–${points[points.length - 1][0]}` },
        { label: '样本内 R²', value: fmt(model.r2, 3), note: model.r2 == null ? '无法计算' : '越接近 1 拟合越紧，不代表预测准确' },
        { label: method === 'log' ? '隐含年增长率' : '每年斜率', value: fmt(method === 'log' ? model.growth * 100 : model.slope, 2), unit: method === 'log' ? '%' : m.unit + '/年', note: method === 'log' ? '指数模型按复合增长理解' : '线性模型按绝对增量理解' },
        { label: `${lastYear + horizon} 年外推值`, value: fmt(model.predict(lastYear + horizon), m.digits), unit: m.unit, note: '外推越远越不可靠', accent: true }
      ].map(kpiCard).join('');

      $('#fc-title').textContent = `${province} · ${m.label} 趋势与外推`;
      $('#fc-sub').textContent = `${method === 'log' ? '指数趋势' : '线性回归'} · 外推 ${horizon} 年至 ${lastYear + horizon} 年`;
      const futureValues = futureYears.map(y => model.predict(y));
      const outOfRange = m.unit === '%' && (Math.min(...futureValues) < 0 || Math.max(...futureValues) > 100);
      $('#fc-warn').innerHTML = outOfRange
        ? `<div class="note danger">外推结果已经超出 0–100% 的合理区间（${futureValues.map(v => fmt(v, 1)).join(' / ')}%），说明该指标在这个区间已不适合线性外推。请缩小外推年数，或改用指数模型做对比。</div>`
        : '';
      Chart.mount($('#fc-chart'), {
        series: [
          { name: '历史值', values: history, color: '#2f7d4f' },
          { name: '模型拟合', values: fitted, color: '#829186', dash: '5 5' },
          { name: '外推', values: future, color: '#c8873a', dash: '6 4' }
        ], labels, unit: m.unit, digits: m.digits, height: 340
      });

      const tableRows = points.map(p => [p[0], p[1], model.predict(p[0]), '历史拟合'])
        .concat(futureYears.map(y => [y, null, model.predict(y), '外推']));
      new DataTable($('#fc-table'), {
        columns: [
          { label: '年份', value: r => r[0], align: 'num', plain: true },
          { label: '实际值', value: r => r[1], align: 'num', digits: m.digits },
          { label: '模型值', value: r => r[2], align: 'num', digits: m.digits },
          { label: '类型', value: r => r[3], render: (row, value) => statusTag(value, value === '外推' ? 'warn' : 'ok') }
        ], pageSize: 20, sort: { key: 0, dir: 1, index: 0 }
      }).setRows(tableRows);
      $('#fc-export').onclick = () => downloadCSV([['年份', '实际值(' + m.unit + ')', '模型值(' + m.unit + ')', '类型'], ...tableRows], `智农宝_预测_${province}_${m.short}`);
    };

    ['#fc-province', '#fc-metric', '#fc-method'].forEach(sel => $(sel).addEventListener('change', draw));
    $('#fc-horizon').addEventListener('input', draw);
    bindChartOpeners();
    draw();
  }

  /* 3.9 模型与图表 */
  function modelPage() {
    const groups = { A: '结构与趋势', B: '模型表现', C: '时序预测', D: '聚类与相关', E: '风险与结论' };
    view.innerHTML = pageHead('模型与图表', `比赛项目保存的 ${app.charts.length} 张分析图`, `<button class="button secondary" id="md-download-all">生成清单 CSV</button>`) +
      `<div class="note">图片为项目文件原样拷贝，站内未重新拟合模型。分析脚本随数据包提供（data/model_code）。</div>
      <div class="filters"><div class="chips" id="md-chips"></div><input class="control grow" id="md-search" placeholder="搜索图名" aria-label="搜索图名"></div>
      <div id="md-count" class="table-meta"></div>
      <div class="image-grid" id="md-grid"></div>`;

    let filter = '';
    const draw = () => {
      const query = $('#md-search').value.trim();
      const list = app.charts.filter(c => (!filter || c.name.startsWith(filter)) && (!query || c.name.includes(query)));
      $('#md-count').textContent = `${list.length} / ${app.charts.length} 张图`;
      $('#md-grid').innerHTML = list.map(c => `<figure class="image-card">
        <button type="button" data-open-chart="${esc(c.file)}" data-title="${esc(c.name)}"><img src="${chartUrl(c.file)}" alt="${esc(c.name)}" loading="lazy"></button>
        <figcaption>${esc(c.name)}<div class="subtle">SHA-256 ${esc(c.sha256.slice(0, 12))}…</div></figcaption></figure>`).join('');
      bindChartOpeners();
    };
    $('#md-chips').innerHTML = `<button class="chip" type="button" data-group="" aria-pressed="true">全部</button>` +
      Object.keys(groups).map(k => `<button class="chip" type="button" data-group="${k}" aria-pressed="false">${k} · ${groups[k]}</button>`).join('');
    $$('#md-chips .chip').forEach(chip => chip.addEventListener('click', () => {
      filter = chip.dataset.group;
      $$('#md-chips .chip').forEach(c => c.setAttribute('aria-pressed', String(c === chip)));
      draw();
    }));
    $('#md-search').addEventListener('input', draw);
    $('#md-download-all').addEventListener('click', () => downloadCSV(
      [['文件名', '名称', 'SHA-256'], ...app.charts.map(c => [c.file, c.name, c.sha256])], '智农宝_图表清单'));
    draw();
  }

  /* 3.10 数据集目录 */
  function datasetsPage() {
    const bytesBySha = new Map();
    (app.sourceManifest.files || []).forEach(file => { if (file.sha256) bytesBySha.set(file.sha256, file.bytes); });
    const tables = app.tableIndex.map(item => ({
      ...item,
      sheetCount: item.sheets.length,
      rowCount: item.sheets.reduce((s, sheet) => s + (sheet.rows || 0), 0),
      bytes: bytesBySha.get(item.sha256) || null
    }));
    const groups = Array.from(new Set(tables.map(t => t.group)));

    view.innerHTML = pageHead('数据集目录', `${tables.length} 份去重可解析工作簿 · ${app.sourceManifest.files.length} 份源文件记录`,
      `<button class="button secondary" id="ds-export">导出目录 CSV</button>`) +
      `<div class="note">按文件内容（SHA-256）去重，同名不同版本会分别列出。点击行可进入逐表预览。<strong>来源路径与原机目录已隐藏</strong>，只保留相对路径。</div>
      <div class="filters">
        <input class="control grow" id="ds-search" placeholder="搜索文件名或工作表名" aria-label="搜索">
        <select class="control" id="ds-group"><option value="">全部来源</option>${groups.map(g => `<option value="${esc(g)}">${esc(g)}</option>`).join('')}</select>
        <span class="subtle" id="ds-count"></span>
      </div>
      <div id="ds-table"></div>`;

    const table = new DataTable($('#ds-table'), {
      columns: [
        { label: '工作簿', value: r => r.name, render: (row, value) => `<a class="file-link" href="#/dataset/${encodeURIComponent(row.id)}">${esc(value)}</a>` },
        { label: '来源分组', value: r => r.group },
        { label: '工作表', value: r => r.sheetCount, align: 'num' },
        { label: '总行数', value: r => r.rowCount, align: 'num' },
        { label: '大小(KB)', value: r => (r.bytes ? r.bytes / 1024 : null), align: 'num', digits: 0 },
        { label: '校验', value: r => r.sha256, render: (row, value) => `<span class="mono">${esc(String(value).slice(0, 10))}…</span>` }
      ], pageSize: 50
    });

    const refresh = () => {
      const query = $('#ds-search').value.trim().toLowerCase();
      const group = $('#ds-group').value;
      const rows = tables.filter(t => (!group || t.group === group) &&
        (!query || t.name.toLowerCase().includes(query) || t.sheets.some(s => String(s.name).toLowerCase().includes(query))));
      $('#ds-count').textContent = `${rows.length} 份`;
      table.setRows(rows);
    };
    $('#ds-search').addEventListener('input', refresh);
    $('#ds-group').addEventListener('change', refresh);
    $('#ds-export').addEventListener('click', () => downloadCSV(
      [['文件名', '来源', '工作表数', '总行数', '字节', 'SHA-256'], ...tables.map(t => [t.name, t.group, t.sheetCount, t.rowCount, t.bytes, t.sha256])],
      '智农宝_数据集目录'));
    refresh();
  }

  /* 3.11 单个工作簿预览 */
  function datasetDetailPage(id) {
    const item = app.tableIndex.find(t => t.id === id) || app.tableIndex.find(t => String(t.id) === String(id));
    if (!item) return notFound('没有找到该工作簿');
    view.innerHTML = pageHead(item.name, `${item.group} · ${item.sheets.length} 张工作表 · SHA-256 ${item.sha256.slice(0, 16)}…`,
      `<a class="button secondary" href="#/datasets">返回目录</a>`) +
      `<div class="filters"><select class="control" id="dt-sheet">${item.sheets.map((s, i) => `<option value="${i}">${esc(s.name)} (${s.rows} 行)</option>`).join('')}</select>
        <input class="control grow" id="dt-search" placeholder="在整张表内搜索" aria-label="搜索表内内容">
        <button class="button secondary" id="dt-export">导出整张表 CSV</button>
        <a class="button secondary" id="dt-raw" href="data/tables/${encodeURIComponent(item.id)}.json" download>下载原始 JSON</a></div>
      <div class="note" id="dt-note"></div><div id="dt-table"></div>`;
    $('#dt-note').textContent = `工作表清单：${item.sheets.map(s => s.name).join(' / ')}`;

    let table = null;
    let rows = [];
    const draw = async () => {
      const index = Number($('#dt-sheet').value);
      const host = $('#dt-table');
      host.innerHTML = '<div class="loading">正在读取工作表…</div>';
      try {
        let sheets = app.tables.get(item.id);
        if (!sheets) {
          const response = await fetch('data/tables/' + encodeURIComponent(item.id) + '.json');
          if (!response.ok) throw new Error('HTTP ' + response.status);
          sheets = await response.json();
          app.tables.set(item.id, sheets);
        }
        const sheet = sheets[index] || { rows: [] };
        rows = sheet.rows || [];
        const header = rows[0] || [];
        const body = rows.slice(1);
        const columns = header.map((label, i) => ({
          label: String(label == null || label === '' ? `第${i + 1}列` : label),
          value: row => row && row[i],
          align: typeof (body[0] || [])[i] === 'number' ? 'num' : 'text',
          digits: 4
        }));
        host.innerHTML = '';
        table = new DataTable(host, { columns: columns.length ? columns : [{ label: '空表', value: () => '' }], pageSize: 50 });
        table.setRows(body);
        $('#dt-search').value = '';
        $('#dt-export').onclick = () => downloadCSV([header, ...rows.slice(1)], `${item.name}_${sheet.name}`);
      } catch (error) {
        host.innerHTML = `<div class="note danger">无法读取工作表数据：${esc(error.message)}。若你是以 file:// 方式打开页面，请改用桌面版或本地服务启动，浏览器会阻止读取同目录 JSON。</div>`;
      }
    };
    $('#dt-sheet').addEventListener('change', draw);
    $('#dt-search').addEventListener('input', event => {
      const query = event.target.value.trim().toLowerCase();
      const body = rows.slice(1);
      const filtered = query ? body.filter(row => row.some(v => String(v == null ? '' : v).toLowerCase().includes(query))) : body;
      if (table) table.setRows(filtered);
    });
    draw();
  }

  /* 3.12 区域工作台 */
  function govPage(regionName) {
    const region = regionName ? regionName.replace('地区', '') : '';
    const metric = metricOf(store.get('govMetric', 'agriShare'));
    view.innerHTML = pageHead(region ? `${region}地区 · 区域下钻` : '区域工作台', '按大区汇总，占比与人均类指标用合计值计算，不把各省百分比直接相加',
      `<select class="control" id="g-metric">${METRICS.map(m => `<option value="${m.id}">${m.label}</option>`).join('')}</select>`) +
      `<div class="filters">${['', ...REGIONS].map(r => `<a class="button ${r === region ? '' : 'secondary'}" href="#/gov-dashboard${r ? '/' + encodeURIComponent(r) : ''}">${r || '全部'}</a>`).join('')}</div>
      <div id="g-body"></div>`;
    $('#g-metric').value = metric.id;

    const draw = () => {
      const m = metricOf($('#g-metric').value);
      store.set('govMetric', m.id);
      const filter = row => !region || row['大区'] === region;
      const rows = rowsOfYear(latestYear()).filter(filter);
      const series = app.years.map(year => {
        const list = rowsOfYear(year).filter(filter);
        return list.length ? aggregate(list, m) : null;
      });
      const first = series.find(v => isNum(v));
      const last = series[series.length - 1];
      $('#g-body').innerHTML = kpiGrid([
        { label: '纳入省份', value: rows.length, unit: '个', note: region || '全国 31 个省级地区' },
        { label: `${latestYear()} 年 ${m.short}`, value: fmt(aggregate(rows, m), m.digits), unit: m.unit, note: m.note, accent: true },
        { label: '起始年值', value: fmt(first, m.digits), unit: m.unit, note: `${series.findIndex(v => isNum(v)) >= 0 ? app.years[series.findIndex(v => isNum(v))] : '—'} 年首个有效值` },
        { label: '首末变化', value: isNum(first) && isNum(last) ? fmt(last - first, m.digits) : '—', unit: m.unit, note: '绝对差，非百分比' }
      ]) +
        `<section class="panel"><div class="panel-head"><h2>${region || '全国'} · ${m.label}</h2><span class="subtle">省级合计计算</span></div>
        <div id="g-chart"></div></section>` +
        `<div class="section-bar"><h2>省份明细</h2><span class="subtle">按指标降序</span></div>
        <div class="province-grid">${rows.sort((a, b) => (b[m.field] || -Infinity) - (a[m.field] || -Infinity)).map(row =>
          `<a class="province-tile" href="#/province/${encodeURIComponent(row['省份'])}"><strong>${esc(row['省份'])}</strong><span>${esc(m.short)} ${fmt(row[m.field], m.digits)}${esc(m.unit)}</span></a>`).join('')}</div>`;
      Chart.mount($('#g-chart'), { series: [{ name: m.label, values: series }], labels: app.years.map(String), unit: m.unit, digits: m.digits, area: true, height: 300 });
    };
    $('#g-metric').addEventListener('change', draw);
    draw();
  }

  /* 3.13 种植成本测算 */
  function costPage() {
    const specs = [
      ['area', '种植面积（亩）', 10], ['yield', '亩产量（公斤/亩）', 500], ['price', '销售单价（元/公斤）', 3.2],
      ['seed', '种苗费用（元/亩）', 260], ['fert', '肥料农药（元/亩）', 480], ['labor', '人工费用（元/亩）', 620],
      ['rent', '土地租金（元/亩）', 400], ['other', '其他费用（元/亩）', 150]
    ];
    view.innerHTML = pageHead('种植成本测算', '按你填写的条件估算收支，不提供市场报价', `<button class="button secondary" id="ct-export">导出测算明细 CSV</button>`) +
      `<div class="note">全部成本与产量由你输入，未考虑补贴、税费、损耗、价格波动与自然灾害，不构成收益承诺。保本单价 = 每亩总成本 ÷ 亩产量。</div>
      <div class="calc-grid">${specs.map(([id, label, value]) => `<label class="field">${label}<input class="control" id="ct-${id}" type="number" min="0" step="any" value="${value}"></label>`).join('')}</div>
      <p id="ct-error" class="note danger" hidden></p>
      <div class="kpi-grid" id="ct-result"></div>
      <div class="two-cols">
        <section class="panel"><div class="panel-head"><h2>每亩成本结构</h2><span class="subtle">元/亩</span></div><div id="ct-structure"></div></section>
        <section class="panel"><div class="panel-head"><h2>单价敏感性</h2><span class="subtle">其他条件不变时的净收益</span></div><div id="ct-sens"></div></section>
      </div>`;

    let lastResult = null;
    const run = () => {
      const values = {};
      for (const [id] of specs) {
        const raw = $('#ct-' + id).value;
        const number = Number(raw);
        if (raw === '' || !Number.isFinite(number) || number < 0) {
          $('#ct-error').hidden = false;
          $('#ct-error').textContent = '请填写有效的非负数。';
          $('#ct-result').innerHTML = '';
          $('#ct-structure').innerHTML = '';
          $('#ct-sens').innerHTML = '';
          lastResult = null;
          return;
        }
        values[id] = number;
      }
      if (values.area <= 0) {
        $('#ct-error').hidden = false;
        $('#ct-error').textContent = '种植面积必须大于 0。';
        return;
      }
      $('#ct-error').hidden = true;
      const perMu = values.seed + values.fert + values.labor + values.rent + values.other;
      const totalCost = perMu * values.area;
      const revenue = values.yield * values.price * values.area;
      const profit = revenue - totalCost;
      const breakEven = values.yield > 0 ? perMu / values.yield : null;
      lastResult = { values, perMu, totalCost, revenue, profit, breakEven };

      $('#ct-result').innerHTML = [
        { label: '每亩总成本', value: fmt(perMu, 0), unit: '元', note: '五项费用相加' },
        { label: '总成本', value: fmt(totalCost, 0), unit: '元', note: `${values.area} 亩` },
        { label: '预计销售额', value: fmt(revenue, 0), unit: '元', note: '亩产 × 单价 × 面积' },
        { label: '条件下净收益', value: fmt(profit, 0), unit: '元', note: profit >= 0 ? '未扣税费与损耗' : '亏损情景', accent: true },
        { label: '保本单价', value: fmt(breakEven, 2), unit: '元/公斤', note: '低于此价即亏损' }
      ].map(kpiCard).join('');

      $('#ct-structure').innerHTML = listBars([
        { label: '种苗', value: values.seed }, { label: '肥料农药', value: values.fert },
        { label: '人工', value: values.labor }, { label: '租金', value: values.rent },
        { label: '其他', value: values.other }
      ], ' 元/亩', 0) + `<div class="chart-note">人工与租金占比越高，价格波动风险越大。</div>`;

      const factors = [0.7, 0.85, 1, 1.15, 1.3];
      $('#ct-sens').innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr><th>单价（元/公斤）</th><th class="num">销售额（元）</th><th class="num">净收益（元）</th><th>状态</th></tr></thead><tbody>${
        factors.map(f => {
          const price = values.price * f;
          const revenueAt = values.yield * price * values.area;
          const net = revenueAt - totalCost;
          return `<tr><td>${fmt(price, 2)}</td><td class="num">${fmt(revenueAt, 0)}</td><td class="num">${fmt(net, 0)}</td><td>${statusTag(net >= 0 ? '盈利' : '亏损', net >= 0 ? 'ok' : 'miss')}</td></tr>`;
        }).join('')}</tbody></table></div>`;
    };

    specs.forEach(([id]) => $('#ct-' + id).addEventListener('input', run));
    $('#ct-export').addEventListener('click', () => {
      if (!lastResult) { toast('请先填写有效参数', 'error'); return; }
      const { values, perMu, totalCost, revenue, profit, breakEven } = lastResult;
      downloadCSV([
        ['项目', '数值', '单位'],
        ...specs.map(([id, label]) => [label, values[id], '']),
        ['每亩总成本', perMu, '元/亩'], ['总成本', totalCost, '元'], ['预计销售额', revenue, '元'],
        ['条件下净收益', profit, '元'], ['保本单价', breakEven, '元/公斤']
      ], '智农宝_种植成本测算');
    });
    run();
  }

  /* 3.14 CSV 导入 */
  function uploadPage() {
    view.innerHTML = pageHead('CSV 数据导入', '文件只在当前浏览器内解析，不会上传到任何服务器', `<button class="button secondary" id="up-template">下载示例模板</button>`) +
      `<div class="panel"><label class="field">选择 UTF-8 CSV 文件（建议小于 5 MB）<input type="file" id="up-file" accept=".csv,text/csv"></label>
        <div class="filters" style="margin-top:10px"><button class="button ghost" type="button" id="up-clear">清空</button><span class="subtle" id="up-status">尚未选择文件</span></div></div>
      <div class="section-bar"><h2>列摘要</h2><span class="subtle">自动识别数值列并统计</span></div>
      <div id="up-summary"></div>
      <div class="section-bar"><h2>数据预览</h2><span class="subtle">最多 200 行</span></div>
      <div id="up-preview"></div>`;

    let parsed = [];
    const reset = () => {
      parsed = [];
      $('#up-file').value = '';
      $('#up-summary').innerHTML = '';
      $('#up-preview').innerHTML = '';
      $('#up-status').textContent = '尚未选择文件';
    };
    $('#up-clear').addEventListener('click', reset);
    $('#up-template').addEventListener('click', () => downloadCSV(
      [['年份', '省份', '指标', '数值', '单位', '来源'], [2024, '广东', '第一产业占GDP比重', 4.1, '%', '示例数据']], '智农宝_导入模板'));

    $('#up-file').addEventListener('change', event => {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) { $('#up-status').textContent = '文件超过 5 MB，已跳过。'; return; }
      Papa.parse(file, {
        skipEmptyLines: 'greedy', encoding: 'UTF-8',
        complete: result => {
          if (result.errors.length) { $('#up-status').textContent = '解析告警：' + result.errors[0].message; }
          parsed = result.data;
          $('#up-status').textContent = `${file.name} · ${parsed.length} 行 · 本地解析完成`;
          const header = parsed[0] || [];
          const body = parsed.slice(1);
          const summary = header.map((label, index) => {
            const values = body.map(row => Number(String(row[index] ?? '').replace(/,/g, ''))).filter(Number.isFinite);
            if (values.length < Math.max(3, body.length * 0.6)) return { label, type: '文本', detail: `${new Set(body.map(r => r[index])).size} 个不同取值` };
            const sum = values.reduce((s, v) => s + v, 0);
            return { label, type: '数值', detail: `最小 ${fmt(Math.min(...values), 2)} · 最大 ${fmt(Math.max(...values), 2)} · 均值 ${fmt(sum / values.length, 2)}` };
          });
          $('#up-summary').innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr><th>列名</th><th>识别类型</th><th>统计</th></tr></thead><tbody>${
            summary.map(item => `<tr><td>${esc(item.label)}</td><td>${statusTag(item.type, item.type === '数值' ? 'ok' : 'warn')}</td><td>${esc(item.detail)}</td></tr>`).join('')}</tbody></table></div>
            <div class="filters" style="margin-top:10px"><button class="button secondary" id="up-export">导出解析结果 CSV</button></div>`;
          $('#up-preview').innerHTML = `<div class="table-wrap"><table class="data-table"><tbody>${
            parsed.slice(0, 200).map(row => `<tr>${row.map(cell => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
          $('#up-export').onclick = () => downloadCSV(parsed, '智农宝_导入解析结果');
        },
        error: error => { $('#up-status').textContent = '解析失败：' + error.message; }
      });
    });
  }

  /* 3.15 功能与恢复进度 */
  function featuresPage() {
    const rows = [
      ['数据总览', '/data', 'ok', '已重建', '年份/大区筛选、排序、分页、CSV 导出、复制'],
      ['省域分布', '/map', 'ok', '已重建', '指标切换、年份滑块、矩阵热力（不使用行政边界）'],
      ['区域对比', '/compare', 'ok', '已重建', '最多四省同图、差值与复合增长率'],
      ['省份详情', '/province/广东', 'ok', '已重建', '多指标趋势、排名、迷你走势、导出'],
      ['作物指标', '/crop-data', 'ok', '资料接入', '31 省 30 类指标、叠加对比、推算年份标注'],
      ['宏观与劳动力', '/macro', 'ok', '资料接入', '宽表原值、缺失值保留、多指标叠加'],
      ['趋势预测', '/forecast', 'ok', '新实现', '本地最小二乘/指数外推，标注 R² 与边界'],
      ['模型与图表', '/model', 'ok', '历史成果', '24 张原项目图、分组检索、灯箱与下载'],
      ['数据集目录', '/datasets', 'ok', '已扩充', `${app.tableIndex.length} 份工作簿、逐表预览、检索分页、CSV/JSON 下载`],
      ['种植成本测算', '/farming-cost', 'ok', '新实现', '成本结构、保本价、单价敏感性'],
      ['种植防亏损决策', '/smart-plan', 'ok', '新实现', '保本价、预期利润、风险评级、AI 建议与敏感性矩阵'],
      ['产量与价格预测', '/predict', 'ok', '新实现', '作物单产/价格参考序列趋势外推与 AI 解读'],
      ['数字农田生态', '/digital-farm', 'ok', '新实现', '四情监测、气象、土壤墒情、长势分区、设备状态'],
      ['CSV 导入', '/data-upload', 'ok', '新实现', '本地解析、列摘要、导出，不上传'],
      ['区域工作台', '/gov-dashboard', 'ok', '已重建', '大区下钻、指标切换、省份明细'],
      ['桌面安装版', '/about', 'ok', '新增', 'Windows exe 安装器，双击启动本地服务'],
      ['项目与答辩', '/presentation', 'ok', '新增', '硕士毕设汇报结构：背景/目标/技术路线/成果/展望'],
      ['数据备份与恢复', '/recovery', 'ok', '新增', '备份恢复时间线、操作步骤、FAQ 与上传演示'],
      ['实时行情/价格预警', '/market-prices', 'miss', '未恢复', '未找到原行情数据源与后台接口'],
      ['AI 助手', '/ai-assistant', 'miss', '未恢复', '未找到原模型服务与凭据'],
      ['账号/管理后台', '/admin', 'miss', '未恢复', '未恢复用户数据库与认证体系'],
      ['政策库 / 国际对比', '/world', 'miss', '未恢复', '未找到可核验的条目数据']
    ];
    view.innerHTML = pageHead('功能与恢复进度', '区分“历史原件”“重建功能”和“仍然缺失的后台能力”') +
      `<div class="note warning">历史记录里能找到 Manus Electron 源码包的下载记录，但下载记录<strong>不等于</strong>包内源码已恢复。原站已下线，前后端工程仍不在本机。</div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>功能</th><th>状态</th><th>说明</th></tr></thead><tbody>${
        rows.map(([name, url, kind, label, detail]) => `<tr><td><a class="file-link" href="#${url}">${esc(name)}</a></td><td>${statusTag(label, kind === 'ok' ? 'ok' : 'miss')}</td><td>${esc(detail)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  /* 3.16 恢复说明 */
  function aboutPage() {
    const manifest = app.sourceManifest;
    const dashboard = app.dashboard;
    view.innerHTML = pageHead('恢复说明', '证据范围、数据口径、安装包信息与使用边界') +
      `<div class="two-cols">
        <section class="panel"><h2>已经恢复</h2><ul class="plain-list">
          <li>2026 年 5–6 月 Manus 站点访问记录与项目身份（路由清单）</li>
          <li>农业比赛主工作簿「${esc(dashboard.source)}」的 31 省经济面板</li>
          <li>31 省作物播种面积工作簿、24 张 V13.5 分析图</li>
          <li>${app.tableIndex.length} 份去重工作簿逐表内容与 SHA-256</li>
          <li>Claude 恢复记录中的早期 Flask 站点代码（归档在 recovery 目录，未直接上线）</li>
        </ul></section>
        <section class="panel"><h2>没有恢复</h2><ul class="plain-list">
          <li>Manus 原始前后端源码、数据库结构与部署配置</li>
          <li>已下线站点的完整页面快照与设计稿</li>
          <li>原站账号体系、实时行情接口、AI 服务</li>
          <li>与原站像素级一致的交互细节</li>
        </ul></section>
      </div>
      <div class="section-bar"><h2>数据口径</h2></div>
      <div class="panel">
        <dl class="def-list">
          <dt>面板来源</dt><dd>${esc(dashboard.source)} · 工作表「${esc(dashboard.source_sheet)}」</dd>
          <dt>记录范围</dt><dd>${app.years[0]}–${latestYear()} 年，${app.provinces.length} 个省级地区，${recordCount().toLocaleString('zh-CN')} 条</dd>
          <dt>占比计算</dt><dd>第一产业GDP 合计 ÷ 总GDP 合计，不是各省百分比的算术平均</dd>
          <dt>缺失处理</dt><dd>保留空值，不做插补；作物指标 ${CROP_IMPUTED_FROM} 年及以后标注“可能含推算”</dd>
          <dt>源文件数</dt><dd>${manifest.files.length} 份原始文件记录，去重后 ${app.tableIndex.length} 份可解析工作簿</dd>
          <dt>校验方式</dt><dd>每份文件记录 SHA-256，可在数据集目录逐项核对</dd>
        </dl>
        <div class="note warning" style="margin-top:12px">${esc(dashboard.note || '')}</div>
      </div>
      <div class="section-bar"><h2>桌面安装版</h2></div>
      <div class="panel">
        <dl class="def-list">
          <dt>启动方式</dt><dd>安装后从桌面或开始菜单打开「智农宝」，程序在本机 <code>127.0.0.1</code> 启动只读静态服务并唤起浏览器</dd>
          <dt>数据位置</dt><dd>全部数据随程序安装，不联网、不上传、不需要账号</dd>
          <dt>卸载</dt><dd>设置 → 应用 → 智农宝 → 卸载，或运行安装目录下的卸载入口</dd>
          <dt>分发提示</dt><dd>安装包内含比赛工作簿与对话恢复文档，对外分发前请确认数据授权范围</dd>
        </dl>
      </div>
      <div class="section-bar"><h2>版本</h2></div>
      <div class="panel"><dl class="def-list">
        <dt>站点版本</dt><dd>v${esc((window.__ZN_CORE__ && window.__ZN_CORE__.build && window.__ZN_CORE__.build.version) || '2.2.0')}（本次升级：农田插画视觉、种植防亏损决策、产量价格预测、数字农田生态大屏、项目与答辩页、数据备份与恢复页、hash 路由、命令面板、排序分页、多省对比、在线回归、灯箱与打印）</dd>
        <dt>构建时间</dt><dd>${esc((window.__ZN_CORE__ && window.__ZN_CORE__.build && window.__ZN_CORE__.build.built) || '构建信息未写入')}</dd>
        <dt>运行环境</dt><dd>Windows 10/11，Chromium 内核浏览器；也可用 python server.py 以源码方式运行</dd>
      </dl></div>`;
  }

  /* 3.14 种植防亏损决策 */
  function smartPlanPage() {
    const saved = store.get('smartPlan', {});
    const startCrop = cropOf(saved.crop || '水稻');

    view.innerHTML = pageHead('种植防亏损决策', '测算保本价、预期利润与风险等级，辅助种植决策') +
      `<div class="note warning">单产、价格、成本为<strong>演示用参考值</strong>（非官方统计），测算仅供决策演示，不构成投资建议。</div>
      <div class="two-cols">
        <section class="panel">
          <div class="panel-head"><h2>种植参数</h2></div>
          <div class="calc-grid">
            <label class="field">作物<select class="control" id="sp-crop">${AGRI_REF.crops.map(c => `<option value="${c.name}"${c.name === startCrop.name ? ' selected' : ''}>${c.name}</option>`).join('')}</select></label>
            <label class="field">种植面积（亩）<input class="control" id="sp-area" type="number" min="1" step="1" value="${saved.area || 100}"></label>
            <label class="field">预估单产（公斤/亩）<input class="control" id="sp-yield" type="number" min="1" step="1" value="${saved.yield ?? startCrop.yield}"></label>
            <label class="field">预期售价（元/公斤）<input class="control" id="sp-price" type="number" min="0" step="0.1" value="${saved.price ?? startCrop.price}"></label>
            <label class="field">每亩成本（元/亩）<input class="control" id="sp-cost" type="number" min="0" step="10" value="${saved.cost ?? startCrop.cost}"></label>
          </div>
          <div class="photo-card"><div class="photo" id="sp-img"></div><div class="photo-cap" id="sp-desc"></div></div>
          <div class="chart-note" style="margin-top:10px">切换作物会自动带出该作物的参考单产/价格/成本，可手工覆盖。</div>
        </section>
        <section>
          <div id="sp-risk"></div>
          <div class="kpi-grid" id="sp-kpi"></div>
          <div class="decision-box" id="sp-advice"></div>
        </section>
      </div>
      <div class="section-bar"><h2>敏感性分析</h2><span class="subtle">预期利润（元）随售价与单产 ±20% 变化</span></div>
      <div class="panel sensi-wrap"><div id="sp-sensi"></div></div>
      <div class="section-bar"><h2>决策口径</h2></div>
      <div class="panel"><ul class="plain-list">
        <li><strong>保本价</strong> = 每亩成本 ÷ 单产；售价高于保本价才有正利润。</li>
        <li><strong>保本单产</strong> = 每亩成本 ÷ 售价；单产低于保本单产即亏损。</li>
        <li><strong>风险评级</strong>：利润率 ≥15% 建议种植（绿），0–15% 谨慎（黄），&lt;0 不建议（红）。</li>
        <li>未计入人工机会成本、灾害与价格波动风险，实际请结合当地行情与农技建议。</li>
      </ul></div>`;

    const cropSel = $('#sp-crop'), area = $('#sp-area'), yieldIn = $('#sp-yield'), priceIn = $('#sp-price'), costIn = $('#sp-cost');

    const render = () => {
      const crop = cropOf(cropSel.value);
      const a = Number(area.value) || 0;
      const y = Number(yieldIn.value) || 0;
      const p = Number(priceIn.value) || 0;
      const c = Number(costIn.value) || 0;

      $('#sp-img').style.backgroundImage = `url('${imgUrl(crop.img)}')`;
      $('#sp-desc').innerHTML = `<strong>${esc(crop.name)}</strong> · ${esc(crop.region)} · ${esc(crop.season)}<div class="subtle">${esc(crop.desc)}</div>`;
      store.set('smartPlan', { crop: crop.name, area: a, yield: y, price: p, cost: c });

      if (a <= 0 || y <= 0 || p <= 0) {
        $('#sp-risk').innerHTML = ''; $('#sp-kpi').innerHTML = '';
        $('#sp-advice').innerHTML = '<div class="empty">请填写有效的面积、单产与价格。</div>';
        $('#sp-sensi').innerHTML = '';
        return;
      }

      const revenue = y * p * a;
      const totalCost = c * a;
      const profit = revenue - totalCost;
      const margin = totalCost > 0 ? profit / totalCost : 0;
      const breakEvenPrice = y > 0 ? c / y : null;
      const breakEvenYield = p > 0 ? c / p : null;
      const profitPerMu = y * p - c;

      let riskClass = 'risk-ok', riskIco = 'i-check', riskTitle = '建议种植', riskText = '预期利润率健康，具备抗风险空间';
      if (margin < 0) { riskClass = 'risk-bad'; riskIco = 'i-close'; riskTitle = '不建议种植'; riskText = '预期售价低于保本价，面临亏损风险'; }
      else if (margin < 0.15) { riskClass = 'risk-warn'; riskIco = 'i-info'; riskTitle = '谨慎种植'; riskText = '利润率偏低，抗价格波动能力弱'; }

      $('#sp-risk').innerHTML = `<div class="risk-banner ${riskClass}"><div class="risk-ico"><svg class="icon"><use href="#${riskIco}"/></svg></div><div><b>${riskTitle}</b><p>${riskText} · 预期利润率 ${fmt(margin * 100, 1)}%</p></div></div>`;

      $('#sp-kpi').innerHTML = [
        { label: '预计销售额', value: fmt(revenue, 0), unit: '元', note: `${fmt(y, 0)} 公斤/亩 × ${fmt(p, 1)} 元 × ${a} 亩` },
        { label: '总成本', value: fmt(totalCost, 0), unit: '元', note: `${fmt(c, 0)} 元/亩 × ${a} 亩` },
        { label: '预期利润', value: fmt(profit, 0), unit: '元', note: `${fmt(profitPerMu, 0)} 元/亩`, accent: true },
        { label: '保本价', value: fmt(breakEvenPrice, 2), unit: '元/公斤', note: '售价低于此价即亏损' },
        { label: '保本单产', value: fmt(breakEvenYield, 0), unit: '公斤/亩', note: '单产低于此值即亏损' }
      ].map(kpiCard).join('');

      const gap = p - breakEvenPrice;
      const advice = [`当前售价 ${fmt(p, 2)} 元/公斤，${gap >= 0 ? '高于' : '低于'}保本价 ${fmt(breakEvenPrice, 2)} 元/公斤 ${fmt(Math.abs(gap), 2)} 元。`];
      if (margin >= 0.15) {
        advice.push('利润率健康，可考虑扩大种植规模或锁定优质销售渠道。');
        advice.push('建议分批销售，避免集中上市导致价格回落。');
      } else if (margin >= 0) {
        advice.push('利润率偏薄，建议压低成本或争取更高收购价。');
        advice.push('可关注农业补贴与订单农业，锁定保底收益。');
      } else {
        advice.push('当前组合面临亏损，建议调整作物、压缩成本或等待更优价格窗口。');
        advice.push('可改种低成本作物或设施农业，提升单位产出。');
      }
      $('#sp-advice').innerHTML = `<div class="dc-head"><svg class="icon"><use href="#i-cpu"/></svg><b>AI 决策建议</b></div><ul>${advice.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;

      const pf = [0.8, 0.9, 1, 1.1, 1.2], yf = [0.8, 0.9, 1, 1.1, 1.2];
      const head = `<tr><th class="corner">售价 \\ 单产</th>${yf.map(f => `<th>${fmt(y * f, 0)}<br>公斤</th>`).join('')}</tr>`;
      const body = pf.map(fp => {
        const cells = yf.map(fy => {
          const net = (y * fy) * (p * fp) * a - totalCost;
          const cls = net > 0 ? 'gain' : net < 0 ? 'loss' : 'flat';
          return `<td class="${cls}">${fmt(net, 0)}</td>`;
        }).join('');
        return `<tr><th class="corner">${fmt(p * fp, 2)}<br>元/公斤</th>${cells}</tr>`;
      }).join('');
      $('#sp-sensi').innerHTML = `<table class="sensi-grid">${head}${body}</table>`;
    };

    cropSel.addEventListener('change', () => {
      const crop = cropOf(cropSel.value);
      yieldIn.value = crop.yield; priceIn.value = crop.price; costIn.value = crop.cost;
      render();
    });
    [area, yieldIn, priceIn, costIn].forEach(el => el.addEventListener('input', render));
    render();
  }

  /* 3.15 产量与价格预测 */
  function predictPage() {
    const saved = store.get('predict', {});
    const startCrop = cropOf(saved.crop || '水稻');
    const horizon = saved.horizon || 3;
    const HIST_END = 2025;

    view.innerHTML = pageHead('产量与价格预测', '基于作物历史参考序列的趋势外推（演示算法）') +
      `<div class="note warning">本页在浏览器内对<strong>演示用历史序列</strong>做最小二乘/指数外推，非官方产量/价格预测，不构成决策依据。</div>
      <div class="filters">
        <select class="control" id="pd-crop">${AGRI_REF.crops.map(c => `<option value="${c.name}"${c.name === startCrop.name ? ' selected' : ''}>${c.name}</option>`).join('')}</select>
        <select class="control" id="pd-target"><option value="yield">单产（公斤/亩）</option><option value="price">价格（元/公斤）</option></select>
        <select class="control" id="pd-method"><option value="linear">线性回归</option><option value="log">指数趋势</option></select>
        <div class="slider-row" style="flex:1 1 220px"><span>外推</span><input type="range" id="pd-horizon" min="1" max="5" step="1" value="${horizon}"><span id="pd-h-label"></span></div>
      </div>
      <div class="two-cols">
        <section class="panel"><div class="panel-head"><h2 id="pd-title"></h2><span class="subtle" id="pd-sub"></span></div><div id="pd-chart"></div></section>
        <section>
          <div class="kpi-grid" id="pd-kpi" style="grid-template-columns:1fr 1fr"></div>
          <div class="decision-box" id="pd-advice"></div>
        </section>
      </div>
      <div class="section-bar"><h2>逐年预测值</h2></div>
      <div id="pd-table"></div>`;

    const draw = () => {
      const crop = cropOf($('#pd-crop').value);
      const target = $('#pd-target').value;
      const method = $('#pd-method').value;
      const h = Number($('#pd-horizon').value);
      store.set('predict', { crop: crop.name, horizon: h });
      $('#pd-h-label').textContent = h + ' 年';

      const hist = target === 'yield' ? crop.yieldHist : crop.priceHist;
      const unit = target === 'yield' ? '公斤/亩' : '元/公斤';
      const digits = target === 'yield' ? 0 : 2;
      const histYears = Array.from({ length: AGRI_REF.histYears }, (_, i) => HIST_END - AGRI_REF.histYears + 1 + i);
      const points = histYears.map((yr, i) => [yr, hist[i]]);
      const model = method === 'log' ? Chart.fitLog(points) : Chart.fit(points);

      if (!model || points.length < 3) {
        $('#pd-chart').innerHTML = '<div class="empty">数据不足，无法拟合</div>';
        $('#pd-kpi').innerHTML = ''; $('#pd-advice').innerHTML = ''; $('#pd-table').innerHTML = '';
        return;
      }

      const futureYears = Array.from({ length: h }, (_, i) => HIST_END + 1 + i);
      const labels = histYears.map(String).concat(futureYears.map(String));
      const history = hist.concat(futureYears.map(() => null));
      const fitted = points.map(p => model.predict(p[0])).concat(futureYears.map(y => model.predict(y)));
      const future = hist.map(() => null).concat(futureYears.map(y => model.predict(y)));
      const lastPred = model.predict(HIST_END + h);
      const base = hist[hist.length - 1];

      $('#pd-title').textContent = `${crop.name} · ${target === 'yield' ? '单产' : '价格'}趋势与外推`;
      $('#pd-sub').textContent = `${crop.region} · ${method === 'log' ? '指数趋势' : '线性回归'} · 外推 ${h} 年至 ${HIST_END + h} 年`;

      $('#pd-kpi').innerHTML = [
        { label: '历史样本', value: points.length, unit: '年', note: `${histYears[0]}–${HIST_END}` },
        { label: '样本内 R²', value: fmt(model.r2, 3), note: '越接近 1 拟合越紧' },
        { label: method === 'log' ? '隐含年增长率' : '每年变化', value: fmt(method === 'log' ? model.growth * 100 : model.slope, 2), unit: method === 'log' ? '%' : unit + '/年' },
        { label: `${HIST_END + h} 年预测值`, value: fmt(lastPred, digits), unit, note: '外推越远越不可靠', accent: true }
      ].map(kpiCard).join('');

      const change = lastPred - base;
      const advice = [];
      if (target === 'yield') {
        advice.push(`参考单产预测 ${fmt(lastPred, 0)} ${unit}，较近期 ${fmt(base, 0)} ${change >= 0 ? '增长' : '下降'} ${fmt(Math.abs(change), 0)} ${unit}。`);
        advice.push('单产受品种、气候与管理影响较大，建议结合当地农技站实测数据校准。');
      } else {
        advice.push(`参考价格预测 ${fmt(lastPred, 2)} ${unit}，较近期 ${fmt(base, 2)} ${change >= 0 ? '上涨' : '下跌'} ${fmt(Math.abs(change), 2)} ${unit}。`);
        advice.push('价格波动剧烈，建议结合「种植防亏损」测算保本价，锁定销售时机。');
      }
      advice.push('本预测为演示算法输出，不构成投资建议。');
      $('#pd-advice').innerHTML = `<div class="dc-head"><svg class="icon"><use href="#i-cpu"/></svg><b>AI 解读</b></div><ul>${advice.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;

      Chart.mount($('#pd-chart'), {
        series: [
          { name: '历史值', values: history, color: '#2f7d4f' },
          { name: '模型拟合', values: fitted, color: '#829186', dash: '5 5' },
          { name: '外推', values: future, color: '#c8873a', dash: '6 4' }
        ], labels, unit, digits, height: 320
      });

      const tableRows = points.map(p => [p[0], p[1], model.predict(p[0]), '历史拟合'])
        .concat(futureYears.map(y => [y, null, model.predict(y), '外推']));
      new DataTable($('#pd-table'), {
        columns: [
          { label: '年份', value: r => r[0], align: 'num', plain: true },
          { label: '参考值', value: r => r[1], align: 'num', digits },
          { label: '模型值', value: r => r[2], align: 'num', digits },
          { label: '类型', value: r => r[3], render: (row, value) => statusTag(value, value === '外推' ? 'warn' : 'ok') }
        ], pageSize: 15, sort: { key: 0, dir: 1, index: 0 }
      }).setRows(tableRows);
    };

    ['#pd-crop', '#pd-target', '#pd-method'].forEach(sel => $(sel).addEventListener('change', draw));
    $('#pd-horizon').addEventListener('input', draw);
    draw();
  }

  /* 3.16 数字农田生态大屏 */
  function digitalFarmPage() {
    const f = FARM_SIM;
    const onlineCount = f.devices.filter(d => d.online).length;

    view.innerHTML = pageHead('数字农田生态', '四情监测、气象、土壤墒情、长势分区与设备状态一屏总览') +
      `<div class="farm-top rise" style="background-image:url('${imgUrl('farm-digital.jpg')}')">
        <div class="sim-badge" style="color:#fff;opacity:.92"><span class="dot"></span>模拟数据 · 实时刷新演示</div>
        <h1 style="color:#fff;margin:8px 0 4px">${esc(f.farm.name)} · 数字孪生</h1>
        <p style="color:rgba(234,247,238,.92);margin:0;font-size:13.5px">${f.note}</p>
        <div class="kpi-grid">
          <div class="kpi"><div class="kpi-label">地块数量</div><div class="kpi-value">${f.farm.plots}<span class="unit">块</span></div></div>
          <div class="kpi"><div class="kpi-label">种植面积</div><div class="kpi-value">${f.farm.area.toLocaleString('zh-CN')}<span class="unit">亩</span></div></div>
          <div class="kpi"><div class="kpi-label">作物种类</div><div class="kpi-value">${f.farm.cropKinds}<span class="unit">类</span></div></div>
          <div class="kpi"><div class="kpi-label">设备在线</div><div class="kpi-value">${onlineCount}<span class="unit">/ ${f.devices.length}</span></div></div>
        </div>
      </div>` +
      `<div class="section-bar"><h2>四情监测</h2><span class="subtle">苗情 · 墒情 · 虫情 · 灾情</span></div>
      <div class="quad-grid">${f.four.map(q => `
        <div class="quad-item">
          <div class="quad-head"><svg class="icon"><use href="#${q.icon}"/></svg><b>${q.key}</b><span class="status ${q.status}">${q.status === 'ok' ? '正常' : '关注'}</span></div>
          <div class="quad-val">${q.val}</div>
          <div class="metric-bar"><div class="track"><div class="fill ${q.status === 'warn' ? 'warn' : ''}" style="width:${q.pct}%"></div></div></div>
          <div class="quad-note">${esc(q.note)}</div>
        </div>`).join('')}</div>` +
      `<div class="two-cols">
        <section class="panel"><div class="panel-head"><h2>气象站实时监测</h2><span class="subtle">模拟 · 每 3 秒刷新</span></div>
          <div class="kpi-grid" style="grid-template-columns:1fr 1fr" id="df-weather-kpi"></div>
          <div class="panel-head" style="margin-top:14px"><h2>24 小时气温趋势</h2></div>
          <div id="df-weather-chart"></div>
        </section>
        <section class="panel"><div class="panel-head"><h2>土壤墒情</h2><span class="subtle">N / P / K / pH / 有机质 / 含水率</span></div>
          <div id="df-soil"></div>
        </section>
      </div>` +
      `<div class="two-cols">
        <section class="panel"><div class="panel-head"><h2>长势分区</h2><span class="subtle">借鉴 NDVI 分区概念</span></div>
          <div class="zone-strip">
            <span style="width:${f.growth.healthy}%;background:#2f9e58">健康 ${f.growth.healthy}%</span>
            <span style="width:${f.growth.attention}%;background:#e0a54a">需关注 ${f.growth.attention}%</span>
            <span style="width:${f.growth.critical}%;background:#c65b4e">危急 ${f.growth.critical}%</span>
          </div>
          <div class="zone-legend"><span><i style="background:#2f9e58"></i>健康 · 长势正常</span><span><i style="background:#e0a54a"></i>需关注 · 水分/养分不足</span><span><i style="background:#c65b4e"></i>危急 · 需立即处理</span></div>
        </section>
        <section class="panel"><div class="panel-head"><h2>农事任务</h2><span class="subtle">近期安排</span></div>
          <div id="df-tasks"></div>
        </section>
      </div>` +
      `<div class="section-bar"><h2>设备状态</h2></div>
      <div class="panel" id="df-devices"></div>`;

    const weatherRender = () => {
      $('#df-weather-kpi').innerHTML = [
        { label: '空气温度', value: fmt(f.weather.temp, 1), unit: '℃' },
        { label: '相对湿度', value: fmt(f.weather.humidity, 0), unit: '%' },
        { label: '累计降雨', value: fmt(f.weather.rainfall, 1), unit: 'mm' },
        { label: '风速', value: fmt(f.weather.wind, 1), unit: 'm/s' },
        { label: '光照强度', value: fmt(f.weather.light, 0), unit: 'lux' },
        { label: '土壤温度', value: fmt(f.weather.soilTemp, 1), unit: '℃' }
      ].map(kpiCard).join('');
    };
    weatherRender();

    const soilRender = () => {
      const items = [
        ['氮 (N)', f.soil.n, 120, 'mg/kg', ''], ['磷 (P)', f.soil.p, 80, 'mg/kg', ''],
        ['钾 (K)', f.soil.k, 200, 'mg/kg', ''], ['pH 值', f.soil.ph, 8, '', 'blue'],
        ['有机质', f.soil.organic, 5, '%', ''], ['含水率', f.soil.moisture, 100, '%', 'blue']
      ];
      $('#df-soil').innerHTML = items.map(([label, v, max, unit, extra]) => `
        <div class="metric-bar">
          <div class="mb-head"><span>${label}</span><b>${v} ${unit}</b></div>
          <div class="track"><div class="fill ${extra}" style="width:${Math.min(100, v / max * 100)}%"></div></div>
        </div>`).join('');
    };
    soilRender();

    $('#df-devices').innerHTML = f.devices.map(d => `
      <div class="device-row"><span class="dot ${d.online ? '' : 'off'}"></span><span>${esc(d.name)}</span><span class="subtle">${esc(d.type)}</span><span class="status ${d.online ? 'ok' : 'miss'}">${d.online ? '在线' : '离线'}</span></div>`).join('');

    $('#df-tasks').innerHTML = `<div class="timeline">${f.tasks.map(t => `
      <div class="tl-item ${t.done ? 'done' : ''}"><div class="tl-time">${t.date}</div><div class="tl-title">${esc(t.name)} <span class="pill">${t.done ? '已完成' : '待办'}</span></div></div>`).join('')}</div>`;

    Chart.mount($('#df-weather-chart'), { series: [{ name: '气温', values: f.weather24 }], labels: f.weather24.map((_, h) => h + '时'), unit: '℃', digits: 1, area: true, height: 240 });

    if (window.__dfTimer) clearInterval(window.__dfTimer);
    window.__dfTimer = setInterval(() => {
      if (!$('#df-weather-kpi')) { clearInterval(window.__dfTimer); return; }
      f.weather.temp = Math.round((f.weather.temp + (Math.random() - 0.5) * 0.3) * 10) / 10;
      f.weather.humidity = Math.round(Math.min(95, Math.max(40, f.weather.humidity + (Math.random() - 0.5) * 2)));
      f.soil.moisture = Math.round(Math.min(90, Math.max(20, f.soil.moisture + (Math.random() - 0.5) * 1)));
      weatherRender();
      soilRender();
    }, 3000);
  }

  /* 3.17 项目与答辩 */
  function presentationPage() {
    const year = latestYear();
    const rows = rowsOfYear(year);
    const share = aggregate(rows, 'agriShare');
    const features = [
      ['i-shield', '种植防亏损', '保本价、预期利润、风险评级与 AI 种植建议'],
      ['i-cpu', '产量价格预测', '作物单产/价格参考序列趋势外推与解读'],
      ['i-layers', '数字农田生态', '四情监测、气象、土壤、长势与设备大屏'],
      ['i-cloud', '数据总览', '年份/大区筛选、排序分页、CSV 导出'],
      ['i-chart', '区域对比', '最多四省同图对照与复合增长率'],
      ['i-rocket', '离线可交付', '静态站点 + Windows 安装版双形态']
    ];
    view.innerHTML =
      `<section class="hero rise">
        <div class="hero-kicker"><svg class="icon" aria-hidden="true"><use href="#i-grad"/></svg> 硕士毕业设计 · 数据可视化方向</div>
        <h1>基于多源农业面板数据的 <span class="grad-text">省级农业经济可视化分析平台</span></h1>
        <p class="hero-sub">面向农业政策研究与教学实训，整合 ${app.provinces.length} 个省级地区 ${app.years[0]}–${year} 年面板数据，构建从数据治理到可视化分析、再到离线交付的完整技术闭环。</p>
        <div class="hero-stats">
          <div class="hero-stat"><b>${app.provinces.length}</b><span>省级地区</span></div>
          <div class="hero-stat"><b>${app.years.length}</b><span>年份跨度</span></div>
          <div class="hero-stat"><b>${recordCount().toLocaleString('zh-CN')}</b><span>面板记录</span></div>
          <div class="hero-stat"><b>${app.tableIndex.length}</b><span>源工作簿</span></div>
          <div class="hero-stat"><b>${app.charts.length}</b><span>分析图</span></div>
        </div>
      </section>` +

      `<div class="section-bar"><h2>研究背景</h2></div>
      <div class="panel"><p class="lead">农业是国民经济的基础，但不同省份在产业结构、资源禀赋与政策环境上差异显著，传统农业数据多以分散表格存在，缺乏统一、直观、可交互的分析入口。本课题以「大数据设计大师」比赛数据集为基础，重建并扩写了一套省级农业经济可视化分析工作台，为农业决策者与研究者提供一站式的数据查询与可视化能力。</p></div>` +

      `<div class="section-bar"><h2>研究目标</h2></div>
      <div class="feature-grid">
        <div class="feature-card"><div class="fc-icon"><svg class="icon"><use href="#i-cloud"/></svg></div><b>统一数据入口</b><span>将分散的 ${app.tableIndex.length} 份工作簿治理为标准化面板数据</span></div>
        <div class="feature-card"><div class="fc-icon"><svg class="icon"><use href="#i-layers"/></svg></div><b>多维可视化</b><span>覆盖时间趋势、省域分布、区域对比与预测外推</span></div>
        <div class="feature-card"><div class="fc-icon"><svg class="icon"><use href="#i-cpu"/></svg></div><b>可交互分析</b><span>筛选、排序、下钻、导出与在线回归全流程</span></div>
        <div class="feature-card"><div class="fc-icon"><svg class="icon"><use href="#i-shield"/></svg></div><b>离线可交付</b><span>静态站点与 Windows 安装版双形态，开箱即用</span></div>
      </div>` +

      `<div class="section-bar"><h2>技术路线</h2></div>
      <div class="steps">
        <div class="step done"><div class="step-num">1</div><div class="step-title">数据采集与治理</div><div class="step-desc">汇总 ${app.tableIndex.length} 份工作簿，去重、校验 SHA-256、统一字段口径</div></div>
        <div class="step done"><div class="step-num">2</div><div class="step-title">指标工程</div><div class="step-desc">抽取 ${METRICS.length} 项核心指标，区分求和/比值/人均/平均口径</div></div>
        <div class="step done"><div class="step-num">3</div><div class="step-title">可视化建模</div><div class="step-desc">自研轻量 SVG 图表引擎，自适应渲染折线/柱状/热力</div></div>
        <div class="step done"><div class="step-num">4</div><div class="step-title">交互分析</div><div class="step-desc">hash 路由、命令面板、多省对比、CSV 导入导出</div></div>
        <div class="step done"><div class="step-num">5</div><div class="step-title">部署交付</div><div class="step-desc">离线静态站点 + PyInstaller 单文件 Windows 安装包</div></div>
      </div>` +

      `<div class="section-bar"><h2>系统架构</h2></div>
      <div class="arch">
        <div class="arch-row"><div class="arch-label">表现层</div><div class="arch-box">总览 · 数据总览 · 省域分布 · 区域对比 · 作物指标 · 趋势预测 · 成本测算 · 种植防亏损 · 产量价格预测 · 数字农田生态（21 个页面）</div></div>
        <div class="arch-row"><div class="arch-label">应用层</div><div class="arch-box">hash 路由 · 命令面板 · 数据表组件 · SVG 图表引擎 · 导入导出</div></div>
        <div class="arch-row primary"><div class="arch-label">数据层</div><div class="arch-box">dashboard.json · crops.json · table_index.json · chart_manifest.json</div></div>
        <div class="arch-row"><div class="arch-label">存储层</div><div class="arch-box">本机 JSON 静态数据 · localStorage 用户偏好</div></div>
      </div>` +

      `<div class="section-bar"><h2>核心功能</h2></div>
      <div class="feature-grid">${features.map(([icon, t, d]) => `<div class="feature-card"><div class="fc-icon"><svg class="icon"><use href="#${icon}"/></svg></div><b>${t}</b><span>${d}</span></div>`).join('')}</div>` +

      `<div class="section-bar"><h2>研究成果</h2></div>` +
      kpiGrid([
        { label: '数据规模', value: recordCount().toLocaleString('zh-CN'), unit: '条', note: `${app.provinces.length} 省 · ${app.years.length} 年面板` },
        { label: '源工作簿', value: app.tableIndex.length, unit: '份', note: '去重后可解析' },
        { label: '分析图表', value: app.charts.length, unit: '张', note: '历史成果 + 在线生成' },
        { label: `${year} 年一产占比`, value: fmt(share, 1), unit: '%', note: '合计值口径', accent: true }
      ]) +
      `<div class="note">以上指标均来自本机比赛工作簿实际数值，可前往「数据总览」「数据集目录」逐项复核。</div>` +

      `<div class="section-bar"><h2>创新点</h2></div>
      <div class="panel"><ul class="plain-list">
        <li><strong>口径透明：</strong>占比类指标用「合计值 ÷ 合计值」，人均用「GDP ÷ 人口」，并逐项标注计算方式，避免百分比平均的统计陷阱。</li>
        <li><strong>离线自包含：</strong>无构建、无框架、无后端，单文件 HTML + 原生 JS + 内嵌数据，双击即开，适合比赛现场演示与评审。</li>
        <li><strong>双形态交付：</strong>既可作为静态站点托管，也可打包为 Windows exe 安装包，兼顾公网访问与本地部署。</li>
        <li><strong>诚实的数据边界：</strong>明确区分「已恢复 / 未恢复 / 推算」，对缺失与推算数据显式标注，保证学术严谨性。</li>
      </ul></div>` +

      `<div class="section-bar"><h2>未来展望</h2></div>
      <div class="panel"><ul class="plain-list">
        <li>接入更多农业子类数据（价格、产量、气候），扩展指标维度。</li>
        <li>引入地理边界图，在合规前提下实现真正的地图可视化。</li>
        <li>补充后端服务，支持多用户协作与实时数据更新。</li>
      </ul></div>` +

      `<div class="divider"></div>
      <div class="note"><a class="file-link" href="#/about">查看数据口径与恢复边界</a> · <a class="file-link" href="#/recovery">数据备份与恢复说明</a> · <a class="file-link" href="#/datasets">浏览全部数据集</a></div>`;
  }

  /* 3.18 数据备份与恢复 */
  function recoveryPage() {
    view.innerHTML =
      `<section class="hero rise">
        <div class="hero-kicker"><svg class="icon" aria-hidden="true"><use href="#i-restore"/></svg> 数据恢复中心</div>
        <h1>备份已就绪 · <span class="grad-text">按顺序恢复您的数据</span></h1>
        <p class="hero-sub">系统按「数据备份 → 按计划删除 → 恢复数据」三个阶段管理您的数据。请严格按以下顺序操作，以完全恢复您的数据。</p>
        <div class="hero-actions"><a class="button light" href="#/data-upload">上传数据备份包</a><a class="button" href="#/datasets">查看已恢复数据集</a></div>
      </section>` +

      `<div class="section-bar"><h2>恢复时间线</h2></div>
      <div class="panel">
        <div class="timeline">
          <div class="tl-item done"><div class="tl-time">2026 年 8 月 11 日 21:00 — 8 月 23 日 8:00 (SGT)</div><div class="tl-title">数据备份 <span class="pill">已结束</span></div><div class="tl-body">备份 Manus 数据，以便将来恢复数据。</div></div>
          <div class="tl-item done"><div class="tl-time">2026 年 8 月 23 日 8:00 — 8 月 25 日 7:59 (SGT)</div><div class="tl-title">数据已按计划删除 <span class="pill">已结束</span></div><div class="tl-body">数据已按计划删除完毕。</div></div>
          <div class="tl-item"><div class="tl-time">2026 年 8 月 25 日 8:00 (SGT)</div><div class="tl-title">恢复您的数据 <span class="pill">进行中</span></div><div class="tl-body">请按顺序完成以下步骤，以完全恢复你的 Manus 数据。</div></div>
        </div>
      </div>` +

      `<div class="section-bar"><h2>恢复步骤</h2></div>
      <div class="steps">
        <div class="step current"><div class="step-num">1</div><div class="step-title">恢复账户</div><div class="step-desc">上传您的 .manusaccount 备份以恢复你的账户。</div></div>
        <div class="step disabled"><div class="step-num">2</div><div class="step-title">恢复任务</div><div class="step-desc">请先恢复您的账户，才能恢复任务。</div></div>
      </div>` +

      `<div class="section-bar"><h2>上传备份包</h2></div>
      <div class="panel">
        <button class="upload-zone" id="recovery-upload" type="button">
          <svg class="icon" aria-hidden="true"><use href="#i-upload"/></svg>
          <b>点击选择数据备份包</b>
          <small>支持一次选择多个原始备份包 · 系统自动去重 · 请勿修改、重命名或移动任何文件</small>
        </button>
        <input type="file" id="recovery-file" multiple hidden>
        <div id="recovery-progress"></div>
      </div>` +

      `<div class="section-bar"><h2>常见问题解答</h2></div>
      <div class="faq-list">
        <div class="faq-item"><button class="faq-q" type="button">我有多个数据备份包，在数据恢复时可以一次性全部上传吗？是否需要先合并或按顺序导入？<svg class="icon"><use href="#i-chevron"/></svg></button><div class="faq-a">您可以在一次恢复操作中同时上传多个原始数据备份包，系统会自动对内容进行去重处理。请勿提前合并数据备份包，也不要修改、重命名或移动任何文件，只需选择原始数据备份包进行上传即可。上传顺序没有要求。虽然您在备份时可以选择不同的任务，但数据恢复是基于数据备份包进行的，我们不保证能够按任务逐一恢复数据。</div></div>
        <div class="faq-item"><button class="faq-q" type="button">如果在成功恢复后发现数据备份中有数据缺失，可以再次进行恢复吗？<svg class="icon"><use href="#i-chevron"/></svg></button><div class="faq-a">可以。您可以在恢复完成后再次发起恢复操作，系统会与已有数据进行合并去重，避免重复写入。</div></div>
        <div class="faq-item"><button class="faq-q" type="button">数据恢复的时间范围是否有限制？<svg class="icon"><use href="#i-chevron"/></svg></button><div class="faq-a">恢复窗口与您备份数据的时间范围一致，超出备份范围的数据无法恢复。</div></div>
        <div class="faq-item"><button class="faq-q" type="button">是否可以只恢复任务数据而不恢复账户数据？<svg class="icon"><use href="#i-chevron"/></svg></button><div class="faq-a">不可以。任务数据依附于账户，必须先恢复账户，才能恢复任务数据。</div></div>
      </div>` +

      `<div class="note">如果您有任何问题，请随时联系客服，我们将竭诚为您提供帮助。</div>`;

    $$('#view .faq-q').forEach(q => q.addEventListener('click', () => q.parentElement.classList.toggle('open')));
    const fileInput = $('#recovery-file');
    const zone = $('#recovery-upload');
    if (zone && fileInput) {
      zone.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files || []);
        if (!files.length) return;
        const progress = $('#recovery-progress');
        progress.innerHTML = `<div class="progress"><span style="width:0%"></span></div><div class="chart-note" id="recovery-status">正在校验 ${files.length} 个备份包…</div>`;
        let pct = 0;
        const timer = setInterval(() => {
          pct += 12;
          const bar = $('#recovery-progress .progress span');
          if (bar) bar.style.width = Math.min(100, pct) + '%';
          if (pct >= 100) {
            clearInterval(timer);
            const status = $('#recovery-status');
            if (status) status.textContent = '校验完成 · 已完成去重合并（本机演示，未实际上传）';
            toast('数据备份包已就绪（演示）');
          }
        }, 160);
      });
    }
  }

  /* 3.19 缺省页 */
  function notFound(detail) {
    view.innerHTML = pageHead('未找到该页面', '可能是旧链接或未恢复的历史路由') +
      `<div class="panel"><p>${esc(detail || '这个地址没有对应内容。')}</p>
      <p class="subtle">原 Manus 站点的部分后台功能未在本机检出，因此不会伪造。</p>
      <a class="button" href="#/">返回总览</a></div>`;
  }

  /* ============================================================
     4. 命令面板
     ============================================================ */
  const palette = { open: false, items: [], active: 0 };

  function buildPaletteIndex() {
    const items = [];
    Object.keys(TITLES).forEach(path => items.push({ group: '页面', title: TITLES[path], meta: path, href: '#' + path }));
    app.provinces.forEach(name => items.push({ group: '省份', title: name, meta: '省份详情', href: '#/province/' + encodeURIComponent(name) }));
    METRICS.forEach(m => items.push({ group: '指标', title: m.label, meta: '省域分布', href: '#/map' }));
    app.charts.forEach(c => items.push({ group: '图表', title: c.name, meta: '灯箱查看', action: () => openLightbox(chartUrl(c.file), c.name) }));
    app.tableIndex.slice(0, 200).forEach(t => items.push({ group: '工作簿', title: t.name, meta: t.group, href: '#/dataset/' + encodeURIComponent(t.id) }));
    return items;
  }

  function openPalette() {
    palette.open = true;
    $('#palette').hidden = false;
    $('#palette-input').value = '';
    $('#palette-input').focus();
    renderPalette('');
  }

  function closePalette() {
    palette.open = false;
    $('#palette').hidden = true;
  }

  function renderPalette(query) {
    const index = palette.index || (palette.index = buildPaletteIndex());
    const q = query.trim().toLowerCase();
    let list = index;
    if (q) {
      list = index.map(item => {
        const title = item.title.toLowerCase();
        const score = title === q ? 0 : title.startsWith(q) ? 1 : title.includes(q) ? 2 : -1;
        return score < 0 ? null : { ...item, score };
      }).filter(Boolean).sort((a, b) => a.score - b.score).slice(0, 40);
    } else {
      list = index.filter(item => item.group === '页面').concat(index.filter(item => ['省份', '指标'].includes(item.group)).slice(0, 12));
    }
    palette.items = list;
    palette.active = 0;
    if (!list.length) {
      $('#palette-results').innerHTML = '<div class="palette-empty">没有匹配项</div>';
      return;
    }
    let html = '';
    let group = '';
    list.forEach((item, i) => {
      if (item.group !== group) { group = item.group; html += `<div class="palette-group">${esc(group)}</div>`; }
      html += `<div class="palette-item${i === 0 ? ' active' : ''}" data-index="${i}"><span>${esc(item.title)}</span><span class="meta">${esc(item.meta || '')}</span></div>`;
    });
    $('#palette-results').innerHTML = html;
    $$('#palette-results .palette-item').forEach(node => node.addEventListener('click', () => runPaletteItem(Number(node.dataset.index))));
  }

  function runPaletteItem(index) {
    const item = palette.items[index];
    if (!item) return;
    closePalette();
    if (item.action) item.action();
    else if (item.href) navigate(item.href.replace(/^#/, ''));
  }

  function movePalette(delta) {
    if (!palette.items.length) return;
    palette.active = (palette.active + delta + palette.items.length) % palette.items.length;
    $$('#palette-results .palette-item').forEach((node, i) => node.classList.toggle('active', i === palette.active));
    const active = $('#palette-results .palette-item.active');
    if (active) active.scrollIntoView({ block: 'nearest' });
  }

  /* ============================================================
     5. 路由
     ============================================================ */
  const ROUTES = {
    '/': overviewPage, '/data': dataPage, '/map': mapPage, '/compare': comparePage,
    '/crop-data': cropPage, '/macro': macroPage, '/forecast': forecastPage, '/model': modelPage,
    '/datasets': datasetsPage, '/features': featuresPage, '/about': aboutPage,
    '/farming-cost': costPage, '/data-upload': uploadPage, '/gov-dashboard': () => govPage(''),
    '/smart-plan': smartPlanPage, '/predict': predictPage, '/digital-farm': digitalFarmPage,
    '/presentation': presentationPage, '/recovery': recoveryPage
  };

  function currentPath() {
    const hash = location.hash.replace(/^#!?/, '');
    if (hash) return normalize(hash);
    const pathname = location.pathname.replace(/index\.html$/i, '');
    if (pathname && pathname !== '/' && !location.protocol.startsWith('file')) {
      history.replaceState(null, '', '/#' + pathname);
      return normalize(pathname);
    }
    return '/';
  }

  function normalize(path) {
    let value = path.startsWith('/') ? path : '/' + path;
    if (value.length > 1 && value.endsWith('/')) value = value.slice(0, -1);
    return value;
  }

  function navigate(path) {
    const target = normalize(path || '/');
    if (currentPath() === target) { render(); return; }
    location.hash = '#' + target;
  }

  function titleOf(path) {
    if (TITLES[path]) return TITLES[path];
    if (path.startsWith('/province/')) return '省份详情';
    if (path.startsWith('/region/')) return '区域下钻';
    if (path.startsWith('/dataset/')) return '工作簿预览';
    if (path === '/gov-dashboard') return TITLES['/gov-dashboard'];
    return '未找到';
  }

  function render() {
    const path = currentPath();
    const title = titleOf(path);
    let handler = ROUTES[path];
    let param = null;
    if (!handler) {
      if (path.startsWith('/province/')) { handler = provincePage; param = decodeURIComponent(path.slice(10)); }
      else if (path.startsWith('/dataset/')) { handler = datasetDetailPage; param = decodeURIComponent(path.slice(9)); }
      else if (path.startsWith('/region/')) { handler = govPage; param = decodeURIComponent(path.slice(8)); }
      else if (path.startsWith('/gov-dashboard/')) { handler = govPage; param = decodeURIComponent(path.slice(15)); }
    }

    crumb.textContent = title;
    document.title = `${title} · 智农宝`;
    $$('.nav a[data-route]').forEach(link => {
      const route = link.dataset.route;
      const active = route === '/' ? path === '/' : path === route || path.startsWith(route + '/');
      link.classList.toggle('active', active);
    });
    sidebar.classList.remove('open');
    view.innerHTML = '';
    if (handler) {
      try { handler(param, path); }
      catch (error) {
        view.innerHTML = pageHead('页面渲染失败', error.message) + `<div class="panel"><p>${esc(error.stack || '')}</p></div>`;
        console.error(error);
      }
    } else {
      notFound(`地址 “${path}” 没有对应的本地数据。`);
    }
    window.scrollTo(0, 0);
  }

  /* ============================================================
     6. 全局事件
     ============================================================ */
  function bindChartOpeners() {
    $$('[data-open-chart]').forEach(node => {
      node.addEventListener('click', () => openLightbox(chartUrl(node.dataset.openChart), node.dataset.title));
    });
  }

  function bindShell() {
    $('#menu-button').addEventListener('click', () => sidebar.classList.toggle('open'));
    $('#open-search').addEventListener('click', openPalette);
    $('#open-search-2').addEventListener('click', openPalette);
    $('#print-button').addEventListener('click', () => window.print());
    $('#lightbox-close').addEventListener('click', closeLightbox);
    $('#lightbox').addEventListener('click', event => { if (event.target.id === 'lightbox') closeLightbox(); });
    $('#palette').addEventListener('click', event => { if (event.target.id === 'palette') closePalette(); });
    $('#palette-input').addEventListener('input', event => renderPalette(event.target.value));

    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); palette.open ? closePalette() : openPalette(); return; }
      if (event.key === 'Escape') { if (palette.open) closePalette(); else if (!$('#lightbox').hidden) closeLightbox(); return; }
      if (palette.open) {
        if (event.key === 'ArrowDown') { event.preventDefault(); movePalette(1); }
        else if (event.key === 'ArrowUp') { event.preventDefault(); movePalette(-1); }
        else if (event.key === 'Enter') { event.preventDefault(); runPaletteItem(palette.active); }
      }
    });

    window.addEventListener('hashchange', render);
    window.addEventListener('scroll', () => { $('#to-top').hidden = window.scrollY < 420; }, { passive: true });
    $('#to-top').addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    document.addEventListener('click', event => {
      const link = event.target.closest('a[href^="#"]');
      if (!link) return;
      if (link.getAttribute('href') === '#') { event.preventDefault(); return; }
      sidebar.classList.remove('open');
    });
  }

  /* ============================================================
     7. 启动
     ============================================================ */
  async function boot() {
    bindShell();
    try {
      await loadData();
    } catch (error) {
      view.innerHTML = pageHead('数据载入失败', error.message) +
        `<div class="panel"><p>请确认 <code>site/data/</code> 下的 JSON 与 <code>core-data.js</code> 完整。</p>
        <p class="subtle">源码方式运行时执行：<code>python server.py</code>；安装版直接双击桌面「智农宝」。</p></div>`;
      return;
    }
    palette.index = null;
    render();
    /* 心跳：桌面版据此判断“还有页面开着”，全部关闭后才会空闲退出 */
    if (location.protocol.startsWith('http')) {
      setInterval(() => { fetch('__zn/health', { cache: 'no-store' }).catch(() => {}); }, 120000);
    }
    if (app.coreOnly && location.protocol === 'file:') {
      toast('当前为 file:// 直接打开模式，工作簿逐表预览需使用安装版');
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
