# cheap-vibecoding

[简体中文](README.md) | **English**

Read only the context needed for the task to save tokens and avoid repeated content.
Run a local self-check first, then separate implementation and read-only review in the same account to reduce rework.
Run python3 tools/init.py --root ../my-project to connect your existing Git project in five minutes.

Rules are plain text; scripts are optional.

Use each component independently: [context skeleton](templates/AGENTS.md), [local self-check](tools/self-check.py), [writing/review templates](templates/dispatch/task.en.md), and [project adaptation prompt](templates/init-prompt.en.md). One person, one account. Tools use Python 3.9+ and its standard library, with no third-party packages.

## Four platforms × four roles

| Role | Claude Code | OpenAI Codex | DeepSeek (Claude Code API) | Gemini CLI |
|---|---|---|---|---|
| Main writer | Sonnet 5.5 / high; Opus 5.5 optional | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high | Strongest tier (fill in model) / high |
| Light review | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |
| Final review | Opus 5.5 / xhigh; only for money calculations, major refactors, or releases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases | Strongest tier (fill in model) / xhigh (confirm support); only for those cases |
| Read-only | Haiku 5.5 / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high | Lightweight tier (fill in model) / high |

Start each light review in a fresh session with no prior conversation. Read-only roles do not edit files. DeepSeek's official API maps xhigh to high, so it is not an xhigh tier; Gemini CLI generation settings must be confirmed for each model. The user fills in unverified model names in platform settings. Use high for routine execution. Reserve xhigh for the final reviews above. Do not use max or medium as execution tiers. When usage is tight, use a lightweight model for small tasks, batch non-urgent work, or pause non-urgent tasks. Do not set CLAUDE_CODE_EFFORT_LEVEL as a global effort setting.

## Five-minute setup

Run these commands from the cloned toolkit repository. The example target is your existing Git project named my-project in a sibling folder; change the source rule and destination in step 1 for your platform.

1. Copy a rule into the target project (Codex example):

   ~~~sh
   python3 -c "from pathlib import Path; import shutil; shutil.copy2(Path('rules/codex/AGENTS.md'), Path('../my-project/AGENTS.md'))"
   ~~~

2. Create the target project's gate.config.json:

   ~~~sh
   python3 tools/init.py --root ../my-project
   ~~~

3. Run a local self-check on the target project:

   ~~~sh
   python3 tools/self-check.py --root ../my-project
   ~~~

init.py and self-check.py are in this repository; --root points to the target project. Initialization preserves existing files by default; add --force only when you intend to overwrite them. On Windows, if python3 is unavailable, use py -3. For the optional Git hook, install-hook.py accepts python or py with --python-command. See [gate configuration](docs/gate-config.en.md), [read on demand](docs/read-on-demand.en.md), and [effort guidance](docs/effort.en.md).

## Platform rules and examples

| Platform | Rule template | Configuration example |
|---|---|---|
| Claude Code | [CLAUDE.md](rules/claude/CLAUDE.en.md) | [settings.json](examples/claude/settings.json) |
| Codex | [AGENTS.md](rules/codex/AGENTS.en.md) | [config.toml](examples/codex/config.toml) |
| DeepSeek | [CLAUDE.md](rules/deepseek/CLAUDE.en.md) | [API reference values](examples/deepseek/reference.json) |
| Gemini CLI | [GEMINI.md](rules/google/GEMINI.en.md) | [settings.json](examples/google/gemini-cli-settings.json) |

The Claude Code, Codex, and Gemini CLI examples contain placeholder model IDs; replace them with confirmed IDs before use. To enable Claude's native hooks, copy the hooks and tools/lib directories into the project root. On Windows, if python3 is unavailable, change the hook command to python or py. Using only a rule file requires no runtime. Self-checks, targeted tests, and the Git hook are optional. See gate.config.example.json and [gate configuration](docs/gate-config.en.md) for fields and local data locations. Read [advanced configuration](docs/advanced.en.md) only when running multiple sessions or coordinating multiple people.

Results vary by computer, model and project. The [historical report](docs/data-report.en.md) preserves its original numbers; they are not a promise for another project. **What we got wrong** and what we changed: see the [retrospective](docs/lessons.en.md).
