# 合成场景与确定性重放

本示例生成一个带植入 slot/tool 真值的 music 场景，由 `ScriptedAdapter` 产生预先定义的
应用事件，再写入带 hash chain 的 session JSONL。脚本使用相同 seed 重放两次，并逐字节比较
trace；它不连接模型端点，也不处理真实音频。

```bash
.venv/bin/python examples/scenario_replay/main.py /tmp/voxwright-replay --seed 11
```

输出目录必须不存在。目录中包含 `scenarios.jsonl`、`session.jsonl`、`trace.json` 和
`summary.json`，其中 `synthetic: true` 明确标记数据来源。
