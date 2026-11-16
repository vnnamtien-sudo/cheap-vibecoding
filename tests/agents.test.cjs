'use strict';
// 四家助手：钩子收发翻译、会话记录读取、总池数会话目录。Gemini / Antigravity 的样本是照官方文档拼的（作者本机没装）。
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-agents-'));
fs.mkdirSync(path.join(dir, 'config'));
fs.writeFileSync(path.join(dir, 'config', 'read-limit.json'), JSON.stringify({ enabled: true, maxLines: 60, wholeFileMax: 150 }));
fs.writeFileSync(path.join(dir, 'config', 'test-queue.json'), JSON.stringify({ hookEnabled: true, slots: 4 }));
process.env.READ_LIMIT_ROOT = dir;
const io = require('../hooks/lib/agent-io.cjs');
const readLimit = require('../hooks/read-limit-hook.cjs');
const S = require('../tools/lib/sessions.cjs');
const big = path.join(dir, 'big.js');
fs.writeFileSync(big, Array.from({ length: 400 }, (_, i) => `line ${i}`).join('\n'));

function hook(file, input, agent) {
  const r = spawnSync(process.execPath, [path.join(__dirname, '..', 'hooks', file), '--agent', agent], {
    input: JSON.stringify(input), env: { ...process.env, READ_LIMIT_ROOT: dir, TEST_QUEUE_ROOT: dir }, encoding: 'utf8',
  });
  assert.strictEqual(r.status, 0);
  return r.stdout ? JSON.parse(r.stdout) : null;
}

test('钩子：Codex 的 Bash（PowerShell 写法）整份读大文件拦下，回 Claude 同款格式', () => {
  const inp = { hook_event_name: 'PreToolUse', turn_id: 't1', tool_name: 'Bash', tool_input: { command: `Get-Content ${big}` }, cwd: dir };
  assert.strictEqual(io.detectAgent(inp), 'codex');
  assert.strictEqual(io.normalize(inp).tool_name, 'PowerShell');
  const out = hook('read-limit-hook.cjs', inp, 'codex');
  assert.strictEqual(out.hookSpecificOutput.permissionDecision, 'deny');
  assert.strictEqual(hook('read-limit-hook.cjs', { ...inp, tool_input: { command: `Get-Content ${big} -TotalCount 30` } }, 'codex'), null);
});

test('钩子：Antigravity 的 view_file / run_command，回 decision=deny', () => {
  const view = { conversationId: 'c', workspacePaths: [dir], toolCall: { name: 'view_file', args: { AbsolutePath: big } } };
  assert.strictEqual(io.detectAgent(view), 'antigravity');
  assert.strictEqual(hook('read-limit-hook.cjs', view, 'antigravity').decision, 'deny');
  const part = { ...view, toolCall: { name: 'view_file', args: { AbsolutePath: big, StartLine: 1, EndLine: 40 } } };
  assert.strictEqual(hook('read-limit-hook.cjs', part, 'antigravity'), null);
  const run = { conversationId: 'c', workspacePaths: [dir], toolCall: { name: 'run_command', args: { CommandLine: 'pytest -q', Cwd: dir } } };
  const out = hook('test-queue-hook.cjs', run, 'antigravity');
  assert.strictEqual(out.decision, 'deny');
  assert.match(out.reason, /test-queue\.cjs/);
});

test('钩子：Gemini CLI 的 read_file 带 start_line/end_line 放行，不带拦下', () => {
  const inp = { hook_event_name: 'BeforeTool', tool_name: 'read_file', tool_input: { file_path: big }, cwd: dir };
  assert.strictEqual(io.detectAgent(inp), 'gemini');
  assert.ok(readLimit.decide(io.normalize(inp)));
  assert.strictEqual(readLimit.decide(io.normalize({ ...inp, tool_input: { file_path: big, start_line: 1, end_line: 50 } })), null);
});

const L = (o) => JSON.stringify(o);
const T = (s) => `2026-11-15T10:00:${String(s).padStart(2, '0')}.000Z`;

