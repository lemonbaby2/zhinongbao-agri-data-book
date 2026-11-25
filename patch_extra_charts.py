from pathlib import Path

p = Path('app/site/assets/js/book_parts.js')
s = p.read_text(encoding='utf-8')

# 1) 初始化 c3/c4
old_init = """    var c1 = ec.init(document.getElementById('bp-c1'), null, { renderer: 'canvas' });
    var c2 = ec.init(document.getElementById('bp-c2'), null, { renderer: 'canvas' });
    var charts = [c1, c2];"""
new_init = """    var c1 = ec.init(document.getElementById('bp-c1'), null, { renderer: 'canvas' });
    var c2 = ec.init(document.getElementById('bp-c2'), null, { renderer: 'canvas' });
    var c3 = document.getElementById('bp-c3') ? ec.init(document.getElementById('bp-c3'), null, { renderer: 'canvas' }) : null;
    var c4 = document.getElementById('bp-c4') ? ec.init(document.getElementById('bp-c4'), null, { renderer: 'canvas' }) : null;
    var charts = [c1, c2, c3, c4].filter(Boolean);"""
assert old_init in s, 'init not found'
s = s.replace(old_init, new_init)

s = s.replace('    setPart();\n\n    // 年份/指标切换',
              '    setPart();\n    buildExtraCharts(p, c3, c4, ec, rows, inc, gross, grain, engel);\n\n    // 年份/指标切换')

extra = r'''  // 分部专属的额外数据图像：雷达画像 + 结构关系（散点/桑基）
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

'''
anchor = '  function latestYear(rows) {'
assert anchor in s, 'anchor not found'
s = s.replace(anchor, extra + anchor)
p.write_text(s, encoding='utf-8')
print('extra charts patched')
