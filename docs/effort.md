# 思考档位怎么用

[← 返回 README](../README.md)

日常写代码、写文档、只读核对和轻验收使用 high。xhigh 只用于最终核验钱、重大重构或发布。执行时不使用 max 或 medium。轻验收使用新会话，不带实现前文。

## 历史实测

以下是历史阶段记录，不是新项目的费用承诺；原始数据见[数据报告](data-report.md)。

| 阶段 | 每步花费 | 每天花费 | 每份交付 | 上下文超 25 万 |
|---|---|---|---|---|
| 最早没调整（默认档） | 10.5 美分 | 约 390 美元 | 16.6 美元 | 33% |
| 全开最高档（max） | 9.8 美分 | 约 1,270 美元 | 23.3 美元 | 75% |
| 只用 high / xhigh 之后 | 7.5 美分 | — | 10.1 美元 | 45% |

“只用 high / xhigh”阶段只有 1 天，样本小，只看方向。

## 平台设置

型号名称和档位支持随平台、账户和客户端而异；只填已确认的型号 ID，并检查当前型号支持的档位。

- Claude Code：用 /model 选择型号，用 /effort high 设置该型号的日常档位；Claude Code 将已选档位按型号保存在 settings.json 的 modelSettings 中。重大最终验收可在新会话中使用 /effort xhigh。不要设置 CLAUDE_CODE_EFFORT_LEVEL 统一会话档位。
- Codex：在 config.toml 中设置已确认的 model 和 model_reasoning_effort = "high"。最终验收只有在型号明确支持 xhigh 时才使用。
- Gemini CLI：用 /model 或 settings.json 的 model.name 选择已确认型号。生成参数按该型号文档配置；Gemini CLI 的参数不是通用 high / xhigh 字符串。
- DeepSeek：官方 API 接受 high 和 max，并将 xhigh 映射为 high。因此它的 xhigh 设置不能承担 xhigh 最终验收；应由用户选定确实支持 xhigh 的型号与平台。日常可以使用 high。

额度紧时用轻量型号处理轻活、合并非急工作，或暂停不急的任务。平台的具体设置方式请看官方文档：

- [Claude Code model configuration](https://code.claude.com/docs/en/model-config) · [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Gemini CLI configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md) · [generation settings](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/generation-settings.md)
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/) · [Claude Code integration](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/)

例子见 examples 目录。设置前由用户确认实际型号和本地配置入口。