test('会话记录：Codex 按 token_usage_record 算，前文含缓存、子代理看 parent_thread_id', async () => {
  const root = path.join(dir, 'codex', '2026', '11', '15'); fs.mkdirSync(root, { recursive: true });
  const usage = (inp, cached, out) => ({ input_tokens: inp, cached_input_tokens: cached, cache_write_input_tokens: 0, output_tokens: out, reasoning_output_tokens: 0, total_tokens: inp + out });
  fs.writeFileSync(path.join(root, 'rollout-a.jsonl'), [
    L({ timestamp: T(0), type: 'session_meta', payload: { session_id: 'S1', id: 'A', parent_thread_id: 'S1' } }),
    L({ timestamp: T(1), type: 'turn_context', payload: { model: 'gpt-x', effort: 'high' } }),
    L({ timestamp: T(2), type: 'response_item', payload: { type: 'function_call', name: 'shell', call_id: 'c1', arguments: L({ command: ['bash', '-lc', "sed -n '1,40p' a.py"] }) } }),
    L({ timestamp: T(3), type: 'token_usage_record', payload: { response_id: 'r1', usage: usage(100000, 98000, 500) } }),
    L({ timestamp: T(3), type: 'event_msg', payload: { type: 'token_count', info: { last_token_usage: usage(100000, 98000, 500), total_token_usage: usage(100000, 98000, 500) } } }),
    L({ timestamp: T(4), type: 'response_item', payload: { type: 'function_call_output', call_id: 'c1', output: 'ok' } }),
    L({ timestamp: T(5), type: 'response_item', payload: { type: 'custom_tool_call', name: 'apply_patch', call_id: 'c2', input: '*** Begin Patch\n*** Update File: a.py\n+x = 1\n*** End Patch' } }),
    L({ timestamp: T(6), type: 'token_usage_record', payload: { response_id: 'r2', usage: usage(120000, 100000, 300) } }),
  ].join('\n'));
  const steps = []; const tools = [];
  await S.walk('codex', { roots: [path.join(dir, 'codex')], onStep: (s) => steps.push(s), onTool: (t) => tools.push(t) });
  assert.strictEqual(steps.length, 2); // token_count 和 token_usage_record 重复的只算一次
  assert.deepStrictEqual(steps.map((s) => [s.u.ctx, s.u.fresh, s.u.cacheRead, s.sub, s.model]), [[100000, 2000, 98000, true, 'gpt-x'], [120000, 20000, 100000, true, 'gpt-x']]);
  const calls = tools.filter((t) => t.done == null);
  assert.strictEqual(calls[0].read, 'part');
  assert.strictEqual(calls[1].codeChars, 5);
  assert.ok(tools.some((t) => t.id === 'c1' && t.done));
});

test('会话记录：老版 Codex 只有 token_count，只刷新额度的重复事件不重复算', async () => {
  const root = path.join(dir, 'codex-old'); fs.mkdirSync(root);
  const tc = (inp, tot) => L({ timestamp: T(1), type: 'event_msg', payload: { type: 'token_count', info: { last_token_usage: { input_tokens: inp, cached_input_tokens: 0, output_tokens: 1 }, total_token_usage: { total_tokens: tot } } } });
  fs.writeFileSync(path.join(root, 'rollout-b.jsonl'), [tc(10, 11), tc(10, 11), tc(20, 32)].join('\n'));
  let n = 0; await S.walk('codex', { roots: [root], onStep: () => { n += 1; } });
  assert.strictEqual(n, 2);
});

