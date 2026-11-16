# DeepSeek project rules

Use this template with DeepSeek's official Anthropic API integration for Claude Code. Keep project instructions in CLAUDE.md; the user configures the API, model, and credentials using the official integration guide.

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

DeepSeek's official API maps xhigh to high, so that setting does not provide an xhigh final-review tier. Ask the user to confirm an available model and platform for that work. Use high for routine work and light review; do not use max or medium as execution tiers. Do not set CLAUDE_CODE_EFFORT_LEVEL to flatten every session to one tier.

See the [effort guide](../../docs/effort.en.md) and [DeepSeek's official Claude Code integration](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/).
