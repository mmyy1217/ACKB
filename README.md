<h1 align="center">ACKB</h1>

<p align="center"><strong>AI Compiler Knowledge Base</strong></p>
<p align="center">面向 AI as Compiler 的目标知识库 · Huawei Ascend 950 / A5 与 NVIDIA B300</p>
<p align="center"><a href="https://mmyy1217.github.io/ACKB/">打开知识库</a> · <a href="https://mmyy1217.github.io/ACKB/#insights">洞察</a> · <a href="docs/ai-entry.md">AI 查询入口</a> · <a href="AGENTS.md">开发与构建</a></p>

ACKB 帮助编译器开发者和 AI 回答三个问题：一个操作在哪一层表达？它有哪些签名和重载？哪些源码、IR 或编译记录能证明它在指定目标上的行为？首页按各自的编译体系组织了 Huawei Ascend 的八个入口和 NVIDIA 的两个入口。[查看编译体系图](https://mmyy1217.github.io/ACKB/)

## Huawei Ascend · 950 / A5

CANN 包内索引固定于 `9.3.0~weekly.20261104.01`，主目标为 `Ascend950PR_9579`（`NpuArch=3510`）。CCE Dialect 和 Issue 33 工作簿独立建库，各自保留来源和版本。

| 知识库 | 可以查什么 |
| --- | --- |
| [AscendC 基础 C++ API](https://mmyy1217.github.io/ACKB/#backend=ascendc&layer=basic) · [AscendC C / SIMT API](https://mmyy1217.github.io/ACKB/#backend=ascendc&layer=capi) | 617 个基础 C++ 接口分组、1,876 个 C / SIMT 接口分组。可查声明、重载和实现中追踪到的 CCEC 调用。 |
| [CCEC 编程接口](https://mmyy1217.github.io/ACKB/#layer=interfaces) · [CCEC Builtins](https://mmyy1217.github.io/ACKB/#layer=intrinsics) | 从开发者使用的接口追到具体的 `__builtin_cce_*`。950 默认显示 368 个声明条件符合的编程接口；跨架构头文件索引共识别 4,353 个唯一 builtin 名称。 |
| [LLVM IR](https://mmyy1217.github.io/ACKB/#backend=llvm) | 从 CANN 包内编译器注册信息、工具和 Bitcode 查名称、声明及直接调用。默认「A5 相关线索」覆盖 1,136 个名称，可按来源筛选。 |
| [A5 Intrinsic 定义](https://mmyy1217.github.io/ACKB/#backend=hivm-defs) | Issue 33 工作簿中的 1,977 个 `int_hivm_*` 定义名及签名。其中 994 项附有工作簿记录的 CANN 9.1.0 / CCEC 15.0.5 编译探针结果。 |
| [CCE Dialect 语义 Ops](https://mmyy1217.github.io/ACKB/#backend=cce-dialect&layer=ops) · [CCE Dialect LLVM Intrinsics](https://mmyy1217.github.io/ACKB/#backend=cce-dialect&layer=intrinsics) | 固定源码提交 `5639e581`，收录 247 个语义 Op。LLVM 入口列出经 Op 定义、校验条件和翻译分支核对后，源码可生成的 1,234 个 LLVM 名称。 |

例如，查 `vsstb` 时，工作簿给出泛型定义 `int_hivm_vsstb_post`，同一行的探针记录了具体调用 `llvm.hivm.vsstb.post.v64f32`。这解释了首页为何把两个入口放在同一虚线组内：一个提供定义和类型约束，另一个可以独立核对指定 CANN 包中观察到的 IR。[查看这条定义与探针记录](https://mmyy1217.github.io/ACKB/#backend=hivm-defs&r=def_int_hivm_vsstb_post)

## NVIDIA · NVVM IR 与 PTX

| 知识库 | 可以查什么 |
| --- | --- |
| [NVVM IR](https://mmyy1217.github.io/ACKB/#backend=nvvm) | CUDA 13.4.3 官方 NVVM IR 规范代码块中的 287 个名称记录，保留泛型占位符、声明及章节出处。 |
| [PTX 虚拟指令集](https://mmyy1217.github.io/ACKB/#backend=ptx) | 以 NVIDIA B300（默认 `sm_103a`）阅读 PTX ISA 9.4。按指令族检索 221 个手册指令条目及已索引的 1,033 种不同拼写，详情可查语法和目标条件。 |

PTX、NVVM IR 和 Huawei Ascend LLVM IR 都支持按点号调整名称展开深度，默认全部展开。滑块可用于观察同一前缀下的变体数量；合法类型和修饰符组合仍需查对应规范。[符号展开与收录规则](docs/symbol-depth.md)

## 跨库对照与使用方式

- **对照两侧名称**　「洞察」中的全量对应表把 1,136 个 CANN A5 线索名称与 1,234 个 Dialect 可生成名称对齐。可区分完整同名、重载基名对应及仅单侧收录，按指令族或来源筛选，也可下载 Excel。[打开全量对应表](https://mmyy1217.github.io/ACKB/#insight=llvm-full-alignment)
- **在线与离线阅读**　在线版可在首页入口旁下载或更新所选库，完成后进入。离线版将全部数据内嵌在单个 HTML 中，构建后直接打开 `dist/index.html`。[加载与更新](docs/loading.md) · [构建入口](AGENTS.md)
- **供 AI 查询**　仓库提供结构化数据与分页 JSON CLI，可按后端搜索名称，再按条目查签名、关联和可用证据。[数据目录](data/) · [AI 使用入口](docs/ai-entry.md) · [各库查询命令](AGENTS.md)

判断某个目标是否支持一条操作时，先看证据来自哪里。头文件条件说明声明何时可见，Dialect 翻译分支说明能生成什么 IR，包内 Bitcode 调用说明该形式实际出现过。编译探针只覆盖记录中的工具链、目标与具体签名；运行正确性和性能还需要独立实验。[LLVM 核心的证据口径](docs/llvm-core.md) · [CCE Dialect 的可达性判定](docs/ascendc-dialect.md)
