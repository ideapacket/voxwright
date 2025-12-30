# Mini voice-agent application

本示例把 calendar、music 与 smart-home 三个合成 backend 接到 permission sandbox。calendar 与
smart-home 首次调用产生确认 prompt，获得 session grant 后才执行；music 直接允许。它还演示
barge-in：幂等 music 操作可完成，非幂等 calendar 操作在取消时回滚到 atomic terminal state。

```bash
.venv/bin/python examples/mini_voice_app/main.py /tmp/voxwright-mini-app
```

脚本根据实际执行的三次 synthetic run 计算 task/slot/tool/latency 指标并生成自包含
`report.html`。报告明确列出未使用真实录音与真实模型端点；`summary.json` 保存 permission、
ledger、barge-in 和指标事实。示例没有真实日历、播放器或智能家居副作用。
