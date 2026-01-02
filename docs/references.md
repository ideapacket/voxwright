# 机制参考

下列资料只用于术语、风险与机制设计；voxwright 的代码、schema 与 fixture 均为独立实现。

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/)：对象与类型验证。
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)：
  direct/indirect injection 与 excessive agency 风险。
- [LiveKit turn-taking tuning](https://docs.livekit.io/agents/logic/turns/tuning/)：区分 endpointing、
  interruption 与 preemptive generation；voxwright 只实现 tool/application state 的中断语义。
- [PyTorch reproducibility](https://docs.pytorch.org/docs/stable/notes/randomness.html)：seed 与限制。
- [ReAct](https://arxiv.org/abs/2210.03629)、[Toolformer](https://arxiv.org/abs/2302.04761) 与
  [Gorilla](https://arxiv.org/abs/2305.15334)：工具使用和 action/observation loop 的研究背景。
- [Moshi](https://arxiv.org/abs/2410.00037)：full-duplex spoken interaction 背景；本项目不实现
  音频模型，只验证应用层 barge-in 后的副作用状态。

引用不表示复现论文结果，也不表示项目拥有预训练权重或真实数据集成绩。
