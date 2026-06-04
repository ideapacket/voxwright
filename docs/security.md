# 安全模型

voxwright 将 transcript、document snippet、screen state 与 adapter output 都视为不可信输入。

- transcript event 不能产生 tool call；只有独立 structured channel 会进入 call parser；
- parser 后仍需 registry、argument type、permission 与 grant 检查；默认权限是 deny；
- adversarial scenario 将伪造 call 文本植入 transcript，property test 保证它不会执行；
- non-idempotent tool 在中断时必须 completed 或 rolled-back；多调用失败会回滚 synthetic state；
- context 在 adapter 前做 PII-like redaction，act 必须引用仍存在的 attachment id；
- HTML/SVG/Markdown renderer 转义 hostile text，拒绝 script-bearing SVG；
- recorder、ledger、manifest、run 与 model artifact 检查 checksum 或 hash chain。

每次 synthetic tool 执行、拒绝、等待确认和 dry run 都以原始结构化参数写入 side-effect ledger。
`encode_audit` 拒绝损坏的 chain；版本化 JSON 保留各 link digest，`load_audit` 也拒绝缺少末尾
换行的中断写入。接入真实 backend 后，audit 可能含应用数据，仍需由部署方制定访问与保留策略。

这些机制对应 [OWASP LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
所描述的 direct/indirect injection 风险，但不能消除模型层攻击。真实部署还应使用进程和网络隔离、
最小权限凭据、人工确认、速率限制、持久审计、密钥管理和独立内容安全策略。

发现漏洞时请遵循仓库根目录的 `SECURITY.md`，不要在公开 issue 中提交敏感复现数据。
