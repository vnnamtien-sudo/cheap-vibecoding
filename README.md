# cheap-vibecoding

**English.** A small, dependency-free kit for running many Claude Code sessions on one machine without burning money: a hook that stops the agent from dumping whole big files into its context, a shared test queue (one pool for sessions + tests, heavy-suite tiering, a 15-minute circuit breaker, a free-memory floor), scripts that measure where your tokens go, and the rules/prompt templates we use. Measured on our own workstation from the untuned baseline: cost per step **−39%** (10.5 → 6.4 cents), whole-file reads 51% → 16%, deliveries per working hour 3.1 → 5.4 — but cost per delivery went **up** 19% and subagent spend share rose 17% → 44%. Both sides are in the [data report](docs/data-report.md). The numbers in `config/` are tuned for a 64 GB / 24-thread box; **measure and retune for your own machine** (see “按你的电脑调参”). Docs are in Chinese.

---

一套让 Claude Code（以及同类 AI 编程助手）**同时开很多路也不乱烧钱**的做法和小工具：钩子、测试排队器、用量查数脚本、规矩和提示词模板。全部是 Node.js 单文件，不装任何依赖。

这些东西是我们一个小团队在两个月里，用 AI 同时开二十来路会话写一套业务系统时，一边挨账单一边改出来的。好的坏的都照实量了，见 [数据报告](docs/data-report.md)。

## 能省在哪，省不了在哪

![每一步花费阶梯](docs/images/cost-per-step.svg)

**能省的**（从最早没调整 9/14–10/2 到现在 11/11 夜–11/16）：

| 指标 | 最早没调整 | 现在 | 变化 |
|---|---|---|---|
| 每一步（一次工具调用）花费 | 10.5 美分 | 6.4 美分 | −39% |
| 每一步新读进上下文的量 | 3.67 千 token | 2.08 千 token | −43% |
| 整份读文件的占比 | 51% | 16% | −35 点 |
| 每个干活小时交付（停工不算） | 3.1 份 | 5.4 份 | +74% |

**省不了、甚至变差的**：

| 指标 | 最早没调整 | 现在 | 变化 |
|---|---|---|---|
| 每份交付花费 | 16.6 美元 | 19.7 美元 | +19% |
| 每美元写进程序的字数 | 2,020 | 1,588 | −21% |
| 子代理花费占比 | 17% | 44% | +27 点 |
| 上下文超 25 万的会话占比 | 33% | 43% | +10 点 |

说人话：

- **单价能压下来**：少读、只读要的那几行、输出落盘、档位别开最高，每一步确实便宜了四成。
- **总账压不下来**：路数一多，每天总花费照样涨（我们从每天约 390 美元涨到约 2,230 美元）。省单价不等于省总账，**路数是总开关**。
- **子代理别乱派**：一次子代理（5.2 美元）比开一个新会话（9.1 美元）便宜，但我们 4 天派了 916 次，钱就花在这上面。
- **测试卡住多半是在排队**：超过 10 分钟的测试，67% 是在等位子，不是跑得慢。所以我们把会话和测试放进同一个池子统一调度。
- **写在规矩里的话不如钩子**：整份读文件的占比，光在规矩里提醒一直降不下来；加了钩子，下一段就从五成多降到一成多。

## 里面有什么

```
hooks/
  read-limit-hook.cjs     读文件限行钩子：大文件不准整份读、一次不超过 60 行
  test-queue-hook.cjs     测试排队钩子：没经排队器跑的测试拦下，并给出改写好的命令
tools/
  test-queue.cjs          测试排队器：总池、整套 / 小测试分级、15 分钟熔断、内存保护
  token-usage.cjs         用量查数：近几天花了多少 token、约多少美元、多少是重读前文
  stages.cjs              阶段对比：按你改规矩的时间点切段，算每段每步花费、读入、产出
config/                   上面几样的参数（按你的电脑改）
rules/
  CLAUDE.md.template      省用量规矩模板，贴进 CLAUDE.md
  prompt-templates.md     开工卡、交接单、每日进度模板
examples/settings.json    钩子怎么注册
docs/data-report.md       数据报告（中文，附英文摘要）
tests/                    自测（node --test）
```

## 怎么装

要求：Node.js 18 以上；Windows 上用 Git Bash 跑 shell 脚本（排队器会自动找 `C:/Program Files/Git/bin/bash.exe`，找不到用系统 shell，也可以设环境变量 `TEST_QUEUE_BASH` 指定）。

1. 克隆到本机任意位置：

   ```bash
   git clone https://github.com/<you>/cheap-vibecoding.git
   ```

2. 跑一遍自测，确认这台机器能用：

   ```bash
   cd cheap-vibecoding && npm test
   ```

