# Workflow crash/resume 与补偿

本示例定义一个 versioned synthetic workflow：`reserve → charge → finish`。它输出固定布局的
SVG，执行一次直线路径，再模拟首步之后崩溃，通过 tamper-evident ledger checkpoint 恢复剩余
步骤，并按完成顺序的逆序演示补偿。

```bash
.venv/bin/python examples/workflow_recovery/main.py /tmp/voxwright-workflow
```

`summary.json` 中的 `resume_matches_straight` 来自实际状态字节比较；`compensated_steps` 为
`charge, reserve`。所有状态都是内存中的合成应用状态，不会创建日历、付款或其他真实副作用。
