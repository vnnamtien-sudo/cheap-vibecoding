# Advanced mechanisms: only for concurrent users or sessions

[中文](advanced.md) · [README](../README.en.md)

The default is one person, one account, targeted tests and a 15-minute timeout. Each mechanism below is optional, with no onboarding prerequisite.

## Shared test pool

For resource contention between sessions on one machine, set testQueue.mode to advanced in gate.config.json. Options include slots (historically 20), poolCountsSessions, minTestSlots, heavyMax, minFreeGB, staleMinutes and pollMs. Tune the pool to the machine. Configure sessionRoots explicitly; empty configuration does not scan personal logs. Atomic directory locks coordinate processes; status and stats read queue receipts.

The default targeted mode does not enable a shared pool. Use argument arrays and specific affected tests. A timeout exits with 124. POSIX process groups and Windows Job Objects clean up descendants.

## Yielding to a workbench

Health probes at `/health`, yielding to slow services and cooldowns are project integration policies. This tool does not probe network services by default. If needed, implement a project wrapper with explicit targets, thresholds and cooldowns; unavailable evidence must remain unknown.

## Whole-chain handoff and integrity checks

Verify the real entry point, source identity, self-check receipt and release state at handoff. Queue admission is not acceptance. Optional integrity comparisons belong in dataCheckCommand: use a project-owned read-only comparator for samples, inputs and outputs. Never change inputs or expected results just to pass.

## Read-only usage and stage reports

Configure tokenUsage or stages sessionRoots, then run `python3 tools/token-usage.py --json` or `python3 tools/stages.py --json`. Logs are read-only; stage export requires explicit --out. Supply prices and cacheReadPrice; missing prices mean unknown cost. Historical report prices and measurements are not current billing.

These mechanisms add maintenance work; use them when evidence warrants it. Results vary by computer, model and project.