test('会话记录：Claude 同一条回复拆几行只算一次；Gemini CLI 照文档样本能读', async () => {
  const cp = path.join(dir, 'claude', 'proj'); fs.mkdirSync(cp, { recursive: true });
  const msg = { id: 'm1', model: 'deepseek-flash', usage: { input_tokens: 10, cache_read_input_tokens: 90, cache_creation_input_tokens: 0, output_tokens: 5 } };
  fs.writeFileSync(path.join(cp, 's1.jsonl'), [
    L({ timestamp: T(1), type: 'assistant', message: { ...msg, content: [{ type: 'tool_use', id: 'u1', name: 'Read', input: { file_path: 'a.py' } }] } }),
    L({ timestamp: T(1), type: 'assistant', message: { ...msg, content: [{ type: 'text', text: 'hi' }] } }),
  ].join('\n'));
  const st = []; const tl = [];
  await S.walk('deepseek', { roots: [path.join(dir, 'claude')], onStep: (s) => st.push(s), onTool: (t) => tl.push(t) });
  assert.strictEqual(st.length, 1); assert.strictEqual(st[0].u.ctx, 100); assert.strictEqual(tl[0].read, 'all');
  const gp = path.join(dir, 'gemini', 'hash1', 'chats'); fs.mkdirSync(gp, { recursive: true });
  fs.writeFileSync(path.join(gp, 'session-1.json'), L({ sessionId: 'g1', messages: [
    { type: 'user', timestamp: T(1), content: 'hi' },
    { id: 'x', type: 'gemini', timestamp: T(2), model: 'gemini-x', tokens: { input: 5000, output: 100, cached: 4000, thoughts: 50, tool: 0, total: 5150 },
      toolCalls: [{ id: 'k1', name: 'read_file', args: { file_path: 'a.py' } }, { id: 'k2', name: 'run_shell_command', args: { command: 'head -n 20 a.py' } }] },
  ] }));
  const gs = []; const gt = [];
  await S.walk('gemini', { roots: [path.join(dir, 'gemini')], onStep: (s) => gs.push(s), onTool: (t) => gt.push(t) });
  assert.deepStrictEqual([gs[0].u.ctx, gs[0].u.fresh, gs[0].u.output], [5000, 1000, 150]);
  assert.deepStrictEqual(gt.map((t) => t.read), ['all', 'part']);
});

test('stages.cjs --agent codex 能按阶段出数，并给每步前文', () => {
  const cfg = path.join(dir, 'stages.json');
  fs.writeFileSync(cfg, L({ agent: 'codex', root: path.join(dir, 'codex'), stages: [{ key: 'S0', name: 'all', from: '2026-11-01T00:00:00Z' }] }));
  const out = path.join(dir, 'stages-out.json');
  const r = spawnSync(process.execPath, [path.join(__dirname, '..', 'tools', 'stages.cjs'), '--stages', cfg, '--out', out], { encoding: 'utf8' });
  assert.strictEqual(r.status, 0, r.stderr);
  const j = JSON.parse(fs.readFileSync(out, 'utf8'));
  assert.strictEqual(j.agent, 'codex');
  assert.strictEqual(j.stages.S0.ctxKPerReply, 110);
  assert.strictEqual(j.stages.S0.steps, 2);
});

test('总池：四家会话目录都数，Codex 只看最近几天的日期文件夹，没装的算 0', () => {
  process.env.TEST_QUEUE_ROOT = dir;
  const q = require('../tools/test-queue.cjs');
  const now = Date.now(); const d = new Date(now);
  const day = path.join(dir, 'cx', `${d.getFullYear()}`, `${d.getMonth() + 1}`.padStart(2, '0'), `${d.getDate()}`.padStart(2, '0'));
  fs.mkdirSync(day, { recursive: true }); fs.writeFileSync(path.join(day, 'r1.jsonl'), '{}');
  fs.mkdirSync(path.join(dir, 'cl', 'p1'), { recursive: true }); fs.writeFileSync(path.join(dir, 'cl', 'p1', 's.jsonl'), '{}');
  fs.mkdirSync(path.join(dir, 'gm', 'h', 'chats'), { recursive: true }); fs.writeFileSync(path.join(dir, 'gm', 'h', 'chats', 's.json'), '{}');
  const cfg = { poolCountsSessions: true, activeSessionMinutes: 10, sessionDirs: [
    { path: path.join(dir, 'cl'), ext: '.jsonl', depth: 2 },
    { path: path.join(dir, 'cx'), ext: '.jsonl', depth: 4, datedDays: 2 },
    { path: path.join(dir, 'gm'), ext: '.json', depth: 3 },
    { path: path.join(dir, 'not-installed'), ext: '.jsonl', depth: 2 },
  ] };
  assert.strictEqual(q.activeSessions(cfg, now), 3);
  assert.strictEqual(q.activeSessions({ ...cfg, activeSessionMinutes: 10 }, now + 3600e3), 0);
  assert.strictEqual(q.sessionDirsOf({ transcriptsRoot: '/x' })[0].path, '/x'); // 老配置照用
});
