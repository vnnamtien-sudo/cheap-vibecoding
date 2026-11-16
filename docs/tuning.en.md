# Tune local configuration

[← Back to README](../README.en.md)

Initialization creates gate.config.json in the target project root. Fill only fields you have confirmed and actually use in this project. Do not commit machine paths, session records, or guessed prices.

- Rules, self-checks, and targeted tests can be enabled separately. Copying a rule file alone requires no Python or other runtime.
- The default testCommand points to the targeted test entry generated for the project. Change it only when its test mapping does not fit the project.
- If you use token or stage statistics, configure only data sources and prices you have confirmed locally. Defaults do not read personal session folders or guess prices.
- The optional Git hook does not overwrite an existing hook. See gate-config.en.md for setup and options.
- After changing configuration, you can run python3 tools/self-check.py --root <project> --config from the toolkit repository.

Queue capacity, health-check cooldowns, and multi-session assignment are advanced tuning. A single person using one session does not need to change them. See [advanced configuration](advanced.en.md).
