# 思考档位怎么设

[← 回到 README](../README.md)

各家的“思考档位”（Claude Code 叫 effort，Codex 叫 reasoning effort）越高，每一步想得越多、写出越多，也越贵。我们的建议：**只用 high 和 xhigh 两档，不开 max，也不用 medium。**

| 什么活 | 档位 | 为什么 |
|---|---|---|
| 写代码、改 bug、写文档、只读核对、查数 | **high** | 日常主力，够用 |
| 验收 / 复查、算钱算账的程序、大重构、子代理做验收 | **xhigh** | 这类活出了错返工更贵，档位往高放 |
| 任何活 | ~~max~~ 不开 | 我们量过：全开最高档那段，每步只便宜了 7%，但每天花费翻了 3.2 倍、每份交付贵了 40%、上下文超 25 万的会话从 33% 涨到 75% |
| 任何活 | ~~medium~~ 不用 | 没单独量过，是取舍：省下的钱抵不过想得不够造成的返工 |

我们量到的数据（详见[数据报告](data-report.md)）：

| 阶段 | 每步花费 | 每天花费 | 每份交付 | 上下文超 25 万 |
|---|---|---|---|---|
| 最早没调整（默认档） | 10.5 美分 | 约 390 美元 | 16.6 美元 | 33% |
| 全开最高档（max） | 9.8 美分 | 约 1,270 美元 | 23.3 美元 | 75% |
| 只用 high / xhigh 之后 | 7.5 美分 | — | 10.1 美元 | 45% |

（“只用 high / xhigh”那段只有 1 天，样本小，只看方向。）

**Codex**：`~/.codex/config.toml` 写 `model_reasoning_effort = "high"`，验收的对话开出来调到 xhigh；不开 max、ultra。**谷歌 Antigravity**：`/effort high`。**DeepSeek（经 Claude Code）**：同下面 Claude Code 的设法；DeepSeek 官方示例里设了 `CLAUDE_CODE_EFFORT_LEVEL=max`，原因见第 5 条，我们的启动脚本把它注释掉了。

**Claude Code** 怎么设（以你所用版本的官方文档为准）：

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
