#!/usr/bin/env node
'use strict';
// 生成 docs/images/*.svg。数字来自 docs/data-report.md（tools/stages.cjs 的输出），改数字改下面的 DATA 再跑一次。
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, 'images');
const FONT = "'PingFang SC','Microsoft YaHei','Noto Sans CJK SC','Noto Sans SC',system-ui,sans-serif";
const C = { bg: '#ffffff', ink: '#1a1a19', ink2: '#52514e', muted: '#8a8984', grid: '#e4e3de', before: '#a9a8a2', after: '#2a78d6', slow: '#eb6834', both: '#c9a227' };

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const t = (x, y, s, o = {}) => `<text x="${x}" y="${y}" font-size="${o.size || 13}" fill="${o.fill || C.ink}"${o.anchor ? ` text-anchor="${o.anchor}"` : ''}${o.bold ? ' font-weight="700"' : ''}>${esc(s)}</text>`;
// 只有数据端圆角（上端或右端），贴着基线的一端是直的
const barUp = (x, y, w, h, fill) => `<path d="M${x},${y + h}V${y + 4}q0,-4 4,-4h${w - 8}q4,0 4,4V${y + h}Z" fill="${fill}"/>`;
const barRight = (x, y, w, h, fill) => (w < 5 ? `<rect x="${x}" y="${y}" width="${Math.max(w, 1)}" height="${h}" fill="${fill}"/>` : `<path d="M${x},${y}H${x + w - 4}q4,0 4,4V${y + h - 4}q0,4 -4,4H${x}Z" fill="${fill}"/>`);
// 坐标统一保留一位小数，SVG 里不留浮点长尾
const tidy = (s) => s.replace(/(\d+\.\d)\d{2,}/g, '$1');
const svg = (w, h, body) => tidy(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${FONT}">\n<rect width="${w}" height="${h}" rx="12" fill="${C.bg}"/>\n${body}\n</svg>\n`);
const legend = (x, y, items) => items.map(([label, color], i) => `<rect x="${x + i * 130}" y="${y - 10}" width="12" height="12" rx="3" fill="${color}"/>${t(x + i * 130 + 18, y, label, { size: 12, fill: C.ink2 })}`).join('');

// ① 每一步花费阶梯
function staircase() {
  const d = [['最早没调整', '9/14–10/2', 10.5], ['全开最高档', '10/3–10/12', 9.8], ['降档+程序先查', '10/13–11/4', 9.9],
    ['一事一对话', '11/5–11/10', 9.2], ['只用高两档', '11/10–11/11', 7.5], ['源头限读', '11/11–11/16', 6.4]];
  const W = 760; const H = 360; const x0 = 40; const base = 270; const bw = 72; const gap = 44; const k = 18;
  let b = t(24, 34, '每一步（一次工具调用）平均花多少美分', { size: 18, bold: true });
  b += t(24, 56, 'Cents per step (one tool call). 从最早没调整到现在 −39%', { size: 12.5, fill: C.ink2 });
  b += `<line x1="${x0 - 10}" y1="${base}" x2="${W - 20}" y2="${base}" stroke="${C.grid}"/>`;
  d.forEach(([name, date, v], i) => {
    const x = x0 + i * (bw + gap); const h = v * k;
    b += barUp(x, base - h, bw, h, i === 0 ? C.before : i === d.length - 1 ? C.after : '#8db6e8');
    b += t(x + bw / 2, base - h - 8, v.toFixed(1), { size: 15, bold: true, anchor: 'middle' });
    b += t(x + bw / 2, base + 20, name, { size: 12.5, anchor: 'middle' });
    b += t(x + bw / 2, base + 38, date, { size: 11.5, fill: C.muted, anchor: 'middle' });
  });
  b += t(24, H - 14, '每段是一次改规矩之后的那几天；花费按估算价目算（见数据报告“口径”），不是账单。', { size: 11.5, fill: C.muted });
  return svg(W, H, b);
}

// ② 前后对比：每行各用自己的刻度（单位不同，不放在同一根轴上），前后两根并排
function beforeAfter() {
  const good = [['每一步花费（美分）', 10.5, 6.4, '−39%'], ['每一步新读入（千 token）', 3.67, 2.08, '−43%'], ['整份读文件的占比（%）', 51, 16, '−35 点'], ['每个干活小时交付（份）', 3.1, 5.4, '+74%']];
  const bad = [['每份交付花费（美元）', 16.6, 19.7, '+19%'], ['每美元写进程序（字）', 2020, 1588, '−21%'], ['子代理花费占比（%）', 17, 44, '+27 点'], ['上下文超 25 万的会话占比（%）', 33, 43, '+10 点']];
  const W = 760; const rowH = 62; const top = 96; const barMax = 380; const lx = 24; const bx = 300;
  const H = top + (good.length + bad.length) * rowH + 2 * 34 + 40;
  let b = t(24, 34, '最早没调整（9/14–10/2） vs 现在（11/11 夜–11/16）', { size: 18, bold: true });
  b += t(24, 56, 'Baseline vs now. 好的坏的都放；停工的小时不算进“干活小时”。', { size: 12.5, fill: C.ink2 });
  b += legend(24, 80, [['最早没调整', C.before], ['现在', C.after]]);
  let y = top;
  const group = (title, rows) => {
    y += 22; b += t(lx, y, title, { size: 14.5, bold: true }); y += 12;
    for (const [name, v0, v1, chg] of rows) {
      const m = Math.max(v0, v1);
      b += t(lx, y + 22, name, { size: 13 });
      b += t(lx, y + 42, chg, { size: 12.5, fill: C.ink2, bold: true });
      b += barRight(bx, y + 8, (v0 / m) * barMax, 14, C.before) + t(bx + (v0 / m) * barMax + 8, y + 20, v0.toLocaleString('en-US'), { size: 12.5, fill: C.ink2 });
      b += barRight(bx, y + 26, (v1 / m) * barMax, 14, C.after) + t(bx + (v1 / m) * barMax + 8, y + 38, v1.toLocaleString('en-US'), { size: 12.5, fill: C.ink });
      y += rowH;
    }
  };
  group('变好的 · Better', good);
  group('变差的 · Worse', bad);
  b += t(24, H - 14, '每行各用自己的刻度，只比同一行的前后两根。数据：本机全部会话记录，同一条回复只算一次。', { size: 11.5, fill: C.muted });
  return svg(W, H, b);
}

// ③ 测试为什么卡
function testWait() {
  const W = 760; const H = 330;
  const parts = [['排队等位', 479, C.after], ['真跑得慢', 126, C.slow], ['两者叠加', 111, C.both]];
  const total = 716; const bw = 700; const x0 = 30;
  let b = t(24, 34, '测试超过 10 分钟的 716 次里，67% 是在排队', { size: 18, bold: true });
  b += t(24, 56, 'Of 4,212 test runs (11/11–11/16), 716 took >10 min. Two thirds of those were waiting, not running.', { size: 12.5, fill: C.ink2 });
  let x = x0;
  parts.forEach(([name, n, color], i) => {
    const w = (n / total) * bw;
    b += `<rect x="${x}" y="84" width="${w - 2}" height="34" ${i === 0 ? 'rx="0"' : ''} fill="${color}"/>`;
    b += t(x + 6, 140, `${name} ${n} 次`, { size: 13 });
    b += t(x + 6, 158, `${Math.round((n / total) * 100)}%`, { size: 12.5, fill: C.ink2, bold: true });
    x += w;
  });
  b += t(24, 200, '为什么排队：测试位一度从 8 减到 4（8 份同时跑内存不够，把正在用的服务挤卡），某晚还临时减到 1；', { size: 13 });
  b += t(24, 220, '二十来路会话同时要测试，于是排长队。真跑慢的主要是合并、验收时跑整套（中位约 19 分钟，最长 74 分钟）。', { size: 13 });
  b += t(24, 252, '对策（v70）：', { size: 13.5, bold: true });
  b += t(24, 274, '① 会话和测试共用一个总池（20 位）  ② 整套只准合并 / 验收跑、最多 2 份，开发只跑点到的测试', { size: 13 });
  b += t(24, 294, '③ 单次满 15 分钟熔断  ④ 空闲内存不够不放新测试。11/19 复量效果后补进数据报告。', { size: 13 });
  b += t(24, H - 12, '来源：测试排队器的运行记录（runs.jsonl）。', { size: 11.5, fill: C.muted });
  return svg(W, H, b);
}

// ④ 子代理 vs 新会话
function subVsSession() {
  const W = 760; const H = 300;
  const rows = [['每次平均花费（美元）', 5.2, 9.1], ['开张先读进来的量（千 token）', 75, 110], ['这几天开了多少次', 916, 656]];
  let b = t(24, 34, '一次子代理 vs 一个新会话（11/11 夜–11/16）', { size: 18, bold: true });
  b += t(24, 56, 'Per run: a subagent costs less than a fresh session. The bill grew because we spawned too many.', { size: 12.5, fill: C.ink2 });
  b += legend(24, 82, [['子代理', C.after], ['新会话', C.before]]);
  let y = 100; const bx = 300; const barMax = 380;
  for (const [name, a, s] of rows) {
    const m = Math.max(a, s);
    b += t(24, y + 26, name, { size: 13 });
    b += barRight(bx, y + 8, (a / m) * barMax, 14, C.after) + t(bx + (a / m) * barMax + 8, y + 20, a.toLocaleString('en-US'), { size: 12.5 });
    b += barRight(bx, y + 26, (s / m) * barMax, 14, C.before) + t(bx + (s / m) * barMax + 8, y + 38, s.toLocaleString('en-US'), { size: 12.5, fill: C.ink2 });
    y += 52;
  }
  b += t(24, y + 22, '结论：单价子代理便宜，费钱在于派得太多（4 天多 916 次、4,722 美元）。要省靠“少开”：', { size: 13 });
  b += t(24, y + 42, '小的查找自己按行读，非开不可的才开。每行各用自己的刻度。', { size: 13 });
  return svg(W, H, b);
}

fs.mkdirSync(OUT, { recursive: true });
for (const [name, fn] of [['cost-per-step', staircase], ['before-after', beforeAfter], ['test-wait', testWait], ['subagent-vs-session', subVsSession]]) {
  fs.writeFileSync(path.join(OUT, `${name}.svg`), fn());
}
console.log('docs/images/*.svg 已生成');
