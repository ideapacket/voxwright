# 命令行界面

`voxwright` 的命令只处理本地、版本化制品。默认流程不访问网络，也不加载预训练模型。

```bash
voxwright simulate scenarios.jsonl --seed 7 --count 4 --task schedule
voxwright run scenarios.jsonl runs.jsonl
voxwright validate runs runs.jsonl
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
