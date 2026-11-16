#!/usr/bin/env node
'use strict';
// 生成 docs/images/*.svg（中文）和 docs/images/en/*.svg（English）。
// 数字来自 docs/data-report.md（tools/stages.cjs、tools/token-usage.cjs 的输出），改数字改下面各图的数据再跑一次。
// Generates Chinese charts in docs/images/ and English ones in docs/images/en/.
const fs = require('fs');
const path = require('path');

const FONT = "'PingFang SC','Microsoft YaHei','Noto Sans CJK SC','Noto Sans SC',system-ui,sans-serif";
const C = { bg: '#ffffff', ink: '#1a1a19', ink2: '#52514e', muted: '#8a8984', grid: '#e4e3de', before: '#a9a8a2', after: '#2a78d6', mid: '#8db6e8', slow: '#eb6834', both: '#c9a227' };

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const t = (x, y, s, o = {}) => `<text x="${x}" y="${y}" font-size="${o.size || 13}" fill="${o.fill || C.ink}"${o.anchor ? ` text-anchor="${o.anchor}"` : ''}${o.bold ? ' font-weight="700"' : ''}>${esc(s)}</text>`;
// 只有数据端圆角（上端或右端），贴着基线的一端是直的
const barUp = (x, y, w, h, fill) => `<path d="M${x},${y + h}V${y + 4}q0,-4 4,-4h${w - 8}q4,0 4,4V${y + h}Z" fill="${fill}"/>`;
const barRight = (x, y, w, h, fill) => (w < 5 ? `<rect x="${x}" y="${y}" width="${Math.max(w, 1)}" height="${h}" fill="${fill}"/>` : `<path d="M${x},${y}H${x + w - 4}q4,0 4,4V${y + h - 4}q0,4 -4,4H${x}Z" fill="${fill}"/>`);
// 坐标统一保留一位小数，SVG 里不留浮点长尾
const tidy = (s) => s.replace(/(\d+\.\d)\d{2,}/g, '$1');
const svg = (w, h, body) => tidy(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${FONT}">\n<rect width="${w}" height="${h}" rx="12" fill="${C.bg}"/>\n${body}\n</svg>\n`);
const legend = (x, y, items) => items.map(([label, color], i) => `<rect x="${x + i * 150}" y="${y - 10}" width="12" height="12" rx="3" fill="${color}"/>${t(x + i * 150 + 18, y, label, { size: 12, fill: C.ink2 })}`).join('');
const num = (v) => v.toLocaleString('en-US');

// 成对横条：每行各用自己的刻度（单位不同，不放在同一根轴上）
function pairedRows(rows, y, colors, bx = 330, barMax = 360, rowH = 62) {
  let b = '';
  for (const [name, v0, v1, chg] of rows) {
    const m = Math.max(v0, v1);
    b += t(24, y + 22, name, { size: 13 });
    if (chg) b += t(24, y + 42, chg, { size: 12.5, fill: C.ink2, bold: true });
    b += barRight(bx, y + 8, (v0 / m) * barMax, 14, colors[0]) + t(bx + (v0 / m) * barMax + 8, y + 20, num(v0), { size: 12.5, fill: C.ink2 });
    b += barRight(bx, y + 26, (v1 / m) * barMax, 14, colors[1]) + t(bx + (v1 / m) * barMax + 8, y + 38, num(v1), { size: 12.5 });
    y += rowH;
  }
  return { b, y };
}

const TEXT = {
  zh: {
    stair: { title: '每一步（一次工具调用）平均花多少美分', sub: '从最早没调整到现在 −39%', foot: '每段是一次改规矩之后的那几天；花费按估算价目算（见数据报告“口径”），不是账单。',
      bars: [['最早没调整', '9/14–10/2'], ['全开最高档', '10/3–10/12'], ['降档+程序先查', '10/13–11/4'], ['一事一对话', '11/5–11/10'], ['只用高两档', '11/10–11/11'], ['源头限读', '11/11–11/16']] },
    ba: { title: '最早没调整（9/14–10/2） vs 现在（11/11 夜–11/16）', sub: '好的坏的都放；停工的小时不算进“干活小时”。', legend: ['最早没调整', '现在'], good: '变好的', bad: '变差的',
      goodRows: ['每一步花费（美分）', '每一步新读入（千 token）', '整份读文件的占比（%）', '每个干活小时交付（份）'], badRows: ['每份交付花费（美元）', '每美元写进程序（字）', '子代理花费占比（%）', '上下文超 25 万的会话占比（%）'],
      chg: ['−39%', '−43%', '−35 点', '+74%', '+19%', '−21%', '+27 点', '+10 点'], foot: '每行各用自己的刻度，只比同一行的前后两根。数据：本机全部会话记录，同一条回复只算一次。' },
    tw: { title: '测试超过 10 分钟的 716 次里，67% 是在排队', sub: '11/11–11/16 一共 4,212 次测试。', parts: ['排队等位', '真跑得慢', '两者叠加'], times: '次',
      lines: ['为什么排队：测试位一度从 8 减到 4（8 份同时跑内存不够，把正在用的服务挤卡），某晚还临时减到 1；', '二十来路会话同时要测试，于是排长队。真跑慢的主要是合并、验收时跑整套（中位约 19 分钟，最长 74 分钟）。'],
      fix: '对策（v70）：', fixes: ['① 会话和测试共用一个总池（20 位）  ② 整套只准合并 / 验收跑、最多 2 份，开发只跑点到的测试', '③ 单次满 15 分钟熔断  ④ 空闲内存不够不放新测试。11/19 复量效果后补进数据报告。'], foot: '来源：测试排队器的运行记录（runs.jsonl）。' },
    sv: { title: '一次子代理 vs 一个新会话（11/11 夜–11/16）', legend: ['子代理', '新会话'], rows: ['每次平均花费（美元）', '开张先读进来的量（千 token）', '这几天开了多少次'],
      lines: ['结论：单价子代理便宜，费钱在于派得太多（4 天多 916 次、4,722 美元）。要省靠“少开”：', '小的查找自己按行读，非开不可的才开。每行各用自己的刻度。'] },
    cx: { title: 'Codex 那边也一样吗：用得最多的一天 vs 11/15', sub: 'Claude 最多是 10/8，Codex 最多是 10/31（本机有记录的日子里）。', legend: ['用得最多的一天', '11/15'],
      rows: ['Claude 每步重读前文（万 token）', 'Codex 每步重读前文（万 token）', 'Claude 整份读文件（%）', 'Codex 整份读文件（%）'], chg: ['−45%', '+35%', '−42 点', '−12 点'], scale: 1,
      foot: '量这组数时两个钩子只装在 Claude 上；Codex 本机记录约是官方用量页的七成，只比趋势。' },
  },
  en: {
    stair: { title: 'Average cost per step (one tool call), in cents', sub: '−39% from the untuned baseline to now', foot: 'Each bar covers the days after one rule change. Costs are estimates from a price table (see Methodology), not invoices.',
      bars: [['Baseline', 'Sep 14–Oct 2'], ['Max effort', 'Oct 3–12'], ['Lower effort', 'Oct 13–Nov 4'], ['1 task/chat', 'Nov 5–10'], ['high/xhigh', 'Nov 10–11'], ['Read limits', 'Nov 11–16']] },
    ba: { title: 'Baseline (Sep 14–Oct 2) vs now (Nov 11 night–Nov 16)', sub: 'Good and bad both shown. Idle hours are not counted as working hours.', legend: ['Baseline', 'Now'], good: 'Better', bad: 'Worse',
      goodRows: ['Cost per step (cents)', 'Fresh input per step (k tokens)', 'Whole-file reads (%)', 'Deliveries per working hour'], badRows: ['Cost per delivery (USD)', 'Code chars written per USD', 'Subagent share of spend (%)', 'Sessions over 250k context (%)'],
      chg: ['−39%', '−43%', '−35 pts', '+74%', '+19%', '−21%', '+27 pts', '+10 pts'], foot: 'Each row has its own scale; compare only the two bars in a row. Data: all sessions on one machine, each reply counted once.' },
    tw: { title: '67% of the 716 tests that took >10 min were waiting', sub: '4,212 test runs between Nov 11 and Nov 16.', parts: ['Waiting', 'Slow run', 'Both'], times: 'runs',
      lines: ['Why the queue: test slots were cut from 8 to 4 (8 at once ran out of memory and froze a live service),', 'once to 1, with ~20 sessions wanting tests. Slow runs: mostly full suites at merge/review (median ~19 min).'],
      fix: 'Fix (rules v70):', fixes: ['1) one shared pool for sessions + tests (20)  2) full suites only for merge/review, max 2; dev runs targeted tests', '3) 15-minute circuit breaker  4) no new tests when free memory is low. To be re-measured Nov 19.'], foot: 'Source: the test queue run log (runs.jsonl).' },
    sv: { title: 'One subagent run vs one fresh session (Nov 11 night–Nov 16)', legend: ['Subagent', 'Fresh session'], rows: ['Average cost per run (USD)', 'Context read at start (k tokens)', 'How many were started'],
      lines: ['Per run, a subagent is cheaper. We overspent because we spawned too many (916 in ~4 days, $4,722).', 'To save: spawn fewer; do small lookups yourself by line range. Each row has its own scale.'] },
    cx: { title: 'Does Codex behave the same? Busiest day vs Nov 15', sub: 'Busiest day: Claude Oct 8, Codex Oct 31 (among days with local logs).', legend: ['Busiest day', 'Nov 15'],
      rows: ['Claude: prior context re-read per step (k)', 'Codex: prior context re-read per step (k)', 'Claude: whole-file reads (%)', 'Codex: whole-file reads (%)'], chg: ['−45%', '+35%', '−42 pts', '−12 pts'], scale: 10,
      foot: 'When measured, the two hooks were only on Claude. Codex local logs are ~70% of its usage page: compare trends only.' },
  },
};

function staircase(L) {
  const v = [10.5, 9.8, 9.9, 9.2, 7.5, 6.4];
  const W = 760; const H = 360; const x0 = 40; const base = 270; const bw = 72; const gap = 44; const k = 16;
  let b = t(24, 34, L.title, { size: 18, bold: true }) + t(24, 56, L.sub, { size: 12.5, fill: C.ink2 });
  b += `<line x1="${x0 - 10}" y1="${base}" x2="${W - 20}" y2="${base}" stroke="${C.grid}"/>`;
  L.bars.forEach(([name, date], i) => {
    const x = x0 + i * (bw + gap); const h = v[i] * k;
    b += barUp(x, base - h, bw, h, i === 0 ? C.before : i === v.length - 1 ? C.after : C.mid);
    b += t(x + bw / 2, base - h - 8, v[i].toFixed(1), { size: 15, bold: true, anchor: 'middle' });
    b += t(x + bw / 2, base + 20, name, { size: 12.5, anchor: 'middle' });
    b += t(x + bw / 2, base + 38, date, { size: 11.5, fill: C.muted, anchor: 'middle' });
  });
  return svg(W, H, b + t(24, H - 14, L.foot, { size: 11.5, fill: C.muted }));
}

function beforeAfter(L) {
  const good = [[10.5, 6.4], [3.67, 2.08], [51, 16], [3.1, 5.4]]; const bad = [[16.6, 19.7], [2020, 1588], [17, 44], [33, 43]];
  const W = 760; const H = 96 + 8 * 62 + 68 + 40;
  let b = t(24, 34, L.title, { size: 18, bold: true }) + t(24, 56, L.sub, { size: 12.5, fill: C.ink2 }) + legend(24, 80, [[L.legend[0], C.before], [L.legend[1], C.after]]);
  let y = 96;
  const group = (title, names, vals, off) => {
    y += 22; b += t(24, y, title, { size: 14.5, bold: true }); y += 12;
    const r = pairedRows(names.map((n, i) => [n, vals[i][0], vals[i][1], L.chg[off + i]]), y, [C.before, C.after]); b += r.b; y = r.y;
  };
  group(L.good, L.goodRows, good, 0); group(L.bad, L.badRows, bad, 4);
  return svg(W, H, b + t(24, H - 14, L.foot, { size: 11.5, fill: C.muted }));
}

function testWait(L) {
  const W = 760; const H = 330; const n = [479, 126, 111]; const col = [C.after, C.slow, C.both]; const total = 716; const bw = 700;
  let b = t(24, 34, L.title, { size: 18, bold: true }) + t(24, 56, L.sub, { size: 12.5, fill: C.ink2 });
  let x = 30;
  n.forEach((v, i) => {
    const w = (v / total) * bw;
    b += `<rect x="${x}" y="84" width="${w - 2}" height="34" fill="${col[i]}"/>`;
    b += t(x + 6, 140, `${L.parts[i]} ${v} ${L.times}`, { size: 13 }) + t(x + 6, 158, `${Math.round((v / total) * 100)}%`, { size: 12.5, fill: C.ink2, bold: true });
    x += w;
  });
  b += t(24, 200, L.lines[0], { size: 13 }) + t(24, 220, L.lines[1], { size: 13 }) + t(24, 252, L.fix, { size: 13.5, bold: true });
  b += t(24, 274, L.fixes[0], { size: 13 }) + t(24, 294, L.fixes[1], { size: 13 });
  return svg(W, H, b + t(24, H - 12, L.foot, { size: 11.5, fill: C.muted }));
}

function subVsSession(L) {
  const W = 760; const H = 300; const vals = [[5.2, 9.1], [75, 110], [916, 656]];
  let b = t(24, 34, L.title, { size: 18, bold: true }) + legend(24, 64, [[L.legend[0], C.after], [L.legend[1], C.before]]);
  const r = pairedRows(L.rows.map((nm, i) => [nm, vals[i][0], vals[i][1]]), 80, [C.after, C.before], 330, 360, 52);
  b += r.b + t(24, r.y + 32, L.lines[0], { size: 13 }) + t(24, r.y + 52, L.lines[1], { size: 13 });
  return svg(W, H, b);
}

function codexVsClaude(L) {
  const vals = [[38.0, 20.8], [15.3, 20.7], [57, 15], [22, 10]];
  const W = 760; const H = 96 + 4 * 62 + 50;
  let b = t(24, 34, L.title, { size: 18, bold: true }) + t(24, 56, L.sub, { size: 12.5, fill: C.ink2 }) + legend(24, 80, [[L.legend[0], C.before], [L.legend[1], C.after]]);
  const r = pairedRows(L.rows.map((nm, i) => [nm, i < 2 ? +(vals[i][0] * L.scale).toFixed(1) : vals[i][0], i < 2 ? +(vals[i][1] * L.scale).toFixed(1) : vals[i][1], L.chg[i]]), 96, [C.before, C.after]);
  return svg(W, H, b + r.b + t(24, H - 14, L.foot, { size: 11.5, fill: C.muted }));
}

const CHARTS = [['cost-per-step', staircase, 'stair'], ['before-after', beforeAfter, 'ba'], ['test-wait', testWait, 'tw'], ['subagent-vs-session', subVsSession, 'sv'], ['codex-vs-claude', codexVsClaude, 'cx']];
for (const [lang, dir] of [['zh', 'images'], ['en', path.join('images', 'en')]]) {
  const out = path.join(__dirname, dir);
  fs.mkdirSync(out, { recursive: true });
  for (const [name, fn, key] of CHARTS) fs.writeFileSync(path.join(out, `${name}.svg`), fn(TEXT[lang][key]));
}
console.log('docs/images/*.svg + docs/images/en/*.svg 已生成');
