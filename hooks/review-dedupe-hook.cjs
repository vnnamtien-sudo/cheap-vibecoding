#!/usr/bin/env node
'use strict';
// PreToolUse 钩子（Claude Code / 接 DeepSeek 的 Claude Code，挂在 Agent|Task 上）：拦重复验收。
// 我们量过：子代理的钱 68% 花在复验 / 验收上，同一个提交常被好几个会话各派一个子代理验一遍。
//   1. 派的子代理看起来是验收类（任务里有 复验 / 验收 / 审查 / review 等）→ 必须写明验哪个提交
//      （“提交 abc1234”“@abc1234”“commit abc1234”），或写“验收对象：<名字>”；都没写就拦，叫它补上。
//   2. 同一个对象 windowHours（默认 24）小时内已经有人派过验收 → 拦下，告诉它谁、几点验的。
//   3. 放行：任务里写“第二轮”（只核第一轮那几条）或“重验：<原因>”。
// 记账在 dataDir/ledger.jsonl（多个会话共用）。钩子自己出错一律放行。开关 config/review-dedupe.json。
const fs = require('fs');
const path = require('path');

const ROOT = process.env.REVIEW_DEDUPE_ROOT || path.join(__dirname, '..');
const DEFAULTS = {
  enabled: true, windowHours: 24, dataDir: 'data/review-dedupe',
  reviewWords: '复验|验收|审查|核验|核对改动|逐行核|review|audit|verify the (change|diff|commit)',
  passWords: '第二轮|重验[:：]|second round|re-review:',
};

function loadConfig() {
  try { return { ...DEFAULTS, ...JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'review-dedupe.json'), 'utf8')) }; } catch (_) { return DEFAULTS; }
}

// 验的对象：提交号（7–40 位十六进制，前面要有 提交 / @ / commit / head 之类的字样，免得把路径里的编号当提交）或“验收对象：xx”
function targetsOf(text) {
  const keys = new Set();
  for (const m of text.matchAll(/(?:提交号?|commit|@|--head\s+|head[:：=\s]+)\s*[:：]?\s*`?((?=[0-9a-f]*[a-f])[0-9a-f]{7,40})\b/gi)) keys.add(`commit:${m[1].slice(0, 7).toLowerCase()}`);
  for (const m of text.matchAll(/(?:验收对象|review target)\s*[:：]\s*([^\s，。,;；`]+)/gi)) keys.add(`name:${m[1]}`);
  return [...keys];
}

function readLedger(file, since) {
  let lines = [];
  try { lines = fs.readFileSync(file, 'utf8').split('\n'); } catch (_) { return []; }
  const out = [];
  for (const l of lines) { if (!l) continue; try { const o = JSON.parse(l); if (o.at >= since) out.push(o); } catch (_) { /* 坏行跳过 */ } }
  return out;
}

function hhmm(t) { const d = new Date(t); return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; }

function decide(input, now = Date.now()) {
  const cfg = loadConfig();
  if (!cfg.enabled) return null;
  if (input.tool_name !== 'Agent' && input.tool_name !== 'Task') return null;
  const ti = input.tool_input || {};
  const text = `${ti.description || ''}\n${ti.prompt || ''}`;
  if (!new RegExp(cfg.reviewWords, 'i').test(text.slice(0, 800))) return null;
  const keys = targetsOf(text);
  const pass = new RegExp(cfg.passWords, 'i').test(text);
  if (!keys.length && !pass) {
    return '派验收类子代理要写明验哪个提交：在任务里写“提交 <提交号>”（或 @<提交号>），没有提交的写“验收对象：<名字>”。同一对象 24 小时内只验一次，免得几个会话各验一遍（我们量过，子代理的钱 68% 花在验收上）。第二轮复核写“第二轮”，确要再验写“重验：<原因>”。';
  }
  const dir = path.resolve(ROOT, cfg.dataDir); const file = path.join(dir, 'ledger.jsonl');
  if (!pass) {
    const hit = readLedger(file, now - cfg.windowHours * 3600e3).reverse().find((o) => (o.keys || []).some((k) => keys.includes(k)));
    if (hit) {
      const k = keys.find((x) => hit.keys.includes(x)).replace(/^(commit|name):/, '');
      return `“${k}” 在 ${hhmm(hit.at)} 已经派人验过了（会话 ${String(hit.session || '?').slice(0, 8)}：${String(hit.desc || '').slice(0, 40)}）。先去拿那次的结论，不要再派一个从头验；确要再验在任务里写“重验：<原因>”，只核上次漏的写“第二轮”。`;
    }
  }
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(file, JSON.stringify({ at: now, keys, session: input.session_id || '', desc: String(ti.description || '').slice(0, 60), pass }) + '\n');
  } catch (_) { /* 记不上也放行 */ }
  return null;
}

function main() {
  let raw = '';
  try { raw = fs.readFileSync(0, 'utf8'); } catch (_) { return; }
  let reason = null;
  try { reason = decide(JSON.parse(raw)); } catch (_) { reason = null; }
  if (reason) process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason } }));
}

if (require.main === module) {
  try { main(); } catch (_) { /* 放行 */ }
  process.exitCode = 0;
} else {
  module.exports = { decide, targetsOf };
}
