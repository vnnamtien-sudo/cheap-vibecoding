# 统一配置与本地自检

[English](gate-config.en.md) · [README](../README.md)

Python 3.9+ 标准库即可运行工具；self-check 还需要 Git。纯文字模板不需要运行环境。四个平台读取同一个项目根 gate.config.json；仓库提供 gate.config.example.json。接入仍是复制规矩、运行 init 两步；自检是随后验证的第三条命令。

| 字段 | 含义 |
|---|---|
| accountMode | 固定 single，一个人一个账号 |
| maxFileLines | 每个改动文本文件的最大行数 |
| maxFunctionLines | 支持语法中的函数最大跨度，含注释与空行 |
| bannedPatterns | 数组，每项有 pattern、description，可选 flags（i/m/s）；使用 Python 正则语法 |
| layers | 数组，每项 path、可选 name、allow 数组；同层也需明确允许 |
| testCommand | 参数数组；{files} 独立展开为改动代码文件；{python} 为当前解释器 |
| testMappings | 源文件或目录前缀到具体测试文件数组，多个命中合并 |
| typeCheckCommand | 可选参数数组，空数组表示跳过类型检查 |
| dataCheckCommand | 可选参数数组，接收全部改动文本；空数组表示跳过数据比对 |
| readLimitLines | 读取钩子和规矩使用的单次上限 |
| roles | claude/codex/deepseek/gemini 下的 mainWriter/lightReview/finalReview/readOnly |
| testQueue | 默认 targeted、timeoutSeconds=900、hookEnabled=false；高级参数见 advanced |
| tokenUsage / stages | 可选，只读会话目录、用户确认的价目及阶段定义 |
| privacy.patterns | 额外脱敏正则数组，每项含 pattern、description |

roles 每项包含 model、tier、effort。model 留空时由用户填写已核实型号；tier 表示 strong/light/strongest 的意图，工具不会擅自配置服务商。Claude 预设 Sonnet 5.5 主写、Haiku 5.5 轻验收和只读、Opus 5.5 最终验收；主写可选 Opus 5.5。日常 high，算钱算账、大重构、发布前的最终验收 xhigh，实际可用能力以平台为准。轻验收使用同账号无前文的新会话。完整对照表见 [README](../README.md)，设置入口见 [思考档位](effort.md)。

命令只用参数数组，绝不经 shell 拼接。示例：`["{python}", ".ai-gates/targeted-tests.py", "{files}"]`。本机项目的测试运行时仍须存在；本工具本身不依赖项目的语言环境。禁止正则会扫描配置文本自身，使用字面规则时也需考虑定义位置。

## 初始化

从工具仓库运行 `python3 tools/init.py --root <已有项目>`。扫描扩展名、真实目录和包管理元数据，不执行项目代码；生成 gate.config.json 和需要时可提交的 .ai-gates/targeted-tests.py。配置已有时保留；--force 仅用于明确覆盖。先查看 detected 和 review；未知框架不能冒称已测试。辅助脚本和配置应随项目提交以便换电脑使用。

## 自检与回执

内建定向映射支持 unittest 与 Node 内置测试；其他框架需用户填写自己的命令数组和映射，不能把未映射当作通过。

运行 `python3 tools/self-check.py --root <项目>`。默认检查 Git 中暂存、未暂存和未追踪的现存改动文本，记录删除和二进制的跳过原因。行数、禁用正则先检查；函数和分层分析依语言而定，再依次类型检查、定向测试、可选数据比对。前项失败阻断后项，任何失败非零退出。

Python 使用 AST；JS/TS 使用词法分析，复杂别名、动态 import 与模板插值需真实类型检查或测试补足。其他语言的函数或引用分析存在能力缺口，回执 limitations 会列出；通用行数和正则仍检查。无测试映射或未配置定向测试不能作为完整通过。未配置的类型与数据检查明确显示 skipped。

回执默认 .gate/self-check.json，可用 --receipt 改路径；--config 选择其他配置。--staged 使用暂存区快照和对应配置执行检查，避免工作区内容掩盖待提交版本。不要把 .gate 中的本地回执当作源码提交。

## 可选 Git 钩子

运行 `python3 tools/install-hook.py --root <项目>`。它生成本地 pre-commit，调用本工具的 self-check --staged，不覆盖已有钩子。工具仓库或解释器移动后重新安装。Windows 可用 --python-command python 或 py；常规工具命令中的 python3 也相应替换。Git 钩子可不用。

Claude 可另外安装读取和测试钩子，见 examples/claude/settings.json；命令写 python3，Windows 改 python 或 py。Codex、DeepSeek、Gemini 使用规矩加可选 pre-commit，不假设它们具有相同钩子协议。

## 脱敏与历史报告

`python3 tools/privacy-scan.py` 检查 Git 管理及未忽略的候选文本，回执 .gate/privacy.json 只列位置和规则，不回显命中值；二进制、链接及未知编码要求复核。它检查常见凭据与私密文本模式，项目专有名称通过 privacy.patterns 补充。忽略目录中的个人日志不会发布，也不属于该扫描范围。历史数据报告数字保持原样，不代表新项目效果；效果因电脑配置、模型、项目而异。
