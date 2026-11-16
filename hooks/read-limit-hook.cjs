#!/usr/bin/env node
'use strict';
// Claude Code PreToolUse 钩子：读文件限流（Read-limit hook: stop dumping whole big files into context）。
//   1. Read 文本文件：超过 wholeFileMax（150）行，且没带 limit 或 limit > maxLines（60）→ 拒绝；
//      图片、PDF、ipynb、二进制不管，150 行以内不管。
//   2. Bash / PowerShell 整份倒出大文件（cat / type / Get-Content / gc 在管道最后一段、没带 -TotalCount / -Tail 等、
//      没重定向进文件），或 sed -n 'a,bp' 范围超过 60 行 → 拒绝并给改写。
// 拿不准的一律放行；钩子自己出错一律放行（不输出、退出码 0）。开关 config/read-limit.json。
const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = process.env.READ_LIMIT_ROOT || path.join(__dirname, "..");
const SKIP_EXT = new Set(['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tif', '.tiff', '.heic', '.pdf', '.ipynb',
  '.xlsx', '.xls', '.xlsm', '.docx', '.doc', '.pptx', '.zip', '.7z', '.rar', '.gz', '.exe', '.dll', '.mp4', '.mp3', '.wav',
  '.db', '.sqlite', '.woff', '.woff2', '.ttf', '.otf']);
const DUMP_BASH = new Set(['cat', 'type', 'get-content', 'gc']);
const PASS_THROUGH = new Set(['cat', 'more', 'less', 'out-host', 'out-string', 'nl']);
const LIMIT_PARAMS = /^-(totalcount|head|first|tail|last)$/i;

function loadConfig() {
  const d = { enabled: true, maxLines: 60, wholeFileMax: 150 };
  try { return { ...d, ...JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'read-limit.json'), 'utf8')) }; } catch (_) { return d; }
}

function toFsPath(p, cwd) {
  let s = String(p);
  if (s.startsWith('~')) s = os.homedir() + s.slice(1);
  const m = /^\/([a-zA-Z])\/(.*)$/.exec(s);
  if (m) s = `${m[1].toUpperCase()}:/${m[2]}`;
  return path.resolve(cwd || process.cwd(), s);
}

// 数行数，超过 cap 就停：返回 {lines, over}；不是普通文件、读不了、像二进制的返回 null。
function countLines(file, cap) {
  let st;
  try { st = fs.statSync(file); } catch (_) { return null; }
  if (!st.isFile()) return null;
  if (SKIP_EXT.has(path.extname(file).toLowerCase())) return null;
  let fd;
  try { fd = fs.openSync(file, 'r'); } catch (_) { return null; }
  try {
    const buf = Buffer.alloc(1 << 16);
    let lines = 0; let last = 10; let first = true; let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) {
      if (first && buf.subarray(0, Math.min(n, 8192)).includes(0)) return null;
      first = false;
      for (let i = 0; i < n; i += 1) if (buf[i] === 10) lines += 1;
      last = buf[n - 1];
      if (lines > cap) return { lines, over: true };
    }
    if (last !== 10 && st.size > 0) lines += 1;
    return { lines, over: lines > cap };
  } finally { fs.closeSync(fd); }
}

// ---- Read ----
function decideRead(ti, cfg) {
  const fp = ti.file_path;
  if (!fp) return null;
  const limit = ti.limit == null ? null : Number(ti.limit);
  if (limit != null && limit > 0 && limit <= cfg.maxLines) return null;
  const c = countLines(fp, cfg.wholeFileMax);
  if (!c || !c.over) return null;
  return `读文件限流：${fp} 超过 ${cfg.wholeFileMax} 行，不准整份读、也不准一次读超过 ${cfg.maxLines} 行`
    + `（本次 limit=${limit == null ? '没带' : limit}）。先用 Grep（-n）找到行号，再 Read 带 offset、limit≤${cfg.maxLines}。`
    + '要跨多个文件核对的派一次性子代理读、只交回 150 字结论。开关 config/read-limit.json。';
}

// ---- 拆命令：按 ; && || 换行 分句，句内按 | 分管道段 ----
function splitStatements(cmd) {
  const out = []; let cur = []; let buf = ''; let q = null;
  const endSeg = () => { cur.push(buf.trim()); buf = ''; };
  const endStmt = () => { endSeg(); if (cur.some(Boolean)) out.push(cur.filter(Boolean)); cur = []; };
  for (let i = 0; i < cmd.length; i += 1) {
    const c = cmd[i];
    if (q) { buf += c; if (c === q) q = null; else if (c === '\\' && q === '"') { buf += cmd[i + 1] || ''; i += 1; } continue; }
    if (c === '"' || c === "'") { q = c; buf += c; continue; }
    if (c === '\n' || c === ';') { endStmt(); continue; }
    if ((c === '&' || c === '|') && cmd[i + 1] === c) { endStmt(); i += 1; continue; }
    if (c === '|') { endSeg(); continue; }
    buf += c;
  }
  endStmt();
  return out;
}

function tokenize(seg) {
  const toks = []; const re = /"((?:[^"\\]|\\.)*)"|'([^']*)'|(\S+)/g; let m;
  while ((m = re.exec(seg))) toks.push(m[1] != null ? m[1] : m[2] != null ? m[2] : m[3]);
  return toks;
}

