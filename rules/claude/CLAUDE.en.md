<!-- Copy this into your CLAUDE.md. -->
# Usage-saving rules (Claude Code: paste at the top of CLAUDE.md in the project root or ~/.claude/CLAUDE.md)

<!-- Change the numbers in [ ] to fit your project and machine. However well the rules are written, the AI will still forget them; anything a hook can enforce (read line limits, test queue) should get a hook — see examples/claude/settings.json. -->

## Where the money goes

- Quota is charged by price: most of the money goes to fresh input and to output. Don't repeat output; when editing a file, change only the lines that need it, don't rewrite the whole file.
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

8. Use only two effort levels: high for writing code, writing docs and read-only checks; xhigh for verification reviews, money and ledger calculations, and large refactors. Don't use max (much more expensive, little extra output); don't use medium (rework costs more). When spawning a subagent, state its effort level: xhigh for verification reviews, high for everything else. For how to set it, see docs/effort.en.md in this repo.

## Tests

9. Always run tests through the queue: `node <cheap-vibecoding dir>/tools/test-queue.cjs run --label <label> -- <command>` (a hook blocks unqueued runs).
10. During development, run only the test files or cases related to the change (target: under 30 seconds); run the full test suite / whole module only at merge and verification review.
11. For new tests, keep one happy-path case plus counterexamples for things that cause real damage (wrong money, messages sent wrongly); don't chase coverage.

## Verification review

12. A verification review blocks only three kinds of issue: wrong money or ledger figures, messages sent wrongly, and blocking business that is in use. Each needs a real, reachable counterexample; everything else is noted for the next version.
13. The second review round checks only the items from the first round; don't re-review from scratch.
