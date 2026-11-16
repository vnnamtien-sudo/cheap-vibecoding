# Rules and effort by platform

[← Back to README](../README.en.md)

The policy table below applies to all four platforms. The user fills in any unverified model ID in the platform settings; this guide does not guess IDs.

| Role | Claude Code | OpenAI Codex | DeepSeek (Claude Code API) | Gemini CLI |
|---|---|---|---|---|
| Main writer | Sonnet 5.5 / high; Opus 5.5 optional | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high |
| Light review | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |
| Final review | Opus 5.5 / xhigh; only for money calculations, major refactors, or releases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases |
| Read-only | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |

Start light reviews in a fresh session with no implementation context; read-only roles do not edit files. DeepSeek's official API maps xhigh to high, so it is not an xhigh tier. Codex and Gemini CLI effort options depend on the model; confirm support for the selected model. Use high for routine work and reserve final review for the cases listed above. Do not use max or medium as execution tiers. Do not set CLAUDE_CODE_EFFORT_LEVEL to flatten session effort.

## Claude Code

- Put project instructions in CLAUDE.md.
- Choose an available model with /model. Set routine effort to high with /effort high; Claude Code saves effort by model.
- Opus 5.5 can be used for high-effort writing. Reserve Opus 5.5 / xhigh for final review of money calculations, major refactors, or releases.
- Do not set CLAUDE_CODE_EFFORT_LEVEL globally; it can override per-model and per-session choices.

## OpenAI Codex

- Put project instructions in AGENTS.md.
- Choose a model the user has confirmed is available and set model_reasoning_effort = "high" in Codex settings.
- Use xhigh for final review only when the selected model explicitly supports it.

## DeepSeek

- DeepSeek can connect to Claude Code through its official Anthropic API. Use the endpoint and model IDs in the official integration guide.
- The official documentation maps xhigh to high. This integration does not provide a separate xhigh effort tier; the user confirms the final-review capability.
- Do not copy an environment setting that forces all sessions to max.

## Gemini CLI

- Put project instructions in the root GEMINI.md; the CLI loads context hierarchically.
- Set model.name in a user or project settings.json when the user has confirmed a model.
- Configure generation parameters according to that model's documentation. Gemini CLI settings may use model-specific parameters such as thinkingBudget; high and xhigh are not universal configuration keys.

## Official sources

- Claude Code: [model configuration](https://code.claude.com/docs/en/model-config) · [settings files](https://code.claude.com/docs/en/settings)
- Codex: [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) · [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- DeepSeek: [Claude Code integration](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) · [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- Gemini CLI: [configuration reference](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md) · [generation settings](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/generation-settings.md)
