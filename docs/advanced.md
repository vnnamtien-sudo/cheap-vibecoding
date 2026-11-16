# 高级机制：多人多会话时再用

[English](advanced.en.md) · [README](../README.md)

默认是一个人一个账号的定向测试与 15 分钟超时熔断。下列机制各自可选，不是入门前置条件。

## 共享测试池

只在同机并行会话争抢资源时，在 gate.config.json 的 testQueue 设置 mode 为 advanced。可配置 slots 为 20、poolCountsSessions 为 true、minTestSlots、heavyMax、minFreeGB、staleMinutes 和 pollMs。20 只是历史设置，需按机器调节。会话目录通过 sessionRoots 配置，空配置不会扫描个人记录。多进程队列用原子目录锁协调，status 和 stats 只读队列回执。

默认 targeted 模式不启用共享池。运行命令使用参数数组，开发期间只点到相关测试；超时退出码为 124。POSIX 使用进程组，Windows 使用 Job Object 清理子孙进程。

## 工作台让路

健康探测 `/health`、服务卡顿让路和冷静期属于项目集成策略，本工具默认不探测网络服务。需要时在项目自己的包装程序中实现，明确探测目标、阈值与冷静期；无法读取时保持待定，避免虚报健康。

## 整链、交班与防作弊

整链验收与交班应核对实际入口、源文件身份、自检回执和发布状态，不以排队成功代替验收。额外防作弊检查可接 dataCheckCommand：由项目自己的只读比较器核对样本、原始数据与输出，不为过关更改输入或预期值。

## 只读用量与阶段报告

配置 tokenUsage 或 stages 的 sessionRoots，再运行 `python3 tools/token-usage.py --json` 或 `python3 tools/stages.py --json`。日志只读；只在显式 --out 时导出阶段报告。价格由用户填 prices 与 cacheReadPrice，未填时金额为未知；历史报告中的价目和数字不代表当前收费。

这些机制增加配置和维护成本，只在证据表明确有需要时使用。效果因电脑配置、模型、项目而异。
