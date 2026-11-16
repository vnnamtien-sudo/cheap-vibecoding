'use strict';
// 钩子收发的“翻译层”：把四家助手送进钩子的 JSON 统一成 Claude Code 的样子 { tool_name, tool_input, cwd }，
// 拦下时再按各家要的格式回话。钩子本体（read-limit / test-queue）只认统一后的样子。
//   Claude Code（含接 DeepSeek 的）：PreToolUse，tool_name = Read / Bash / PowerShell。
//   OpenAI Codex：PreToolUse，格式和 Claude 一样；shell 和 exec_command 都叫 Bash（Windows 上命令其实是 PowerShell 写法）。
//   Google Antigravity CLI：PreToolUse，{ toolCall: { name, args } }；run_command 的命令在 args.CommandLine，view_file 的路径在 args.AbsolutePath。【未在本机实测】
//   Gemini CLI（2026-06 起个人账号停用，换 Antigravity）：BeforeTool，tool_name = run_shell_command（command、dir_path）/ read_file（file_path、start_line、end_line）。【未在本机实测】
// 回话：Claude、Codex 用 hookSpecificOutput.permissionDecision = deny；Antigravity、Gemini CLI 用 { decision: 'deny', reason }。

const PS_MARK = /\bGet-Content\b|\bSelect-Object\b|\$env:|-LiteralPath\b|\bSet-Location\b|\bWrite-Output\b|\bGet-ChildItem\b/i;

function detectAgent(input) {
  if (input && input.toolCall && typeof input.toolCall === 'object') return 'antigravity';
  if (input && input.hook_event_name === 'BeforeTool') return 'gemini';
  if (input && (input.turn_id || /[\\/]\.codex[\\/]/.test(String(input.transcript_path || '')))) return 'codex';
  return 'claude';
}

function normalize(input, forced) {
  const agent = forced || detectAgent(input);
  if (agent === 'antigravity') {
    const c = input.toolCall || {}; const a = c.args || {};
    const cwd = a.Cwd || (input.workspacePaths || [])[0];
    if (c.name === 'view_file') {
      const part = a.StartLine != null || a.EndLine != null;
      const limit = part ? Math.max(1, Number(a.EndLine || 0) - Number(a.StartLine || 0) + 1) : undefined;
      return { agent, tool_name: 'Read', tool_input: { file_path: a.AbsolutePath, limit }, cwd };
    }
    if (c.name === 'run_command') {
      const cmd = String(a.CommandLine || '');
      return { agent, tool_name: PS_MARK.test(cmd) ? 'PowerShell' : 'Bash', tool_input: { command: cmd }, cwd };
    }
    return { agent, tool_name: String(c.name || ''), tool_input: a, cwd };
  }
  if (agent === 'gemini') {
    const ti = input.tool_input || {};
    if (input.tool_name === 'read_file') {
      const part = ti.start_line != null || ti.end_line != null;
      const limit = part ? Math.max(1, Number(ti.end_line || 1e9) - Number(ti.start_line || 1) + 1) : undefined;
      return { agent, tool_name: 'Read', tool_input: { file_path: ti.file_path || ti.absolute_path, limit }, cwd: input.cwd };
    }
    if (input.tool_name === 'run_shell_command') {
      const cmd = String(ti.command || '');
      return { agent, tool_name: PS_MARK.test(cmd) ? 'PowerShell' : 'Bash', tool_input: { command: cmd }, cwd: ti.dir_path || input.cwd };
    }
    return { agent, tool_name: String(input.tool_name || ''), tool_input: ti, cwd: input.cwd };
  }
  if (agent === 'codex' && input.tool_name === 'Bash') {
    const cmd = String((input.tool_input || {}).command || '');
    return { agent, tool_name: PS_MARK.test(cmd) ? 'PowerShell' : 'Bash', tool_input: { command: cmd }, cwd: input.cwd };
  }
  return { agent, tool_name: input.tool_name, tool_input: input.tool_input || {}, cwd: input.cwd };
}

function denyOutput(agent, reason) {
  if (agent === 'antigravity' || agent === 'gemini') return { decision: 'deny', reason };
  return { hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason } };
}

// 钩子入口：读标准输入 → 统一 → decide → 拦就按各家格式写标准输出。任何出错一律放行（不输出、退出码 0）。
function runHook(decide) {
  const fs = require('fs');
  const i = process.argv.indexOf('--agent'); const forced = i >= 0 ? process.argv[i + 1] : undefined;
  let raw = '';
  try { raw = fs.readFileSync(0, 'utf8'); } catch (_) { return; }
  let norm = null; let reason = null;
  try { norm = normalize(JSON.parse(raw), forced); reason = decide(norm); } catch (_) { reason = null; }
  if (reason && norm) process.stdout.write(JSON.stringify(denyOutput(norm.agent, reason)));
}

module.exports = { detectAgent, normalize, denyOutput, runHook };