3. 注册钩子：把 [`examples/settings.json`](examples/settings.json) 里的 `hooks` 合并进 `~/.claude/settings.json`（全局）或项目的 `.claude/settings.json`，`/path/to/cheap-vibecoding` 换成你克隆的位置。
4. 把 [`rules/CLAUDE.md.template`](rules/CLAUDE.md.template) 里的规矩贴进你的 `CLAUDE.md` 最上面，【】里的数按你的项目改。
5. **按下一节调好 `config/test-queue.json`**，再开始用。

钩子自己出错一律放行（不输出、退出码 0），不会因为钩子坏了卡住你的会话。出了问题想先停拦：`config/read-limit.json` 的 `enabled`、`config/test-queue.json` 的 `hookEnabled` 改成 `false`。

## 按你的电脑调参（一定要看）

我们的机器：**Windows 11、64 GB 内存、24 线程**。`config/test-queue.json` 里的数（总池 20 位、空闲内存下限 8 GB 等）**是按这台机器调的，不要原样照抄**。

总池 `slots` 的意思：**正在干活的会话数 + 在跑测试占的位 ≤ slots**。每个会话本身也吃内存和 CPU，所以会话也算进池子里；`pytest -n K` 一份占 K 位。

建议起点：

| 你的内存 | 总池 `slots` | 最少测试位 `minTestSlots` | 整套最多几份 `heavyMax` | 空闲内存下限 `minFreeGB` | 熔断分钟 `timeoutMinutes` |
|---|---|---|---|---|---|
| 16 GB | 6 | 1 | 1 | 3 | 10 |
| 32 GB | 10 | 2 | 1 | 5 | 15 |
| 64 GB | 20 | 2 | 2 | 8 | 15 |

另外：

- **先量再调**。先照表里的起点用两三天，再跑 `node tools/test-queue.cjs stats --days 3` 看超 10 分钟的次数、其中排队为主的占几成、熔断了几次；跑 `node tools/test-queue.cjs status` 看空闲内存。排队为主 → 内存有富余就加 `slots`；真跑得慢 → 把整套拆小、开发期只跑点到的测试，别加位。
- **内存不够会把正在用的服务挤卡**。我们吃过这个亏：曾让 8 份测试同时跑，同一台机器上正在给人用的服务直接不回话。如果你的开发机上还跑着别的东西（数据库、本地服务、浏览器一堆标签），`minFreeGB` 宁可设高一点。
- **CPU 也有上限**：所有测试的并行进程数加起来，最好不超过 CPU 线程数。`pytest -n auto` 在排队器里按 `autoWeight`（默认 4 位）算，线程少的机器把它调小，或者干脆写死 `-n 2`。
- **熔断分钟数按你最慢的“该跑的”测试定**。开发期点到的测试应该在 30 秒内跑完；整套该在合并、验收时跑。15 分钟都跑不完的，多半该拆了。
- **路径和 shell 改成你自己的**：`transcriptsRoot` 默认 `~/.claude/projects`（Claude Code 会话记录的位置）；`examples/settings.json` 里的路径换成你的；Windows 上命令要在 Git Bash 里跑，PowerShell 也能用但引号规则不一样。
- **会话路数受套餐额度限制**。总池再大，额度跟不上也白搭；路数是花费的总开关，见数据报告。

## 思考档位怎么设

Claude Code 的“思考档位”（effort）越高，每一步想得越多、写出越多，也越贵。我们的建议：**只用 high 和 xhigh 两档，不开 max，也不用 medium。**

| 什么活 | 档位 | 为什么 |
|---|---|---|
| 写代码、改 bug、写文档、只读核对、查数 | **high** | 日常主力，够用 |
| 验收 / 复查、算钱算账的程序、大重构、子代理做验收 | **xhigh** | 这类活出了错返工更贵，档位往高放 |
| 任何活 | ~~max~~ 不开 | 我们量过：全开最高档那段，每步只便宜了 7%，但每天花费翻了 3.2 倍、每份交付贵了 40%、上下文超 25 万的会话从 33% 涨到 75% |
| 任何活 | ~~medium~~ 不用 | 没单独量过，是取舍：省下的钱抵不过想得不够造成的返工 |

我们量到的数据（详见[数据报告](docs/data-report.md)）：

| 阶段 | 每步花费 | 每天花费 | 每份交付 | 上下文超 25 万 |
|---|---|---|---|---|
| 最早没调整（默认档） | 10.5 美分 | 约 390 美元 | 16.6 美元 | 33% |
| 全开最高档（max） | 9.8 美分 | 约 1,270 美元 | 23.3 美元 | 75% |
| 只用 high / xhigh 之后 | 7.5 美分 | — | 10.1 美元 | 45% |

（“只用 high / xhigh”那段只有 1 天，样本小，只看方向。）

怎么设（以你所用版本的官方文档为准）：

