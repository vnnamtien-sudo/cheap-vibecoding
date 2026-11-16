#!/usr/bin/env node
'use strict';
// Claude Code PreToolUse hook: tests must go through the queue (tools/test-queue.cjs).
// 测试排队钩子：Bash / PowerShell 里跑测试（pytest、manage.py test、npm test、node --test 等，
//   含 bash xx.sh 脚本里跑的）没经 tools/test-queue.cjs run 排队的，拒绝并给出改写好的命令。
// 钩子自己出错一律放行（不输出、退出码 0），不能因为钩子坏了卡住所有会话。
// 开关：config/test-queue.json 的 hookEnabled。
const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = process.env.TEST_QUEUE_ROOT || path.join(__dirname, '..');
const QUEUE = path.join(ROOT, 'tools', 'test-queue.cjs').replace(/\\/g, '/');
const READ_ONLY = new Set(['grep', 'egrep', 'rg', 'cat', 'head', 'tail', 'less', 'more', 'echo', 'printf', 'ls', 'dir', 'find', 'wc',
  'sed', 'awk', 'git', 'diff', 'jq', 'type', 'select-string', 'get-content', 'write-output', 'write-host', 'test', '[', 'rm', 'mv', 'cp', 'mkdir', 'touch']);

function loadConfig() {
  try { return JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'test-queue.json'), 'utf8')); } catch (_) { return {}; }
}

// ---- 拆命令 ----
function splitSegments(cmd) {
  const segs = [];
  let start = 0; let q = null;
  const push = (end) => {
    const raw = cmd.slice(start, end);
    const lead = raw.length - raw.trimStart().length;
    const text = raw.trim();
    if (text) segs.push({ text, start: start + lead, end: start + lead + text.length });
  };
  for (let i = 0; i < cmd.length; i += 1) {
    const c = cmd[i];
    if (q) {
      if (c === q) q = null;
      else if (c === '\\' && q === '"') i += 1;
      continue;
    }
    if (c === '"' || c === "'") { q = c; continue; }
    if (c === '\\' && cmd[i + 1] === '\n') { i += 1; continue; } // 续行
    let sepLen = 0;
    if (c === '\n' || c === ';' || c === '(' || c === ')' || c === '{' || c === '}') sepLen = 1;
    else if (c === '|') sepLen = cmd[i + 1] === '|' ? 2 : 1;
    else if (c === '&') {
      if (cmd[i - 1] === '>' || cmd[i + 1] === '>') continue; // 2>&1、&>
      sepLen = cmd[i + 1] === '&' ? 2 : 1;
    } else if (c === '$' && cmd[i + 1] === '(') sepLen = 2;
    if (sepLen) { push(i); start = i + sepLen; i += sepLen - 1; }
  }
  push(cmd.length);
  return segs;
}

function tokenize(text) {
  const toks = []; let cur = ''; let has = false; let q = null;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (q) {
      if (c === q) q = null;
      else if (c === '\\' && q === '"' && text[i + 1] === '"') { cur += '"'; i += 1; } else cur += c;
      continue;
    }
    if (c === '"' || c === "'") { q = c; has = true; continue; }
    if (c === '\\' && text[i + 1] === '\n') { i += 1; continue; }
    if (/\s/.test(c)) { if (has) { toks.push(cur); cur = ''; has = false; } continue; }
    cur += c; has = true;
  }
  if (has) toks.push(cur);
  // 去掉重定向
  const out = [];
  for (let i = 0; i < toks.length; i += 1) {
    const t = toks[i];
    if (/^\d*(>>?|<)&?\d*$/.test(t) || /^&>>?$/.test(t)) { i += 1; continue; }
    if (/^\d*(>>?|<)/.test(t) || /^&>/.test(t)) continue;
    out.push(t);
  }
  return out;
}

function base(t) {
  return String(t).replace(/\\/g, '/').split('/').pop().toLowerCase().replace(/\.(exe|cmd|bat)$/, '');
}

function toFsPath(p, cwd) {
  let s = String(p);
  if (s.startsWith('~')) s = os.homedir() + s.slice(1);
  const m = /^\/([a-zA-Z])\/(.*)$/.exec(s);
  if (m) s = `${m[1].toUpperCase()}:/${m[2]}`;
  return path.resolve(cwd || process.cwd(), s);
}

