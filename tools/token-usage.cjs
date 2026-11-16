#!/usr/bin/env node
'use strict';
// token-usage: 只读。统计本机全部 Claude Code 会话记录（主会话 + 子代理）用了多少 token、约合多少美元。
//
//   node tools/token-usage.cjs [--projects ~/.claude/projects] [--days 7] [--week-reset <ISO 时刻>] [--five-hour-reset <ISO 时刻>]
//
//   --week-reset / --five-hour-reset：你的用量页面给出的“下次重置时刻”；给了就额外算“重置前 7 天 / 5 小时”这一段，
//   方便和额度百分比对着看，反推“1% 额度约等于多少 token / 美元”。
// 同一条回复会拆成几行写进记录，按 message.id 去重。价目同 tools/stages.cjs（估算，不是账单）。
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

function arg(name, dflt) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : dflt; }
const home = (p) => String(p).replace(/^~(?=$|[\\/])/, os.homedir());
const PRICES = [[/fable/, [8, 40]], [/sonnet/, [3, 15]], [/haiku/, [1, 5]], [/./, [4, 20]]];
const CACHE_READ = 0.2;

function listJsonl(dir, since, acc = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) listJsonl(p, since, acc);
    else if (e.name.endsWith('.jsonl') && fs.statSync(p).mtimeMs >= since) acc.push(p);
  }
  return acc;
}
const blank = () => ({ replies: 0, input: 0, cacheWrite: 0, cacheRead: 0, output: 0, usd: 0 });
function add(g, u, usd) {
  g.replies += 1; g.input += u.input_tokens || 0; g.cacheWrite += u.cache_creation_input_tokens || 0;
  g.cacheRead += u.cache_read_input_tokens || 0; g.output += u.output_tokens || 0; g.usd += usd;
}
const fmt = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n));
function line(name, g) {
  const all = g.input + g.cacheWrite + g.cacheRead + g.output;
  const reread = all ? ((100 * g.cacheRead) / all).toFixed(1) : '0';
  return `${name.padEnd(22)} 回复 ${String(g.replies).padStart(7)}  合计 ${fmt(all).padStart(8)}  其中重读前文 ${reread}%  输出 ${fmt(g.output).padStart(7)}  约 $${g.usd.toFixed(0)}`;
}

async function main() {
  const root = home(arg('--projects', '~/.claude/projects'));
  const days = Number(arg('--days', 7));
  const now = Date.now();
  const windows = [];
  if (arg('--week-reset')) { const r = Date.parse(arg('--week-reset')); windows.push(['本周额度段', r - 7 * 864e5, r]); }
  if (arg('--five-hour-reset')) { const r = Date.parse(arg('--five-hour-reset')); windows.push(['本 5 小时段', r - 5 * 3600e3, r]); }
  const since = Math.min(now - days * 864e5, ...windows.map((w) => w[1]));
  const seen = new Set(); const total = blank(); const byDay = {}; const byModel = {}; const subs = blank();
  const win = windows.map(() => blank());
  for (const f of listJsonl(root, since)) {
    const isSub = /subagents/.test(f);
    const rl = readline.createInterface({ input: fs.createReadStream(f, 'utf8'), crlfDelay: Infinity });
    for await (const ln of rl) {
      if (!ln.includes('"usage"')) continue;
      let o; try { o = JSON.parse(ln); } catch (_) { continue; }
      const m = o.message; const t = Date.parse(o.timestamp || '');
      if (o.type !== 'assistant' || !m || !m.usage || !m.id || seen.has(m.id) || !t || t < since) continue;
      seen.add(m.id);
      const u = m.usage; const p = PRICES.find(([re]) => re.test(m.model || ''))[1];
      const usd = ((u.input_tokens || 0) * p[0] + (u.cache_creation_input_tokens || 0) * p[0] * 1.25 + (u.cache_read_input_tokens || 0) * CACHE_READ + (u.output_tokens || 0) * p[1]) / 1e6;
      windows.forEach((w, i) => { if (t >= w[1] && t < w[2]) add(win[i], u, usd); });
      if (t < now - days * 864e5) continue;
      add(total, u, usd);
      if (isSub || o.isSidechain) add(subs, u, usd);
      const d = new Date(t); const day = `${d.getMonth() + 1}/${d.getDate()}`;
      add(byDay[day] = byDay[day] || blank(), u, usd);
      add(byModel[m.model || '?'] = byModel[m.model || '?'] || blank(), u, usd);
    }
  }
  console.log(line(`近 ${days} 天合计`, total));
  console.log(line('其中子代理', subs));
  for (const [k, g] of Object.entries(byModel)) console.log(line(k, g));
  for (const [k, g] of Object.entries(byDay)) console.log(line(k, g));
  windows.forEach((w, i) => console.log(line(w[0], win[i])));
}

main().catch((e) => { console.error(e.message); process.exitCode = 1; });
