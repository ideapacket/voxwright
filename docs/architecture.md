# 架构

voxwright 把 spoken-language application 的可验证机制分成六层：

1. `events`、`recording` 与 `replay` 定义严格事件边界、hash chain 和逻辑时钟重放。
2. `scenarios` 与 `manifests` 生成 seeded 文本 fixture、误听、攻击字符串和植入真值。
3. `adapters` 只规定 observe→act 协议；scripted、recorded、template、local loopback 与可选
   CPU model adapter 均不得绕过事件边界。
4. `call_grammar`、`tool_schema`、`frames` 与 `context` 分离模型文本、工具通道、slot 状态和
   multimodal attachment。
5. `workflow`、`sandbox`、`barge_in` 与 `repair` 管理确定性编排、权限、副作用、补偿和中断。
6. `runtime`、`latency`、`evaluation` 与 `reports` 从实际执行的合成 run 计算指标和制品。

默认路径只依赖 NumPy。PyTorch extra 是调用方训练的小模型，用于验证 slot/tool 接线；导入基础
包不会加载 PyTorch。所有时间来自逻辑时钟，所有随机选择来自显式 seed，JSON 使用 canonical
encoding，跨边界制品带版本，关键 JSONL、模型和 ledger 制品带 checksum 或 hash chain。

## 信任边界

Transcript 与 context 始终是不可信数据，不能直接成为 tool call。只有 structured call channel
经过 grammar、registry、类型校验和 permission policy 后才可到达 synthetic backend。报告会
转义 hostile text；privacy filter 在 adapter view 之前处理 PII-like pattern。真实应用仍需在
进程外补充身份认证、持久权限、网络隔离和审计存储。
