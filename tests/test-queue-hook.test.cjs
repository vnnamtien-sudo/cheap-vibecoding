'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-hook-'));
fs.mkdirSync(path.join(dir, 'config'));
fs.writeFileSync(path.join(dir, 'config', 'test-queue.json'), JSON.stringify({ hookEnabled: true, slots: 8 }));
fs.writeFileSync(path.join(dir, 'run-tests.sh'), '#!/bin/sh\ncd backend\npython -m pytest apps -q\n');
fs.writeFileSync(path.join(dir, 'harmless.sh'), '#!/bin/sh\ngrep -rn pytest .\necho done\n');
process.env.TEST_QUEUE_ROOT = dir;
const { decide } = require('../hooks/test-queue-hook.cjs');

const bash = (command) => ({ tool_name: 'Bash', tool_input: { command }, cwd: dir });

test('没经排队的测试命令拦下，并给出改写命令', () => {
  for (const c of ['pytest -q', 'cd backend && PYTHONUTF8=1 python -m pytest apps -q', 'npm test', 'npm run test:unit',
    'node --test tests/', 'python manage.py test apps.hr', 'uv run pytest -n 4 core', 'bash run-tests.sh', 'bash -c "cd x && pytest -q"']) {
    const r = decide(bash(c));
    assert.ok(r, `应拦：${c}`);
    assert.match(r, /test-queue\.cjs" run --label <label> --/, c);
  }
  assert.ok(decide({ tool_name: 'PowerShell', tool_input: { command: '& python.exe -m pytest apps' }, cwd: dir }));
});

test('不是跑测试的、或已经经排队的放行', () => {
  for (const c of ['grep -rn pytest . | head', 'git commit -m "fix pytest"', 'echo "python -m pytest"', 'python scripts/report.py',
    'node tools/test-queue.cjs run --label a -- pytest -q', 'node tools/test-queue.cjs status', 'bash harmless.sh',
    'python -c "import pytest; print(pytest.__version__)"']) {
    assert.strictEqual(decide(bash(c)), null, `应放行：${c}`);
  }
  assert.strictEqual(decide({ tool_name: 'Read', tool_input: { file_path: 'pytest.ini' } }), null);
});

test('hookEnabled 关掉就全放行', () => {
  fs.writeFileSync(path.join(dir, 'config', 'test-queue.json'), JSON.stringify({ hookEnabled: false }));
  assert.strictEqual(decide(bash('pytest -q')), null);
});
