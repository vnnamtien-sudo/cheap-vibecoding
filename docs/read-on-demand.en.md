# Read on demand to reduce repeated context

[中文](read-on-demand.md) · [README](../README.en.md)

Scope a dispatch to a function and one synthetic sample: for example `src/total.py: sum_values`, input `[2, 5]`, expected `7`. Paths are examples, chosen from the actual project. Include change boundaries, protected rules and the acceptance command rather than asking a model to read the whole project.

1. Search the target symbol and call sites; note line numbers.
2. Read a range near the target, within gate.config.json's readLimitLines.
3. Read callers, types or one test only when evidence requires it; state the purpose.
4. Hand off the dispatch, diff, receipt and one sample. Light review starts a fresh session in the same account.

Text templates need no runtime: [AGENTS skeleton](../templates/AGENTS.md), [dispatch](../templates/dispatch/task.en.md), [handoff](../templates/dispatch/handoff.en.md). The optional Claude read hook reads the same config; other platforms use rules. The hook is not a shell sandbox and cannot identify every possible command that reads a file.

Locate before reading large files in chunks; avoid whole-file dumps. Inspect sources of generated or binary files. Unsupported analysis is not verification. Results vary by computer, model and project.
