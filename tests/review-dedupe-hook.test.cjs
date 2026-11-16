'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-review-'));
fs.mkdirSync(path.join(dir, 'config'));
fs.writeFileSync(path.join(dir, 'config', 'review-dedupe.json'), JSON.stringify({ enabled: true, windowHours: 24, dataDir: 'data' }));
process.env.REVIEW_DEDUPE_ROOT = dir;
const { decide, targetsOf } = require('../hooks/review-dedupe-hook.cjs');
const agent = (prompt, session = 's1', description = '复验') => ({ tool_name: 'Agent', session_id: session, tool_input: { description, prompt } });

test('认得出验的对象：提交号要有字样在前，路径里的编号、纯数字日期不算', () => {
  assert.deepStrictEqual(targetsOf('复验 local/line4 提交 a1b2c3d4e5'), ['commit:a1b2c3d']);
  assert.deepStrictEqual(targetsOf('看 /tmp/ab12cd34ef/x 和 head 1234567'), []);
  assert.deepStrictEqual(targetsOf('验收对象：登录页'), ['name:登录页']);
});

test('验收类没写对象拦下；同一提交 24 小时内第二个会话再派拦下；第二轮、重验放行', () => {
  const t = Date.parse('2026-11-16T10:00:00Z');
  assert.match(decide(agent('请复验这次改动'), t), /写明验哪个提交/);
  assert.strictEqual(decide(agent('复验 提交 abc1234 的改动'), t), null);
  assert.match(decide(agent('逐行核 @abc1234def', 's2'), t + 3600e3), /已经派人验过/);
  assert.strictEqual(decide(agent('第二轮：只核上次那 3 条，提交 abc1234', 's2'), t + 3600e3), null);
  assert.strictEqual(decide(agent('重验：上次帮手中途断了，提交 abc1234', 's2'), t + 7200e3), null);
  assert.strictEqual(decide(agent('复验 提交 abc1234', 's3'), t + 27 * 3600e3), null); // 离最后一次（重验）过了 24 小时
});

test('不是验收的子代理、不是 Agent 工具，一律不管', () => {
  assert.strictEqual(decide(agent('查一下 foo 函数在哪调用', 's1', '查找')), null);
  assert.strictEqual(decide({ tool_name: 'Bash', tool_input: { command: 'echo 复验' } }), null);
});
