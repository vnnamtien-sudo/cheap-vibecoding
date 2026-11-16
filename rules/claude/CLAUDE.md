# Claude Code 项目规矩

将本文件放入项目根目录 CLAUDE.md，或按官方设置加入项目规则。

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

日常执行和只读轻验收用 high；xhigh 仅用于表中限定的最终验收。DeepSeek 官方 API 会把 xhigh 映射为 high，不能视为 xhigh；Gemini CLI 的生成参数按型号确认，不把 high 或 xhigh 当作通用配置键。不使用 max 或 medium 作为执行档。每次轻验收使用全新会话。未核实的模型 ID 由用户在实际平台中选择。不要设置 CLAUDE_CODE_EFFORT_LEVEL 统一会话档位。

平台设置方法见[思考档位说明](../../docs/effort.md)和[官方模型配置文档](https://code.claude.com/docs/en/model-config)。
