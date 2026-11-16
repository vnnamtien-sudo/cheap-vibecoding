#!/usr/bin/env node
'use strict';
// test-queue: one shared pool for "AI sessions working + tests running" on one machine.
// 测试排队器：本机所有会话的测试都经它跑，避免 20 路会话同时起测试把内存和硬盘挤爆。
//
//   node tools/test-queue.cjs run --label <label> [--weight N] -- <command ...>
//   node tools/test-queue.cjs status
//   node tools/test-queue.cjs stats [--days N]
//
// 四件事（参数都在 config/test-queue.json，按自己电脑调，见 README“按你的电脑调参”）：
//   1. 总池 slots：正在干活的会话数 + 在跑测试占的位 ≤ slots，测试至少留 minTestSlots 位；
//      pytest -n K 占 K 位（-n auto 按 autoWeight 算）。
//   2. 分级：整套 / 整目录测试（没点到具体文件或用例）算“重型”，最多 heavyMax 份同时跑；
//      heavyOnlyLabels 开着时只有标签匹配 heavyLabels 的（如合并、验收）才准跑重型，开发期只跑点到的测试。
//   3. 熔断：单次跑满 timeoutMinutes 分钟强制结束整棵进程树，记 timeout，退出码 124。
//   4. 内存保护：空闲内存低于 minFreeGB 不再放新测试（在跑的不停；一个都没在跑时仍放一个）。
// 记录：<dataDir>/runs.jsonl 每次一行（标签、命令、排队毫秒、运行毫秒、结局）。
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const ROOT = process.env.TEST_QUEUE_ROOT || path.join(__dirname, '..');
const CONFIG_FILE = path.join(ROOT, 'config', 'test-queue.json');
const DEFAULTS = {
  hookEnabled: true, slots: 8, poolCountsSessions: true, sessionDirs: null, transcriptsRoot: '~/.claude/projects', activeSessionMinutes: 10,
  minTestSlots: 1, heavyMax: 1, heavyOnlyLabels: false, heavyLabels: 'merge|verify|nightly', autoWeight: 4,
  timeoutMinutes: 15, minFreeGB: 4, staleMinutes: 20, pollMs: 2000, dataDir: 'data/test-queue',
};

function expandHome(p) { return String(p || '').replace(/^~(?=$|[\\/])/, os.homedir()); }