1. **全局默认**：在 `~/.claude/settings.json` 里写 `"effortLevel": "high"`。
2. **按型号再写一遍**：我们这一版里，顶层 `effortLevel` 对新型号不生效，定时任务设的是 xhigh、实际跑的却是 medium，直到加了按型号的设置才对上。所以建议两处都写：

   ```json
   {
     "effortLevel": "high",
     "modelSettings": {
       "<你用的型号 ID>": { "effortLevel": "high" }
     }
   }
   ```

   换新型号时记得给新型号补一项。
3. **单个会话临时调**：在会话里用 `/effort xhigh`，或在桌面应用输入框旁边选。验收类会话开出来就调到 xhigh。
4. **派子代理时写明档位**：做验收的子代理给 xhigh，其余 high；不写就跟着默认走。
5. **不要设环境变量 `CLAUDE_CODE_EFFORT_LEVEL`**：它会把所有会话压成同一档，按会话、按子代理单独设的档位都失效。
6. **设完要核对**：看会话记录或用量页面，确认实际跑的档位和你设的一样。我们就是核对时才发现定时任务一直跑在 medium。

## 怎么量自己的

```bash
# 近 7 天花了多少、多少是重读前文、子代理占多少
node tools/token-usage.cjs --days 7

# 按你改规矩的时间点切段对比（先复制 config/stages.example.json 改成你的日期）
node tools/stages.cjs --stages config/stages.example.json --out stages-out.json

# 测试排队情况
node tools/test-queue.cjs status
node tools/test-queue.cjs stats --days 7
```

都是只读的，只读本机 `~/.claude/projects` 下的会话记录，不联网。花费是按价目表估的“等价美元”，不是账单；价目在 `config/stages.example.json` 的 `prices` 里，按你的套餐改。口径见[数据报告第五节](docs/data-report.md#五口径说明)。

## 改进过程

我们不是一开始就想好的，是一步步试出来的，中间也走过弯路。挑关键的几步：

| 日期 | 遇到的问题 | 改了什么 | 结果 |
|---|---|---|---|
| 9/14–10/2 | （起点）默认设置，几路会话 | 什么都没调 | 每步 10.5 美分，作为对比基准 |
| 10/3 | 想让 AI 做得更好 | 所有会话默认开最高思考档 | 每步 9.8 美分，但每天花费翻了三倍多，上下文超 25 万的会话从 33% 涨到 75% |
| 10/13 | 额度很快用完 | 子代理和定时检查降一档 | 每步没怎么变（9.9） |
| 10/15 | 不知道钱花在哪 | 写了只读查数脚本（就是 `tools/token-usage.cjs`） | 发现 98% 以上的 token 是在重读前文 |
| 11/2 | 定时检查每次都叫 AI | 改成程序先查，有新错才叫 AI | 没有新错的那几轮不花 token |
| 11/4 | 花了很多钱，交付很少 | 一件事一个新对话、照方案新写、范围派出时定死 | 每步 9.2 美分 |
| 11/5 | 验收反复不过、整份重写 | 验收只拦三类（算错钱、乱发消息、挡住在用的业务），第二轮只核第一轮那几条 | 不再三五版重写 |
| 11/10 | 档位乱开 | 只用 high、xhigh 两档，不开 max | max 用法当天归零；每步 7.5 美分 |
| 11/10 | 每一步平均要重读 27 万 token | 查出新读入 57% 来自命令输出、32% 来自读文件；命令输出一律落盘，屏幕只打结论 | — |
| 11/10 | 试了提前交接、40% 自动压缩 | 按真实价格回放：省不了钱（−25%～+7%），**撤回** | 走过的弯路 |
| 11/11 | 二十来路会话同时跑测试，机器卡死 | 测试最多 8 份、一律经排队器；一棒做完一个闭环小功能，上下文约 25 万就交接 | — |
| 11/11 夜 | 规矩里写了“少读”，AI 照样整份读 | 加读文件限行钩子（`hooks/read-limit-hook.cjs`） | 整份读文件 55% → 16%，每步降到 6.4 美分 |
| 11/12 | 复盘 | 每步更便宜了，但每小时做完的功能项从 10 降到 6.2 | 省钱和提速不是一回事 |
| 11/13–11/15 | 8 份测试同时跑把正在用的服务挤卡 | 测试位减到 4，某晚临时减到 1 | 排队变长：超 10 分钟的测试 67% 是在等位子 |
| 11/16 | 测试卡在排队 | 会话和测试共用 20 位总池，整套只准合并 / 验收跑，15 分钟熔断，内存保护（`tools/test-queue.cjs`） | 11/19 复量后补进数据报告 |
| 11/16 | 重新算账 | 从最早没调整算起，更正自己早先“每步省 59%”的说法（那次拿 11/10 当起点） | 实际是 −39% |

## 数据报告

完整的数字、图、口径和局限都在 [docs/data-report.md](docs/data-report.md)。

![前后对比](docs/images/before-after.svg)

## License

[MIT](LICENSE)
