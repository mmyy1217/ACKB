# ACKB 知识索引与查询契约

## 目标与来源

CCEC 与 PTX 分别建库，保留其抽象层差异。CCEC 是 ccec 接受的源码接口层，PTX 是虚拟 ISA；当前不提供两端等价转换。术语见 [CONTEXT](../CONTEXT.md)。

CCEC 原始记录位于版本化 catalog；`data/ccec/knowledge.json` 绑定其 SHA-256，新增 8 个头文件表面主题和 2,222 个 builtin 名称引用。引用中 2 个没有可关联的解析记录，原始 catalog 的 29 个未解析项继续保留。主题包含来源、缺失种子和未知项，不凭名称补造硬件语义。

PTX 固定 ISA 9.4 / CUDA 文档归档 13.4.3。`data/ptx` 保存全部 743 个 HTML 章节目录，221 个指令条目、39 个伪指令、35 个特殊寄存器及 77 个执行模型/状态空间章节。全文描述不入库；`syntax.json` 保存 296 个官方语法块（覆盖 221 条指令），`learning.json` 保存 15 篇原创中文主题、术语与教学代码。旧 4 篇笔记快照保留用于追溯。来源与支持归类规则见 [PTX 索引](ptx-index.md)。

## 查询协议

命令集中在 [AGENTS.md](../AGENTS.md)。全局参数置于子命令前。

| 入口 | 行为 |
| --- | --- |
| 默认 CCEC 声明查询 | 保留 `cce-ops.query.v1`、原有记录/symbol/variant ID 与筛选语义 |
| CCEC topics / builtins / 对应 ID 查询 | 返回 `ackb.knowledge-query.v1` |
| `--backend ptx` | 返回 `ackb.knowledge-query.v1`；`--data` 可指定 PTX 索引目录 |
| topics | 分页列出重点笔记；get 读取正文及未知项 |
| search | PTX 默认仅 instruction；`--kind all` 搜索全部章节；query 匹配标题、助记符、锚点与章节号，`--name` 精确匹配助记符 |
| get | PTX 支持 entry_id、章节 anchor 或 learn_ 开头的学习主题 ID；CCEC 主题与 builtin 使用返回 ID |
| relations | 章节返回直接子章节；笔记返回引用章节；CCEC 主题/builtin 返回头文件记录引用 |
| evidence | 知识条目返回来源定位与哈希，原有 CCEC 记录仍返回提取文本 |

响应含 backend、version、provenance、limitations、verification，以及 total、offset、items、next_offset、truncated。结果预算沿用原 CLI，单个条目过大时返回错误，不截断成虚假完整条目。每项最多预览 3 条 evidence，完整引用通过 evidence 分页取得。

知识响应的信封规范见 [Schema](../schemas/knowledge-v1.schema.json)；异构条目由各数据文件定义，Schema 不保证硬件语义正确。PTX 的 schema 命令返回该规范；CCEC 默认 schema 仍返回旧声明协议。失败返回结构化错误和退出码 2。

PTX ID 绑定 ISA 版本、章节号与锚点，不保证跨版本稳定。CCEC 主题 ID 由主题键生成，builtin ID 由名称生成；原有词法签名身份不变。勿用 ID 推断两端语义等价。

## 支持与验证

PTX `--support` 仅筛选文档状态：documented_supported、documented_not_supported、partial、unknown。partial 表示条目内存在不同目标条件，不是所有形式都可用。`get` 的 target_isa / ptx_isa 保留具体形式与版本条件。CCEC 仍使用三值声明条件，不强行转换成 PTX 的支持分类。

当前主目标是 NVIDIA B300 / CC 10.3，默认 `sm_103a`。查询可选择 `sm_103`、`sm_103f`、`sm_103a`，也保留历史 `sm_89`。`target_assessment` 对应本次目标，不能读取原始快照里的 sm_89 字段充当 B300 结论。设备映射依据与哈希保存在 `device.json`；所有编译、运行和性能状态均未验证。

本机只读检查发现 nvcc 为 CUDA 12.9 / V12.9.86；这与文档归档 13.4.3 不同，不能推断本机编译器接受 PTX ISA 9.4。此环境观察不属于目标 GPU 实验，也不代表用户笔记本已安装该版本。

## 深度缺口

CCEC 还缺完整编译器 builtin 清单、核宏环境、每项参数单位/对齐/副作用、流水与同步语义及真实跨版本历史。PTX 还缺全部语法形式的结构化约束和逐形式目标判定。两边都缺编译/运行探针与性能证据。页面已接入 CCEC / PTX 双后端；全部已收录章节、规则和笔记可离线检索。手册正文仍通过官方链接阅读。

## PTX 阅读数据

学习层次是编辑组织，不是官方 ISA 分组，也不按 CCEC 单元对齐。每个主题有引用锚点、解释、示例、验证状态及单独折叠的比较提示。`topics` 枚举主题；`get` 返回正文或官方语法与示例；`relations` / `evidence` 可遍历其出处。中文逐操作数解释目前覆盖 16 个特定指令条目，其余条目明确提示待整理。详细边界见 [PTX 阅读层](ptx-learning.md)。
