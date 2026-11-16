# Change history

[← Back to README](../README.en.md)

The current version keeps rules as plain text and separates project configuration, local self-checks, and targeted tests so each can be adopted as needed.

- Search first and read focused sections to reduce irrelevant context.
- The implementer runs a local self-check before a fresh session reviews changes and evidence in read-only mode.
- gate.config.json describes project rules, test entry points, and optional data sources.
- Git hooks and targeted tests remain optional; rule files do not require scripts.

Historical measurements remain in the [data report](data-report.en.md). Read [advanced configuration](advanced.en.md) only for multi-person work or multiple concurrent sessions.
