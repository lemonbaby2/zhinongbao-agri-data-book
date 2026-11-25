// 站点自动化验收：逐路由加载、收集控制台错误、关键交互断言、截图。
// 运行前需要本地服务已启动：
//   python desktop/zhinongbao.py --no-browser --no-prompt --idle 900 --port 8899
// 然后：node tools/smoke_test.mjs
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.ZN_BASE || 'http://127.0.0.1:8899';
const OUT = 'outputs/qa';
mkdirSync(OUT, { recursive: true });

const ROUTES = [
  ['/', '总览'], ['/data', '数据总览'], ['/map', '省域分布'], ['/compare', '区域对比'],
  ['/crop-data', '作物指标'], ['/macro', '宏观与劳动力'], ['/forecast', '趋势预测'],
  ['/model', '模型与图表'], ['/datasets', '数据集目录'], ['/features', '功能与恢复进度'],
  ['/about', '恢复说明'], ['/farming-cost', '种植成本测算'], ['/data-upload', 'CSV 数据导入'],
  ['/gov-dashboard', '区域工作台'], ['/province/广东', '广东'], ['/dataset/754403788736c810', ''],
  ['/presentation', '可视化分析平台'], ['/recovery', '常见问题解答'],
  ['/smart-plan', '种植防亏损'], ['/predict', '产量与价格预测'], ['/digital-farm', '数字农田生态']
];

const SHOTS = new Set(['/', '/data', '/map', '/compare', '/crop-data', '/forecast', '/datasets', '/farming-cost', '/about', '/dataset/754403788736c810', '/presentation', '/recovery', '/smart-plan', '/predict', '/digital-farm']);

const errors = [];
const results = [];

let browser;
try {
  browser = await chromium.launch({ channel: 'msedge' });
} catch (error) {
  console.log('msedge 启动失败，尝试 chrome：' + error.message);
  browser = await chromium.launch({ channel: 'chrome' });
}

const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, deviceScaleFactor: 1, locale: 'zh-CN' });
const page = await context.newPage();
page.on('console', message => { if (message.type() === 'error') errors.push({ where: page.url(), text: message.text() }); });
page.on('pageerror', error => errors.push({ where: page.url(), text: 'pageerror: ' + error.message }));