function loadConfig() {
  let c = {};
  try { c = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')); } catch (_) { /* 没配置用默认 */ }
  const cfg = { ...DEFAULTS };
  for (const [k, v] of Object.entries(c)) if (!k.startsWith('_')) cfg[k] = v;
  cfg.slots = Math.max(1, Math.floor(Number(cfg.slots) || DEFAULTS.slots));
  cfg.minTestSlots = Math.max(1, Math.min(cfg.slots, Math.floor(Number(cfg.minTestSlots) || 1)));
  cfg.heavyMax = Math.max(1, Math.floor(Number(cfg.heavyMax) || 1));
  cfg.dataPath = path.resolve(ROOT, expandHome(cfg.dataDir));
  return cfg;
}

// ---- 状态文件（多进程共用，mkdir 当锁） ----
function sleepSync(ms) { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms); }
function alive(pid) { try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; } }
function files(cfg) {
  fs.mkdirSync(cfg.dataPath, { recursive: true });
  return { state: path.join(cfg.dataPath, 'state.json'), lock: path.join(cfg.dataPath, '.lock'), runs: path.join(cfg.dataPath, 'runs.jsonl') };
}
function withLock(cfg, fn) {
  const f = files(cfg);
  for (let i = 0; ; i += 1) {
    try { fs.mkdirSync(f.lock); break; } catch (_) {
      try { if (Date.now() - fs.statSync(f.lock).mtimeMs > 10000) fs.rmdirSync(f.lock); } catch (__) { /* 别人刚删 */ }
      if (i > 500) throw new Error('test-queue: lock busy');
      sleepSync(20);
    }
  }
  try {
    let st = { holders: [], waiters: [] };
    try { st = JSON.parse(fs.readFileSync(f.state, 'utf8')); } catch (_) { /* 第一次 */ }
    const out = fn(st);
    const tmp = `${f.state}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(st, null, 1));
    fs.renameSync(tmp, f.state);
    return out;
  } finally { try { fs.rmdirSync(f.lock); } catch (_) { /* 已删 */ } }
}
function clean(st, cfg, now = Date.now()) {
  const staleMs = cfg.staleMinutes * 60000;
  st.holders = st.holders.filter((h) => alive(h.pid));
  st.waiters = st.waiters.filter((w) => alive(w.pid) && now - (w.seen || w.since) < staleMs);
}
function used(st) { return st.holders.reduce((s, h) => s + h.weight, 0); }

// ---- 总池：正在干活的会话（会话记录最近 N 分钟写过）也占位 ----
// sessionDirs 列出要数的会话目录（四家助手各自的位置），每项 { path, ext, depth, datedDays }：
//   depth = 记录文件在 path 下第几层（Claude 是 2：项目/会话.jsonl）；datedDays 给了就只看最近几天的 年/月/日 文件夹（Codex）。
// 没写 sessionDirs 时退回老参数 transcriptsRoot（只数 Claude Code）。
const DEFAULT_SESSION_DIRS = [
  { name: 'claude', path: '~/.claude/projects', ext: '.jsonl', depth: 2 },
  { name: 'codex', path: '~/.codex/sessions', ext: '.jsonl', depth: 4, datedDays: 3 },
  { name: 'gemini', path: '~/.gemini/tmp', ext: '.json', depth: 3 },
];
function sessionDirsOf(cfg) {
  if (Array.isArray(cfg.sessionDirs)) return cfg.sessionDirs;
  return [{ name: 'claude', path: cfg.transcriptsRoot || '~/.claude/projects', ext: '.jsonl', depth: 2 }];
}
function countFresh(dir, ext, depth, cutoff) {
  let n = 0; let ents;
  try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return 0; }
  for (const e of ents) {
    const p = path.join(dir, e.name);
    if (depth > 1 && e.isDirectory()) n += countFresh(p, ext, depth - 1, cutoff);
    else if (depth === 1 && e.isFile() && e.name.endsWith(ext)) { try { if (fs.statSync(p).mtimeMs >= cutoff) n += 1; } catch (_) { /* 刚删 */ } }
  }
  return n;
}
function activeSessions(cfg, now = Date.now()) {
  if (cfg.poolCountsSessions === false) return 0;
  const cutoff = now - cfg.activeSessionMinutes * 60000;
  let n = 0;
  for (const d of sessionDirsOf(cfg)) {
    const root = expandHome(d.path); const ext = d.ext || '.jsonl'; const depth = Math.max(1, Number(d.depth) || 1);
    if (d.datedDays && depth >= 4) {
      for (let i = 0; i < d.datedDays; i += 1) {
        const t = new Date(now - i * 864e5);
        const day = path.join(root, `${t.getFullYear()}`, `${t.getMonth() + 1}`.padStart(2, '0'), `${t.getDate()}`.padStart(2, '0'));
        n += countFresh(day, ext, depth - 3, cutoff);
      }
    } else n += countFresh(root, ext, depth, cutoff); // 目录不存在就是没装这家，算 0
  }
  return n;
}
// 测试能用几位：总池减去正在干活的会话（排队等测试的会话不重复算），至少留 minTestSlots；内存不够不再放新的
function testLimit(cfg, st, active, freeBytes = os.freemem()) {
  let lim = Math.max(cfg.minTestSlots, cfg.slots - Math.max(0, active - st.holders.length - st.waiters.length));
  if (freeBytes < cfg.minFreeGB * 2 ** 30) lim = Math.min(lim, used(st));
  return lim;
}
function canGrant(st, w, limit) { const u = used(st); return u + w.weight <= limit || u === 0; }
// 快慢隔离：重型已满 heavyMax 份时，排前面的重型让开，轻的照常往前走
function headOf(st, cfg) {
  const heavyFull = st.holders.filter((h) => h.heavy).length >= cfg.heavyMax;
  return st.waiters.find((w) => !(w.heavy && heavyFull)) || null;
}

// ---- 看命令：重不重、占几位 ----
function readSmallScripts(text, cwd) {
  const out = [];
  for (const tok of String(text).split(/\s+/)) {
    const t = tok.replace(/^["']|["';]$/g, '');
    if (!/\.(sh|bash)$/i.test(t)) continue;
    try { const p = path.resolve(cwd, t); if (fs.statSync(p).size < 512 * 1024) out.push(fs.readFileSync(p, 'utf8')); } catch (_) { /* 不是文件 */ }
  }
  return out;
}
// 整套：没点到具体测试文件或用例的 pytest、manage.py test、unittest discover、npm test
function heavyText(text) {
  if (/\bnpm (run )?test\b|\byarn test\b|\bpnpm test\b/.test(text)) return true;
  return String(text).split(/\r?\n/).some((line) => {
    const m = /\b(pytest|py\.test|manage\.py\s+test|unittest\s+discover)\b(.*)$/.exec(line);
    return Boolean(m) && !/\.py\b|::|\s-k\s|\.tests?\.\w/.test(m[2]);
  });
}
function scanWeight(text, cfg) {
  let w = 0;
  const re = /(?:^|[\s"'=])(?:-n[ \t]*|--numprocesses(?:=|[ \t]+))(auto|logical|\d+)\b/g;
  for (const line of String(text).split(/\r?\n/)) {
    if (!/pytest/.test(line) && !/[A-Za-z_][A-Za-z0-9_]*=["']?-(n|-numprocesses)\b/.test(line)) continue;
    let m;
    while ((m = re.exec(line))) { const k = /^\d+$/.test(m[1]) ? Number(m[1]) : cfg.autoWeight; if (k > w) w = k; }
  }
  return w;
}
function classify(cmd, cwd, cfg) {
  const text = cmd.join(' ');
  const texts = [text, ...readSmallScripts(text, cwd)];
  const heavy = texts.some(heavyText);
  const weight = Math.min(cfg.slots, Math.max(1, ...texts.map((t) => scanWeight(t, cfg))));
  return { heavy, weight };
}

// ---- 跑命令 ----
function findBash() {
  if (process.env.TEST_QUEUE_BASH) return process.env.TEST_QUEUE_BASH;
  if (process.platform !== 'win32') return 'bash';
  for (const p of ['C:/Program Files/Git/bin/bash.exe', 'C:/Program Files (x86)/Git/bin/bash.exe']) if (fs.existsSync(p)) return p;
  return null;
}
function quoteWin(a) { return /[\s"&|<>^()]/.test(a) ? `"${a.replace(/"/g, '\\"')}"` : a; }
function killTree(pid) {
  if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' });
  else { try { process.kill(-pid, 'SIGKILL'); } catch (_) { try { process.kill(pid, 'SIGKILL'); } catch (__) { /* 已退 */ } } }
}
function startChild(cmd, onExit) {
  let file = cmd[0]; let args = cmd.slice(1);
  if (cmd.length === 1 && /\s/.test(cmd[0])) {
    const bash = findBash();
    if (bash) { file = bash; args = ['-c', cmd[0]]; } else { file = null; }
  }
  const opts = { stdio: 'inherit', detached: process.platform !== 'win32' };
  const ref = {};
  const go = (useShell) => {
    const child = useShell || file === null
      ? spawn(file === null ? cmd[0] : [file, ...args].map(quoteWin).join(' '), { ...opts, shell: true })
      : spawn(file, args, opts);
    ref.child = child;
    let done = false;
    child.on('error', (err) => {
      if (!useShell && process.platform === 'win32' && (err.code === 'ENOENT' || err.code === 'EINVAL')) { done = true; go(true); return; }
      if (!done) { done = true; process.stderr.write(`test-queue: ${err.message}\n`); onExit(127, null, child); }
    });
    child.on('exit', (code, signal) => { if (!done) { done = true; onExit(code, signal, child); } });
  };
  go(false);
  return ref; // ref.child 是当前真正在跑的子进程（Windows 上找不到程序会改走 shell 重起一次）
}

