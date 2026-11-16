'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-read-'));
fs.mkdirSync(path.join(dir, 'config'));
fs.writeFileSync(path.join(dir, 'config', 'read-limit.json'), JSON.stringify({ enabled: true, maxLines: 60, wholeFileMax: 150 }));
process.env.READ_LIMIT_ROOT = dir;
const { decide } = require('../hooks/read-limit-hook.cjs');

const big = path.join(dir, 'big.js');
const small = path.join(dir, 'small.js');
fs.writeFileSync(big, Array.from({ length: 400 }, (_, i) => `line ${i}`).join('\n'));
fs.writeFileSync(small, 'a\nb\nc\n');
const bash = (command) => ({ tool_name: 'Bash', tool_input: { command }, cwd: dir });

test('Read：大文件不带 limit 拦下，带 ≤60 行放行', () => {
  assert.match(decide({ tool_name: 'Read', tool_input: { file_path: big } }), /超过 150 行/);
  assert.ok(decide({ tool_name: 'Read', tool_input: { file_path: big, limit: 100 } }));
  assert.strictEqual(decide({ tool_name: 'Read', tool_input: { file_path: big, offset: 10, limit: 60 } }), null);
  assert.strictEqual(decide({ tool_name: 'Read', tool_input: { file_path: small } }), null);
});

test('Shell：整份倒出大文件拦下，接 head / grep 或重定向放行', () => {
  assert.ok(decide(bash(`cat ${big}`)));
  assert.ok(decide(bash(`sed -n '1,100p' ${big}`)));
  assert.strictEqual(decide(bash(`sed -n '1,40p' ${big}`)), null);
  assert.strictEqual(decide(bash(`cat ${big} | head -20`)), null);
  assert.strictEqual(decide(bash(`cat ${big} > /dev/null`)), null);
  assert.strictEqual(decide(bash(`cat ${small}`)), null);
  assert.ok(decide({ tool_name: 'PowerShell', tool_input: { command: `Get-Content ${big}` }, cwd: dir }));
  assert.strictEqual(decide({ tool_name: 'PowerShell', tool_input: { command: `Get-Content ${big} -TotalCount 30` }, cwd: dir }), null);
});

test('开关关掉就全放行', () => {
  fs.writeFileSync(path.join(dir, 'config', 'read-limit.json'), JSON.stringify({ enabled: false }));
  assert.strictEqual(decide({ tool_name: 'Read', tool_input: { file_path: big } }), null);
});
