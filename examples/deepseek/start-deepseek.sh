#!/usr/bin/env bash
# 用 DeepSeek 跑 Claude Code：只在这个窗口里设环境变量，不改系统全局，不影响你平时用的 Claude Code。
# 接口和型号名照 DeepSeek 官方文档（api-docs.deepseek.com，Claude Code 接入页）写，作者没有在本机实测，以官方现行文档为准。
# 用法：先 export DEEPSEEK_API_KEY=你的密钥，再 bash examples/deepseek/start-deepseek.sh
: "${DEEPSEEK_API_KEY:?先设 DEEPSEEK_API_KEY}"
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY"
export ANTHROPIC_MODEL='deepseek-flash[1m]'
export ANTHROPIC_DEFAULT_OPUS_MODEL='deepseek-flash[1m]'
export ANTHROPIC_DEFAULT_SONNET_MODEL='deepseek-flash[1m]'
export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-flash
export CLAUDE_CODE_SUBAGENT_MODEL=deepseek-flash
# 官方示例还设了 CLAUDE_CODE_EFFORT_LEVEL=max 和 CLAUDE_CODE_AUTO_COMPACT_WINDOW。我们不设前一个（会把所有会话、子代理压成同一档，
# 而且我们量过开最高档更贵），进去以后用 /effort high；要照官方全设，自己把下面两行的 # 去掉。
# export CLAUDE_CODE_EFFORT_LEVEL=max
# export CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432
exec claude "$@"
