# 植入误听下的 repair policy 比较

脚本在 seeded schedule transcript 中植入 token 删除与 filler 插入，比较 cautious 与 permissive
两个有界 repair policy。每个点实际运行 `run_repair`，再计算 task success、repair rate 与 handoff
rate；结果来自文本合成 fixture，不代表真实 ASR、真实录音或人工对话质量。

```bash
.venv/bin/python examples/repair_comparison/main.py /tmp/voxwright-repair \
  --seed 7 --samples 20
```

输出包括 `metrics.json` 以及每个 policy 的 success/repair SVG 曲线。相同 seed 与样本数会生成
逐字节相同的制品；repair loop 始终受 `max_attempts` 限制。
