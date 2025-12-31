# Public API

稳定入口由 `voxwright.__all__` 明确定义；子模块还公开高级集成所需的 codec 与分析函数。

| 领域 | 主要入口 | 约束 |
| --- | --- | --- |
| Events | `EventEnvelope`, `EventKind`, `envelope_for` | sequence 单调，payload 按 kind 校验 |
| Adapters | `SpokenAdapter`, `AdapterTurn` | 非空 observe 后恰好一次 act |
| Calls | `parse_call`, `ToolSchema`, `ToolRegistry` | transcript 与 call channel 分离 |
| Frames | `TaskFrame`, `GroundedSlot`, `FrameStack` | lifecycle 与 nested restore 显式 |
| Workflow | `WorkflowDefinition`, `WorkflowStep`, `run_linear` | reference/cycle/precondition 先验证 |
| Tools | `ToolSandbox`, `PermissionPolicy` | deny by default；confirm 需要 session grant |
| Repair | `RepairConfig`, `run_repair` | `max_attempts` 保证终止 |
| Runtime | `LatencyBudget`, `LatencyTrace` | 仅逻辑毫秒，不读取 wall clock |
| Evaluation | `EvaluationRun`, `score_runs` | 只对植入真值运行评分 |

函数和 dataclass 都有类型注解。需要序列化时应使用对应 codec，而不是 `pickle` 或
`dataclasses.asdict`：codec 会检查字段集合、嵌套类型、版本、完整行和 checksum。
