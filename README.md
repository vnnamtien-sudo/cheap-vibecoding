# cheap-vibecoding

**简体中文** | [English](README.en.md)

让 AI 编程助手**同时开很多路也不乱烧钱**的几件小工具。Claude Code、OpenAI Codex、谷歌 Antigravity、DeepSeek 都能用；Node.js 单文件，零依赖。

![每一步花费](docs/images/cost-per-step.svg)

在我们自己一台工作站上，两个月、65 万条回复实测：

- **每一步花费 −39%**：10.5 → 6.4 美分（一步 = 一次工具调用）
- **整份读大文件 51% → 16%**：靠钩子拦下来的，光在规矩里写“少读”降不下来
- **测试“卡住”的 67% 其实在排队**：所以会话和测试共用一个总池统一放行

## 里面就三样

| 文件 | 做什么 |
|---|---|
| `hooks/read-limit-hook.cjs` | 大文件不准整份读，一次最多 60 行，拦下时给出改好的命令 |
| `hooks/test-queue-hook.cjs` + `tools/test-queue.cjs` | 测试必须排队：会话和测试共用总池、整套测试分级、15 分钟熔断、内存不够不放 |
| `tools/token-usage.cjs`、`tools/stages.cjs` | 查钱花在哪；按你改规矩的日期切段，比改前改后 |

另有四家各一份省用量规矩模板：`rules/claude/`、`rules/codex/`、`rules/google/`、`rules/deepseek/`。

## 五分钟装好

1. 克隆本仓库，跑自测：`npm test`（要 Node.js 18 以上）。
2. 注册钩子，照你用的那家抄 `examples/<家>/`：
   - Claude Code：`examples/claude/settings.json` 合并进 `~/.claude/settings.json`
   - Codex：`examples/codex/hooks.json` 放到 `~/.codex/hooks.json`，再在 `/hooks` 里点信任（**不信任会被静默跳过**）
   - 谷歌 Antigravity：`examples/google/hooks.json` 放到项目的 `.agents/hooks.json`
   - DeepSeek：钩子同 Claude Code，用 `examples/deepseek/` 的启动脚本
3. 把 `rules/<家>/` 的规矩贴进它认的规矩文件最上面。
4. 按下一节改 `config/test-queue.json`。
5. 试一下：叫助手整份读一个 300 行的文件、直接跑一次测试，两次都应被拦下。

四家各能做到哪一步（有没有钩子、用量能不能查、我们实测到哪）：[docs/agents.md](docs/agents.md)。

## 按你的电脑调参

默认值是按我们 64 GB / 24 线程的机器调的，**别照抄**。起点：

| 内存 | 总池 `slots` | 最少测试位 | 整套最多几份 | 空闲内存下限 GB | 熔断分钟 |
|---|---|---|---|---|---|
| 16 GB | 6 | 1 | 1 | 3 | 10 |
| 32 GB | 10 | 2 | 1 | 5 | 15 |
| 64 GB | 20 | 2 | 2 | 8 | 15 |

用两三天再跑 `node tools/test-queue.cjs stats --days 3` 看情况调。细节：[docs/tuning.md](docs/tuning.md)。

## 量你自己的

```bash
node tools/token-usage.cjs --days 7                 # 近 7 天花了多少、多少是重读前文
node tools/token-usage.cjs --agent codex --days 7   # 换一家：codex / gemini / deepseek / all
node tools/test-queue.cjs status                    # 测试排队情况
```

只读本机会话记录，不联网。

## 照实说：总账没省下来

单价降了四成，但每份活的总花费没降（16.6 → 19.7 美元）。拆开看：**主会话每份活降了 20%，涨的全在子代理**——子代理的钱 68% 花在验收上，同一个分支常被好几个会话各验一遍。教训：会话路数和子代理才是总开关，省单价不等于省总账。我们正在加一个拦重复验收的钩子，复量后更新这里。完整数字和口径：[数据报告](docs/data-report.md)。

## 更多

- [思考档位怎么设](docs/effort.md)（只用 high / xhigh，不开最高档的理由和数据）
- [改进过程](docs/history.md)（一步步怎么改的，包括走过的弯路）
- [数据报告](docs/data-report.md)

[MIT](LICENSE)
