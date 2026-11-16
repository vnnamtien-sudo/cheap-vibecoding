# 用 DeepSeek 跑 Claude Code（PowerShell 版）：只在这个窗口里设环境变量，不改系统全局。说明同 start-deepseek.sh。
# 用法：先 $env:DEEPSEEK_API_KEY = '你的密钥'，再 powershell -File examples/deepseek/start-deepseek.ps1
if (-not $env:DEEPSEEK_API_KEY) { Write-Error '先设 $env:DEEPSEEK_API_KEY'; exit 1 }
$env:ANTHROPIC_BASE_URL = 'https://api.deepseek.com/anthropic'
$env:ANTHROPIC_AUTH_TOKEN = $env:DEEPSEEK_API_KEY
$env:ANTHROPIC_MODEL = 'deepseek-flash[1m]'
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = 'deepseek-flash[1m]'
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = 'deepseek-flash[1m]'
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = 'deepseek-flash'
$env:CLAUDE_CODE_SUBAGENT_MODEL = 'deepseek-flash'
claude @args
