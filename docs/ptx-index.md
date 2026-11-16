# PTX ISA 9.4 索引

这份索引覆盖 PTX，现已接入统一 `scripts/query.py --backend ptx` 入口；原有 CCEC 声明数据与页面行为保持兼容。PTX ISA 版本与查询目标不是同一个编号：手册是 PTX ISA 9.4，当前默认查询目标是 B300 / `sm_103a`。本文下列 sm_89 计数和规则描述历史原始快照；当前阅读层与目标评估见 [PTX 阅读层](ptx-learning.md)。

## 钉住的来源

全文快照在仓库外：`/home/zuomin/Projects/Compiler/work/experiments/ackb/ptx-index/source/`。原始索引保留锚点、短标题、助记符、结构化目标和哈希；新增 `syntax.json` 提取功能性语法，`learning.json` 保存原创解释，完整手册正文仍在仓库外。

| 文件 | 作用 | URL | 字节 | SHA-256 |
| --- | --- | --- | --- | --- |
| `ptx-isa-13.4.3-index.html` | 抽取用的单页手册，锚点来源 | https://docs.nvidia.com/cuda/archive/13.4.3/parallel-thread-execution/index.html | 3928317 | `f1e14ad07468e26bf3724e41be86f3a68ab7914bcf0fc9824a6ad31a1eb2ec26` |
| `ptx_isa_9.4.pdf` | 同一归档的 PDF。标题页为 PTX ISA Release 9.4，NVIDIA Corporation，Oct 12, 2026。抽取器只核对 `%PDF-` 与哈希 | https://docs.nvidia.com/cuda/archive/13.4.3/pdf/ptx_isa_9.4.pdf | 31078744 | `3851871026ca5bc81d85189cd3a70a2f9a9a4bb32208d927b3f0cd03c7b16e4e` |
| `cuda-gpus.md` | 官方 GPU 表的 Markdown | https://developer.nvidia.com/cuda/gpus.md （页面 https://developer.nvidia.com/cuda/gpus ） | 2604 | `864921385310f9ce7d9911db863aa75286e590e8658b502b0aff28a74ffc03b7` |
| `ada-tuning-guide-13.4.3.html` | Ada 定义为计算能力 8.9 | https://docs.nvidia.com/cuda/archive/13.4.3/ada-tuning-guide/index.html | 22758 | `e86ba37e8db39f8863bc555572632d02280215f2e6f5cbbf3acd4685b70f1fcc` |
| `cuda-platform-13.4.3.html` | CC X.Y 对应 SM 版本；例子是 CC 12.0 与 `sm_120` | https://docs.nvidia.com/cuda/archive/13.4.3/cuda-programming-guide/01-introduction/cuda-platform.html#compute-capability-and-streaming-multiprocessor-versions | 43874 | `d65e5ba5b1ed1e559f16839c437ec81d715f60a14c18cdf1a76d638bd0d5fd2a` |

CUDA 文档归档 13.4.3 是同时提供这份 HTML 和 `ptx_isa_9.4.pdf` 的版本。HTML 标题是 “1. Introduction — PTX ISA 9.4 documentation”。发布史表在手册第 13 章，表锚点 `release-notes-ptx-release-history`：PTX ISA 7.8（CUDA 11.8, driver r520）首次列入 `sm_89`，PTX ISA 9.4（CUDA 13.4, driver r615）的目标列表仍包含 `sm_89`。共 47 行版本记录。

官方 GPU 表的计算能力 8.9 行写有 GeForce RTX 4080，没有 RTX 4080 Laptop。Ada Tuning Guide 把 NVIDIA Ada 定义为计算能力 8.9。把 8.9 写成 `sm_89` 用的是编程指南的命名规则，不是对这张笔记本 SKU 的设备查询。`names_rtx_4080_laptop` 保持 false。

## 仓库里的文件

`data/ptx/` 由 `scripts/ptx_index.py` 写出，协议名 `ptx-index.v1`，提取器修订 `1`。

| 文件 | 内容 |
| --- | --- |
| `source.json` | 版本、URL、哈希、发布史中的 7.8 与 9.4 行、SKU 证据、判断规则与限制 |
| `scan.json` | 扫描范围、分类计数、`sm_89` 支持计数、未解析计数 |
| `sections.json` | 743 个 `section id` 的锚点、章节号、标题、种类 |
| `instructions.json` | 第 9.7 章里带 Syntax 或 Target ISA Notes 的 221 条指令 |
| `execution.json` | 执行模型 63 节 + 状态空间 14 节。只保留锚点与 rubric 名，`text_stored` 为 false |
| `directives.json` | 带 Syntax、PTX ISA Notes 或 Target ISA Notes 的 39 条指令性伪指令 |
| `special_registers.json` | 同样标准下的 35 个特殊寄存器 |
| `notes.json` | 四条中文深度笔记 |

指令身份是 `ptx_` 加 `{anchor, isa: 9.4, section}` 的 SHA-256 前 24 位，不使用文件偏移。Syntax 与 Description 只存 SHA-256、行数或字符数。

## 重建与检查

提取、校验与测试命令集中在 [AGENTS.md](../AGENTS.md)。

`extract` 拒绝与上表哈希不一致的输入。不下载、不调用编译器、不访问设备。

## 这次扫描

743 个 HTML section 全部分类，各类之和为 743。

| 种类 | 数量 |
| --- | --- |
| instruction | 221 |
| instruction_topic | 229 |
| execution_model | 63 |
| state_space | 14 |
| special_register | 35 |
| special_register_topic | 1 |
| directive | 39 |
| directive_topic | 10 |
| introduction | 5 |
| release_note | 42 |
| notice | 4 |
| other | 80 |

