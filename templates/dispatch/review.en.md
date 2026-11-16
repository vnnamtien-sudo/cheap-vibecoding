# Cross-check checklist for light review

One person, one account; use a light model with high effort or a fresh session without previous conversation.

- Confirm the goal from the named function and single synthetic sample.
- Read the diff and self-check receipt first; inspect adjacent callers only as needed.
- Verify targeted tests actually ran and the failure sample is blocked.
- Inspect skipped checks, parser limitations, missing test mappings and data comparisons.
- Check unauthorized changes, overwritten concurrent work and duplicate implementations.
- Read back the real usage entry; an exit status alone is insufficient.
- Report actionable findings with file, function, trigger and impact. If none, state the evidence scope.

Light review is not release approval. Money, large refactors and release readiness require a strongest-tier xhigh final review; explicitly disclose unsupported platform capability.
