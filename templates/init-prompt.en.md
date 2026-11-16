# Initialization prompt for a new project

This is a one-person, single-account workflow. This text needs no runtime.

Adapt this project to a token-saving, low-rework workflow:
1. Inventory extensions, top-level directories, package metadata and test entry points. Search first; read ranges of at most 60 lines.
2. Read the root gate.config.json draft, or draft one from gate.config.example.json. Optional script: run `python3 tools/init.py --root <project-directory>` from the tool checkout.
3. Adjust layers to actual directories and imports. Flag conflicting evidence.
4. Set executable testCommand and testMappings. Commands are argument arrays; {files} occupies its own argument. Do not build shell strings.
5. Type and data checks may be empty. Receipts must report skipped checks without claiming verification.
6. Set maxFileLines, maxFunctionLines, bannedPatterns with descriptions, and readLimitLines.
7. Keep four platform roles: main writer, light review, final review and read-only check. Fill only verified available model IDs.
8. Use high for routine writing and checks, xhigh for final money, large-refactor or release review. Disclose unsupported platform settings.
9. Light review uses a fresh session in the same account, without previous conversation. For limited capacity, use light models for small tasks, batch reviews or pause nonurgent work.
10. Use a synthetic sample to prove affected tests are selected, and a failing sample to prove the local gate blocks errors.

Return the draft config, evidence locations, unresolved facts and a first dispatch scoped to one function. Do not inspect private samples or execute project code to infer architecture.
