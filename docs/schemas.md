# 制品与 schema

`voxwright.schemas.ARTIFACT_SCHEMAS` 是公开 catalog，列出 12 种版本化制品的 envelope 字段、
media type 与完整性保护。当前版本均为 1；未知版本和多余字段会被拒绝，不做静默降级。

JSONL 制品要求最后一行以换行结束，避免把中断写入误当成完整记录。scenario manifest、run
stream 与 model artifact 对内容计算 SHA-256；session record 与 workflow ledger 使用前向 hash
chain，因此修改历史记录会暴露第一个不一致位置。普通 JSON summary 通过上游已验证事实重建。

字段约束借鉴 [JSON Schema Draft 2020-12 Core](https://json-schema.org/draft/2020-12/json-schema-core.html)
与 [Validation](https://json-schema.org/draft/2020-12/json-schema-validation.html) 的对象、类型和必需
字段概念，但 voxwright 使用小型专用 validator，以便提供领域路径和精确错误。项目不宣称其
Python validator 是完整 JSON Schema 实现。

```python
from voxwright.schemas import artifact_schema

schema = artifact_schema("session-record")
assert schema.version == 1
assert schema.checksummed
```

workflow definition 采用单个 canonical JSON 文档，显式保存 schema version、workflow version、
入口和有序 step 列表。decoder 拒绝未知字段、悬空引用和非 bounded loop 形成的环；文件缺少末尾
换行时也会被视作可能中断的写入。`workflow_digest` 对包含末尾换行的规范字节计算 SHA-256，
因此同一语义制品在支持的 Python 版本间具有相同标识。

workflow checkpoint 记录已完成 step 的严格前缀、最后状态和 ledger tail digest。读取文件时会检查
schema、字段类型与末尾换行；恢复前用 `verify_checkpoint` 对照完整的 hash-chain ledger，任何状态、
前缀、digest 或 ledger 历史变化都会被拒绝。`resume_suffix` 只返回声明顺序中尚未完成的后缀。

context snapshot 保存 token budget 和 attachment 的 id、kind、content、version、cost、priority；
canonical digest 会随任一版本或内容变化。每次应用上下文变化可写成 `context-update` session event，
其中引用 snapshot digest 和当前版本表，因此 replay 可验证当时 adapter 可见的应用状态。
