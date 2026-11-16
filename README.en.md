# cheap-vibecoding

[简体中文](README.md) | **English**

A few small tools for running **many AI coding-agent sessions at once without burning money**. Works with Claude Code, OpenAI Codex, Google Antigravity and DeepSeek. Single-file Node.js, zero dependencies.

![Cost per step](docs/images/en/cost-per-step.svg)

Measured on our own workstation over two months and 650,000 replies:

- **Cost per step −39%**: 10.5 → 6.4 cents (a step = one tool call)
- **Whole-file reads 51% → 16%**: done by a hook; writing "read less" in the rules never moved it
- **67% of "stuck" tests were just waiting in line**: so sessions and tests now share one pool

## Just three things

| File | What it does |
|---|---|
| `hooks/read-limit-hook.cjs` | No dumping whole big files; at most 60 lines at a time, and it hands back the fixed command |
| `hooks/test-queue-hook.cjs` + `tools/test-queue.cjs` | Tests must queue: one pool for sessions and tests, full-suite tiering, 15-minute circuit breaker, free-memory floor |
| `tools/token-usage.cjs`, `tools/stages.cjs` | Where the money goes; before/after comparison split by the dates you changed your rules |

Plus a token-saving rules template per agent: `rules/claude/`, `rules/codex/`, `rules/google/`, `rules/deepseek/`.

## Set up in five minutes

1. Clone this repo and run the self-test: `npm test` (Node.js 18+).
2. Register the hooks, copying from `examples/<agent>/`:
   - Claude Code: merge `examples/claude/settings.json` into `~/.claude/settings.json`
   - Codex: put `examples/codex/hooks.json` at `~/.codex/hooks.json`, then trust it in `/hooks` (**untrusted hooks are skipped silently**)
   - Google Antigravity: put `examples/google/hooks.json` at `.agents/hooks.json` in your project
   - DeepSeek: same hooks as Claude Code; start with the script in `examples/deepseek/`
3. Paste `rules/<agent>/` at the top of the rules file your agent reads.
4. Adjust `config/test-queue.json` using the next section.
5. Try it: ask the agent to read a 300-line file whole, and to run a test directly. Both should be blocked.

How far each agent goes (hooks, usage stats, what we actually tested): [docs/agents.en.md](docs/agents.en.md).

## Tune for your machine

The defaults are tuned for our 64 GB / 24-thread box. **Don't copy them.** Starting points:

| RAM | Pool `slots` | Min test slots | Max full suites | Free-memory floor GB | Breaker minutes |
|---|---|---|---|---|---|
| 16 GB | 6 | 1 | 1 | 3 | 10 |
| 32 GB | 10 | 2 | 1 | 5 | 15 |
| 64 GB | 20 | 2 | 2 | 8 | 15 |

After two or three days run `node tools/test-queue.cjs stats --days 3` and adjust. Details: [docs/tuning.en.md](docs/tuning.en.md).

## Measure your own

```bash
node tools/token-usage.cjs --days 7                 # last 7 days: spend, share spent re-reading context
node tools/token-usage.cjs --agent codex --days 7   # another agent: codex / gemini / deepseek / all
node tools/test-queue.cjs status                    # test queue
```

Read-only, local transcripts only, no network.

## Honestly: the total bill did not go down

Unit cost fell 40%, but total cost per delivery did not (16.6 → 19.7 USD). Split it and **main sessions got 20% cheaper per delivery; the whole increase is subagents**: 68% of subagent spend went to reviews, and the same branch was often reviewed again by several sessions. Lesson: the number of sessions and subagents is the master switch; a cheaper unit cost is not a smaller bill. We are adding a hook that blocks duplicate reviews and will update this after re-measuring. Full numbers and method: [data report](docs/data-report.en.md).

## More

- [How to set the effort level](docs/effort.en.md) (only high / xhigh, and the data behind not using the top level)
- [How we got here](docs/history.en.md) (step by step, including the wrong turns)
- [Data report](docs/data-report.en.md)

[MIT](LICENSE)
