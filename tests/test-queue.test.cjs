'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-queue-'));
fs.mkdirSync(path.join(dir, 'config'));
const writeCfg = (c) => fs.writeFileSync(path.join(dir, 'config', 'test-queue.json'), JSON.stringify({
  slots: 1, poolCountsSessions: false, minTestSlots: 1, heavyMax: 1, heavyOnlyLabels: true, heavyLabels: 'merge',
  timeoutMinutes: 0.03, minFreeGB: 0, pollMs: 100, dataDir: 'data', ...c,
}));
writeCfg({});
process.env.TEST_QUEUE_ROOT = dir;
const Q = path.join(__dirname, '..', 'tools', 'test-queue.cjs');
const q = require(Q);

function run(args) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [Q, ...args], { env: { ...process.env, TEST_QUEUE_ROOT: dir }, stdio: ['ignore', 'pipe', 'pipe'] });
    let err = ''; p.stderr.on('data', (d) => { err += d; });
    p.on('exit', (code) => resolve({ code, err }));
  });
}
const runs = () => fs.readFileSync(path.join(dir, 'data', 'runs.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));

test('分级与占位：没点到文件的 pytest 是重型；-n 8 占 8 位（封顶总池）', () => {
  const cfg = { ...q.loadConfig(), slots: 20, autoWeight: 4 };
  assert.deepStrictEqual(q.classify(['pytest', '-q'], dir, cfg), { heavy: true, weight: 1 });
  assert.deepStrictEqual(q.classify(['pytest', 'tests/test_a.py', '-n', '8'], dir, cfg), { heavy: false, weight: 8 });
  assert.deepStrictEqual(q.classify(['pytest', '-k', 'money', '-n', 'auto'], dir, cfg), { heavy: false, weight: 4 });
  assert.strictEqual(q.classify(['npm', 'test'], dir, cfg).heavy, true);
  assert.strictEqual(q.classify(['node', '--test', 'tests/a.test.cjs'], dir, cfg).heavy, false);
});

test('总池：会话占的位要让出来，至少留 minTestSlots；内存不够不放新的', () => {
  const cfg = { slots: 20, minTestSlots: 2, minFreeGB: 8 };
  const st = { holders: [{ weight: 3 }], waiters: [{}] };
  const GB = 2 ** 30;
  assert.strictEqual(q.testLimit(cfg, st, 10, 32 * GB), 12); // 10 个会话里 2 个在等测试，不重复算
  assert.strictEqual(q.testLimit(cfg, st, 30, 32 * GB), 2);
  assert.strictEqual(q.testLimit(cfg, st, 10, 4 * GB), 3); // 内存不够：只保持在跑的
  assert.strictEqual(q.canGrant({ holders: [] }, { weight: 5 }, 0), true); // 一个都没在跑时仍放一个
});

test('快慢隔离：重型满了，排前面的重型让开，轻的先走', () => {
  const st = { holders: [{ heavy: true, weight: 1 }], waiters: [{ id: 'h', heavy: true }, { id: 'l', heavy: false }] };
  assert.strictEqual(q.headOf(st, { heavyMax: 1 }).id, 'l');
});

test('跑命令：退出码照传，记进 runs.jsonl', async () => {
  const r = await run(['run', '--label', 'dev', '--', process.execPath, '-e', 'process.exit(3)']);
  assert.strictEqual(r.code, 3);
  const last = runs().pop();
  assert.strictEqual(last.outcome, 'fail');
  assert.strictEqual(last.label, 'dev');
});

test('熔断：跑满 timeoutMinutes 强制结束，退出码 124', async () => {
  const r = await run(['run', '--label', 'dev', '--', process.execPath, '-e', 'setTimeout(() => {}, 20000)']);
  assert.strictEqual(r.code, 124);
  assert.strictEqual(runs().pop().outcome, 'timeout');
});

test('整套测试只准合并标签跑', async () => {
  const r = await run(['run', '--label', 'dev', '--', 'pytest', '-q']);
  assert.strictEqual(r.code, 2);
  assert.match(r.err, /整套/);
});

test('总池 1 位时两份测试排队先后跑', async () => {
  writeCfg({ timeoutMinutes: 1 });
  const slow = [process.execPath, '-e', 'setTimeout(() => {}, 1200)'];
  const [a, b] = await Promise.all([run(['run', '--label', 'a', '--', ...slow]), run(['run', '--label', 'b', '--', ...slow])]);
  assert.strictEqual(a.code, 0); assert.strictEqual(b.code, 0);
  const two = runs().slice(-2);
  assert.ok(two.some((x) => x.waitMs >= 800), `后一份应排队等：${two.map((x) => x.waitMs)}`);
  const st = JSON.parse(fs.readFileSync(path.join(dir, 'data', 'state.json'), 'utf8'));
  assert.strictEqual(st.holders.length + st.waiters.length, 0);
});