function arg(argv, name) { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; }

function cmdRun(argv) {
  const cfg = loadConfig();
  const dd = argv.indexOf('--');
  const cmd = dd >= 0 ? argv.slice(dd + 1) : [];
  if (!cmd.length) { console.error('用法：test-queue.cjs run --label <label> [--weight N] -- <command ...>'); return 2; }
  const head = dd >= 0 ? argv.slice(0, dd) : argv;
  const label = arg(head, '--label') || 'unlabeled';
  const c = classify(cmd, process.cwd(), cfg);
  if (arg(head, '--weight')) c.weight = Math.min(cfg.slots, Math.max(1, Math.floor(Number(arg(head, '--weight')) || 1)));
  if (c.heavy && cfg.heavyOnlyLabels && !new RegExp(cfg.heavyLabels, 'i').test(label)) {
    console.error(`test-queue: 这是整套 / 整目录测试，只准标签匹配 /${cfg.heavyLabels}/ 的跑。开发期请点到具体测试文件或用例。`);
    return 2;
  }
  const me = { id: `${process.pid}-${Date.now()}`, pid: process.pid, label, weight: c.weight, heavy: c.heavy, since: Date.now(), cmd: cmd.join(' ').slice(0, 300) };
  withLock(cfg, (st) => { clean(st, cfg); st.waiters.push(me); });
  const f = files(cfg);
  let granted = false; let lastNote = 0;
  const release = () => withLock(cfg, (st) => {
    st.holders = st.holders.filter((h) => h.id !== me.id); st.waiters = st.waiters.filter((w) => w.id !== me.id);
  });
  let running = null;
  const onSignal = () => {
    if (running && running.child && running.child.pid) killTree(running.child.pid);
    try { release(); } catch (_) { /* 尽力 */ }
    process.exit(130);
  };
  process.on('SIGINT', onSignal); process.on('SIGTERM', onSignal);
  while (!granted) {
    const active = activeSessions(cfg);
    granted = withLock(cfg, (st) => {
      clean(st, cfg);
      const w = st.waiters.find((x) => x.id === me.id);
      if (!w) st.waiters.push(me); else w.seen = Date.now();
      const limit = testLimit(cfg, st, active);
      const h = headOf(st, cfg);
      if (h && h.id === me.id && canGrant(st, me, limit)) {
        st.waiters = st.waiters.filter((x) => x.id !== me.id);
        st.holders.push({ ...me, startedAt: Date.now() });
        return true;
      }
      if (Date.now() - lastNote > 60000) {
        lastNote = Date.now();
        process.stderr.write(`test-queue: 排队中（在跑 ${used(st)}/${limit} 位，前面 ${st.waiters.findIndex((x) => x.id === me.id)} 个）\n`);
      }
      return false;
    });
    if (!granted) sleepSync(cfg.pollMs);
  }
  const waitMs = Date.now() - me.since; const t0 = Date.now();
  return new Promise((resolve) => {
    let outcome = 'done';
    const ref = startChild(cmd, (code, signal) => {
      clearTimeout(timer);
      const exitCode = outcome === 'timeout' ? 124 : (code == null ? 1 : code);
      release();
      const rec = { at: new Date().toISOString(), label, cmd: me.cmd, weight: me.weight, heavy: me.heavy, waitMs, runMs: Date.now() - t0, outcome: outcome === 'timeout' ? 'timeout' : (exitCode === 0 ? 'pass' : 'fail'), exitCode, signal: signal || undefined };
      try { fs.appendFileSync(f.runs, `${JSON.stringify(rec)}\n`); } catch (_) { /* 记不上不影响结果 */ }
      if (outcome === 'timeout') process.stderr.write(`test-queue: 跑满 ${cfg.timeoutMinutes} 分钟，已熔断（只跑点到的测试，或把整套拆小）\n`);
      resolve(exitCode);
    });
    running = ref;
    const timer = setTimeout(() => { outcome = 'timeout'; if (ref.child && ref.child.pid) killTree(ref.child.pid); }, cfg.timeoutMinutes * 60000);
  });
}

