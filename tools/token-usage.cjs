#!/usr/bin/env node
'use strict';
// token-usage: 只读。统计本机 AI 编程助手会话记录（主会话 + 子代理）用了多少 token、约合多少美元。
//
//   node tools/token-usage.cjs [--agent claude|codex|gemini|deepseek|all] [--root <记录目录>] [--days 7]
//        [--week-reset <ISO 时刻>] [--five-hour-reset <ISO 时刻>]
//
//   --agent：默认 claude。codex 读 ~/.codex/sessions（+ archived_sessions）；gemini 读 ~/.gemini/tmp/*/chats（未在本机实测）；
//            deepseek 指“Claude Code 接 DeepSeek 接口”，记录和 Claude 同一处，按型号名分得开。all = 四家各出一段。
//   --root：记录不在默认位置时指定（可写多个，用英文逗号隔开）。老参数 --projects 等同 --root。
//   --week-reset / --five-hour-reset：用量页面给出的“下次重置时刻”；给了就额外算“重置前 7 天 / 5 小时”这一段。
// 价目是估算（每百万 token 美元，[输入, 输出]），不是账单；Codex、Gemini、DeepSeek 请在 PRICES 里按你的套餐补一行。
const { walk, AGENTS } = require('./lib/sessions.cjs');

function arg(name, dflt) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : dflt; }
const PRICES = [[/fable/, [8, 40]], [/sonnet/, [3, 15]], [/haiku/, [1, 5]], [/./, [4, 20]]];
const CACHE_READ = 0.2;

const blank = () => ({ replies: 0, fresh: 0, cacheRead: 0, output: 0, usd: 0 });
function add(g, u, usd) { g.replies += 1; g.fresh += u.fresh; g.cacheRead += u.cacheRead; g.output += u.output; g.usd += usd; }
const fmt = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n));
function line(name, g) {
  const all = g.fresh + g.cacheRead + g.output;
  const reread = all ? ((100 * g.cacheRead) / all).toFixed(1) : '0';
  return `${name.padEnd(22)} 回复 ${String(g.replies).padStart(7)}  合计 ${fmt(all).padStart(8)}  其中重读前文 ${reread}%  输出 ${fmt(g.output).padStart(7)}  约 $${g.usd.toFixed(0)}`;
}
function usdOf(u, model) {
  const p = PRICES.find(([re]) => re.test(model))[1];
  return (u.freshPlain * p[0] + u.cacheW5 * p[0] * 1.25 + u.cacheW1h * p[0] * 2 + u.cacheRead * CACHE_READ + u.output * p[1]) / 1e6;
}

async function one(agent, roots, days, windows, now) {
  const since = Math.min(now - days * 864e5, ...windows.map((w) => w[1]));
  const total = blank(); const byDay = {}; const byModel = {}; const subs = blank(); const win = windows.map(() => blank());
  const isDeepseek = (m) => /deepseek/i.test(m);
  const r = await walk(agent, { roots, since, onStep: (s) => {
    if (s.t < since) return;
    if (agent === 'deepseek' && !isDeepseek(s.model)) return;
    if (agent === 'claude' && isDeepseek(s.model)) return;
    const usd = usdOf(s.u, s.model);
    windows.forEach((w, i) => { if (s.t >= w[1] && s.t < w[2]) add(win[i], s.u, usd); });
    if (s.t < now - days * 864e5) return;
    add(total, s.u, usd);
    if (s.sub) add(subs, s.u, usd);
    const d = new Date(s.t); const day = `${d.getMonth() + 1}/${d.getDate()}`;
    add(byDay[day] = byDay[day] || blank(), s.u, usd);
    add(byModel[s.model] = byModel[s.model] || blank(), s.u, usd);
  } });
  console.log(`== ${agent}（记录 ${r.files} 份）`);
  console.log(line(`近 ${days} 天合计`, total));
  console.log(line('其中子代理', subs));
  for (const [k, g] of Object.entries(byModel)) console.log(line(k, g));
  for (const [k, g] of Object.entries(byDay)) console.log(line(k, g));
  windows.forEach((w, i) => console.log(line(w[0], win[i])));
}

async function main() {
  const agent = arg('--agent', 'claude');
  const roots = (arg('--root') || arg('--projects') || '').split(',').filter(Boolean);
  const days = Number(arg('--days', 7));
  const now = Date.now(); const windows = [];
  if (arg('--week-reset')) { const r = Date.parse(arg('--week-reset')); windows.push(['本周额度段', r - 7 * 864e5, r]); }
  if (arg('--five-hour-reset')) { const r = Date.parse(arg('--five-hour-reset')); windows.push(['本 5 小时段', r - 5 * 3600e3, r]); }
  for (const a of agent === 'all' ? AGENTS : [agent]) await one(a, agent === 'all' ? [] : roots, days, windows, now);
}

main().catch((e) => { console.error(e.message); process.exitCode = 1; });