// ---- 一段命令是不是跑测试 ----
// 返回 null（不是）| {why} | {queued:true}
function analyze(tokens, ctx, depth) {
  let t = tokens.slice();
  for (let guard = 0; guard < 20 && t.length; guard += 1) {
    const b = base(t[0]);
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(t[0])) { t.shift(); continue; }
    if (['if', 'then', 'else', 'elif', 'do', 'while', 'until', '!', 'sudo'].includes(b)) { t.shift(); continue; }
    if (['env', 'time', 'nohup', 'exec', 'command', 'builtin', 'nice', 'winpty', 'stdbuf', 'call'].includes(b)) {
      t.shift(); while (t.length && t[0].startsWith('-')) t.shift(); continue;
    }
    if (b === 'timeout') { t.shift(); while (t.length && t[0].startsWith('-')) t.shift(); t.shift(); continue; }
    if (['uv', 'poetry', 'pipenv', 'pdm', 'hatch', 'rye'].includes(b) && t[1] === 'run') {
      t = t.slice(2); while (t.length && t[0].startsWith('-')) { const o = t.shift(); if (/^--(with|python|env-file|project|directory|group|extra)$/.test(o)) t.shift(); } continue;
    }
    if (b === 'conda' && t[1] === 'run') {
      t = t.slice(2); while (t.length && t[0].startsWith('-')) { const o = t.shift(); if (/^(-n|--name|-p|--prefix)$/.test(o)) t.shift(); } continue;
    }
    break;
  }
  if (!t.length) return null;
  const b = base(t[0]);
  const args = t.slice(1);
  const joined = t.join(' ');
  if (b === 'node' || b === 'nodejs') {
    const si = args.findIndex((a) => !a.startsWith('-'));
    const pre = si < 0 ? args : args.slice(0, si);
    if (pre.some((a) => a === '--test' || a.startsWith('--test='))) return { why: 'node --test' };
    if (si >= 0 && base(args[si]) === 'test-queue.cjs') return args[si + 1] === 'run' ? { queued: true } : null;
    const dd = args.indexOf('--'); // 经别的包装程序跑测试（如 node "$Q" --lane x -- pytest …）
    if (dd >= 0) {
      const r2 = analyze(args.slice(dd + 1), ctx, depth + 1);
      if (r2 && r2.why) return { why: `经别的工具跑的 ${r2.why}` };
    }
    return null;
  }
  if (READ_ONLY.has(b)) return null;
  if (b === 'cd' || b === 'set-location' || b === 'sl' || b === 'pushd' || b === 'chdir') {
    const d = args.find((a) => !a.startsWith('-'));
    if (d) ctx.cwd = toFsPath(d, ctx.cwd);
    return null;
  }
  if (b === 'pytest' || b === 'py.test') return { why: 'pytest' };
  if (/^(python|pythonw|py)(\d+(\.\d+)?)?$/.test(b) || /^\$\{?[A-Za-z_]/.test(t[0])) return analyzePython(args, b);
  if (['npm', 'pnpm', 'yarn', 'bun'].includes(b)) {
    if (['test', 't', 'tst'].includes(args[0])) return { why: `${b} test` };
    if (['run', 'run-script'].includes(args[0]) && /^test(:|$)/.test(args[1] || '')) return { why: `${b} run test` };
    if (['exec', 'dlx', 'x'].includes(args[0])) return runnerName(args.slice(1));
    return null;
  }
  if (['npx', 'pnpx', 'bunx'].includes(b)) return runnerName(args);
  if (['jest', 'vitest', 'mocha', 'ava'].includes(b)) return { why: b };
  if (['go', 'cargo', 'dotnet', 'mvn', 'gradle'].includes(b) && args[0] === 'test') return { why: `${b} test` };
  if (b === 'cmd' && args[0] && /^\/[ck]$/i.test(args[0])) return detect(args.slice(1).join(' '), ctx, depth + 1);
  if (['bash', 'sh', 'zsh', 'dash'].includes(b)) {
    for (let i = 0; i < args.length; i += 1) {
      const a = args[i];
      if (a === '-c' || /^-[a-z]*c$/.test(a)) return args[i + 1] ? detect(args[i + 1], ctx, depth + 1) : null;
      if (a.startsWith('-')) continue;
      return script(a, ctx, depth);
    }
    return null;
  }
  if (b === 'powershell' || b === 'pwsh') {
    for (let i = 0; i < args.length; i += 1) {
      const a = args[i].toLowerCase();
      if (a === '-file' || a === '-f') return args[i + 1] ? script(args[i + 1], ctx, depth) : null;
      if (a === '-command' || a === '-c') return detect(args.slice(i + 1).join(' '), ctx, depth + 1);
      if (/^-(executionpolicy|ep|windowstyle|w)$/.test(a)) { i += 1; continue; }
      if (a.startsWith('-')) continue;
      return detect(args.slice(i).join(' '), ctx, depth + 1);
    }
    return null;
  }
  if ((b === 'source' || b === '.') && args[0]) return script(args[0], ctx, depth);
  if (/\.(sh|bash|ps1)$/i.test(t[0])) return script(t[0], ctx, depth);
  return null;
}