function cmdStatus() {
  const cfg = loadConfig();
  const active = activeSessions(cfg);
  withLock(cfg, (st) => {
    clean(st, cfg);
    const lim = testLimit(cfg, st, active);
    console.log(`总池 ${cfg.slots} 位；正在干活的会话 ${active}；测试可用 ${lim} 位，在跑 ${used(st)} 位；空闲内存 ${(os.freemem() / 2 ** 30).toFixed(1)} GB（下限 ${cfg.minFreeGB}）`);
    for (const h of st.holders) console.log(`  跑  ${h.label}  ${h.weight}位${h.heavy ? ' 重型' : ''}  ${Math.round((Date.now() - h.startedAt) / 60000)}分钟  ${h.cmd.slice(0, 80)}`);
    for (const w of st.waiters) console.log(`  等  ${w.label}  ${w.weight}位${w.heavy ? ' 重型' : ''}  ${Math.round((Date.now() - w.since) / 60000)}分钟`);
  });
  return 0;
}

// 统计：多少次超 10 分钟、其中排队为主的占几成（这正是我们找到“测试卡住多半是在排队”的办法）
function cmdStats(argv) {
  const cfg = loadConfig();
  const days = Number(arg(argv, '--days') || 7);
  const since = Date.now() - days * 864e5;
  let rows = [];
  try { rows = fs.readFileSync(files(cfg).runs, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)); } catch (_) { /* 没记录 */ }
  rows = rows.filter((r) => Date.parse(r.at) >= since);
  const long = rows.filter((r) => r.waitMs + r.runMs > 600000);
  const waitLong = long.filter((r) => r.waitMs >= r.runMs).length;
  const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
  console.log(`近 ${days} 天 ${rows.length} 次；排队加运行超 10 分钟 ${long.length} 次，其中排队为主 ${waitLong} 次（${pct(waitLong, long.length)}%）；熔断 ${rows.filter((r) => r.outcome === 'timeout').length} 次；重型 ${rows.filter((r) => r.heavy).length} 次`);
  return 0;
}

async function main(argv) {
  const sub = argv[0];
  if (sub === 'run') return cmdRun(argv.slice(1));
  if (sub === 'status') return cmdStatus();
  if (sub === 'stats') return cmdStats(argv.slice(1));
  console.log('用法：test-queue.cjs run --label <label> -- <command ...> | status | stats [--days N]');
  return sub ? 2 : 0;
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; });
} else {
  module.exports = { DEFAULT_SESSION_DIRS, sessionDirsOf, activeSessions, loadConfig, classify, heavyText, scanWeight, testLimit, headOf, canGrant, main };
}
