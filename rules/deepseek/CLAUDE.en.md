<!-- Copy this into your CLAUDE.md. -->
# Usage-saving rules (DeepSeek (via Claude Code connected to DeepSeek's Anthropic-compatible API): paste into CLAUDE.md in the project root)

<!-- DeepSeek has no coding agent of its own; one of its officially recommended setups is Claude Code pointed at api.deepseek.com/anthropic, so the rules file, hooks and session logs all follow Claude Code. For how to launch it, see examples/deepseek/. Change the numbers in [ ] to fit your project. -->

## Where the money goes

- Quota is charged by price: most of the money goes to fresh input and to output. Don't repeat output; when editing a file, change only the lines that need it, don't rewrite the whole file.
- DeepSeek's cache is handled automatically on the server (cache_control is ignored); the more stable the prior context and the less you change its beginning, the more cache hits you get.
- Don't compact context early: we measured that compacting early or handing off early doesn't save money, and it loses detail.

## Read less at the source

1. Search before reading: find line numbers with grep / search first, then Read with offset and limit, reading only the target snippet, ≤ [60] lines each time; don't read code or data files over [150] lines in full (a hook blocks this).
2. Send command output to disk: write the full output of data lookups, reconciliations, tests and batch checks to a temp file and print only the conclusion on screen, ≤ [15] lines. Don't dump long lists or whole error traces into the conversation.
3. To check old logic across many files, spawn a one-off subagent to read, returning only a conclusion of ≤ [100] words; subagents don't spawn subagents. Do small lookups yourself by line range; don't spawn at the slightest reason.
4. In a large codebase, check an index first (file map, function directory); don't search the whole repo.

## One task, one conversation

5. Start a fresh conversation for each task, bringing only: the plan file, the list of files to change, and the definition of done. Don't read old conversations; write fresh from the plan.
6. Each leg delivers one small feature that can be verified on its own (read, write, API or page, tests — all four). When context reaches about [250k] tokens or a loop is closed, write a one-page handoff (exact numbers, changed files, where to pick up next) and switch to a fresh conversation.
7. Fix the scope when the work is assigned; anything you want to add midway becomes a separate ticket. Only one line of work changes a given module at a time.

## Effort level

8. Use only two effort levels: high for writing code, writing docs and read-only checks; xhigh for verification reviews, money and ledger calculations, and large refactors. Don't use max (much more expensive, little extra output); don't use medium (rework costs more). DeepSeek's official example uses the environment variable `CLAUDE_CODE_EFFORT_LEVEL=max`; we don't recommend it: it forces every session and subagent in that process to the same level. If you set it at all, set it only in the window where you launch DeepSeek, never system-wide.

## Tests

9. Always run tests through the queue: `node <cheap-vibecoding dir>/tools/test-queue.cjs run --label <label> -- <command>` (a hook blocks unqueued runs).
10. During development, run only the test files or cases related to the change (target: under 30 seconds); run the full test suite / whole module only at merge and verification review.
11. For new tests, keep one happy-path case plus counterexamples for things that cause real damage (wrong money, messages sent wrongly); don't chase coverage.

## Verification review

12. A verification review blocks only three kinds of issue: wrong money or ledger figures, messages sent wrongly, and blocking business that is in use. Each needs a real, reachable counterexample; everything else is noted for the next version.
13. The second review round checks only the items from the first round; don't re-review from scratch.
14. A review subagent must name the commit it checks ("commit <sha>"; without a commit, "review target: <name>"). The same commit is reviewed once per 24 hours; ask for the earlier result instead of reviewing again (the Claude hook blocks repeats).
