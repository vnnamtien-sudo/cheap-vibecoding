# Prompt templates

Change the values in [ ] to fit your project and machine.

## Template A: kickoff card for a fresh conversation

```markdown
[Kickoff card]
Model: [Opus]; effort level: [high / xhigh].

1. Read less: search for line numbers before reading a file, ≤ 60 lines each time; send large chunks of old code to a one-off subagent that returns only ≤ 100 words; write data lookups and test details to a temp file and print a conclusion of ≤ 15 lines on screen.
2. Goal of this leg: finish one small feature with all four parts (read, write, API or page, tests) that can be verified on its own. If context reaches about [250k] and nothing verifiable has been delivered yet, write the exact numbers, changed file paths and where to pick up next into the handoff note, and end the conversation.
3. Always run tests through the queue (node <cheap-vibecoding dir>/tools/test-queue.cjs run --label <label> -- …); during development, run only targeted tests.
4. Read only these three things, then start: handoff note [path], plan [path], files to change [list]. Don't read old conversations; don't page through old code line by line.

After reading the handoff note, state the goal of this leg in one sentence and start right away.
```

## Template B: handoff note

```markdown
# Handoff: [feature name], leg [N]

- Done: [one sentence]; changed files: [list of paths]
- Exact numbers: [tests x/y passing; against old data, a records match, b differ (line numbers of the differences)]
- Not done / where to pick up: [which function in which file to continue from]
- Pitfalls to avoid next time: [one or two]
```

## Template C: daily progress, 4 items only

```markdown
[Daily progress: report only 4 items]
Don't report how many lines were written. Report only:
1. Ticks on the feature checklist: an item counts only when all four parts (read, write, page or API, tests) are done.
2. Cumulative number of feature items merged to main; how many are backlogged waiting for verification review and waiting to merge.
3. Average test time and queue status (node <cheap-vibecoding dir>/tools/test-queue.cjs stats); were any runs over 10 minutes?
4. Today's usage (node tools/token-usage.cjs --days 1) and whether cost per step changed.
```
