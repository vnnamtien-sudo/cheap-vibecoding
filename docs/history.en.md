# How we got here

[← Back to README](../README.en.md)

We didn't plan this up front; we found it step by step, with some wrong turns. The key steps:

| Date | Problem | What we changed | Result |
|---|---|---|---|
| Sep 14 – Oct 2 | (Baseline) default settings, a few sessions | Nothing tuned | 10.5 cents per step, used as the comparison baseline |
| Oct 3 | Wanted the AI to do better work | Max effort by default for every session | 9.8 cents per step, but daily spend more than tripled, and sessions with context over 250k went from 33% to 75% |
| Oct 13 | Quota ran out fast | Lowered subagents and scheduled checks by one effort level | Per-step cost barely changed (9.9) |
| Oct 15 | Didn't know where the money went | Wrote a read-only usage script (this is `tools/token-usage.cjs`) | Found that over 98% of tokens were re-reading prior context |
| Nov 2 | Scheduled checks called the AI every time | Changed to a program checking first, calling the AI only on new errors | Rounds with no new errors cost no tokens |
| Nov 4 | Lots of spend, few deliveries | One task per fresh conversation, write fresh from the plan, scope fixed when the task is handed out | 9.2 cents per step |
| Nov 5 | Verification review kept failing, leading to full rewrites | Verification review blocks only three kinds of problems (wrong money calculations, messages sent to the wrong place, blocking business in use); the second round only re-checks the first round's items | No more three-to-five-version rewrites |
| Nov 10 | Effort levels used inconsistently | Only high and xhigh, no max | Max usage dropped to zero that day; 7.5 cents per step |
| Nov 10 | Each step re-read 270k tokens on average | Found 57% of fresh input came from command output and 32% from file reads; all command output now goes to disk, only conclusions printed to screen | — |
| Nov 10 | Tried early handoff and auto-compaction at 40% | Replayed at real prices: no savings (−25% to +7%), **reverted** | A wrong turn |
| Nov 11 | About twenty sessions running tests at once froze the machine | At most 8 test runs, all through the queue; each run finishes one closed-loop small feature, and hands off at about 250k context | — |
| Nov 11 (night) | The rules said "read less", the AI still did whole-file reads | Added the read line-limit hook (`hooks/read-limit-hook.cjs`) | Whole-file reads 55% → 16%, per step down to 6.4 cents |
| Nov 12 | Retrospective | Each step was cheaper, but features finished per hour dropped from 10 to 6.2 | Saving money and going faster are not the same thing |
| Nov 13 – Nov 15 | 8 concurrent test runs stalled a service in use | Test slots cut to 4, temporarily to 1 one night | Queues got longer: 67% of tests over 10 minutes were waiting for a slot |
| Nov 16 | Tests stuck in the queue | Sessions and tests share a 20-slot shared pool, full test suite only for merge / verification review, 15-minute circuit breaker, memory guard (`tools/test-queue.cjs`) | To be added to the data report after re-measuring on Nov 19 |
| Nov 16 | Re-did the math | Counted from the untuned baseline and corrected our earlier claim of "59% saved per step" (that one used Nov 10 as the starting point) | Actually −39% |
| Nov 16 | On the same machine, Codex's prior context per step actually rose from 150k to 210k (see section 5 of the data report); the hooks only covered Claude | Confirmed Codex has the same kind of hooks, wired the read line limit and test queue into Codex; the shared pool now also counts Codex sessions; also released Google and DeepSeek versions written per docs | Awaiting re-measurement |
