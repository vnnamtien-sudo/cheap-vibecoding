#!/usr/bin/env node
'use strict';
// npm test 入口：列出 tests/*.test.cjs 交给 node --test。不靠 shell 展开通配符，Windows 的 cmd 和 Node 18–20 也能跑。
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const files = fs.readdirSync(__dirname).filter((n) => n.endsWith('.test.cjs')).sort().map((n) => path.join(__dirname, n));
const r = spawnSync(process.execPath, ['--test', ...files], { stdio: 'inherit' });
process.exitCode = r.status == null ? 1 : r.status;
