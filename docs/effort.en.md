# How to use effort levels

[← Back to README](../README.en.md)

Use high for routine code and documentation work, read-only checks, and light review. Reserve xhigh for final review of money calculations, major refactors, or releases. Do not use max or medium as execution tiers. Start light reviews in fresh sessions without implementation context.

## Historical measurements

These are historical measurements, not a cost promise for a new project. See the [data report](data-report.en.md) for the source data.

| Period | Cost per step | Spend per day | Cost per delivery | Context over 250k |
|---|---|---|---|---|
| Untuned baseline (default effort) | 10.5 cents | about $390 | $16.6 | 33% |
| Max effort everywhere | 9.8 cents | about $1,270 | $23.3 | 75% |
| After switching to high / xhigh only | 7.5 cents | — | $10.1 | 45% |

The “high / xhigh only” period is just 1 day; the sample is small, so use it only as a directional result.

## Platform settings

Model names and supported effort levels depend on the platform, account, and client. Fill in only confirmed model IDs and check the selected model's supported levels.

- Claude Code: choose a model with /model and set its routine effort with /effort high. Claude Code saves selected effort by model under modelSettings in settings.json. For a high-stakes final review, use /effort xhigh in a fresh session. Do not set CLAUDE_CODE_EFFORT_LEVEL to flatten session effort.
- Codex: set a confirmed model and model_reasoning_effort = "high" in config.toml. Use xhigh for final review only when the selected model explicitly supports it.
- Gemini CLI: choose a confirmed model with /model or model.name in settings.json. Configure generation parameters only as documented for that model; Gemini CLI does not use universal high / xhigh strings.
- DeepSeek: its official API accepts high and max, and maps xhigh to high. Therefore its xhigh setting cannot provide an xhigh final-review tier. The user must select a model and platform that truly support xhigh for that role. Routine work can use high.

When usage is tight, use a lightweight model for small tasks, batch non-urgent work, or pause non-urgent tasks. Check the official platform documentation for setup details:

- [Claude Code model configuration](https://code.claude.com/docs/en/model-config) · [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Gemini CLI configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md) · [generation settings](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/generation-settings.md)
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/) · [Claude Code integration](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/)

See the examples directory. The user confirms the actual model and local settings entry before applying a configuration.
