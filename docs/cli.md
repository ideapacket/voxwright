# 命令行界面

`voxwright` 的命令只处理本地、版本化制品。默认流程不访问网络，也不加载预训练模型。

```bash
voxwright simulate scenarios.jsonl --seed 7 --count 4 --task schedule
voxwright run scenarios.jsonl runs.jsonl
voxwright validate runs runs.jsonl
voxwright validate workflow workflow.json --diagram workflow.svg
voxwright validate checkpoint checkpoint.json
voxwright validate audit sandbox-audit.json
voxwright validate context context.json
voxwright validate runtime runtime.json
voxwright validate campaign campaign.json
voxwright score runs.jsonl
voxwright bench runs.jsonl --budgets 50 75 100 150
voxwright report runs.jsonl report.html --format html
```

`demo` 将 manifest、观测运行、指标摘要和自包含 HTML 报告写入一个新目录：

```bash
voxwright demo demo-output --seed 7 --count 4
```

所有输出目标都必须不存在，因此失败的命令不会覆盖已有制品。`diff` 在会话完全相同时返回
0，存在差异时返回 1；参数、校验或 I/O 错误返回 2。报告和 benchmark 中的数字只来自输入的
离线合成运行及其植入真值。

`validate workflow` 会执行 envelope、step 类型、引用和 cycle 校验，并打印 workflow 名称、版本、
step 数量及 canonical digest。可选 `--diagram` 写出确定性的自包含 SVG；目标已存在时命令返回 2，
不会覆盖原文件。

`validate checkpoint` 校验版本、完成前缀、状态对象与 digest 形状，并报告已完成数量和状态 key。
它不替代恢复时的 ledger 比对；应用恢复必须同时保留 ledger 并调用 `verify_checkpoint`。

`validate audit` 重新计算完整 hash chain，并分别报告 executed、denied、confirmation-required 和
dry-run 数量。统计只描述输入制品中的 synthetic side-effect 证据，不代表真实 backend 审计。

`validate context` 严格校验 snapshot schema、attachment version 与 budget accounting，并打印
canonical digest。它处理原始 snapshot；传给 adapter 的 view 仍会执行预算 eviction 与 PII-like
redaction。

`validate runtime` 只使用 logical clock interval，报告 turn 数、完整 trace 数、active milliseconds 和
canonical digest；不读取 wall clock，也不把这些 synthetic duration 描述成真实服务延迟。

`validate campaign` 校验 config digest 与完整 metric bundle，报告 campaign 名称、seed、run count 和
task success。所有数字仍来自已执行的 synthetic runs 与 planted ground truth。
