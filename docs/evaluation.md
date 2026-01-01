# 合成评估方法

Evaluation run 同时保存 planted truth 与 application observation。指标均从这些已执行记录计算：

- task success：报告满足的 planted goal 比例；
- slot accuracy：按 slot name/value 精确匹配；
- tool precision/recall/F1：每个 run 内做 multiset 匹配，禁止跨 run 抵消；
- mean turns、repair rate、false execute count 与 latency adherence；
- task type、difficulty 与 noise band slice，以及 slot/tool 名称 breakdown。

零分母有明确语义，浮点值在产生点量化到 6 位，percentile 使用整数 nearest-rank。报告只渲染
实际 `EvaluationRun`，同时嵌入 seed、config digest、coverage facts 和由 coverage 生成的限制。
默认 scripted run 完全遵循植入真值，因此用于验证计分与制品链路，不代表 conversational
intelligence。误听示例的曲线来自 seeded token corruption；可选模型 accuracy 来自合成 split。

禁止把这些数字描述为真实语音 benchmark、人类评价或预训练模型能力。真实评估必须接入经授权
的数据、定义独立标注协议，并将 adapter capability 与 coverage facts 如实记录。