function analyzePython(args, b) {
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i];
    if (a === '-m') {
      const mod = args[i + 1] || '';
      if (/^(pytest|py\.test|unittest)$/.test(mod)) return { why: `python -m ${mod}` };
      if (mod === 'django' && args.slice(i + 2).find((x) => !x.startsWith('-')) === 'test') return { why: 'django test' };
      return null;
    }
    if (a === '-c') return null;
    if (a === '-X' || a === '-W') { i += 1; continue; }
    if (a.startsWith('-')) continue;
    if (base(a) === 'manage.py' && args.slice(i + 1).find((x) => !x.startsWith('-')) === 'test') return { why: 'manage.py test' };
    if (/^\$/.test(b) && (a === 'pytest' || a === 'py.test')) return { why: 'pytest' };
    return null;
  }
  return null;
}

function runnerName(args) {
  const n = args.find((a) => !a.startsWith('-'));
  return n && ['jest', 'vitest', 'mocha', 'playwright', 'ava', 'tap', 'pytest'].includes(base(n)) ? { why: base(n) } : null;
}

function script(p, ctx, depth) {
  if (depth >= 3 || /^\$/.test(p)) return null;
  const file = toFsPath(p, ctx.cwd);
  let text;
  try {
    const st = fs.statSync(file);
    if (!st.isFile() || st.size > 512 * 1024) return null;
    text = fs.readFileSync(file, 'utf8');
  } catch (_) { return null; }
  const body = text.split(/\r?\n/).filter((l) => !/^\s*#/.test(l)).join('\n');
  const r = detect(body, { cwd: ctx.cwd }, depth + 1, true);
  if (r && r.why) return { why: `脚本 ${path.basename(file)} 里的 ${r.why}`, inScript: true };
  return null;
}

// 整条命令：返回第一处没排队的测试 {why, seg}；没有返回 null
function detect(cmd, ctx, depth, inScript) {
  if (depth > 4) return null;
  for (const seg of splitSegments(String(cmd || ''))) {
    let r = null;
    try { r = analyze(tokenize(seg.text), ctx, depth); } catch (_) { r = null; }
    if (!r || r.queued) continue;
    if (r.why) return { ...r, seg, inScript: !!(inScript || r.inScript) };
  }
  return null;
}

// ---- 改写建议 ----
function shQuote(s) { return `'${s.replace(/'/g, `'\\''`)}'`; }

function rewrite(cmd, seg, tool) {
  let inner = seg.text;
  if (tool === 'PowerShell') {
    inner = inner.replace(/^&\s*/, '');
  } else if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(inner) || /[$*~`]/.test(inner)) {
    inner = shQuote(inner);
  }
  const q = `node "${QUEUE}" run --label <label> -- ${inner}`;
  return cmd.slice(0, seg.start) + q + cmd.slice(seg.end);
}

function testReason(r, cmd, tool) {
  const n = Math.max(1, Math.floor(Number(loadConfig().slots) || 4));
  const head = `测试一律经排队工具跑（总池 ${n} 位，见 config/test-queue.json）。`;
  const tail = `\n<label> 写这一路的简称。排队可能超过 2 分钟，建议放后台跑；看排队：node "${QUEUE}" status`;
  if (r.inScript) {
    return `${head}这条命令要跑的脚本里有测试（${r.why}），没经排队，已拦下。改成（整个脚本放进排队）：\n${rewrite(cmd, r.seg, tool)}${tail}`;
  }
  return `${head}这条命令（${r.why}）没经排队，已拦下。改成：\n${rewrite(cmd, r.seg, tool)}${tail}`;
}

function decide(input) {
  const cfg = loadConfig();
  const tool = input.tool_name;
  const ti = input.tool_input || {};
  if (tool !== 'Bash' && tool !== 'PowerShell') return null;
  const cmd = String(ti.command || '');
  if (cfg.hookEnabled === false) return null;
  if (!/pytest|py\.test|manage\.py|unittest|test|\.sh\b|\.ps1\b|\.bash\b/i.test(cmd)) return null; // 快速放行
  const r = detect(cmd, { cwd: input.cwd || process.cwd() }, 0, false);
  return r ? testReason(r, cmd, tool) : null;
}

function main() { require('./lib/agent-io.cjs').runHook(decide); }

if (require.main === module) {
  try { main(); } catch (_) { /* 放行 */ }
  process.exitCode = 0;
} else {
  module.exports = { decide, detect };
}
