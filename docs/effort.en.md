# How to set the effort level

[← Back to README](../README.en.md)

The higher each agent's effort level (Claude Code calls it effort, Codex calls it reasoning effort), the more each step thinks and writes, and the more it costs. Our recommendation: **use only high and xhigh; don't use max, and don't use medium.**

| Work | Effort level | Why |
|---|---|---|
| Writing code, fixing bugs, writing docs, read-only checks, querying numbers | **high** | The everyday workhorse; good enough |
| Verification review / re-checks, programs that compute money and accounts, big refactors, subagents doing verification review | **xhigh** | Mistakes here are more expensive to redo, so set effort higher |
| Any work | ~~max~~ off | We measured: in the period with max on everywhere, each step was only 7% cheaper, but daily spend went up 3.2×, cost per delivery went up 40%, and sessions with context over 250k went from 33% to 75% |
| Any work | ~~medium~~ not used | Not measured separately; a trade-off: the savings don't cover the rework caused by not thinking enough |

What we measured (details in the [data report](data-report.en.md)):

| Period | Cost per step | Spend per day | Cost per delivery | Context over 250k |
|---|---|---|---|---|
| Untuned baseline (default effort) | 10.5 cents | about $390 | $16.6 | 33% |
| Max effort everywhere | 9.8 cents | about $1,270 | $23.3 | 75% |
| After switching to high / xhigh only | 7.5 cents | — | $10.1 | 45% |

(The "high / xhigh only" period is just 1 day; the sample is small, so only read the direction.)

**Codex**: in `~/.codex/config.toml` set `model_reasoning_effort = "high"`, and raise verification-review conversations to xhigh when you open them; don't use max or ultra. **Google Antigravity**: `/effort high`. **DeepSeek (via Claude Code)**: set it the same way as Claude Code below; DeepSeek's official example sets `CLAUDE_CODE_EFFORT_LEVEL=max`; see item 5 for why our launch script comments it out.

**Claude Code** (the official docs for your version take precedence):

1. **Global default**: put `"effortLevel": "high"` in `~/.claude/settings.json`.
2. **Set it again per model**: in our version, the top-level `effortLevel` did not apply to newer models. A scheduled task was set to xhigh but actually ran at medium, until we added the per-model setting. So we recommend setting both:

   ```json
   {
     "effortLevel": "high",
     "modelSettings": {
       "<your model ID>": { "effortLevel": "high" }
     }
   }
   ```

   When you switch to a new model, remember to add an entry for it.
3. **Per-session override**: use `/effort xhigh` in the session, or pick it next to the input box in the desktop app. Set verification-review sessions to xhigh as soon as they open.
4. **State the effort level when launching subagents**: xhigh for subagents doing verification review, high for the rest; if you don't set it, it follows the default.
5. **Don't set the environment variable `CLAUDE_CODE_EFFORT_LEVEL`**: it forces every session to the same level, and per-session and per-subagent settings stop working.
6. **Verify after setting it**: check session logs or the usage page to confirm the level actually running matches what you set. That's how we found our scheduled tasks had been running at medium all along.
