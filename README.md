# cheap-vibecoding

**简体中文** | [English](README.en.md)

按需读取上下文，减少重复内容，省 Token。
先运行本地 self-check 挡住改动错误，再在同一账号里分开写入与只读验收，降低返工。
运行 python3 tools/init.py --root ../my-project，五分钟接入你已有的 Git 项目。

规矩是纯文字，脚本可选。

四个组件可独立使用：[上下文骨架](templates/AGENTS.md)、[本地自检](tools/self-check.py)、[写审模板](templates/dispatch/task.md)、[项目适配提示](templates/init-prompt.md)。单人单账号即可；Python 工具使用 Python 3.9+ 标准库，不需要第三方包。

## 四个平台 × 四个角色

| 角色 | Claude Code | OpenAI Codex | DeepSeek（Claude Code API） | Gemini CLI |
|---|---|---|---|---|
| 主写 | Sonnet 5.5 / high；可选 Opus 5.5 | 最强档（填型号）/ high | 最强档（填型号）/ high | 最强档（填型号）/ high |
| 轻验收 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |
| 最终验收 | Opus 5.5 / xhigh；仅算钱、大重构、发布 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 | 最强档（填型号）/ xhigh（须确认支持）；仅限以上场景 |
| 只读 | Haiku 5.5 / high | 轻量档（填型号）/ high | 轻量档（填型号）/ high | 轻量档（填型号）/ high |

轻验收使用全新会话，不带前文；只读角色不改文件。DeepSeek 官方 API 会把 xhigh 映射为 high，不能视为 xhigh；Gemini CLI 生成参数按型号确认，不把 high 或 xhigh 当作通用配置键。未核实的型号由你在平台设置中确认，不在模板里猜型号。日常执行使用 high；xhigh 只用于上述最终验收，不用 max 或 medium 作为执行档。额度紧时用轻量型号处理轻活、合并非急工作，或暂停不急的任务。不要设置 CLAUDE_CODE_EFFORT_LEVEL 统一档位。

## 五分钟三步

从本工具仓库的克隆目录运行。示例目标是你已有的 Git 项目 my-project，位于本仓库的同级目录；把第一条的规则来源和目标文件改成你使用的平台。

1. 复制规则到目标项目（以下示例为 Codex）：

   ~~~sh
   python3 -c "from pathlib import Path; import shutil; shutil.copy2(Path('rules/codex/AGENTS.md'), Path('../my-project/AGENTS.md'))"
   ~~~

2. 生成目标项目的 gate.config.json：

   ~~~sh
   python3 tools/init.py --root ../my-project
   ~~~

3. 对目标项目做本地自检：

   ~~~sh
   python3 tools/self-check.py --root ../my-project
   ~~~

init.py 和 self-check.py 在本仓库中；命令通过 --root 指向目标项目。初始化默认不覆盖已有文件，需要覆盖时才显式加 --force。Windows 上若没有 python3 命令，可改用 py -3；选装 Git 提交钩子时，install-hook.py 的 --python-command 可填 python 或 py。更多设置见[门禁配置](docs/gate-config.md)、[按需读取](docs/read-on-demand.md)和[档位建议](docs/effort.md)。

## 平台规则与配置

| 平台 | 规则模板 | 配置示例 |
|---|---|---|
| Claude Code | [CLAUDE.md](rules/claude/CLAUDE.md) | [settings.json](examples/claude/settings.json) |
| Codex | [AGENTS.md](rules/codex/AGENTS.md) | [config.toml](examples/codex/config.toml) |
| DeepSeek | [CLAUDE.md](rules/deepseek/CLAUDE.md) | [API 参考值](examples/deepseek/reference.json) |
| Gemini CLI | [GEMINI.md](rules/google/GEMINI.md) | [settings.json](examples/google/gemini-cli-settings.json) |

Claude Code、Codex 和 Gemini CLI 配置示例中的型号 ID 是占位值，使用前要替换成你已确认的型号。启用 Claude 原生钩子时，需把 hooks 和 tools/lib 目录复制到项目根目录；Windows 若无 python3 命令，可在设置中改为 python 或 py。只用规则文件不需要运行时。自检、定向测试和 Git 提交钩子是可选的；详细字段和本地数据位置见 gate.config.example.json 与[配置说明](docs/gate-config.md)。多人或多会话并行时再看[高级配置](docs/advanced.md)。

效果因电脑配置、模型、项目而异。[历史数据报告](docs/data-report.md)保留原数字，不代表对新项目的效果承诺。
