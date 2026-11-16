# Project rules: one person, one account

- Goal: deliver the requested behavior with the smallest complete change.
- Read gate.config.json and only the rules needed for this task.
- Dispatch to named files and functions, one synthetic input sample, and an expected result.
- Search symbols first; read bounded ranges up to readLimitLines. Do not dump large files.
- Read callers only when the target function or evidence requires it.
- Preserve concurrent edits and confirmed business rules; keep unknown facts explicit.
- Main writing, documentation and read-only checks use high effort.
- A light model reviews in a new session with no prior conversation, in the same account.
- Use xhigh only for final review involving money, large refactors or release readiness.
- Select actual available model IDs through roles in gate.config.json and platform settings.
- When capacity is tight, use a light model for small tasks, batch reviews or pause nonurgent work.
- Run only tests related to changed files; enforce the configured timeout.
- Before model review, run the optional Python self-check and provide its JSON receipt.
- Verify the original usage scenario, including a meaningful failure case.
- Report changed files, exact checks, results and remaining gaps; distinguish local checks from release.
- Text templates work without any runtime; scripts and Git hooks are optional.
