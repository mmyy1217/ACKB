# AscendC 与 CCE Dialect 索引

本轮在既有 CCEC / PTX 之外增加两个独立来源体系。它们帮助理解同一目标上的不同抽象层，不构成四套硬件 ISA，也不证明跨层一一对应。执行命令集中于根目录 AGENTS.md。

## 来源与层级

| 体系 | 列表身份 | 来源 |
| --- | --- | --- |
| AscendC basic | 命名空间分组与函数名；当前 617 组 | 固定 CANN weekly 的 basic_api、寄存器接口、SIMT C++ 接口及选定实现 |
| AscendC capi | C / SIMT 函数名；当前 1,876 组 | c_api、simt_api 与 reg_base_impl / experimental / SIMT 实现 |
| CCE Dialect ops | TableGen 定义的语义 Op；247 项 | CCEDialect 的 CCEOps.td / CCESIMTOps.td |
| CCE Dialect intrinsics | 静态映射表出现的完整 llvm.hivm.* 符号；1,069 项 | CCEIntrinsicMap.td / CCESIMTIntrinsicMap.td，附关联 cce.intr.* 定义 |

AscendC 扫描 373 个头文件，370 个文件的哈希与已有原包核验快照相符；其余 3 个只记录本地文件哈希，不声称原包已核验。版本固定为 9.3.0~weekly.20261104.01。Dialect 扫描 17 个源码及文档文件，保留 Git commit、工作区是否有修改及逐文件哈希；实际内容以哈希为准。两个数据文件同时绑定生成器与 CCEC catalog 哈希，陈旧快照会拒绝构建。

这些是有界静态提取，不是 AscendC 全部 API 或 LLVM intrinsic 全集。函数解析器不是完整 C++ 前端；命名空间部分按来源目录推断，宏生成函数与任意模板语义尚未全面求值。具体 TableGen 映射行保存原始来源，语义 Op 与映射键的关联另标为候选。

## 950 条件的含义

目标固定 Huawei Ascend 950PR_9579，条件环境只提供 `__NPU_ARCH__=3510`，不猜测其他架构宏等价。逐来源保留完整预处理条件，包括已识别的头文件保护宏；仅在发现成对 `#ifndef` / `#define` 的头文件保护时忽略其判定影响。

- basic：聚合声明的局部条件。至少一条符合为 matches；全部排除为 excluded；否则 unknown。
- capi：声明全部排除时为 excluded；至少一个声明与至少一个候选实现的局部条件分别符合时为 matches；否则 unknown。声明和实现的独立聚合另行保存，不能据此认定每个重载都有对应实现。
- 不按目录名或“存在函数体”宣布 950 已实现；未找到目标实现也不直接认定不支持。
- matches 不证明 include 路径可达、C++ 重载可用、核环境满足或设备支持。编译、运行、性能均未验证。

当前 basic 为 491 符合 / 4 未知 / 122 排除；capi 为 1,304 符合 / 552 未知 / 20 排除。与旧分支不同，9201/9202 专属的 FP4 等实现不会被函数体存在这一事实提升为 3510 符合。所有声明形式及其独立条件仍可阅读。

## 参数与关联的完整性

数据库和离线页面保留全部词法声明形式及同形式的所有来源，不进行 24/12 项裁切。例如 asc_cast 的 467 种形式全部保留；这里的形式数不是经 C++ 类型系统归一化的重载数。网页选择写入深链接，导出保留全部形式、条件、文件哈希与限制。

AscendC 到 CCEC 的关系来自函数名与词法引用，候选实现关联还使用名称后缀及有限深度遍历；未完成命名空间、模板、重载和控制流解析。`ccec_candidate_op_ids` 与 `resolution=lexical_name_candidate` 明确标为候选，不当作已证实调用边。Dialect 到 CCEC 的名称归一化同样只是候选，不是编译器 CodeGen 映射证据。页面不再给出缺少可复算口径的 42.5% 调用比例。

分类来自本仓库的文件名和名称启发式规则，不是官方硬件分类；不再将所有 Fixpipe 统一断言为 L0C→GM。

## 具体 intrinsic 与待解析条目

1,069 个 LLVM 符号都实际出现在静态 TableGen 映射行中。另有 5 个 `cce.intr.*` 条目没有静态映射，放在 `unresolved_lowerings`，在覆盖页和 CLI 独立提供；不为它们编造含 `<dtype>` 的 LLVM 名称，也不将运行时打印函数计作 intrinsic。这不表示它们没有动态翻译实现。

## AI 查询契约

两个新后端使用 `ackb.multi-backend.query.v1`，对应 `schemas/multi-backend-query-v1.schema.json`；既有 CCEC / PTX 查询不变。`--data` 支持索引文件或目录，读取后核验快照。未支持的筛选或不同芯片请求会明确报错。

`search` 提供摘要；`get` 提供元数据及参数/证据分页入口；AscendC `forms` 分页读取全部声明形式；`relations` 输出候选边和实现来源；`evidence` 按摘录行分页并附源文件哈希，摘录行序号不冒充原文件行号；Dialect `unresolved` 列出未建立静态映射的 MLIR Op。响应带来源、验证状态与限制。单条超预算时返回错误，不截断为假完整结果。
