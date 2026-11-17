<h1 align="center">ACKB</h1>

<p align="center"><strong>AI Compiler Knowledge Base</strong></p>
<p align="center">面向 AI as Compiler 的底层目标知识库 · CCEC / PTX</p>
<p align="center"><a href="https://mmyy1217.github.io/ACKB/">在线阅读</a> · <a href="docs/knowledge.md">知识索引</a> · <a href="docs/ai-entry.md">AI 入口</a> · <a href="docs/scope.md">范围与证据</a> · <a href="docs/roadmap.md">路线</a> · <a href="AGENTS.md">开发入口</a></p>

---

AI 直接生成底层代码，需要知道目标的执行模型、地址空间、接口、架构条件与约束。ACKB 为这个过程提供可查询、有来源的知识和验证入口。以 Huawei Ascend LLVM IR 目标层为核心，向上追踪 CCEC / AscendC / CCE Dialect，并独立建立 PTX；先分别建立知识库，再研究两者的设计逻辑与差异。

## 当前覆盖

| 后端 | 索引范围 | 深度补充 |
| --- | --- | --- |
| LLVM IR 核心 | 12,363 个包内注册名称；535 种 Bitcode 声明类型；12 个来源文件已核对原包 | 950 包内调用证据、类型选择、工具链差异、跨层关联与显式未知项 |
| CCEC | CANN 9.3.0 weekly：23 个头文件、5,714 条接口记录、4,353 个唯一 builtin 身份 | 8 个主题：执行、存储、搬运、同步、类型、计算、生命周期、控制 |
| AscendC | 395 个头文件：617 个 basic 分组、1,876 个底层接口分组 | 全部声明形式、局部架构条件、候选 CCEC 关联 |
| CCE Dialect | 247 个语义 Op、1,069 个具体 LLVM intrinsic | TableGen 映射、规格说明；5 个未建立静态映射的条目单列 |
| PTX | ISA 9.4：743 个章节、221 个指令条目、39 个伪指令、35 个特殊寄存器 | 7 个学习层次、15 篇中文主题、3 份教学 kernel；221 条指令的官方语法 |

CCEC 保留完整签名、重载、原始条件、宏来源与 29 个待处理项；23 个扫描头文件已与原包逐字节匹配。主要目标为 `Ascend950PR_9579`，同时保留 74 个芯片配置的条件证据。新增 1,608 个与原包一致的 AscendC 文件，形成 5,714 条接口 × 14 个架构的静态证据矩阵，可追踪架构分支、核保护及缺失宏；这仍不是经过编译验证的支持清单。

PTX 固定官方手册版本与哈希，当前主目标为 NVIDIA B300（CC 10.3），分别核对 `sm_103`、`sm_103f`、`sm_103a`，默认 `sm_103a`。从执行模型、存储、基本指令、协作、矩阵到完整程序建立理解；历史 `sm_89` 快照保留用于追溯。条目不是全部语法变体的数量，文档支持不等于设备验证。

## 人与 AI 共用的入口

原生离线 HTML 手册保留黑白高密度列表、可调左右栏、连续加载、全结果进度轨道、架构筛选和 JSON 导出。首页提供文字层级图和数据库入口。当前网页支持 **LLVM IR / CCEC / AscendC / CCE Dialect / PTX**，可直接[在线阅读](https://mmyy1217.github.io/ACKB/)。PTX 以正文为中心，术语与代码旁的指令可在侧栏随手查；按 [开发入口](AGENTS.md) 构建后打开 `dist/index.html`。

在线版首页仅约 0.20 MB（含代码和样式），数据库按需压缩加载。页面与数据分别缓存，更新时只重新下载发生变化的资源；单文件离线版继续保留。详见 [加载与更新](docs/loading.md)。

统一 JSON CLI 提供 `--backend llvm|ccec|ascendc|cce-dialect|ptx`、分页搜索、主题、关联和证据查询。CCEC 原有声明协议保持兼容；新增知识查询带来源哈希、未知项和验证状态。先读 [AI 使用入口](docs/ai-entry.md)，无需将整份数据库塞入上下文。

LLVM 核心默认聚焦 A5 来源，注册范围与 950 支持严格分开。120 项厂商类型编码未解析，16 种模块签名含未知类型；完整边界见 [LLVM 核心](docs/llvm-core.md)。

## 证据边界

“全面索引”始终限定来源版本和文件范围：CCEC 头文件引用不等于编译器内部 builtin 全集，PTX 章节索引不等于所有变体的完整调用规范。当前编译、运行、性能实验均未开展；跨版本弃用历史、参数与同步语义深挖、两端对比仍在建设中。

仓库负责知识与验证工具；AI 代码生成和优化循环属于使用方。不会把 CCEC 编程接口、PTX 虚拟 ISA 与硬件机器指令假定为一一对应。

CCEC 页面固定 **950 / A5**，提供 **CCEC 编程接口 / CCEC Builtins** 两层。默认阅读 368 个声明条件符合的调用接口（357 个封装及 11 个已追踪的搬运直连入口），191 个待确认接口可按需显示；底层 builtin 保持唯一身份，原始来源完整保留。声明条件符合不等于设备验证；详见 [层级模型](docs/ccec-ops.md)。

AscendC 与 CCE Dialect 的跨层关联标明候选性质，不能代替重载解析或语义等价证明；详见 [扩展索引与证据边界](docs/ascendc-dialect.md)。

LLVM 默认显示 522 个有 c310 模块直接调用的名称，完整保留 308,558 个调用位置。A5 名称线索及外部映射可单独切换；静态模块证据不等于目标编译或运行验证，详见 [950 判定](docs/llvm-core.md)。