const hasRedirect = (toks) => toks.some((t) => /^(\d|&|\*)?>>?/.test(t) && !/^2>/.test(t));
// 单引号里是字面量，不算变量
const unsure = (seg) => /\$\(|`|\$\{|\$[A-Za-z_]|%[A-Za-z_]+%/.test(seg.replace(/'[^']*'/g, "''"));

function bigFiles(args, ctx, cfg) {
  const hits = [];
  for (const a of args) {
    if (!a || a.startsWith('-') || a.startsWith('<')) continue;
    const c = countLines(toFsPath(a, ctx.cwd), cfg.wholeFileMax);
    if (c && c.over) hits.push(a);
  }
  return hits;
}

function dumpReason(file, cfg, ps) {
  const n = cfg.maxLines;
  const fix = ps
    ? `Select-String -Path "${file}" -Pattern "关键词" | Select-Object -First 20 找行号，再 Get-Content "${file}" | Select-Object -Skip <起行-1> -First ${n}`
    : `grep -n "关键词" "${file}" | head -20 找行号，再 sed -n '<起>,<起+${n - 1}>p' "${file}"`;
  return `读文件限流：${file} 超过 ${cfg.wholeFileMax} 行，不准整份倒到屏幕。改成：${fix}（每次 ≤${n} 行）；`
    + '要全文处理的把输出重定向进临时文件、屏幕只打结论 ≤15 行。开关 config/read-limit.json。';
}

function sedReason(seg, toks, ctx, cfg) {
  if (toks[0] !== 'sed' || toks[1] !== '-n') return null;
  const m = /^(\d+),(\d+|\$)p$/.exec(toks[2] || '');
  if (!m || toks.length !== 4) return null;
  const c = countLines(toFsPath(toks[3], ctx.cwd), cfg.wholeFileMax);
  if (!c || !c.over) return null;
  const a = Number(m[1]);
  if (m[2] === '$') {
    const full = countLines(toFsPath(toks[3], ctx.cwd), Infinity);
    if (!full || full.lines - a + 1 <= cfg.maxLines) return null;
  } else if (Number(m[2]) - a + 1 <= cfg.maxLines) return null;
  return `读文件限流：${seg} 一次超过 ${cfg.maxLines} 行。改成 sed -n '${a},${a + cfg.maxLines - 1}p' "${toks[3]}"，要更多先 grep -n 定位。开关 config/read-limit.json。`;
}

// 去掉 heredoc / PowerShell here-string 正文（正文是数据，不是命令）
function stripHeredocs(cmd) {
  let s = cmd.replace(/@'[\s\S]*?\n'@/g, "''").replace(/@"[\s\S]*?\n"@/g, "''");
  const re = /<<-?\s*(['"]?)([A-Za-z_][\w]*)\1[^\n]*\n/g; let m; let out = ''; let pos = 0;
  while ((m = re.exec(s))) {
    const bodyStart = m.index + m[0].length;
    const end = new RegExp(`^\\s*${m[2]}\\s*$`, 'm');
    const rest = s.slice(bodyStart); const e = end.exec(rest);
    out += s.slice(pos, bodyStart);
    pos = e ? bodyStart + e.index + e[0].length : s.length;
    re.lastIndex = pos;
  }
  return out + s.slice(pos);
}

function decideShell(rawCmd, cwd, cfg, ps) {
  if (!/\b(cat|type|get-content|gc|sed)\b/i.test(rawCmd)) return null; // 快速放行
  const cmd = stripHeredocs(rawCmd);
  const ctx = { cwd };
  for (const stages of splitStatements(cmd)) {
    const first = tokenize(stages[0]);
    const h0 = (first[0] || '').toLowerCase();
    if (stages.length === 1 && ['cd', 'set-location', 'pushd', 'sl'].includes(h0) && first[1] && !unsure(stages[0])) {
      ctx.cwd = toFsPath(first[1], ctx.cwd); continue;
    }
    for (let k = 0; k < stages.length; k += 1) {
      const seg = stages[k];
      if (unsure(seg)) continue;
      const toks = tokenize(seg);
      const head = (toks[0] || '').toLowerCase();
      const rest = stages.slice(k + 1).map((s) => (tokenize(s)[0] || '').toLowerCase());
      if (!rest.every((h) => PASS_THROUGH.has(h))) continue; // 后面接了 head / grep / Select-Object 等，放行
      if (hasRedirect(toks)) continue;
      const sr = sedReason(seg, toks, ctx, cfg);
      if (sr) return sr;
      if (!DUMP_BASH.has(head)) continue;
      if (toks.slice(1).some((t) => LIMIT_PARAMS.test(t))) continue;
      const hits = bigFiles(toks.slice(1), ctx, cfg);
      if (hits.length) return dumpReason(hits[0], cfg, ps || head === 'get-content' || head === 'gc');
    }
  }
  return null;
}

function decide(input) {
  const cfg = loadConfig();
  if (!cfg.enabled) return null;
  const tool = input.tool_name; const ti = input.tool_input || {};
  if (tool === 'Read') return decideRead(ti, cfg);
  if (tool === 'Bash' || tool === 'PowerShell') return decideShell(String(ti.command || ''), input.cwd || process.cwd(), cfg, tool === 'PowerShell');
  return null;
}

function main() {
  let raw = '';
  try { raw = fs.readFileSync(0, 'utf8'); } catch (_) { return; }
  let reason = null;
  try { reason = decide(JSON.parse(raw)); } catch (_) { reason = null; }
  if (reason) {
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason },
    }));
  }
}

if (require.main === module) {
  try { main(); } catch (_) { /* 放行 */ }
  process.exitCode = 0;
} else {
  module.exports = { decide, splitStatements, tokenize, countLines };
}
