'use strict';
// 读四家 AI 编程助手的本机会话记录，统一成同一种“步”给 token-usage / stages 用。只读，不联网。
//   claude  ~/.claude/projects/<项目>/<会话>.jsonl（子代理在 <会话>/subagents/ 下）。DeepSeek 接进 Claude Code 用时也是这份。
//   codex   ~/.codex/sessions/年/月/日/rollout-*.jsonl（+ archived_sessions），每一步用量在 token_count 事件。
//   gemini  ~/.gemini/tmp/<项目>/chats/session-*.json，每条模型回复带 tokens。【未在本机实测，照官方文档写】
// 统一后每一步：{ t, key, model, sid, runId, sub, u: { fresh, cacheW5, cacheW1h, cacheRead, output, ctx } }
//   fresh = 真正新进上下文的输入（不含缓存读）；ctx = 这一步模型看到的全部前文。
// 工具调用：{ t, id, read: 'all'|'part'|null, shell: 命令文字|null, bg, codeChars, done: 结果到达时刻 }
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

const home = (p) => String(p).replace(/^~(?=$|[\\/])/, os.homedir());
const AGENTS = ['claude', 'codex', 'gemini', 'deepseek'];
const DEFAULT_ROOTS = {
  claude: ['~/.claude/projects'],
  deepseek: ['~/.claude/projects'], // DeepSeek 官方给的接法是 Claude Code 接它的 Anthropic 兼容接口，记录同 Claude
  codex: ['~/.codex/sessions', '~/.codex/archived_sessions'],
  gemini: ['~/.gemini/tmp'],
};
const CODE = /\.(c?js|mjs|ts|tsx|jsx|py|ps1|cmd|bat|sql|css|vue|sh|go|rs|java|kt|rb|php|cs)$/i;
const PART_READ = /sed -n|head -n|head -\d|tail -n|tail -\d|-TotalCount|-Tail\b|Select-Object -(First|Skip|Last)|\bnl -ba\b.*\|/;
const ALL_READ = /(^|[\s;&|(])(cat|type|Get-Content|gc)\s+[^|>]/;

function listFiles(dir, ext, since, acc = []) {
  let ents; try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return acc; }
  for (const e of ents) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) listFiles(p, ext, since, acc);
    else if (e.name.endsWith(ext) && (!since || fs.statSync(p).mtimeMs >= since)) acc.push(p);
  }
  return acc;
}
// 一个代理的全部记录文件；同名文件（归档里的副本）只算一次
function filesOf(agent, roots, since) {
  const ext = agent === 'gemini' ? '.json' : '.jsonl';
  const seen = new Set(); const out = [];
  for (const r of roots) {
    for (const f of listFiles(home(r), ext, since)) {
      if (agent === 'gemini' && !/[\\/]chats[\\/]/.test(f)) continue;
      const b = path.basename(f); if (agent === 'codex' && seen.has(b)) continue;
      seen.add(b); out.push(f);
    }
  }
  return out;
}

function shellRead(cmd) { return PART_READ.test(cmd) ? 'part' : ALL_READ.test(cmd) ? 'all' : null; }
// apply_patch 补丁里加进代码文件的字数
function patchChars(text) {
  let n = 0; let code = false;
  for (const ln of String(text).split('\n')) {
    const m = /^\*\*\* (Add|Update) File: (.+)$/.exec(ln.trim());
    if (m) { code = CODE.test(m[2]); continue; }
    if (code && ln.startsWith('+') && !ln.startsWith('+++')) n += ln.length - 1;
  }
  return n;
}