for (const [route, expect] of ROUTES) {
  const url = BASE + '/#' + route;
  const before = errors.length;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#view h1', { timeout: 15000 });
  await page.waitForTimeout(route === '/dataset/754403788736c810' ? 1500 : 600);
  const heading = await page.locator('#view h1').first().innerText();
  const bodyText = await page.locator('#view').innerText();
  const newErrors = errors.slice(before);
  results.push({
    route, heading: heading.replace(/\s+/g, ' ').trim(),
    expectHit: !expect || heading.includes(expect) || bodyText.includes(expect),
    chars: bodyText.length, errors: newErrors.length
  });
  if (SHOTS.has(route)) {
    const name = route === '/' ? 'home' : route.replace(/^\//, '').replace(/[/]/g, '_');
    await page.screenshot({ path: `${OUT}/page_${name}.png`, fullPage: false });
  }
}

/* ---------- 交互断言 ---------- */
const interactions = [];
async function check(name, fn) {
  try { const detail = await fn(); interactions.push({ name, ok: true, detail }); }
  catch (error) { interactions.push({ name, ok: false, detail: error.message }); errors.push({ where: 'interaction:' + name, text: error.message }); }
}

await page.goto(BASE + '/#/data', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#data-table tbody tr');
await check('数据总览-表格行数', async () => String(await page.locator('#data-table tbody tr').count()));
await check('数据总览-切换年份', async () => {
  await page.selectOption('#f-year', { index: 3 });
  await page.waitForTimeout(250);
  return await page.locator('[data-count]').innerText();
});
await check('数据总览-点表头排序', async () => {
  await page.locator('#data-table th').nth(3).click();
  await page.waitForTimeout(200);
  return (await page.locator('#data-table th').nth(3).innerText()).replace(/\s+/g, '');
});
await check('数据总览-大区筛选', async () => {
  await page.locator('#f-regions .chip').first().click();
  await page.waitForTimeout(250);
  return await page.locator('[data-count]').innerText();
});

await page.goto(BASE + '/#/map', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.province-tile');
await check('省域分布-省份卡片数', async () => String(await page.locator('.province-tile').count()));
await check('省域分布-切换指标', async () => {
  await page.selectOption('#m-metric', 'gdpPer');
  await page.waitForTimeout(250);
  return await page.locator('#m-scale').innerText();
});

await page.goto(BASE + '/#/compare', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#c-chart svg');
await check('区域对比-四省选择', async () => {
  await page.selectOption('select[data-slot="2"]', '黑龙江');
  await page.waitForTimeout(300);
  return String(await page.locator('#c-table tbody tr').count());
});

await page.goto(BASE + '/#/forecast', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#fc-chart svg');
await check('趋势预测-KPI 与图表', async () => {
  await page.fill('#fc-horizon', '8');
  await page.dispatchEvent('#fc-horizon', 'input');
  await page.waitForTimeout(300);
  const kpis = await page.locator('#fc-kpis .kpi').count();
  const rows = await page.locator('#fc-table tbody tr').count();
  return `kpi=${kpis} rows=${rows}`;
});

await page.goto(BASE + '/#/datasets', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#ds-table tbody tr');
await check('数据集目录-搜索过滤', async () => {
  await page.fill('#ds-search', '综合');
  await page.waitForTimeout(300);
  return await page.locator('[data-count]').first().innerText();
});

await page.goto(BASE + '/#/dataset/754403788736c810', { waitUntil: 'domcontentloaded' });
await check('工作簿预览-读取工作表', async () => {
  await page.waitForSelector('#dt-table tbody tr', { timeout: 8000 });
  return String(await page.locator('#dt-table tbody tr').count());
});

await page.goto(BASE + '/#/', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#view h1');
await check('命令面板 Ctrl+K', async () => {
  await page.keyboard.press('Control+k');
  await page.waitForSelector('#palette:not([hidden])');
  await page.fill('#palette-input', '广东');
  await page.waitForTimeout(300);
  const items = await page.locator('.palette-item').count();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  return `items=${items} heading=${(await page.locator('#view h1').innerText()).trim()}`;
});
await check('图表灯箱', async () => {
  await page.goto(BASE + '/#/model', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-open-chart]');
  await page.locator('[data-open-chart]').first().click();
  await page.waitForTimeout(400);
  const visible = await page.locator('#lightbox:not([hidden])').count();
  await page.keyboard.press('Escape');
  return 'visible=' + visible;
});
await check('种植成本-改变输入', async () => {
  await page.goto(BASE + '/#/farming-cost', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#ct-result .kpi');
  await page.fill('#ct-price', '5');
  await page.dispatchEvent('#ct-price', 'input');
  await page.waitForTimeout(300);
  return (await page.locator('#ct-result .kpi').first().innerText()).replace(/\s+/g, ' ');
});
await check('项目与答辩-技术路线步骤', async () => {
  await page.goto(BASE + '/#/presentation', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.steps .step');
  return String(await page.locator('.steps .step').count());
});
await check('项目与答辩-架构分层', async () => {
  const rows = await page.locator('.arch .arch-row').count();
  return 'rows=' + rows;
});
await check('备份恢复-FAQ 折叠', async () => {
  await page.goto(BASE + '/#/recovery', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.faq-item');
  const faqs = await page.locator('.faq-item').count();
  await page.locator('.faq-q').first().click();
  await page.waitForTimeout(200);
  const open = await page.locator('.faq-item.open').count();
  return `faqs=${faqs} open=${open}`;
});
await check('种植防亏损-风险评级', async () => {
  await page.goto(BASE + '/#/smart-plan', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#sp-risk .risk-banner');
  const risk = (await page.locator('#sp-risk .risk-banner b').innerText()).trim();
  const kpi = await page.locator('#sp-kpi .kpi').count();
  const sensi = await page.locator('#sp-sensi td').count();
  return `risk=${risk} kpi=${kpi} sensi=${sensi}`;
});
await check('种植防亏损-切换作物', async () => {
  await page.selectOption('#sp-crop', '苹果');
  await page.waitForTimeout(300);
  return await page.locator('#sp-yield').inputValue();
});
await check('产量预测-趋势图', async () => {
  await page.goto(BASE + '/#/predict', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#pd-chart svg');
  await page.selectOption('#pd-target', 'price');
  await page.waitForTimeout(300);
  const rows = await page.locator('#pd-table tbody tr').count();
  return `rows=${rows}`;
});
await check('数字农田-四情与设备', async () => {
  await page.goto(BASE + '/#/digital-farm', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.quad-item');
  const quads = await page.locator('.quad-item').count();
  const devices = await page.locator('.device-row').count();
  const chart = await page.locator('#df-weather-chart svg').count();
  return `quads=${quads} devices=${devices} chart=${chart}`;
});
await check('移动端侧边栏', async () => {
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 420, height: 860 });
  await mobile.goto(BASE + '/#/', { waitUntil: 'domcontentloaded' });
  await mobile.waitForSelector('#view h1');
  await mobile.click('#menu-button');
  await mobile.waitForTimeout(300);
  const open = await mobile.locator('#sidebar.open').count();
  await mobile.screenshot({ path: `${OUT}/page_mobile_home.png` });
  await mobile.screenshot({ path: `${OUT}/page_mobile_menu.png` });
  await mobile.close();
  return 'open=' + open;
});

await page.screenshot({ path: `${OUT}/page_lightbox.png` }).catch(() => {});

const summary = {
  base: BASE,
  routes: results,
  interactions,
  errorCount: errors.length,
  errors: errors.slice(0, 40),
  failed: results.filter(r => !r.expectHit || r.errors > 0).map(r => r.route).concat(interactions.filter(i => !i.ok).map(i => i.name))
};
writeFileSync(`${OUT}/smoke_result.json`, JSON.stringify(summary, null, 2), 'utf8');
console.log(JSON.stringify({ errorCount: summary.errorCount, failed: summary.failed, interactions }, null, 2));
console.log('\n路由结果：');
for (const item of results) console.log(`  ${item.expectHit ? 'OK ' : 'FAIL'} ${item.route.padEnd(30)} ${item.heading}  (${item.chars} 字, ${item.errors} 错误)`);
await browser.close();
