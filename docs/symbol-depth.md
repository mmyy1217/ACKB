# 点号展开与 NVIDIA 符号索引

PTX、Huawei Ascend LLVM IR 与 NVVM IR 共用纯符号展开控件。默认全部展开。只按 `.` 分段，保留原始顺序、大小写和下划线，不分析语义。先对该数据库完整列表计算最长公共段前缀（至少保留一个可展示段），滑块从下一段开始。搜索、指令族和来源筛选不改变此前缀。名称不足当前深度时原样保留；同前缀聚合行的详情可选成员。

数量区分当前符号组与底层记录；相同完整拼写在不同手册条目出现时，列表归为一组，来源记录不丢失。聚合组不继承某个成员的支持结论。`depth` URL 参数保存层级；省略为全部展开。滑块仅影响列表，JSON 导出仍保留完整记录。

## PTX

`data/ptx/forms.json` 由固定哈希 PTX ISA 9.4 原文及现有语法快照提取。当前包含 1,057 条形式／保留条目记录、1,033 个不同拼写。来源包括官方 Examples 中完整拼写，以及有界的整数、扩展精度和浮点算术语法展开；排除 64 位 wide 乘法。没有枚举出来的条目保留原名，不静默删除。

这不是所有合法参数组合的穷举。`coverage` 对每个原始指令条目报告形式数；复杂组合完整语法保留在详情中。目标筛选沿用原始条目的文档条件，形式行明确标注需逐项核对，不能据此称该形式已在 B300 验证。默认入口改为指令族列表，教程不再是导航入口；旧学习数据及深链接保留。

```sh
python scripts/ptx_forms.py --html /path/to/pinned/ptx-isa-13.4.3-index.html
```

## NVVM

`data/nvvm/index.json` 来自固定 CUDA 13.4.3 官方 NVVM IR 规范 HTML。保存 SHA-256、章节锚点、HTML 行号、原始声明行和稳定 ID。287 个名称记录中，带 `<n>` 等占位符的泛型名称原样保留并标注模板，不截断成假的具体符号，也不推测全部类型实例。指令族来自官方章节标题。

范围限定为该规范代码块中的函数符号；不是 libNVVM 的全部注册表，不保证覆盖 LLVM NVPTX 后端的全部扩展。此版本规范区分 LLVM 7 与现代 LLVM dialect，当前索引未逐项判定两者或 B300 的支持，界面明确保持未验证。

```sh
python scripts/nvvm_index.py extract --html /path/to/nvvm-ir-spec-13.4.3.html
python scripts/nvvm_index.py validate
python scripts/query.py --backend nvvm info
python scripts/query.py --backend nvvm search --name barrier
python scripts/query.py --backend nvvm get llvm.nvvm.barrier0
```

构建、独立数据库下载／更新与离线单文件均包含 NVVM。来源：[官方 NVVM IR 规范](https://docs.nvidia.com/cuda/archive/13.4.3/nvvm-ir-spec/index.html)。

## 验证

`node tests/symbol-depth.cjs` 验证公共前缀、短名称、筛选前缀稳定性与默认全展开。`tests/test_symbol_sources.py` 验证提取边界；`tests/knowledge-browser.cjs` 覆盖三库滑块、成员选择、搜索、深链接、窄屏和离线无网络请求。线上下载回归仍由 `npm run test:site` 执行。
