# What we got wrong (Nov 16 retrospective)

[← Back to README](../README.en.md) | [简体中文](lessons.md)

After open-sourcing, we checked our own approach against similar projects on GitHub, the official cost guidance and public experience with running many agents in parallel. Verdict: **the direction was right, but we aimed at the small part of the bill**. Each step did get 39% cheaper, yet each delivery got 19% more expensive. Most of the money was not going to file reads but to the three things below.

## 1. Too much is loaded before any work starts

- A main session starts with about 110k tokens of fixed content (system prompt, tool descriptions, our own rules and memory), and **every later step re-reads all of it**. At estimated prices, this fixed block is about a third of the cost of each step.
- Our own rules and memory were about 40k Chinese characters before trimming: root rules ~16k, global rules ~5k, memory index ~19k. The rules we added to save money had become a fixed cost themselves.
- **What we changed**: root rules cut to 13.5k characters; the memory index keeps only the 125 most-used entries (~6k characters); the other 164 moved to a second file that is looked up only when needed. About 15k characters removed in total.
- **Correction**: our first estimate counted bytes as characters, so we thought the rules were 30k characters and that trimming would save about a sixth of each step. Recounted in characters, this trim saves roughly 5% per step.

## 2. Too many sessions at once

- We ran about 20 sessions at once on one 64 GB / 24-thread PC. Most public experience puts the practical ceiling at 5–6 per 32 GB machine, 4–5 on a typical laptop.
- Result: long test queues (67% of tests stuck over 10 minutes were waiting for a slot), a machine under memory pressure, and more and more rules (queueing, circuit breakers, yielding) to manage the crowding. The real bottleneck was that reviews could not keep up.
- **What we changed**: at most 8 sessions at once, as a one-week trial, re-measured on Nov 24.

## 3. We watched the wrong number

- We treated "cost per step" as the score. That is a component metric. Per delivery, cost rose 19% and code written per dollar fell 21%.
- Reading ~208 review verdicts one by one, 71 were real rejections: **about one in three was sent back**, mostly because the work wasn't checked against real data and the old system, or tests weren't run. Rework cost more than the reading we saved.
- **What we changed**: we now score only three numbers: cost per feature that passes review, days from assignment to release, and review rejection rate. Check against real data before writing code, run tests before review; target rejection rate under one in five.
- **Not done yet**: our new measuring script is rough. Its automatic rejection rate is only 5–8%, far from the ~34% found by reading verdicts by hand; we are still calibrating it.

## 4. Some wheels don't need reinventing

- Mature open-source usage trackers already exist (e.g. [ccusage](https://github.com/ccusage/ccusage), [splitrail](https://github.com/Piebald-AI/splitrail)) and support several agents. Our own scripts exist only for stage-by-stage comparison; for day-to-day usage, use the existing tools.
- The community has several similar read-limit hooks ([cc-safe-setup](https://yurukusa.github.io/cc-safe-setup/token-saving-hooks.html), [read-once](https://dev.to/boucle2026/read-once-a-claude-code-hook-that-stops-redundant-file-reads-4bjk)). That confirms the direction, but it isn't novel.

## When results will be added

- Nov 19: re-measure the new test-queue setup (shared pool, circuit breaker).
- Nov 24: re-measure cost per feature, days to release and rejection rate after cutting to 8 sessions, compared with before.

Both results will be added to this page, good or bad.