带目标说明的记录共 295 条（221 条指令 + 39 条伪指令 + 35 个特殊寄存器）。`sm_89` 支持：

| 状态 | 指令 | 全部带注记录 |
| --- | --- | --- |
| documented_supported | 110 | 171 |
| documented_not_supported | 71 | 83 |
| partial | 40 | 41 |
| unknown | 0 | 0 |

Target ISA Notes 的未解析块为 0。PTX ISA Notes 有 2 句只保留 SHA-256：`mov`（9.7.10.3）里关于 kernel 函数地址使用场合的限制，以及 `cvta`（9.7.10.23）里关于 generic 指针与 const 的实现限制。这两句不参与 `sm_89` 判断。

## `sm_89` 怎么判断

规则编号是 `explicit_target_note_plus_numeric_cc_order`。只读 Target ISA Notes，外加 PTX ISA Notes 里整条指令 “not supported … for .target sm_N or higher” 这种句子。

- “supported on all target architectures” 只有在 ISA 9.4 的发布史目标列表含有 `sm_89` 时才算支持。
- 不带后缀的 “sm_N or higher” 按计算能力数值比较。两位的 `sm_89` 是 major 8、minor 9；三位及以上用除最后一位以外的数字做 major。
- “or higher in the same family” 要求 major、后缀都相同，且 minor 不低于下限。
- `sm_90a`、`sm_100f` 这类带后缀的目标不会被 `sm_89` 满足。
- 同一主题上，较晚的 “not supported on sm_N or higher” 覆盖更早的最低版本要求。`shfl` 因此对 `sm_89` 是 documented_not_supported。
- 不同形式结论不一致时为 partial。整数 `add`、`membar`/`fence`、`mma`、`cvt` 都是 partial。
- 性能注释、advisory，以及只约束 `sm_1x` 的句子，不把 `sm_89` 判成不支持。
- 纯交叉引用会阻止把正面结论升成 documented_supported。
- 没有 Target ISA Notes 时为 unknown。这一版手册里，进入指令、伪指令和特殊寄存器表的条目都解析出了目标句，所以 unknown 的计数是 0，不是省略。

编译、运行、性能都是 `unverified`。`experiments` 为空。没有在 RTX 4080 Laptop 上跑过指令。

若干已核对的边界：`bar.warp.sync` 的句子是 sm_30 或更高，数值比较覆盖 `sm_89`；`barrier.cluster` 与 `wgmma` 的句子分别是 sm_90 或更高、`sm_90a`，不覆盖 `sm_89`；`tcgen05.mma` 的目标在 sm_100 一代，不覆盖 `sm_89`；`mma` 的 e4m3/e5m2 写明 sm_89 或更高，f64 的 m16n8k4/8/16 与 e2m1/e2m3/e3m2、`.kind` 等要求更高或带后缀的目标。

## 深度笔记

`notes.json` 有四条中文笔记，`depth` 为 selected。每条都带章节锚点和未知项。

| id | 主题 | 锚点 |
| --- | --- | --- |
| `note_execution_hierarchy` | grid、CTA、cluster、warp、SIMT、Independent Thread Scheduling | 2.2、2.2.1、2.2.2、3.1、3.2、9.5 |
| `note_state_spaces` | 状态空间名字、`.shared::cta` 与 `::cluster`、48KB 静态 shared | 5.1、5.1.1、5.1.7、2.2.2 |
| `note_synchronization` | `bar`、`bar.warp.sync`、`barrier.cluster`、`membar`/`fence`、`mbarrier.init` | 9.7.15.1、9.7.15.2、9.7.15.3、9.7.15.4、9.7.15.16.12、第 8 章 |
| `note_selected_instruction_constraints` | `mma`、`wgmma`、`tcgen05.mma`、`cvt` 与 ISA 9.4 发布表 | 9.7.16.5.14、9.7.17.5.2、9.7.18.10.10.1、9.7.10.24、1.3、13 |

cluster 只写明适用于 sm_90 或更高。第 8 章只作锚点，不改写内存一致性模型。笔记里的未知项包括：笔记本 SKU 未被 GPU 表点名、warp 宽度没有在这张卡上测量、`.shared::cluster` 没有编译实验、同步限定符不能收成一个布尔值。

## 已实现的查询契约

统一入口使用 `ackb.knowledge-query.v1`；字段、分页和身份规则见 [知识索引](knowledge.md)，执行命令见 [AGENTS.md](../AGENTS.md)。支持 info、targets、search、topics、get、relations、evidence 和 schema。

`get` 返回当前目标规则、官方语法、学习解释与主题关联，不返回手册全文描述；`evidence` 返回官方锚点和来源哈希。支持状态仅表示文档规则对本次所选目标的归类；原始文件里的 `sm_89` 是历史评估。

## 限制

- “or higher” 的数值比较是索引规则，不是设备运行结果。
- GPU 表没有 RTX 4080 Laptop 这一行。
- ISA 9.4 仍把 `sm_89` 列为可写目标，并不表示 9.4 新增的 `sm_107`、`tcgen05` 或其他高架构形式在 `sm_89` 上存在。
- 伪指令或特殊寄存器若缺少目标句，状态应为 unknown。本快照里这类缺失计数为 0。
- 编译、运行、性能未验证，实验数组为空。
- PTX 网页已接入全部索引与笔记；原有 CCEC 浏览与深链接保持兼容。
