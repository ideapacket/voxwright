# voxwright

voxwright 是一个 Python 3.11+ 离线工具箱，用于实现和验证端到端 spoken language model
接入应用时的工程机制：事件记录与重放、受约束工具调用、状态编排、权限、修复策略、
逻辑时钟延迟统计与合成场景评估。

项目只评估这些应用机制。默认测试与示例使用带有植入真值的合成数据和确定性适配器，
不连接真实模型端点，不需要 API key、预训练权重、外部数据集、GPU 或付费服务。

## 开始使用

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
make test
.venv/bin/voxwright --help
```

完整的离线命令链、制品约束与退出码见 [`docs/cli.md`](docs/cli.md)。
可选 CPU 训练层的范围与验证方式见 [`docs/model-extra.md`](docs/model-extra.md)。

## 文档与示例

- [架构](docs/architecture.md) · [使用](docs/usage.md) · [API](docs/api.md)
- [制品 schema](docs/schemas.md) · [评估方法](docs/evaluation.md) · [安全](docs/security.md)
- [可复现性](docs/reproducibility.md) · [机制参考](docs/references.md)
- [四个完整离线示例](examples/README.md)

## 时间线说明

本项目于 2026 年 10 月创建和验证。Git 中 2025 年 1 月至 2026 年 10 月的日期是本次生成的演示时间线，不代表那些日期已经开展的工作。每次开发提交均执行构建、测试与格式检查；未使用空提交。项目未宣称论文成果、预训练模型或真实语音数据集成绩。

## 许可

项目使用 MIT License，详情见 `LICENSE`。
