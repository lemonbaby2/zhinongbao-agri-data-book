/* 轻量 SVG 图表库（无第三方依赖）
   只做这个站点需要的折线、迷你趋势图与最小二乘拟合。
   所有输出都是字符串，调用方直接塞进 innerHTML。 */
(function (global) {
  'use strict';

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const isNum = v => typeof v === 'number' && Number.isFinite(v);

  const PALETTE = ['#2f7d4f', '#c8873a', '#3f6f9c', '#9a5b8f', '#5b8d3f', '#a8543f'];

  function fmt(value, digits = 1) {
    if (!isNum(value)) return '—';
    return value.toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
  }

  function compact(value) {
    if (!isNum(value)) return '';
    const abs = Math.abs(value);
    if (abs >= 100000000) return fmt(value / 100000000, 2) + '亿';
    if (abs >= 10000) return fmt(value / 10000, abs >= 100000 ? 0 : 1) + '万';
    return fmt(value, abs >= 100 ? 0 : 1);
  }

  /* 生成“好看”的坐标刻度：1/2/2.5/5 × 10^n 步长 */
  function scale(min, max, count) {
    count = count || 4;
    if (!isNum(min) || !isNum(max)) return { min: 0, max: 1, ticks: [0, 1] };
    if (min === max) { const pad = Math.abs(min) || 1; min -= pad; max += pad; }
    const rough = (max - min) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    const norm = rough / mag;
    const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
    let lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    /* 全为非负数据时不要把下限拉到负数，否则会出现一条没用的负刻度带 */
    if (min >= 0 && lo < 0) lo = 0;
    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v / step) * step);
    return { min: lo, max: hi, ticks };
  }

  /* 折线图
     opts: { series:[{name, values:[], color, dash, kind}], labels:[], unit, digits,
             height, yZero, bands:[{from,to,label}], legend:true, marker:true } */
  function line(opts) {
    const o = opts || {};
    const series = (o.series || []).filter(s => Array.isArray(s.values));
    const labels = o.labels || [];
    if (!series.length || !labels.length) return '<div class="empty">没有可绘制的数据</div>';

    const all = series.flatMap(s => s.values.filter(isNum));
    if (!all.length) return '<div class="empty">没有可绘制的数据</div>';

    let min = Math.min(...all);
    let max = Math.max(...all);
    if (o.yZero) min = Math.min(0, min);
    const sc = scale(min, max, 4);

    const W = o.width || 940, H = o.height || 320;
    const padL = 58, padR = 20, padT = 16, padB = 34;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;
    const n = labels.length;
    const x = i => padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = v => padT + innerH - ((v - sc.min) / (sc.max - sc.min || 1)) * innerH;

    /* 背景色带（例如“可能含推算”的年份） */
    const bands = (o.bands || []).map(b => {
      const x1 = x(Math.max(0, b.from));
      const x2 = x(Math.min(n - 1, b.to));
      return `<rect x="${x1.toFixed(1)}" y="${padT}" width="${Math.max(2, x2 - x1).toFixed(1)}" height="${innerH}" fill="${b.color || '#c8873a'}" opacity=".09"/>` +
        (b.label ? `<text x="${((x1 + x2) / 2).toFixed(1)}" y="${padT + 12}" text-anchor="middle" font-size="11" fill="#a9742c">${esc(b.label)}</text>` : '');
    }).join('');

    const grid = sc.ticks.map(v => {
      const yy = y(v).toFixed(1);
      return `<line x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}" stroke="#e9f0e6" stroke-width="1"/>` +
        `<text x="${padL - 9}" y="${(Number(yy) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#829186">${compact(v)}</text>`;
    }).join('');

    /* X 轴刻度：均匀取样，但避免最后一个年份和倒数第二个标签挤在一起 */
    const step = Math.max(1, Math.ceil(n / 8));
    const tickIndices = [];
    for (let i = 0; i < n; i += step) tickIndices.push(i);
    const lastIndex = n - 1;
    if (tickIndices[tickIndices.length - 1] !== lastIndex) {
      if (lastIndex - tickIndices[tickIndices.length - 1] >= step * 0.6) tickIndices.push(lastIndex);
      else tickIndices[tickIndices.length - 1] = lastIndex;
    }
    const xTicks = tickIndices.map(i =>
      `<text x="${x(i).toFixed(1)}" y="${H - 12}" text-anchor="middle" font-size="11" fill="#829186">${esc(labels[i])}</text>`).join('');

    const paths = series.map((s, k) => {
      const color = s.color || PALETTE[k % PALETTE.length];
      const dash = s.dash ? ` stroke-dasharray="${s.dash}"` : '';
      let d = '', started = false, area = '', run = [];
      s.values.forEach((v, i) => {
        if (isNum(v)) {
          d += `${started ? ' L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
          started = true;
          run.push([i, v]);
        } else {
          started = false;
          if (run.length > 1 && o.area && series.length === 1) area += areaPath(run, x, y, padT + innerH);
          run = [];
        }
      });
      if (run.length > 1 && o.area && series.length === 1) area += areaPath(run, x, y, padT + innerH);
      const markers = o.marker === false ? '' : s.values.map((v, i) => isNum(v)
        ? `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="9" fill="transparent"><title>${esc(s.name)} · ${esc(labels[i])}：${fmt(v, o.digits)}${esc(o.unit || '')}</title></circle>`
        : '').join('');
      return area + `<path d="${d}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"${dash}/>` + markers;
    }).join('');

    const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || '趋势折线图')}" xmlns="http://www.w3.org/2000/svg">` +
      bands + grid + xTicks + paths +
      (o.unit ? `<text x="${padL}" y="${padT - 2}" font-size="11" fill="#829186">单位：${esc(o.unit)}</text>` : '') +
      `</svg>`;

    const legend = o.legend === false || series.length < 2 ? '' : `<div class="chart-legend">${series.map((s, k) => {
      const color = s.color || PALETTE[k % PALETTE.length];
      return `<span class="key"><span class="swatch" style="background:${color}"></span>${esc(s.name)}</span>`;
    }).join('')}</div>`;

    return `<div class="chart-box">${svg}${legend}</div>`;
  }

  function areaPath(run, x, y, base) {
    const top = run.map(([i, v]) => `${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' L');
    const first = run[0][0], last = run[run.length - 1][0];
    return `<path d="M${x(first).toFixed(1)} ${base} L${top} L${x(last).toFixed(1)} ${base} Z" fill="#2f7d4f" opacity=".08"/>`;
  }

  /* 迷你趋势线（省份卡片、KPI 辅助） */
  function spark(values, opts) {
    const o = opts || {};
    const nums = (values || []).map(v => (isNum(v) ? v : null));
    const finite = nums.filter(isNum);
    if (finite.length < 2) return '<div class="empty" style="padding:8px">数据不足</div>';
    const W = 220, H = o.height || 42, pad = 3;
    const min = Math.min(...finite), max = Math.max(...finite);
    const x = i => pad + (i / (nums.length - 1)) * (W - pad * 2);
    const y = v => H - pad - ((v - min) / (max - min || 1)) * (H - pad * 2);
    let d = '', started = false;
    nums.forEach((v, i) => {
      if (isNum(v)) { d += `${started ? ' L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`; started = true; }
      else started = false;
    });
    const color = o.color || '#2f7d4f';
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">` +
      `<path d="${d}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round"/></svg>`;
  }

  /* 最小二乘线性拟合 */
  function fit(points) {
    const pts = (points || []).filter(p => isNum(p[0]) && isNum(p[1]));
    const n = pts.length;
    if (n < 2) return null;
    const sx = pts.reduce((s, p) => s + p[0], 0);
    const sy = pts.reduce((s, p) => s + p[1], 0);
    const sxx = pts.reduce((s, p) => s + p[0] * p[0], 0);
    const sxy = pts.reduce((s, p) => s + p[0] * p[1], 0);
    const denom = n * sxx - sx * sx;
    if (!denom) return null;
    const slope = (n * sxy - sx * sy) / denom;
    const intercept = (sy - slope * sx) / n;
    const meanY = sy / n;
    const ssTot = pts.reduce((s, p) => s + Math.pow(p[1] - meanY, 2), 0);
    const ssRes = pts.reduce((s, p) => s + Math.pow(p[1] - (slope * p[0] + intercept), 2), 0);
    const r2 = ssTot ? 1 - ssRes / ssTot : null;
    return { n, slope, intercept, r2, predict: value => slope * value + intercept };
  }

  /* 对数线性（等价于复合增长率）拟合：y = a·e^(b·x) */
  function fitLog(points) {
    const pts = (points || []).filter(p => isNum(p[0]) && isNum(p[1]) && p[1] > 0);
    if (pts.length < 2) return null;
    const inner = fit(pts.map(p => [p[0], Math.log(p[1])]));
    if (!inner) return null;
    return {
      n: inner.n,
      r2: inner.r2,
      growth: Math.exp(inner.slope) - 1,
      predict: value => Math.exp(inner.predict(value))
    };
  }

  /* 挂载折线图：按容器实际宽度渲染，保证字号接近 1:1，窗口变化时防抖重绘 */
  function mount(el, spec) {
    if (!el) return;
    const render = () => {
      const width = Math.max(280, Math.round(el.clientWidth || el.parentElement?.clientWidth || 940));
      el.innerHTML = line({ ...spec, width });
    };
    render();
    if (typeof ResizeObserver === 'undefined') return;
    if (el.__znObserver) el.__znObserver.disconnect();
    let lastWidth = el.clientWidth;
    let timer = 0;
    const observer = new ResizeObserver(() => {
      const width = el.clientWidth;
      if (Math.abs(width - lastWidth) < 10) return;
      lastWidth = width;
      clearTimeout(timer);
      timer = setTimeout(render, 140);
    });
    observer.observe(el);
    el.__znObserver = observer;
  }

  global.Chart = { line, mount, spark, fit, fitLog, fmt, compact, esc, PALETTE, isNum };
})(window);
