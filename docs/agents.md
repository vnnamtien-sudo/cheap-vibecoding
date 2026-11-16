# 四个平台的规则与档位

[← 返回 README](../README.md)

以下政策表适用于四个平台。未确认的型号留给用户在平台设置中填写，不猜测型号 ID。

| 角色 | Claude Code | OpenAI Codex | DeepSeek（Claude Code API） | Gemini CLI |
|---|---|---|---|---|
| 主写 | Sonnet 5.5 / high；可选 Opus 5.5 | 最强档（填型号）/ high | 最强档（填型号）/ high | 最强档（填型号）/ high |
| 轻验收 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |
| 最终验收 | Opus 5.5 / xhigh；仅算钱、大重构、发布 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 |
| 只读 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |

轻验收使用全新会话，不带实现前文；只读角色不改文件。DeepSeek 官方 API 把 xhigh 映射为 high，不能视为 xhigh。Codex 和 Gemini CLI 的档位随模型而异；先确认所选型号实际支持的档位。日常执行用 high；最终验收只用于表中列出的高影响事项，不用 max 或 medium 作为执行档。不要设置 CLAUDE_CODE_EFFORT_LEVEL 统一会话档位。

## Claude Code

- 项目规矩放在 CLAUDE.md。
- 用 /model 选择可用型号；用 /effort high 为该型号设置日常档位。Claude Code 将按型号保存档位。
- Opus 5.5 可用 high 写作；最终验收只在算钱、大重构或发布时选择 Opus 5.5 / xhigh。
- 不要全局设置 CLAUDE_CODE_EFFORT_LEVEL，以免覆盖按型号和会话选择。

## OpenAI Codex

- 项目规矩放在 AGENTS.md。
- 在 Codex 配置中选择用户确认可用的型号，并设置 model_reasoning_effort = "high"。
- 只有当所选型号明确支持 xhigh 时，才把它用于表中限定的最终验收。

## DeepSeek

- DeepSeek 通过官方 Anthropic API 接入 Claude Code；接口地址和模型名称使用官方接入说明中的值。
- 官方说明显示 xhigh 会映射到 high。此接法不提供独立的 xhigh 思考档；最终验收能力由用户确认。
- 不复制会把所有会话设成统一 max 的环境变量设置。

## Gemini CLI

- 项目规矩放在根目录 GEMINI.md；CLI 按层级装载上下文。
- 项目或用户 settings.json 可设置 model.name；生成参数按所选模型的官方说明配置。
- Gemini CLI 的生成配置可能使用模型专属 thinkingBudget 等参数，不能把 high 或 xhigh 文本当作通用配置键。

## 官方来源

- Claude Code：[模型配置](https://code.claude.com/docs/en/model-config) · [设置文件](https://code.claude.com/docs/en/settings)
- Codex：[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference) · [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- DeepSeek：[Claude Code 接入](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) · [思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)
- Gemini CLI：[配置参考](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md) · [模型生成设置](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/generation-settings.md)