// ---- Claude Code（以及接 DeepSeek 的 Claude Code） ----
async function readClaude(f, onStep, onTool) {
  const isSub = /subagents/.test(f);
  const runId = isSub ? f : path.basename(f, '.jsonl');
  const sid = isSub ? path.basename(path.dirname(path.dirname(f))) : runId;
  const rl = readline.createInterface({ input: fs.createReadStream(f, 'utf8'), crlfDelay: Infinity });
  for await (const ln of rl) {
    if (!ln || ln[0] !== '{') continue;
    let o; try { o = JSON.parse(ln); } catch (_) { continue; }
    const t = Date.parse(o.timestamp || ''); if (!t) continue;
    const m = o.message;
    if (o.type === 'assistant' && m && m.usage && m.id) {
      const u = m.usage; const cw = u.cache_creation || {};
      const w5 = cw.ephemeral_5m_input_tokens ?? u.cache_creation_input_tokens ?? 0; const w1 = cw.ephemeral_1h_input_tokens ?? 0;
      const inp = u.input_tokens || 0; const cr = u.cache_read_input_tokens || 0;
      onStep({ t, key: m.id, model: m.model || '?', sid, runId, sub: isSub || o.isSidechain === true,
        u: { fresh: inp + w5 + w1, freshPlain: inp, cacheW5: w5, cacheW1h: w1, cacheRead: cr, output: u.output_tokens || 0, ctx: inp + w5 + w1 + cr } });
    }
    if (!m || !Array.isArray(m.content)) continue;
    for (const b of m.content) {
      if (b.type === 'tool_use' && b.id) {
        const inp = b.input || {}; let codeChars = 0;
        if (CODE.test(String(inp.file_path || ''))) {
          if (b.name === 'Edit') codeChars = String(inp.new_string || '').length;
          else if (b.name === 'Write') codeChars = String(inp.content || '').length;
          else if (b.name === 'MultiEdit') for (const e of inp.edits || []) codeChars += String(e.new_string || '').length;
        }
        const shell = b.name === 'Bash' || b.name === 'PowerShell' ? String(inp.command || '') : null;
        onTool({ t, id: b.id, read: b.name === 'Read' ? (inp.limit ? 'part' : 'all') : null, shell, bg: !!inp.run_in_background, codeChars });
      }
      if (b.type === 'tool_result' && b.tool_use_id) onTool({ t, id: b.tool_use_id, done: t });
    }
  }
}

// ---- OpenAI Codex（CLI 和桌面应用同一种记录） ----
// 用量：新版每次模型回复写一条 token_usage_record（带 response_id），老版只有 event_msg/token_count 的 last_token_usage。
// input_tokens 里已经含 cached_input_tokens；output_tokens 里已经含 reasoning_output_tokens。
async function readCodex(f, onStep, onTool) {
  const runId = path.basename(f, '.jsonl');
  let sid = runId; let sub = false; let model = '?'; let hasRecord = null; let lastTotal = -1; let n = 0;
  const rl = readline.createInterface({ input: fs.createReadStream(f, 'utf8'), crlfDelay: Infinity });
  const lines = []; for await (const ln of rl) if (ln && ln[0] === '{') lines.push(ln);
  hasRecord = lines.some((l) => l.includes('"token_usage_record"'));
  for (const ln of lines) {
    let o; try { o = JSON.parse(ln); } catch (_) { continue; }
    const t = Date.parse(o.timestamp || ''); if (!t) continue;
    const p = o.payload || {};
    if (o.type === 'session_meta') { sid = p.session_id || p.id || sid; sub = !!p.parent_thread_id; continue; }
    if (o.type === 'turn_context') { model = p.model || model; continue; }
    let u = null; let key = null;
    if (hasRecord && o.type === 'token_usage_record' && p.usage) { u = p.usage; key = p.response_id || `${runId}#${n}`; }
    if (!hasRecord && p.type === 'token_count' && p.info && p.info.last_token_usage) {
      const tot = (p.info.total_token_usage || {}).total_tokens;
      if (tot != null && tot === lastTotal) continue; // 只刷新额度的重复事件
      lastTotal = tot ?? -1; u = p.info.last_token_usage; key = `${runId}#${n}`;
    }
    if (u) {
      n += 1;
      const inp = u.input_tokens || 0; const cr = u.cached_input_tokens || 0; const cw = u.cache_write_input_tokens || 0;
      onStep({ t, key, model, sid, runId, sub, u: { fresh: Math.max(0, inp - cr), freshPlain: Math.max(0, inp - cr - cw), cacheW5: cw, cacheW1h: 0, cacheRead: cr, output: u.output_tokens || 0, ctx: inp } });
      continue;
    }
    if (o.type !== 'response_item') continue;
    const id = p.call_id || p.id;
    if (p.type === 'function_call_output' || p.type === 'custom_tool_call_output' || p.type === 'local_shell_call_output') { if (id) onTool({ t, id, done: t }); continue; }
    let text = null;
    if (p.type === 'function_call') {
      let a = {}; try { a = JSON.parse(p.arguments || '{}'); } catch (_) { a = {}; }
      const c = a.command ?? a.cmd; text = Array.isArray(c) ? c.join(' ') : c != null ? String(c) : String(p.arguments || '');
    } else if (p.type === 'custom_tool_call') text = String(p.input || '');
    else if (p.type === 'local_shell_call') { const c = (p.action || {}).command; text = Array.isArray(c) ? c.join(' ') : String(c || ''); }
    if (text == null || !id) continue;
    const patch = text.includes('*** Begin Patch');
    onTool({ t, id, read: patch ? null : shellRead(text), shell: patch ? null : text, bg: false, codeChars: patch ? patchChars(text) : 0 });
  }
}

