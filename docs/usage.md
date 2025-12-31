# 使用指南

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
make build
make test
make typecheck
```

默认安装不需要网络服务、API key、GPU、真实录音或模型权重。可选 CPU 训练层见
[`model-extra.md`](model-extra.md)。

```python
from voxwright import TaskType, application_scenario
from voxwright.manifests import encode_manifest

scenario = application_scenario(TaskType.SCHEDULE, seed=7)
manifest = encode_manifest([scenario])
assert "calendar.create" in manifest
```

命令行可以把同一流程扩展为制品：

```bash
voxwright simulate scenarios.jsonl --seed 7 --count 4
voxwright run scenarios.jsonl runs.jsonl
voxwright validate runs runs.jsonl
voxwright score runs.jsonl
voxwright report runs.jsonl report.html
```

输出目标必须不存在。`run` 当前执行 scripted fixture truth，用于验证 mechanics，不是对真实
spoken model 的评测。四个端到端脚本及预期制品见 [`../examples/README.md`](../examples/README.md)。
