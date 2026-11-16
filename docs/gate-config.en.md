# Shared configuration and local checks

[中文](gate-config.md) · [README](../README.en.md)

Tools require only Python 3.9+ standard library; self-check also requires Git. Text templates need no runtime. All four platforms share the project's root gate.config.json; gate.config.example.json is included. Onboarding is two steps: copy rules, then run init. Self-check is the third command that verifies the setup.

| Field | Meaning |
|---|---|
| accountMode | single: one person, one account |
| maxFileLines | Maximum lines per changed text file |
| maxFunctionLines | Maximum supported function span, including comments and blank lines |
| bannedPatterns | Array of pattern, description, optional flags (i/m/s); Python regex syntax |
| layers | Array of path, optional name, and allow arrays; explicitly permit same-layer imports |
| testCommand | Argument array; standalone {files} expands changed code paths, {python} is this interpreter |
| testMappings | Source paths or directory prefixes mapped to exact test-path arrays; matches are combined |
| typeCheckCommand | Optional argument array; empty skips type checking |
| dataCheckCommand | Optional argument array receiving all changed text paths; empty skips comparison |
| readLimitLines | Bounded-read limit for hooks and rules |
| roles | claude/codex/deepseek/gemini, each with mainWriter/lightReview/finalReview/readOnly |
| testQueue | Defaults: targeted, timeoutSeconds=900, hookEnabled=false; advanced options are separate |
| tokenUsage / stages | Optional explicit log roots, verified prices and stage definitions |
| privacy.patterns | Extra privacy rules, each with pattern and description |

Each role has model, tier and effort. Empty model IDs require user verification; strong/light/strongest describe intent, without changing provider settings. Claude presets: Sonnet 5.5 writing (optionally Opus 5.5), Haiku 5.5 light review/read-only, Opus 5.5 final review. Routine work uses high; final money, large-refactor and release review uses xhigh, subject to actual platform support. Light review starts a fresh session in the same account. See the [README](../README.en.md) for the shared table and [effort guidance](effort.en.md) for setup entries.

Commands are argument arrays, never shell strings. Example: `["{python}", ".ai-gates/targeted-tests.py", "{files}"]`. The project's own test runtime must still exist; the tool itself has no dependency on that runtime. Banned patterns also inspect configuration text, so consider where literal pattern definitions match.

## Initialize

From the tool checkout run `python3 tools/init.py --root <existing-project>`. It inspects extensions, actual directories and package metadata without executing project code, then creates gate.config.json and, when needed, the versionable .ai-gates/targeted-tests.py. Existing configuration is preserved; --force explicitly overwrites. Inspect detected and review; unknown frameworks are not verified tests. Commit the helper and config for use on another computer.

## Self-check and receipt

Built-in targeted mapping supports unittest and the Node test runner. Other frameworks require a user-provided command and mappings; missing mappings must not count as passed.

Run `python3 tools/self-check.py --root <project>`. It checks existing changed text files from staged, unstaged and untracked Git changes, recording deleted/binary skips. It checks line limits and patterns, language-dependent functions/import layers, then type checks, affected tests and optional data comparisons. A failure blocks later checks and exits nonzero.

Python uses AST. JS/TS use lexical analysis; complex aliases, computed imports and template interpolation need real type checks or tests. Other languages have function/import analysis gaps listed under receipt limitations; file and pattern checks still apply. Missing test mappings or an unconfigured targeted test command are not full verification. Unconfigured type and data checks are explicitly skipped.

The default receipt is .gate/self-check.json; --receipt changes it, --config selects another config. --staged executes against an index snapshot with its corresponding config so working-tree contents cannot hide pending changes. Do not commit local .gate receipts as source.

## Optional Git hook

Run `python3 tools/install-hook.py --root <project>`. It creates a local pre-commit calling this checkout's self-check --staged, without overwriting an existing hook. Reinstall after moving this tool checkout or interpreter. On Windows use --python-command python or py, and replace python3 accordingly in other tool commands. Hooks are optional.

Claude may additionally install read/test hooks using examples/claude/settings.json: commands use python3; Windows users replace it with python or py. Codex, DeepSeek and Gemini use rules plus optional pre-commit; their hook protocols are not assumed identical.

## Privacy and historical reports

`python3 tools/privacy-scan.py` checks Git-managed and nonignored candidate text. Its .gate/privacy.json receipt records locations and rules without exposing matching values. Binary files, links and unknown encodings require review. It detects common credential/private-text patterns; add project-specific names through privacy.patterns. Ignored personal logs are unpublished and outside scan scope. Historical report numbers are unchanged, not predictions for another project. Results vary by computer, model and project.
