# Tune for your machine

[← Back to README](../README.en.md)

Our machine: **Windows 11, 64 GB RAM, 24 threads**. The numbers in `config/test-queue.json` (shared pool of 20 slots, 8 GB free-memory floor, etc.) **are tuned for this machine; don't copy them as-is**.

What the shared pool `slots` means: **active sessions + slots taken by running tests ≤ slots**. Each session also uses memory and CPU, so sessions count toward the pool; one `pytest -n K` takes K slots.

Suggested starting points:

| Your RAM | Shared pool `slots` | Min test slots `minTestSlots` | Max full suites at once `heavyMax` | Free-memory floor `minFreeGB` | Circuit breaker minutes `timeoutMinutes` |
|---|---|---|---|---|---|
| 16 GB | 6 | 1 | 1 | 3 | 10 |
| 32 GB | 10 | 2 | 1 | 5 | 15 |
| 64 GB | 20 | 2 | 2 | 8 | 15 |

Also:

- **Measure, then tune.** Use the starting values from the table for two or three days, then run `node tools/test-queue.cjs stats --days 3` to see how many runs took over 10 minutes, what share of those were mostly queueing, and how many hit the circuit breaker; run `node tools/test-queue.cjs status` to see free memory. Mostly queueing → if you have memory to spare, raise `slots`. Actually slow → split the full suite and run only the targeted tests during development; don't add slots.
- **Running out of memory stalls the services you're using.** We learned this the hard way: once we let 8 test runs go at the same time, and a service on the same machine that people were actively using stopped responding. If your dev machine also runs other things (a database, local services, a browser with lots of tabs), set `minFreeGB` on the high side.
- **CPU has a limit too**: the total number of parallel test processes should ideally not exceed the CPU thread count. In the queue, `pytest -n auto` counts as `autoWeight` (default 4 slots); on machines with fewer threads lower it, or just hardcode `-n 2`.
- **Set the circuit breaker by your slowest test that should be run.** Targeted tests during development should finish within 30 seconds; the full test suite belongs in merge and verification review. Anything that can't finish in 15 minutes probably needs splitting.
- **The shared pool must count all your agents** (Antigravity sessions are not counted: their log location is not documented): `sessionDirs` in `config/test-queue.json` lists the session log directories for Claude, Codex and Gemini CLI; an agent you haven't installed counts as 0. If your logs live elsewhere, change `path`. DeepSeek runs on Claude Code, so it counts under the Claude entry.
- **Change paths and shell to your own**: replace the paths in `examples/` with yours; on Windows, run commands in Git Bash. PowerShell works too, but its quoting rules differ.
- **The number of sessions is limited by your plan's quota.** However large the pool, it's no use if the quota can't keep up; the number of parallel sessions is the master switch for spend, see the data report.
