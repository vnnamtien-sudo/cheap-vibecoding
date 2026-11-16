# Claude Code project rules

Place this file at the project root as CLAUDE.md, or add it to project rules using the official settings.

## Working method

- Start with a clear goal, allowed scope, and completion criteria.
- Search for files and symbols before reading sections. Read no more than 60 lines at a time. Save full command output to a temporary file and print only conclusions.
- Inspect the current implementation and callers before making the smallest change that meets the goal. Preserve existing behavior and data formats.
- After writing, the implementer runs the local self-check first: `python3 <toolkit>/tools/self-check.py --root .` (`py -3` on Windows), and hands over for review only when it passes; optionally run `tools/install-hook.py` to self-check before every Git commit. Record the command, result, and anything not run.
- Run light acceptance in a fresh session with no implementation context. Review changes, criteria, and evidence in read-only mode.
- Report only evidence-backed defects with file location, impact, and evidence. Mark unsupported assumptions as unconfirmed.

## Four platforms × four roles

| Role | Claude Code | OpenAI Codex | DeepSeek (Claude Code API) | Gemini CLI |
|---|---|---|---|---|
| Main writer | Sonnet 5.5 / high; Opus 5.5 optional | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high |
| Light review | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |
| Final review | Opus 5.5 / xhigh; only for money calculations, major refactors, or releases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases |
| Read-only | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |

Use high for routine execution and light read-only review. Reserve xhigh for the final reviews above. DeepSeek's official API maps xhigh to high, so it is not an xhigh tier; Gemini CLI generation settings must be confirmed for each model. Do not use max or medium as execution tiers. Start each light review in a fresh session. The user fills in unverified model IDs in actual platform settings. Do not set CLAUDE_CODE_EFFORT_LEVEL as a global effort setting.

See the [effort guide](../../docs/effort.en.md) and [official model configuration](https://code.claude.com/docs/en/model-config).
