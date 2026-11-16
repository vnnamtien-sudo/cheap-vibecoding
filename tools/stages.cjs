#!/usr/bin/env node
'use strict';
// stages: 只读。把本机 Claude Code 会话记录按“阶段”（你改规矩的时间点）切开，算每段的花费、读入、产出，
// 用来回答“这次改规矩到底省没省”。数据报告 docs/data-report.md 里的数字就是它算的。
//
//   node tools/stages.cjs --stages config/stages.example.json
//        [--projects ~/.claude/projects] [--deliveries <交付记录目录>] [--out stages-out.json]
//
// 口径（和数据报告一致）：
//   - 同一条回复会拆成几行写进记录，按回复编号（message.id）全局只算一次；同一次工具调用按 tool_use id 只算一次。
//   - 花费是按价目表估算的“等价美元”，不是账单；价目在 stages 配置的 prices 里，按你的套餐改。
//     公式：输入×入价 + 缓存写(5分钟)×入价×1.25 + 缓存写(1小时)×入价×2 + 缓存读×cacheReadPrice + 输出×出价，单位每百万 token。
//   - “一步”= 一次工具调用。“新读入”= 输入 + 缓存写（不含缓存读），即真正新进上下文的量。
//   - “干活的小时”= 当小时花费 ≥ activeHourMinUSD（默认 1 美元）的小时；停工的小时不算。
//   - 交付份数：给了 --deliveries 才算，数目录里文件名以 YYYY-MM-DD 开头的文件；份数只是粗口径，大小不一。
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

function arg(name, dflt) { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : dflt; }
const home = (p) => String(p).replace(/^~(?=$|[\\/])/, os.homedir());

const DEFAULT_PRICES = { opus: [4, 20], fable: [8, 40], sonnet: [3, 15], haiku: [1, 5], default: [4, 20], cacheReadPrice: 0.2 };
const CODE = /\.(c?js|mjs|ts|tsx|jsx|py|ps1|cmd|bat|sql|css|vue|sh|go|rs|java|kt|rb|php|cs)$/i;
const TEST = /pytest|manage\.py test|npm (run )?test|node --test|\.test\.c?js|test-queue/;

function priceOf(prices, model) {
  for (const [k, v] of Object.entries(prices)) if (Array.isArray(v) && k !== 'default' && model.includes(k)) return v;
  return prices.default || DEFAULT_PRICES.default;
}
function costOf(u, p, cacheRead) {
  const cw = u.cache_creation || {};
  const w5 = cw.ephemeral_5m_input_tokens ?? u.cache_creation_input_tokens ?? 0;
  const w1 = cw.ephemeral_1h_input_tokens ?? 0;
  const c = ((u.input_tokens || 0) * p[0] + w5 * p[0] * 1.25 + w1 * p[0] * 2 + (u.cache_read_input_tokens || 0) * cacheRead + (u.output_tokens || 0) * p[1]) / 1e6;
  return { c, fresh: (u.input_tokens || 0) + w5 + w1, ctx: (u.input_tokens || 0) + w5 + w1 + (u.cache_read_input_tokens || 0) };
}

function listJsonl(dir, acc = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) listJsonl(p, acc); else if (e.name.endsWith('.jsonl')) acc.push(p);
  }
  return acc;
}

