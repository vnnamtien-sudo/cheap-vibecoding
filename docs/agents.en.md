# Four versions: how far each one goes

[← Back to README](../README.en.md)

In November 2026 we checked each item against each vendor's current official docs (links below the table). "Tested" = installed on our own machine and seen actually blocking; "per docs" = not installed or no account, written from the official docs, may be off. Issues with corrections are welcome.

| | Claude Code | OpenAI Codex | Google Antigravity CLI (agy) | DeepSeek |
|---|---|---|---|---|
| What it is | Anthropic's coding agent | OpenAI's coding agent (CLI and desktop app share the same setup) | Google's current coding agent; since 2026-06-18 Gemini CLI is no longer available to personal accounts (enterprise and paid API keys still work) | **No coding agent of its own**. One of its officially recommended setups: Claude Code pointed at `api.deepseek.com/anthropic` (Codex, OpenCode and others are also listed) |
| Rules file | `CLAUDE.md` (project root, `~/.claude/`) | `AGENTS.md` (every project level, `~/.codex/`; 32 KiB combined by default) | `AGENTS.md` or `GEMINI.md`, `.agents/rules/*.md`, `~/.gemini/GEMINI.md` (global and always-on rules share about 20k tokens) | Same as Claude Code: `CLAUDE.md` |
| Our template | [rules/claude/CLAUDE.en.md](../rules/claude/CLAUDE.en.md) | [rules/codex/AGENTS.en.md](../rules/codex/AGENTS.en.md) | [rules/google/GEMINI.en.md](../rules/google/GEMINI.en.md) | [rules/deepseek/CLAUDE.en.md](../rules/deepseek/CLAUDE.en.md) |
| Blocking hook available? | Yes: PreToolUse (`settings.json`) | Yes: PreToolUse (`~/.codex/hooks.json`), format almost identical to Claude's; the first time you must **trust** it in `/hooks` or settings, otherwise it is silently skipped | Yes: PreToolUse (`.agents/hooks.json`), returns `{"decision":"deny"}`; the old Gemini CLI uses BeforeTool | Same as Claude Code |
| Read line limit | Blocks Read and cat / Get-Content in the shell | Blocks the shell (Codex reads all files through the shell) | Blocks view_file and run_command | Same as Claude Code |
| Test queue | Hook blocks unqueued tests | Hook blocks | Hook blocks | Same as Claude Code |
| Effort level | `effortLevel` + per-model `modelSettings`; `/effort` | `model_reasoning_effort` (low…xhigh, max, ultra, depending on model) | `/effort` (low…max, depending on model) | Claude Code's `/effort`; the official example sets `CLAUDE_CODE_EFFORT_LEVEL=max`, which we don't recommend it (see item 5 in [effort.en.md](effort.en.md)) |
| Session logs and per-step usage | `~/.claude/projects/**/*.jsonl`, every reply carries usage | `~/.codex/sessions/<year>/<month>/<day>/rollout-*.jsonl`, each step has `token_count` / `token_usage_record` (this format isn't in the official docs; we read it from our local logs) | Has session logs (`brain/<session>/…/transcript.jsonl`), but the docs don't say they contain usage; **the usage scripts can't read them**. The old Gemini CLI's `~/.gemini/tmp/*/chats/*.json` carries tokens and the scripts can read it (per docs) | Same logs as Claude; the scripts split it out by "deepseek" in the model name |
| Config examples | [examples/claude/](../examples/claude/) | [examples/codex/](../examples/codex/) | [examples/google/](../examples/google/) | [examples/deepseek/](../examples/deepseek/) |
| How far we tested | Tested (two months) | Tested: both hooks actually blocked in our local Codex 0.169; the usage scripts have read 877 local logs | **Per docs**, not installed locally | Hooks and tools same as Claude, tested; **DeepSeek API per docs**, no account, never run |

The `.en.md` rules files are English translations. Copy the one for your agent into the file name it actually reads (`CLAUDE.md`, `AGENTS.md` or `GEMINI.md`).

Without hooks, or when the hooks aren't wired up, you only have the words in the rules file, and **they don't stop anything** (we measured: with rules alone, whole-file reads never came down). Alternatives:

- The test queue works for anyone, no hook needed: `node tools/test-queue.cjs run --label <name> -- <command>`, and state in the rules that "all tests run this way".
- The usage scripts need no hook: run `node tools/token-usage.cjs --agent <agent>` (share spent re-reading context) and `node tools/stages.cjs --agent <agent>` (whole-file read share) regularly and check whether the whole-file-read and re-read shares are coming down.

Official docs (checked 2026-11): [Claude Code hooks](https://docs.claude.com/en/docs/claude-code/hooks) · [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [Codex hooks](https://learn.chatgpt.com/docs/hooks) · [Codex config](https://learn.chatgpt.com/docs/config-file/config-reference) · [Antigravity rules](https://antigravity.google/docs/rules) · [Antigravity hooks](https://antigravity.google/docs/hooks) · [Gemini CLI to Antigravity CLI](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) · [Gemini CLI hooks](https://geminicli.com/docs/hooks/) · [DeepSeek coding agent setup](https://api-docs.deepseek.com/guides/coding_agents) · [DeepSeek with Claude Code](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code)
