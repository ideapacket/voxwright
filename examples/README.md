# 离线示例

所有示例都使用 seeded synthetic fixture，不访问模型端点或真实应用服务。输出目录必须不存在。

| 示例 | 运行命令 | 主要制品 |
| --- | --- | --- |
| Scenario replay | `python examples/scenario_replay/main.py OUT --seed 11` | manifest、session、trace |
| Workflow recovery | `python examples/workflow_recovery/main.py OUT` | checkpoint facts、SVG |
| Repair comparison | `python examples/repair_comparison/main.py OUT --seed 7` | metrics、curve SVG |
| Mini voice app | `python examples/mini_voice_app/main.py OUT` | permission facts、HTML report |

每个目录的 README 说明真实性边界和字段。根目录的 `quickstart.py` 是最小 API 片段，不计入上述
四个端到端示例。
