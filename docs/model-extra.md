# 可选的 CPU 模型适配层

`voxwright[torch]` 提供一个小型 token slot-tagger 与 tool-selector，用于验证应用接线、
训练制品和 adapter contract。它从 scenario factory 生成的文本及植入真值训练；不包含预训练
权重，不下载模型或数据集，也不代表真实语音或对话质量。

```bash
uv pip install --python .venv/bin/python -e ".[dev,torch]" \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match
.venv/bin/pytest -q -m "model"
```

训练使用明确 seed，在 CPU 上同时优化 token tag loss 和 tool class loss。测试实际检查合成训练
loss 下降，并在独立的 seeded validation split 上报告 slot/tool accuracy。这些数字只说明嵌入的
合成任务结构是否被学到，不能外推到真实录音、真实 spoken language model 或人工评价。

`requirements-torch.lock` 记录已验证的 CPU extra 版本；应用仍应通过项目的 `torch` extra 安装，
并使用 CPU wheel index。模型快照采用带 checksum 的 JSON 数组，不使用 pickle，恢复时会再次
验证词表、标签、参数名、维度和有限数值。
