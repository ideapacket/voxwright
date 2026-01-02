# 可复现性

- scenario、repair campaign、replay 和可选训练全部接收非负 seed；
- `SeedStream` 用 namespace、seed、counter 的 SHA-256 派生选择，不依赖全局 PRNG；
- runtime 使用 `LogicalClock`，输出中不读取 wall clock；
- canonical JSON 固定 key 顺序、分隔符和 UTF-8；集合在进入 codec 前排序；
- 浮点 metric 在产生点 `round(..., 6)`，不在 codec 层改变值；
- lock 文件固定 dev 与 CPU model 环境，CI 覆盖 Python 3.11/3.12/3.13；
- replay、report、SVG、manifest 与示例有 byte-equality 测试。

可选 PyTorch 路径使用 CPU tensor 和显式 seed。PyTorch 官方的
[Reproducibility 说明](https://docs.pytorch.org/docs/stable/notes/randomness.html)指出，不同 release、
平台或 device 之间不保证完全相同；因此项目不把随机初始权重的字节作为跨版本 golden，公共
metric 会量化，model artifact 记录实际参数。基础 mechanics 不依赖 PyTorch。

```bash
make test-all
make format-check
make typecheck
make build
```