// ---- Google Gemini CLI【未在本机实测】 ----
// 官方文档：会话自动存到 ~/.gemini/tmp/<项目哈希>/chats/，一份 JSON：{ sessionId, messages: [{ type: 'gemini', timestamp, model,
//   tokens: { input, output, cached, thoughts, tool, total }, toolCalls: [{ id, name, args, timestamp }] }] }。
// input 里含 cached（Gemini 接口的 promptTokenCount 含缓存部分）；思考 thoughts 单列，这里并进输出。
async function readGemini(f, onStep, onTool) {
  let j; try { j = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return; }
  const runId = path.basename(f, '.json'); const sid = j.sessionId || runId;
  (j.messages || []).forEach((m, i) => {
    const t = Date.parse(m.timestamp || j.lastUpdated || ''); if (!t) return;
    const k = m.tokens;
    if (k && (m.type === 'gemini' || m.type === 'model')) {
      const inp = k.input || 0; const cr = k.cached || 0;
      onStep({ t, key: `${sid}#${m.id || i}`, model: m.model || '?', sid, runId, sub: false,
        u: { fresh: Math.max(0, inp - cr), freshPlain: Math.max(0, inp - cr), cacheW5: 0, cacheW1h: 0, cacheRead: cr, output: (k.output || 0) + (k.thoughts || 0), ctx: inp } });
    }
    for (const c of m.toolCalls || []) {
      const a = c.args || {}; const name = String(c.name || ''); const id = c.id || `${sid}#${i}#${name}`;
      let read = null; let shell = null; let codeChars = 0;
      if (name === 'read_file') read = a.limit ? 'part' : 'all';
      else if (name === 'read_many_files') read = 'all';
      else if (name === 'run_shell_command') { shell = String(a.command || ''); read = shellRead(shell); }
      else if ((name === 'write_file' || name === 'replace') && CODE.test(String(a.file_path || ''))) codeChars = String(a.content ?? a.new_string ?? '').length;
      onTool({ t: Date.parse(c.timestamp || '') || t, id, read, shell, bg: false, codeChars });
    }
  });
}

const READERS = { claude: readClaude, deepseek: readClaude, codex: readCodex, gemini: readGemini };
// 遍历一个代理的记录：onStep 对每一步（已按 key 去重）调用一次，onTool 对每次工具调用 / 工具结果调用
async function walk(agent, { roots, since = 0, onStep = () => {}, onTool = () => {} } = {}) {
  if (!READERS[agent]) throw new Error(`不认识的代理 ${agent}，可选：${AGENTS.join(' / ')}`);
  const files = filesOf(agent, roots && roots.length ? roots : DEFAULT_ROOTS[agent], since);
  const seen = new Set(); const seenTool = new Set();
  for (const f of files) {
    await READERS[agent](f, (s) => { if (seen.has(s.key)) return; seen.add(s.key); onStep(s); }, (c) => {
      if (c.done != null) { onTool(c); return; }
      if (seenTool.has(c.id)) return; seenTool.add(c.id); onTool(c);
    });
  }
  return { files: files.length, steps: seen.size };
}

module.exports = { AGENTS, DEFAULT_ROOTS, walk, filesOf, patchChars, shellRead, home };
