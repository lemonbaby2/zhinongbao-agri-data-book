/* 智农宝 · 卷分类分部分演示（part0 → part1..part4）
 * 参考「数据展示系统」框架的 part 分屏演示：每部一个主题大屏，
 * echarts 图表 + 数字翻牌 + 时间轴 + 关键词标注 + 触摸反馈。
 * 依赖：window.__ZN_BOOKPARTS__ 暴露 init(view, ctx, helpers)
 */
(function () {
  'use strict';

  // 书的四部分类（与 content/typography.py 同源）
  var PARTS = [
    { id: 'part1', no: 'Ⅰ', title: '国土与数据', en: 'LAND & DATA', theme: '#1f9d55', theme2: '#0f7a44',
      lead: '从 31 省面板到岭南 21 市，先看清脚下的土地。',
      desc: '一部关于尺度的书：45 年、31 省、21 市。数据是它的经纬，地图是它的骨架。',
      tags: ['31省面板', '1980—2024', '岭南21市', '市域版图'], vols: ['vol1', 'vol5'], img: 'guangdong_map' },
    { id: 'part2', no: 'Ⅱ', title: '作物与田畴', en: 'CROPS & FIELDS', theme: '#b07d2b', theme2: '#7d5715',
      lead: '一粒种子里，藏着播种面积、产量与市场的全部秘密。',
      desc: '茶叶、粮食、果蔬——每一种作物都是一段自然与人的博弈史，用数据读懂它的脾气。',
      tags: ['播种面积', '茶香数据志', '产量', '市场'], vols: ['vol2', 'vol3'], img: 'tea_garden' },
    { id: 'part3', no: 'Ⅲ', title: '预测与决策', en: 'FORECAST & DECISION', theme: '#3d7ab5', theme2: '#24568a',
      lead: '让数据替农民先算一遍账，少亏一次就是多赚一季。',
      desc: '预测不是算命，是把不确定性压缩成可执行的三个动作：做什么、不做什么、何时收手。',
      tags: ['防亏损', '保本测算', '价格预测', '决策Agent', '算法精准干预', '保本价', '止损线'], vols: ['vol4', 'vol8'], img: 'dashboard' },
    { id: 'part4', no: 'Ⅳ', title: '四十八年长卷', en: '48 YEARS', theme: '#a3412f', theme2: '#71291c',
      lead: '1978—2026，一条田埂上的中国：从生存到未来。',
      desc: '全书压卷之作。10 章 × 20 页，用官方长面板讲述一场仍未结束的农村实验。',
      tags: ['1978—2026', '10章200页', '改革开放', '决策系统'], vols: ['vol6', 'vol7'], img: 'reform_timeline' }
  ];

  var KW = {
    policy: ['家庭联产承包责任制','改革开放','乡村振兴','农业现代化','脱贫攻坚','全面小康','三权分置','土地流转','取消农业税','一号文件','城镇化','粮食安全','耕地红线','粮食安全','数字乡村','共同富裕','供给侧结构性改革'],
    metric: ['第一产业增加值','农林牧渔业总产值','农村居民人均可支配收入','恩格尔系数','粮食产量','播种面积','复合增长率','人均','占比','产值','产量'],
    decision: ['防亏损','保本','止损','风险','预警','底线','切忌','警示','非官方统计','模型外推','幻觉','结论','建议']
  };
  var NUMRE = /(\d[\d,，]*\.?\d*)\s*(亿元|万吨|万亩|万人|元|%|倍|年|个点)/g;
  var YRRE = /(19[7-9]\d|20[0-2]\d)\s*年?/g;

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  // 关键词标注：制度红 / 指标蓝 / 决断金；年份数字 Times New Roman
  function mark(text) {
    if (text == null) return '';
    var s = esc(text), slots = [];
    function hold(html) { slots.push(html); return '\x00' + (slots.length - 1) + '\x00'; }
    Object.keys(KW).forEach(function (kind) {
      KW[kind].forEach(function (w) {
        var color = { policy: '#a3412f', metric: '#2f6094', decision: '#9a6b12' }[kind];
        s = s.split(w).join(hold('<b style="color:' + color + '">' + w + '</b>'));
      });
    });
    s = s.replace(NUMRE, function (m) { return hold('<b class="tnr">' + m + '</b>'); });
    s = s.replace(YRRE, function (m) { return hold('<b class="tnr">' + m + '</b>'); });
    slots.forEach(function (frag, i) { s = s.split('\x00' + i + '\x00').join(frag); });
    return s;
  }

  function bookOf(ctx, vid) { return (ctx.books || []).filter(function (b) { return b.id === vid; })[0]; }

  // ----------------------------------------------------------------------
  // part0 总目：4 部 3D 翻转卡片（参考 part2-0/index.html 的 stage/scene）
  // ----------------------------------------------------------------------
  function renderIndex(view, ctx, H) {
    view.innerHTML =
      '<style>' + css() + '</style>' +
      '<div class="bp-wrap">' +
      '  <div class="bp-hero" style="background-image:linear-gradient(90deg,rgba(15,107,63,.96) 0%,rgba(15,107,63,.82) 52%,rgba(15,107,63,.14) 100%),url(assets/img3d/smart_farm.jpg);background-size:cover;background-position:right center">' +
      '    <div class="bp-hero-tag">智农宝 · 农业数据全书</div>' +
      '    <h1 class="bp-hero-title">八卷之书，四部之旅</h1>' +
      '    <p class="bp-hero-sub">从国土数据到算法精准干预 —— 卷八 5 章 100 页写清决策链路 —— 点击任一「部」进入分屏演示</p>' +
      '    <div class="bp-hero-stats"><span>4 部</span><span>8 卷</span><span>40 章</span><span>300 页真书</span></div>' +
      '  </div>' +
      '  <div class="bp-stage">' + PARTS.map(function (p) {
        return '<div class="bp-scene" data-part="' + p.id + '" style="--pc:' + p.theme + ';--pc2:' + p.theme2 + '">' +
          '  <div class="bp-card">' +
          '    <div class="bp-face bp-front">' +
          '      <div class="bp-no">' + p.no + '</div>' +
          '      <div class="bp-en">' + p.en + '</div>' +
          '      <h2 class="bp-ct">' + esc(p.title) + '</h2>' +
          '      <p class="bp-lead">' + mark(p.lead) + '</p>' +
          '      <div class="bp-vols">' + p.vols.map(function (v) { var b = bookOf(ctx, v); return esc(b ? b.title : v); }).join(' · ') + '</div>' +
          '      <div class="bp-enter">点击进入 →</div>' +
          '    </div>' +
          '    <div class="bp-face bp-back">' +
          '      <h3>' + esc(p.title) + '</h3>' +
          '      <p>' + mark(p.desc) + '</p>' +
          '      <div class="bp-tags">' + p.tags.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join('') + '</div>' +
          '      <div class="bp-enter">进入分屏 →</div>' +
          '    </div>' +
          '  </div>' +
          '</div>';
      }).join('') + '</div>' +
      '  <div class="bp-footnote">本目录按主题将七卷归为四部 · 每一部都有独立的数据大屏与交互演示</div>' +
      '</div>';

    // 触摸/悬停翻转 + 点击进入
    Array.prototype.forEach.call(view.querySelectorAll('.bp-scene'), function (el) {
      el.addEventListener('click', function () {
        var id = el.getAttribute('data-part');
        if (location.hash !== '#/part/' + id) location.hash = '#/part/' + id;
      });
      el.addEventListener('mouseenter', function () { try { H.sfx && H.sfx('tick'); } catch (e) {} });
    });
  }

  // ----------------------------------------------------------------------
  // part1..part4 分屏大屏
  // ----------------------------------------------------------------------
  function renderPart(view, ctx, H, pid) {
    var p = PARTS.filter(function (x) { return x.id === pid; })[0];
    if (!p) { renderIndex(view, ctx, H); return; }
    var ec = window.echarts;
    view.innerHTML =
      '<style>' + css() + '</style>' +
      '<div class="bp-wrap bp-part" style="--pc:' + p.theme + ';--pc2:' + p.theme2 + '">' +
      '  <div class="bp-part-head">' +
      '    <a class="bp-backlink" href="#/parts">← 返回总目</a>' +
      '    <div class="bp-part-tag">第 ' + p.no + ' 部 · ' + p.en + '</div>' +
      '    <h1 class="bp-part-title">' + esc(p.title) + '</h1>' +
      '    <p class="bp-part-lead">' + mark(p.lead) + '</p>' +
      '  </div>' +
      '  <div class="bp-banner" style="background-image:url(assets/img3d/' + p.img + '.jpg)">' +
      '    <div class="bp-banner-cap"><b>' + esc(p.title) + '</b> · ' + esc(p.en) + '</div>' +
      '  </div>' +
      '  <div class="bp-kpi" id="bp-kpi"></div>' +
      '  <div class="bp-grid">' +
      '    <section class="bp-panel span2"><div class="bp-panel-h"><h3 id="bp-c1t">主图</h3><span class="bp-pill" id="bp-pill1"></span></div><div id="bp-c1" class="bp-chart"></div></section>' +
      '    <section class="bp-panel"><div class="bp-panel-h"><h3 id="bp-c2t">结构</h3></div><div id="bp-c2" class="bp-chart"></div></section>' +
      '    <section class="bp-panel"><div class="bp-panel-h"><h3>卷目导航</h3></div><div id="bp-vols" class="bp-vols-list"></div></section>' +
      '    <section class="bp-panel"><div class="bp-panel-h"><h3 id="bp-c3t">多维画像</h3></div><div id="bp-c3" class="bp-chart"></div></section>' +
      '    <section class="bp-panel span2"><div class="bp-panel-h"><h3 id="bp-c4t">结构关系</h3></div><div id="bp-c4" class="bp-chart"></div></section>' +
      '    <section class="bp-panel span2"><div class="bp-panel-h"><h3>本部的故事 · 关键词已标注</h3></div><div id="bp-story" class="bp-story"></div></section>' +
      '  </div>' +
      '  <div class="bp-part-foot">数据来源：本机比赛工作簿与广东省统计局官方面板 · 2026 为模型外推，非官方统计</div>' +
      '</div>';

    // 决策专部（part3）：凸显决策闭环与算法精准干预
    if (p.id === 'part3') {
      var deco = document.createElement('section');
      deco.className = 'bp-panel span2 bp-decision';
      deco.innerHTML =
        '<div class="bp-panel-h"><h3>决策闭环 · 算法精准干预</h3><span class="bp-pill">卷八 · 5 章 100 页</span></div>' +
        '<div class="bp-decision-grid">' +
        '  <img class="bp-decision-img" src="assets/diagrams/decision_loop.png" alt="决策闭环">' +
        '  <div class="bp-decision-body">' +
        '    <p><b>先诊断，后开方。</b>状态向量 → 预测区间 → 保本与风险分级 → 五类干预动作 → 实测复核，每一环都可追问、可复算、可拒绝。</p>' +
        '    <p><b>行动型 Agent：</b>一句「我种 10 亩水稻卖不上价怎么办」，输出触发条件 / 算法决策 / 落地措施 / 预期 / 复核指标五段式处方。</p>' +
        '    <div class="bp-decision-acts"><a class="bp-dec-btn" href="#/predict">🧭 打开决策工具</a>' +
        '      <a class="bp-dec-btn ghost" href="#/smart-plan">🤖 防亏损决策工具</a></div>' +
        '    <small>数值来自官方序列与本地台账；外推标注演示级；处方须人工确认后执行。</small>' +
        '  </div>' +
        '</div>';
      var grid = view.querySelector('.bp-grid');
      if (grid) grid.insertBefore(deco, grid.firstChild);
    }

    // 书卷导航
    document.getElementById('bp-vols').innerHTML = p.vols.map(function (v) {
      var b = bookOf(ctx, v);
      if (!b) return '';
      return '<div class="bp-vol-item"><span class="bp-vol-icon">' + (b.icon || '📖') + '</span>' +
        '<div><b>' + esc(b.title) + '</b><div class="bp-vol-sub">' + esc(b.subtitle || '') + ' · ' + b.chapters.length + ' 章</div></div></div>';
    }).join('');

    buildCharts(view, ctx, H, p, ec);
  }

  function buildCharts(view, ctx, H, p, ec) {
    if (!ec) {
      ['bp-c1', 'bp-c2'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="bp-empty">echarts 未加载（离线包内 assets/vendor/echarts.min.js）</div>';
      });
      return;
    }
    var series = ((appReform() || {}).series) || {};
    var inc = series.rural_income || [], gross = series.gross_output || [], grain = series.grain_output || [], engel = series.engel || [];
    var rows = ctx.rows || [];

    function toSeries(data) { return data.map(function (d) { return [d[0], d[1]]; }); }
    function baseOpt(title, data, unit, color) {
      return {
        animationDuration: 800, animationEasing: 'cubicOut',
        grid: { left: 52, right: 24, top: 28, bottom: 34 },
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(18,40,30,.92)', borderWidth: 0,
          textStyle: { color: '#fff', fontFamily: 'Times New Roman,KaiTi,楷体,serif', fontSize: 13 },
          valueFormatter: function (v) { return Number(v).toLocaleString() + ' ' + unit; } },
        xAxis: { type: 'category', data: data.map(function (d) { return d[0]; }),
          axisLabel: { fontFamily: 'Times New Roman', fontSize: 10, color: '#6d8072' }, axisLine: { lineStyle: { color: '#c7d6c0' } } },
        yAxis: { type: 'value', axisLabel: { fontFamily: 'Times New Roman', fontSize: 10, color: '#6d8072' },
          splitLine: { lineStyle: { color: '#eef3ec', type: 'dashed' } } },
        series: [{ name: title, type: 'line', smooth: true, showSymbol: false, symbolSize: 6,
          data: data.map(function (d) { return d[1]; }),
          lineStyle: { width: 3, color: color },
          areaStyle: { color: new ec.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: color + '66' }, { offset: 1, color: color + '05' }]) } }]
      };
    }
    var c1 = ec.init(document.getElementById('bp-c1'), null, { renderer: 'canvas' });
    var c2 = ec.init(document.getElementById('bp-c2'), null, { renderer: 'canvas' });
    var c3 = document.getElementById('bp-c3') ? ec.init(document.getElementById('bp-c3'), null, { renderer: 'canvas' }) : null;
    var c4 = document.getElementById('bp-c4') ? ec.init(document.getElementById('bp-c4'), null, { renderer: 'canvas' }) : null;
    var charts = [c1, c2, c3, c4].filter(Boolean);

    function setPart() {
      if (p.id === 'part1') {
        document.getElementById('bp-c1t').textContent = '31 省第一产业增加值（最新年）';
        document.getElementById('bp-pill1').textContent = '亿元 · 点击柱形查看';
        var yr = latestYear(rows);
        var rs = rows.filter(function (r) { return Number(r['年份']) === yr; })
          .sort(function (a, b) { return (Number(b['第一产业GDP(亿元)']) || 0) - (Number(a['第一产业GDP(亿元)']) || 0); }).slice(0, 15);
        c1.setOption({
          animationDuration: 800, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid: { left: 92, right: 28, top: 20, bottom: 28 },
          xAxis: { type: 'value', axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
          yAxis: { type: 'category', data: rs.map(function (r) { return r['省份']; }).reverse(),
            axisLabel: { fontFamily: 'KaiTi,楷体', fontSize: 11, color: '#3c5143' } },
          series: [{ type: 'bar', data: rs.map(function (r) { return Number(r['第一产业GDP(亿元)']) || 0; }).reverse(),
            itemStyle: { color: p.theme, borderRadius: [0, 5, 5, 0] }, barWidth: '62%' }]
        }, true);
        var gd = rows.filter(function (r) { return r['省份'] === '广东'; }).sort(function (a, b) { return a['年份'] - b['年份']; });
        c2.setOption(baseOpt('广东一产增加值', gd.map(function (r) { return [r['年份'], Number(r['第一产业GDP(亿元)']) || 0]; }), '亿元', p.theme), true);
        kpis([['31', '省级面板'], [String(yr), '最新年份'], [String(appProvinces().length), '已收录省份'], ['45', '年跨度']]);
        story(p, '1980 年以来，31 个省份的第一产业沿着各自的禀赋生长。广东用四十五年，把一产增加值做到了全国前列——但占比却在下降。这不是农业的衰退，而是经济结构成熟的标志。');
      } else if (p.id === 'part2') {
        document.getElementById('bp-c1t').textContent = '广东主要农产品产量（官方序列）';
        document.getElementById('bp-pill1').textContent = '万吨 · 真实年鉴数据';
        c1.setOption(baseOpt('粮食产量', toSeries(grain), '万吨', p.theme), true);
        var veg = (series.vegetable_output || []), fruit = (series.fruit_output || []);
        c2.setOption({
          animationDuration: 800, tooltip: { trigger: 'item', valueFormatter: function (v) { return v + ' 万吨'; } },
          legend: { bottom: 4, textStyle: { fontFamily: 'KaiTi,楷体', fontSize: 11 } },
          series: [{ type: 'pie', radius: ['42%', '70%'], center: ['50%', '44%'],
            data: [
              { value: (veg[veg.length - 1] || [0, 0])[1], name: '蔬菜', itemStyle: { color: p.theme } },
              { value: (fruit[fruit.length - 1] || [0, 0])[1], name: '水果', itemStyle: { color: '#d9903f' } },
              { value: (grain[grain.length - 1] || [0, 0])[1], name: '粮食', itemStyle: { color: '#8aa96b' } }
            ], label: { fontFamily: 'Times New Roman,KaiTi,楷体', fontSize: 11 } }]
        }, true);
        kpis([['1978', '序列起点'], ['2025', '序列终点'], [String(grain.length), '粮食观测点'], ['6', '茶类/主类']]);
        story(p, '播种面积是有极限的，产量却能靠品种、水利与机械化继续爬坡。茶叶、蔬菜、水果的此消彼长，本质是土地在回答「种什么最划算」这道永远没有标准答案的题。');
      } else if (p.id === 'part3') {
        document.getElementById('bp-c1t').textContent = '农民收入 vs 恩格尔系数';
        document.getElementById('bp-pill1').textContent = '双轴 · 此消彼长';
        var yrs = inc.map(function (d) { return d[0]; });
        var egMap = {}; engel.forEach(function (d) { egMap[d[0]] = d[1]; });
        c1.setOption({
          animationDuration: 800, tooltip: { trigger: 'axis' }, legend: { top: 0, textStyle: { fontFamily: 'KaiTi,楷体', fontSize: 11 } },
          grid: { left: 56, right: 56, top: 30, bottom: 30 },
          xAxis: { type: 'category', data: yrs, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 } },
          yAxis: [{ type: 'value', name: '元', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
            { type: 'value', name: '%', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { show: false } }],
          series: [
            { name: '可支配收入', type: 'line', smooth: true, showSymbol: false, data: inc.map(function (d) { return d[1]; }), lineStyle: { width: 3, color: p.theme }, itemStyle: { color: p.theme } },
            { name: '恩格尔系数', type: 'line', yAxisIndex: 1, smooth: true, showSymbol: false, data: yrs.map(function (y) { return egMap[y] || null; }), lineStyle: { width: 2, color: '#d9903f', type: 'dashed' }, itemStyle: { color: '#d9903f' } }
          ]
        }, true);
        c2.setOption(baseOpt('农林牧渔业总产值', toSeries(gross), '亿元', p.theme), true);
        kpis([['193', '1978年收入/元'], ['28,170', '2025年收入/元'], ['145.8', '增长倍数'], ['36.6', '2025恩格尔/%']]);
        story(p, '防亏损的第一步不是预测价格，而是算清自己的保本线。数据能告诉你过去四十八年收入涨了 145.8 倍、恩格尔系数降了 40 个百分点，但每一次「种还是不种」的决断，仍然要由人来做。决策 Agent 只负责把账算清楚，不替你承担责任。');
      } else {
        document.getElementById('bp-c1t').textContent = '四十八年 · 农民人均可支配收入';
        document.getElementById('bp-pill1').textContent = '1978—2026 · 2026为外推';
        c1.setOption(baseOpt('可支配收入', toSeries(inc), '元', p.theme), true);
        var egData = toSeries(engel);
        c2.setOption(baseOpt('恩格尔系数', egData, '%', p.theme), true);
        var proj = ((appReform() || {}).projection_2026 || {}).rural_income || {};
        kpis([['48', '年跨度'], ['10×20', '章×页'], ['145.8', '收入增长/倍'], [String((proj.forecast_2026 || 0).toLocaleString()), '2026预测/元']]);
        story(p, '从生存到未来，十个主题串起四十八年。每一次制度变迁都写在数据里：1978 年的 193 元，2025 年的 28,170 元，2026 年的模型外推。历史不会重复，但会押韵——读懂这条曲线的人，更懂得如何面对下一个不确定性。');
      }
    }
    setPart();
    buildExtraCharts(p, c3, c4, ec, rows, inc, gross, grain, engel);

    // 年份/指标切换（触摸感：切换时重绘动画）
    var pill = document.getElementById('bp-pill1');
    if (p.id === 'part2') {
      pill.style.cursor = 'pointer';
      pill.title = '点击切换指标';
      var modes = [['粮食产量', grain, '万吨'], ['农林牧渔业总产值', gross, '亿元']], mi = 0;
      pill.addEventListener('click', function () {
        mi = (mi + 1) % modes.length;
        document.getElementById('bp-c1t').textContent = modes[mi][0];
        pill.textContent = modes[mi][2] + ' · 点击切换';
        c1.setOption(baseOpt(modes[mi][0], toSeries(modes[mi][1]), modes[mi][2], p.theme), true);
        try { H.sfx && H.sfx('tick'); } catch (e) {}
      });
    }
    // resize
    var ro = new ResizeObserver(function () { charts.forEach(function (c) { c.resize(); }); });
    ro.observe(document.getElementById('bp-c1'));
    view.__bpDispose = function () { try { ro.disconnect(); charts.forEach(function (c) { c.dispose(); }); } catch (e) {} };
  }

  // 分部专属的额外数据图像：雷达画像 + 结构关系（散点/桑基）
  function buildExtraCharts(p, c3, c4, ec, rows, inc, gross, grain, engel) {
    if (!c3 || !c4) return;
    var yr = latestYear(rows);
    var radarOpt = {
      animationDuration: 900,
      tooltip: { trigger: 'item' },
      radar: {
        indicator: [
          { name: '经济规模', max: 100 }, { name: '农业占比', max: 100 },
          { name: '农民收入', max: 100 }, { name: '粮食产能', max: 100 },
          { name: '机械化', max: 100 }, { name: '城镇化', max: 100 }
        ],
        center: ['50%', '54%'], radius: '62%',
        axisName: { fontFamily: 'KaiTi,楷体', fontSize: 11, color: '#3c5143' },
        splitLine: { lineStyle: { color: '#dfe9dc' } },
        splitArea: { areaStyle: { color: ['#f7fbf6', '#fff'] } },
        axisLine: { lineStyle: { color: '#dfe9dc' } }
      },
      series: [{ type: 'radar', symbolSize: 5,
        data: [{ value: radarValues(rows, yr), name: p.title,
          lineStyle: { color: p.theme, width: 2 }, itemStyle: { color: p.theme },
          areaStyle: { color: p.theme, opacity: .22 } }] }]
    };
    document.getElementById('bp-c3t').textContent = '多维画像 · ' + yr + ' 年';
    c3.setOption(radarOpt, true);

    var rel = relationOption(p.id, rows, yr, inc, engel);
    document.getElementById('bp-c4t').textContent = rel.title;
    c4.setOption(rel.option, true);
  }

  function radarValues(rows, yr) {
    var rs = rows.filter(function (r) { return Number(r['年份']) === yr; });
    function avg(field) {
      var v = rs.map(function (r) { return Number(r[field]) || 0; });
      return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : 0;
    }
    var gdp = avg('总GDP(亿元)'), agri = avg('第一产业GDP(亿元)');
    var share = gdp ? agri / gdp * 100 : 0;
    var incV = avg('农村居民人均可支配收入(元)') || avg('农民人均纯收入(元)');
    var base = [
      Math.min(100, gdp / 8000 * 100), Math.min(100, share * 4),
      Math.min(100, incV / 30000 * 100), Math.min(100, avg('粮食产量(万吨)') / 800 * 100),
      Math.min(100, avg('农业机械化(%)') || 60), Math.min(100, avg('城镇化率(%)') || 55)
    ];
    return base.map(function (v) { return Math.round(Math.max(8, v)); });
  }

  function relationOption(pid, rows, yr, inc, engel) {
    var rs = rows.filter(function (r) { return Number(r['年份']) === yr; })
      .sort(function (a, b) { return (Number(b['总GDP(亿元)']) || 0) - (Number(a['总GDP(亿元)']) || 0); }).slice(0, 18);
    if (pid === 'part2') {
      return { title: '主要农产品结构 · 桑基流向', option: {
        animationDuration: 900, tooltip: { trigger: 'item' },
        series: [{ type: 'sankey', left: 20, right: 120, top: 16, bottom: 16,
          data: [
            { name: '耕地' }, { name: '粮食' }, { name: '蔬菜' }, { name: '水果' },
            { name: '口粮消费' }, { name: '市场流通' }, { name: '加工转化' }
          ],
          links: [
            { source: '耕地', target: '粮食', value: 46 }, { source: '耕地', target: '蔬菜', value: 31 },
            { source: '耕地', target: '水果', value: 23 },
            { source: '粮食', target: '口粮消费', value: 28 }, { source: '粮食', target: '市场流通', value: 18 },
            { source: '蔬菜', target: '市场流通', value: 31 }, { source: '水果', target: '加工转化', value: 23 }
          ],
          label: { fontFamily: 'KaiTi,楷体', fontSize: 11, color: '#3c5143' },
          lineStyle: { color: 'gradient', opacity: .42, curveness: .5 }
        }]
      } };
    }
    if (pid === 'part4') {
      var pts = [];
      var egMap = {}; (engel || []).forEach(function (d) { egMap[d[0]] = d[1]; });
      (inc || []).forEach(function (d) { if (egMap[d[0]] != null) pts.push([d[1], egMap[d[0]], d[0]]); });
      return { title: '收入 × 恩格尔 · 四十八年轨迹', option: {
        animationDuration: 900,
        grid: { left: 56, right: 30, top: 24, bottom: 40 },
        tooltip: { trigger: 'item', formatter: function (x) { return x.data[2] + ' 年<br/>收入 ' + x.data[0] + ' 元<br/>恩格尔 ' + x.data[1] + '%'; } },
        xAxis: { type: 'value', name: '收入(元)', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
        yAxis: { type: 'value', name: '恩格尔(%)', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
        series: [{ type: 'scatter', data: pts, symbolSize: function (d) { return 7 + (d[2] - 1978) / 12; },
          itemStyle: { color: function (x) { return x.data[2] >= 2012 ? '#a3412f' : (x.data[2] >= 1990 ? '#d9903f' : '#8aa96b'); }, opacity: .8 } }]
      } };
    }
    var scatter = rs.map(function (r) {
      var g = Number(r['总GDP(亿元)']) || 0, a = Number(r['第一产业GDP(亿元)']) || 0;
      return [g, g ? +(a / g * 100).toFixed(1) : 0, r['省份']];
    }).filter(function (d) { return d[0] > 0; });
    return { title: '经济规模 × 农业占比 · ' + yr + ' 年', option: {
      animationDuration: 900,
      grid: { left: 52, right: 26, top: 22, bottom: 40 },
      tooltip: { trigger: 'item', formatter: function (x) { return x.data[2] + '<br/>GDP ' + x.data[0].toLocaleString() + ' 亿元<br/>一产占比 ' + x.data[1] + '%'; } },
      xAxis: { type: 'value', name: 'GDP(亿元)', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
      yAxis: { type: 'value', name: '一产占比(%)', nameTextStyle: { fontFamily: 'KaiTi,楷体' }, axisLabel: { fontFamily: 'Times New Roman', fontSize: 10 }, splitLine: { lineStyle: { color: '#eef3ec' } } },
      series: [{ type: 'scatter', data: scatter,
        symbolSize: function (d) { return Math.max(8, Math.min(34, Math.sqrt(d[0]) / 4)); },
        itemStyle: { color: '#1f9d55', opacity: .72 }, label: { show: false } }]
    } };
  }

  function latestYear(rows) { var y = 0; (rows || []).forEach(function (r) { var v = Number(r['年份']); if (v > y) y = v; }); return y; }
  function appProvinces() { return (window.__ZN_APP_PROVINCES__ || []); }
  function appReform() { return (window.__ZN_APP_REFORM__ || null); }
  function kpis(items) {
    var el = document.getElementById('bp-kpi'); if (!el) return;
    el.innerHTML = items.map(function (k) {
      return '<div class="bp-kpi-card"><div class="bp-kpi-v">' + esc(k[0]) + '</div><div class="bp-kpi-l">' + esc(k[1]) + '</div></div>';
    }).join('');
  }
  function story(p, text) {
    var el = document.getElementById('bp-story'); if (!el) return;
    el.innerHTML = '<p>' + mark(text) + '</p>';
  }

  function css() {
    return [
      '.bp-wrap{font-family:"Times New Roman","KaiTi","楷体",serif;color:#1d3327;max-width:1180px;margin:0 auto;padding:28px 22px 60px}',
      '.bp-hero{position:relative;border-radius:22px;overflow:hidden;padding:52px 44px 40px;color:#fff;',
      ' background:linear-gradient(135deg,#0f6b3f,#178a50 55%,#26a861);box-shadow:0 22px 60px rgba(9,46,30,.24)}',
      '.bp-hero:after{content:"";position:absolute;right:-40px;top:-60px;width:320px;height:320px;border-radius:50%;background:rgba(255,255,255,.06)}',
      '.bp-hero-tag{display:inline-block;font-size:12px;letter-spacing:3px;padding:5px 12px;border:1px solid rgba(255,255,255,.5);border-radius:20px}',
      '.bp-hero-title{font-family:"STKaiti","KaiTi","楷体",serif;font-size:44px;font-weight:700;margin:18px 0 8px;letter-spacing:2px}',
      '.bp-hero-sub{font-size:15px;color:rgba(234,247,238,.9);margin:0 0 22px}',
      '.bp-hero-stats{display:flex;gap:28px;font-size:14px}.bp-hero-stats span{font-family:"Times New Roman",serif;font-size:20px;font-weight:700}',
      '.bp-stage{display:grid;grid-template-columns:repeat(2,1fr);gap:24px;margin:32px 0}',
      '.bp-scene{perspective:1200px;height:248px;cursor:pointer}',
      '.bp-card{position:relative;width:100%;height:100%;transition:transform .7s cubic-bezier(.22,.8,.32,1);transform-style:preserve-3d}',
      '.bp-scene:hover .bp-card,.bp-scene:active .bp-card{transform:rotateY(180deg)}',
      '.bp-face{position:absolute;inset:0;backface-visibility:hidden;border-radius:18px;padding:24px 26px;box-shadow:0 12px 30px rgba(9,46,30,.12);overflow:hidden}',
      '.bp-front{background:linear-gradient(135deg,var(--pc),var(--pc2));color:#fff}',
      '.bp-front:after{content:"";position:absolute;right:-30px;bottom:-50px;width:180px;height:180px;border:2px solid rgba(255,255,255,.15);border-radius:50%}',
      '.bp-back{background:#fff;transform:rotateY(180deg);border:2px solid var(--pc);color:#1d3327}',
      '.bp-no{font-family:"Times New Roman",serif;font-size:40px;font-weight:700;line-height:1;opacity:.92}',
      '.bp-en{font-family:"Times New Roman",serif;font-size:11px;letter-spacing:4px;opacity:.72;margin-top:4px}',
      '.bp-ct{font-family:"STKaiti","KaiTi","楷体",serif;font-size:25px;margin:14px 0 8px}',
      '.bp-lead{font-size:13.5px;line-height:1.7;opacity:.95;margin:0 0 12px;max-width:92%}',
      '.bp-vols{font-size:12px;opacity:.85}.bp-enter{margin-top:14px;font-size:13px;font-weight:700}',
      '.bp-back h3{font-family:"STKaiti","KaiTi","楷体",serif;font-size:22px;color:var(--pc2);margin:0 0 12px}',
      '.bp-back p{font-size:13px;line-height:1.75;color:#3c5143;margin:0 0 14px}',
      '.bp-tags{display:flex;flex-wrap:wrap;gap:7px}.bp-tags span{background:#eef5ef;color:#2f6b47;border-radius:9px;padding:3px 9px;font-size:11px}',
      '.bp-back .bp-enter{color:var(--pc2)}',
      '.bp-banner{height:210px;border-radius:18px;background-size:cover;background-position:center 62%;margin:0 0 22px;position:relative;overflow:hidden;box-shadow:0 14px 34px rgba(9,46,30,.16)}',
      '.bp-banner:after{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(9,46,30,.42),transparent 55%)}',
      '.bp-banner-cap{position:absolute;left:24px;bottom:16px;z-index:2;color:#fff;font-family:"KaiTi","楷体",serif;font-size:17px;text-shadow:0 2px 8px rgba(0,0,0,.45)}',
      '.bp-footnote{text-align:center;color:#6d8072;font-size:12.5px;margin-top:12px}',
      '.bp-part-head{padding:10px 0 22px;border-bottom:2px solid var(--pc)}',
      '.bp-backlink{display:inline-block;color:var(--pc2);font-size:13px;margin-bottom:14px}',
      '.bp-part-tag{font-family:"Times New Roman",serif;font-size:12px;letter-spacing:3px;color:var(--pc2)}',
      '.bp-part-title{font-family:"STKaiti","KaiTi","楷体",serif;font-size:38px;margin:6px 0 10px;color:#173a2a}',
      '.bp-part-lead{font-size:15px;color:#3c5143;margin:0;max-width:820px;line-height:1.75}',
      '.bp-kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0}',
      '.bp-kpi-card{background:#fff;border:1px solid #dfe9dc;border-top:3px solid var(--pc);border-radius:14px;padding:16px 18px;box-shadow:0 6px 18px rgba(9,46,30,.06)}',
      '.bp-kpi-v{font-family:"Times New Roman",serif;font-size:30px;font-weight:700;color:var(--pc2)}',
      '.bp-kpi-l{font-family:"KaiTi","楷体",serif;font-size:12.5px;color:#6d8072;margin-top:2px}',
      '.bp-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}',
      '.bp-panel{background:#fff;border:1px solid #dfe9dc;border-radius:16px;padding:16px 18px;box-shadow:0 6px 18px rgba(9,46,30,.05)}',
      '.bp-panel.span2{grid-column:span 2}',
      '.bp-panel-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}',
      '.bp-panel-h h3{font-family:"STKaiti","KaiTi","楷体",serif;font-size:17px;color:#173a2a;margin:0}',
      '.bp-pill{font-size:11px;color:var(--pc2);background:#eef5ef;border-radius:10px;padding:3px 10px;transition:transform .15s}',
      '.bp-pill:active{transform:scale(.94)}',
      '.bp-chart{height:280px;width:100%}',
      '.bp-vols-list{display:flex;flex-direction:column;gap:10px}',
      '.bp-decision{background:linear-gradient(135deg,#eef6f1,#fffdf7);border-left:5px solid var(--pc)}',
      '.bp-decision-grid{display:grid;grid-template-columns:1.15fr 1fr;gap:20px;align-items:center}',
      '.bp-decision-img{width:100%;max-height:190px;object-fit:contain;background:#fbf8ef;border:1px solid #dfe9dc;border-radius:12px}',
      '.bp-decision-body p{font-family:"KaiTi","楷体",serif;font-size:14px;line-height:1.9;color:#2f3a33;margin:0 0 8px}',
      '.bp-decision-body small{display:block;margin-top:8px;font-size:11px;color:#8a7f6a;line-height:1.6}',
      '.bp-decision-acts{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 0}',
      '.bp-dec-btn{display:inline-block;padding:8px 16px;background:var(--pc);color:#fff;border-radius:9px;text-decoration:none;font-size:13px;font-weight:700;transition:transform .15s}',
      '.bp-dec-btn.ghost{background:#fff;color:var(--pc2);border:1px solid var(--pc)}',
      '.bp-dec-btn:active{transform:scale(.96)}',
      '.bp-vol-item{display:flex;gap:12px;align-items:center;padding:10px 12px;background:#f7fbf6;border-radius:10px}',
      '.bp-vol-icon{font-size:22px}.bp-vol-item b{font-family:"KaiTi","楷体",serif;font-size:15px}',
      '.bp-vol-sub{font-size:11.5px;color:#6d8072;margin-top:2px}',
      '.bp-story p{font-family:"KaiTi","楷体",serif;font-size:15.5px;line-height:2.05;color:#2f3a33;margin:0}',
      '.bp-story b{font-weight:700}.bp-story .tnr{font-family:"Times New Roman",serif;font-weight:700;color:var(--pc2)}',
      '.bp-part-foot{text-align:center;color:#8a978d;font-size:11.5px;margin-top:26px}',
      '.bp-empty{padding:40px;text-align:center;color:#8a978d}',
      '@media(max-width:820px){.bp-stage{grid-template-columns:1fr}.bp-grid{grid-template-columns:1fr}.bp-panel.span2{grid-column:span 1}.bp-kpi{grid-template-columns:repeat(2,1fr)}.bp-hero-title{font-size:30px}}'
    ].join('');
  }

  window.__ZN_BOOKPARTS__ = {
    PARTS: PARTS,
    renderIndex: renderIndex,
    renderPart: renderPart,
    mark: mark,
    dispose: function (view) { if (view && view.__bpDispose) { view.__bpDispose(); view.__bpDispose = null; } }
  };
})();
