# DeepSeek 项目规矩

本模板用于 DeepSeek 官方 Anthropic API 接入 Claude Code。项目规矩仍放在 CLAUDE.md；接口、型号和密钥按官方接入说明由用户配置。

## 工作方式

- 开始前先明确目标、允许改动范围和完成条件。
- 先搜索文件和符号，再分段读取；每次读取最多 60 行。完整输出写入临时文件，屏幕只显示结论。
- 先读当前实现与调用点，再做最小修改；保留已有行为和数据格式。
- 写入后由实现者先跑本地自检：`python3 <本工具目录>/tools/self-check.py --root .`（Windows 用 `py -3`），全过再交验收；可选用 `tools/install-hook.py` 装 Git 提交前自动自检。记录命令、结果和未运行项。
- 轻验收在全新会话进行，不带实现对话前文；只读核对变更、条件和证据，不编辑文件。
- 只对明确的缺陷报告文件位置、影响和证据；无证据的推测标为待确认。

## 四个平台 × 四个角色

| 角色 | Claude Code | OpenAI Codex | DeepSeek（Claude Code API） | Gemini CLI |
|---|---|---|---|---|
| 主写 | Sonnet 5.5 / high；可选 Opus 5.5 | 最强档（填型号）/ high | 最强档（填型号）/ high | 最强档（填型号）/ high |
| 轻验收 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |
| 最终验收 | Opus 5.5 / xhigh；仅算钱、大重构、发布 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 |
| 只读 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |

DeepSeek 官方接口把 xhigh 映射为 high，不能以该设置声称完成了 xhigh 最终验收。此类工作应由用户确认可用的型号和平台。日常执行与轻验收用 high；不使用 max 或 medium 作为执行档。不要设置 CLAUDE_CODE_EFFORT_LEVEL 统一所有会话的档位。

见[档位说明](../../docs/effort.md)和[DeepSeek 官方 Claude Code 接入说明](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/)。