async function main() {
  const conf = JSON.parse(fs.readFileSync(arg('--stages', 'config/stages.example.json'), 'utf8'));
  const root = home(arg('--projects', conf.projects || '~/.claude/projects'));
  const prices = { ...DEFAULT_PRICES, ...(conf.prices || {}) };
  const minHour = conf.activeHourMinUSD ?? 1;
  const ctxLine = conf.bigContextTokens ?? 250000;
  const ST = conf.stages.map((s) => ({ ...s, a: Date.parse(s.from), b: s.to ? Date.parse(s.to) : Date.now() }));
  const stageOf = (t) => ST.find((s) => t >= s.a && t < s.b) || null;
  const blank = () => ({ cost: 0, sub: 0, fresh: 0, steps: 0, readLim: 0, readAll: 0, tests: 0, testLong: 0, code: 0, ctx: {}, runs: {}, first: Infinity, last: 0, dlv: 0 });
  const S = Object.fromEntries(ST.map((s) => [s.key, blank()]));
  const hourCost = {}; const seenMsg = new Set(); const seenTool = new Set(); const testPend = new Map();
  const files = listJsonl(root);
  for (const f of files) {
    const isSub = /subagents/.test(f);
    const runId = isSub ? f : path.basename(f, '.jsonl');
    const sid = isSub ? path.basename(path.dirname(path.dirname(f))) : runId;
    const rl = readline.createInterface({ input: fs.createReadStream(f, 'utf8'), crlfDelay: Infinity });
    for await (const ln of rl) {
      if (!ln || ln[0] !== '{') continue;
      let o; try { o = JSON.parse(ln); } catch (_) { continue; }
      const t = Date.parse(o.timestamp || ''); if (!t) continue;
      const st = stageOf(t); if (!st) continue;
      const s = S[st.key]; const m = o.message;
      if (o.type === 'assistant' && m && m.usage && m.id && !seenMsg.has(m.id)) {
        seenMsg.add(m.id);
        const sub = isSub || o.isSidechain === true;
        const { c, fresh, ctx } = costOf(m.usage, priceOf(prices, m.model || ''), prices.cacheReadPrice);
        s.cost += c; s.fresh += fresh; if (sub) s.sub += c;
        if (t < s.first) s.first = t; if (t > s.last) s.last = t;
        const h = Math.floor(t / 3600000); hourCost[h] = (hourCost[h] || 0) + c;
        if (!sub) s.ctx[sid] = Math.max(s.ctx[sid] || 0, ctx);
        const r = s.runs[runId] = s.runs[runId] || { sub, cost: 0 }; r.cost += c;
      }
      if (!m || !Array.isArray(m.content)) continue;
      for (const b of m.content) {
        if (b.type === 'tool_use' && b.id && !seenTool.has(b.id)) {
          seenTool.add(b.id); s.steps += 1; const inp = b.input || {};
          if (b.name === 'Read') { if (inp.limit) s.readLim += 1; else s.readAll += 1; }
          if ((b.name === 'Bash' || b.name === 'PowerShell') && TEST.test(String(inp.command || '')) && !inp.run_in_background) testPend.set(b.id, t);
          if (CODE.test(String(inp.file_path || ''))) {
            if (b.name === 'Edit') s.code += String(inp.new_string || '').length;
            else if (b.name === 'Write') s.code += String(inp.content || '').length;
            else if (b.name === 'MultiEdit') for (const e of inp.edits || []) s.code += String(e.new_string || '').length;
          }
        }
        if (b.type === 'tool_result' && testPend.has(b.tool_use_id)) {
          const d = t - testPend.get(b.tool_use_id); testPend.delete(b.tool_use_id); s.tests += 1; if (d > 600000) s.testLong += 1;
        }
      }
    }
  }
  const dlvDir = arg('--deliveries');
  if (dlvDir) {
    for (const n of fs.readdirSync(dlvDir)) {
      const mm = /^(\d{4}-\d{2}-\d{2})/.exec(n); if (!mm) continue;
      let t = new Date(`${mm[1]}T12:00:00`).getTime();
      const bt = fs.statSync(path.join(dlvDir, n)).birthtimeMs;
      const d = new Date(bt); const local = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      if (local === mm[1]) t = bt; // 同一天的按创建时刻细分到阶段
      const st = stageOf(t); if (st) S[st.key].dlv += 1;
    }
  }
  const out = {};
  for (const st of ST) {
    const s = S[st.key]; if (!s.steps) continue;
    const a = Math.max(st.a, s.first); const b = Math.min(st.b, Date.now());
    let act = 0; for (let h = Math.floor(a / 3600000); h < Math.floor(b / 3600000); h += 1) if ((hourCost[h] || 0) >= minHour) act += 1;
    const ctx = Object.values(s.ctx); const runs = Object.values(s.runs);
    const avg = (xs) => (xs.length ? +(xs.reduce((x, r) => x + r.cost, 0) / xs.length).toFixed(2) : null);
    out[st.key] = {
      name: st.name, from: new Date(a).toISOString().slice(0, 16), to: new Date(b).toISOString().slice(0, 16), days: +((b - a) / 864e5).toFixed(1),
      costUSD: Math.round(s.cost), steps: s.steps, centPerStep: +((s.cost / s.steps) * 100).toFixed(1), freshInKPerStep: +(s.fresh / s.steps / 1000).toFixed(2),
      wholeFileReadPct: Math.round((s.readAll / Math.max(1, s.readAll + s.readLim)) * 100), subagentCostPct: Math.round((s.sub / s.cost) * 100),
      sessions: ctx.length, bigContextPct: Math.round((ctx.filter((x) => x > ctxLine).length / Math.max(1, ctx.length)) * 100),
      foregroundTests: s.tests, testsOver10minPct: +((s.testLong / Math.max(1, s.tests)) * 100).toFixed(1), codeCharsPerUSD: Math.round(s.code / s.cost),
      usdPerSubagentRun: avg(runs.filter((r) => r.sub)), usdPerSession: avg(runs.filter((r) => !r.sub)),
      activeHours: act, usdPerActiveHour: Math.round(s.cost / Math.max(1, act)),
      ...(dlvDir ? { deliveries: s.dlv, usdPerDelivery: +(s.cost / Math.max(1, s.dlv)).toFixed(1), deliveriesPerActiveHour: +(s.dlv / Math.max(1, act)).toFixed(2) } : {}),
    };
  }
  const outFile = arg('--out', 'stages-out.json');
  fs.writeFileSync(outFile, JSON.stringify({ files: files.length, uniqueReplies: seenMsg.size, stages: out }, null, 1));
  for (const [k, r] of Object.entries(out)) {
    console.log(`${k} ${r.name} ${r.from.slice(0, 10)}~${r.to.slice(0, 10)} $${r.costUSD} 每步${r.centPerStep}¢ 新读${r.freshInKPerStep}k 整份读${r.wholeFileReadPct}% 帮手${r.subagentCostPct}% 大上下文${r.bigContextPct}% 字/$${r.codeCharsPerUSD}${r.deliveries != null ? ` 交付${r.deliveries} $/份${r.usdPerDelivery} 份/h${r.deliveriesPerActiveHour}` : ''}`);
  }
  console.log(`明细写到 ${outFile}`);
}

main().catch((e) => { console.error(e.message); process.exitCode = 1; });
