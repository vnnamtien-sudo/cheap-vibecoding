# 四个版本：各家能做到哪一步

[← 回到 README](../README.md)

我们 2026 年 11 月按各家官方现行文档逐项核过（链接在表下）。“已实测”= 在我们自己的机器上装上、真拦下过；“照文档”= 没装或没账号，照官方文档写，可能有出入，欢迎提问题单更正。

| | Claude Code | OpenAI Codex | 谷歌 Antigravity CLI（agy） | DeepSeek |
|---|---|---|---|---|
| 是什么 | Anthropic 的编程助手 | OpenAI 的编程助手（命令行、桌面应用同一套） | 谷歌现在的编程助手；Gemini CLI 2026-06-18 起不再给个人账号用（企业版、付费密钥还能用） | **没有自家编程助手**。官方推荐接法之一：Claude Code 接 `api.deepseek.com/anthropic`（也列了 Codex、OpenCode 等） |
| 规矩文件 | `CLAUDE.md`（项目根、`~/.claude/`） | `AGENTS.md`（项目每层、`~/.codex/`；合计默认 32 KiB） | `AGENTS.md` 或 `GEMINI.md`、`.agents/rules/*.md`、`~/.gemini/GEMINI.md`（全局和常开规则合用约 2 万 token） | 跟 Claude Code：`CLAUDE.md` |
| 我们的模板 | [rules/claude/CLAUDE.md](../rules/claude/CLAUDE.md) | [rules/codex/AGENTS.md](../rules/codex/AGENTS.md) | [rules/google/GEMINI.md](../rules/google/GEMINI.md) | [rules/deepseek/CLAUDE.md](../rules/deepseek/CLAUDE.md) |
| 有没有能拦的钩子 | 有：PreToolUse（`settings.json`） | 有：PreToolUse（`~/.codex/hooks.json`），格式和 Claude 几乎一样；第一次要在 `/hooks` 或设置里**信任**，不信任会被静默跳过 | 有：PreToolUse（`.agents/hooks.json`），回 `{"decision":"deny"}`；旧 Gemini CLI 是 BeforeTool | 跟 Claude Code |
| 读文件限行 | 拦 Read 和 shell 里的 cat / Get-Content | 拦 shell（Codex 读文件都走 shell） | 拦 view_file 和 run_command | 跟 Claude Code |
| 测试排队 | 钩子拦没排队的测试 | 钩子拦 | 钩子拦 | 跟 Claude Code |
| 思考档位 | `effortLevel` + 按型号 `modelSettings`；`/effort` | `model_reasoning_effort`（low…xhigh、max、ultra，看型号） | `/effort`（low…max，看型号） | Claude Code 的 `/effort`；官方示例设了 `CLAUDE_CODE_EFFORT_LEVEL=max`，我们不建议（原因见 [effort.md](effort.md) 第 5 条） |
| 会话记录和每步用量 | `~/.claude/projects/**/*.jsonl`，每条回复带 usage | `~/.codex/sessions/年/月/日/rollout-*.jsonl`，每步 `token_count` / `token_usage_record`（官方文档没写这份格式，我们按本机记录读） | 有会话记录（`brain/<会话>/…/transcript.jsonl`），官方没写里面有用量；**查数脚本读不了**。旧 Gemini CLI 的 `~/.gemini/tmp/*/chats/*.json` 带 tokens，脚本能读（照文档） | 同 Claude 记录，脚本按型号名里的 deepseek 分开算 |
| 配置示例 | [examples/claude/](../examples/claude/) | [examples/codex/](../examples/codex/) | [examples/google/](../examples/google/) | [examples/deepseek/](../examples/deepseek/) |
| 我们实测到哪 | 已实测（两个月） | 已实测：两个钩子在本机 Codex 0.169 里真拦下过；查数脚本读过本机 877 份记录 | **照文档**，没在本机装 | 钩子、工具同 Claude，已实测；**DeepSeek 接口照文档**，没有账号没跑过 |

没有钩子、或钩子没配上的时候，只能靠规矩文件里的文字，**拦不住**（我们量过：光写在规矩里，整份读文件一直降不下来）。替代办法：

- 测试排队器本身谁都能用，不靠钩子：`node tools/test-queue.cjs run --label <名> -- <命令>`，在规矩里写死“测试一律这样跑”。
- 查数脚本不靠钩子：定期跑 `node tools/token-usage.cjs --agent <家>` 看重读前文的比例、`node tools/stages.cjs --agent <家>` 看整份读文件的比例有没有降。

官方文档（2026-11 核）：[Claude Code 钩子](https://docs.claude.com/en/docs/claude-code/hooks) · [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [Codex 钩子](https://learn.chatgpt.com/docs/hooks) · [Codex 配置](https://learn.chatgpt.com/docs/config-file/config-reference) · [Antigravity 规则](https://antigravity.google/docs/rules) · [Antigravity 钩子](https://antigravity.google/docs/hooks) · [Gemini CLI 换 Antigravity CLI](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) · [Gemini CLI 钩子](https://geminicli.com/docs/hooks/) · [DeepSeek 编程助手接法](https://api-docs.deepseek.com/guides/coding_agents) · [DeepSeek 接 Claude Code](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code)
