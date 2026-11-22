# AscendC 与 CCE Dialect 索引

本轮在既有 CCEC / PTX 之外增加两个独立来源体系。它们帮助理解同一目标上的不同抽象层，不构成四套硬件 ISA，也不证明跨层一一对应。执行命令集中于根目录 AGENTS.md。

## 来源与层级

| 体系 | 列表身份 | 来源 |
| --- | --- | --- |
| AscendC basic | 命名空间分组与函数名；当前 617 组 | 固定 CANN weekly 的 basic_api、寄存器接口、SIMT C++ 接口及选定实现 |
| AscendC capi | C / SIMT 函数名；当前 1,876 组 | c_api、simt_api 与 reg_base_impl / experimental / SIMT 实现 |
| CCE Dialect ops | TableGen 定义的语义 Op；247 项 | CCEDialect 的 CCEOps.td / CCESIMTOps.td |
| CCE Dialect intrinsics | 网页收录 1,234 个源码可达的 LLVM 名称 | CCEIntrinsicMap.td / CCESIMTIntrinsicMap.td，附关联 cce.intr.* 定义 |

AscendC 扫描 395 个头文件，392 个文件的哈希与已有原包核验快照相符；其余 3 个只记录本地文件哈希，不声称原包已核验。版本固定为 9.3.0~weekly.20261104.01。Dialect 扫描 19 个源码及文档文件，保留 Git commit、工作区是否有修改及逐文件哈希；实际内容以哈希为准。两个数据文件同时绑定生成器与 CCEC catalog 哈希，陈旧快照会拒绝构建。

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

1,069 个名称来自 TableGen。补扫翻译器、FP8 适配和打印库的直接调用与动态规则后，按完整拼写去重为 1,433 个。CppNameRule 表示按翻译函数的分支组合得到的可能拼写，未证明高层入口可达或后端接受；窄类型原子操作在记录中标明上层 verifier 限制。SIMT 全局访存按输入位宽拼名，展开常见的 8/16/32/64 位，其他位宽保留为开放规则。另有 1 个 `cce.intr.print` 条目没有静态映射，放在 `unresolved_lowerings`，在覆盖页和 CLI 独立提供；不为它们编造含 `<dtype>` 的 LLVM 名称，也不将运行时打印函数计作 intrinsic。这不表示它们没有动态翻译实现。

## AI 查询契约

两个新后端使用 `ackb.multi-backend.query.v1`，对应 `schemas/multi-backend-query-v1.schema.json`；既有 CCEC / PTX 查询不变。`--data` 支持索引文件或目录，读取后核验快照。未支持的筛选或不同芯片请求会明确报错。

`search` 提供摘要；`get` 提供元数据及参数/证据分页入口；AscendC `forms` 分页读取全部声明形式；`relations` 输出候选边和实现来源；`evidence` 按摘录行分页并附源文件哈希，摘录行序号不冒充原文件行号；Dialect `unresolved` 列出未建立静态映射的 MLIR Op。响应带来源、验证状态与限制。单条超预算时返回错误，不截断为假完整结果。


## Reg 公共转发层与逐调用来源

寄存器接口额外扫描 `impl/basic_api/reg_compute/*.h` 的公共转发文件，保留原有 `reg_compute/dav_3510` 目标实现。例如 `LoadAlign` / `StoreAlign` 的声明位于 `include/basic_api/reg_compute/kernel_reg_compute_datacopy_intf.h`，定义在同名公共 `*_intf_impl.h`，两者分别调用 `DataCopyImpl(dstReg, srcAddr, …)` 和 `DataCopyImpl(dstAddr, srcReg, mask, …)`；目标候选分别落在 `dav_3510` 的 load / store 实现中，进而引用 `vlds/vld` 和 `vsts/vst` 等 CCEC 符号。

不能把同名 `DataCopyImpl` 的所有重载直接合并。此次跟踪按调用实参数量和直接参数绑定的 `__ubuf__` 地址空间排除明显矛盾候选，并排除局部 3510 条件明确为假的函数及调用点。未知条件保留，模板实参和 C++ 重载并未完整求值，最多沿 4 条 helper 边展开。`call_trace` 保存函数节点、每处调用的文件/行号/实参/原始条件，以及未找到兼容 helper 或达到深度限制的断点；网页可展开查看，CLI `relations` 分页输出并附调用文件与函数来源哈希。它不是完整 include 可达性证明，也不替代编译器的调用图。

这次补链不提升 CCEC builtin 的架构状态。`vldsx1_*`、`vstsx1_*` 各 34 个 builtin 只在调用处取得身份，仍缺明确入口声明，保持待确认。页面搜索在存在隐藏结果时显示数量，并允许一键启用“显示待确认”；已有可见名称组中的未知重载不重复计为隐藏条目。宽泛搜索 `vlds` 还会匹配 34 个 `vldsx2_*`（合计 68），`vsts` 还会匹配 3 个 `vstsx2_*`（合计 37），这些也保持待确认。

Dialect LLVM 列表的「来源」列列出映射或调用文件和关联的 MLIR 定义文件。列表支持名称搜索与指令族导航，来源以文本显示。四个低层入口 cce.intr.simt.load / store / atomic_rmw / atomic_cas 保留在具体记录的 mlir_intr_ops；访存映射的 name_pattern 描述 N 随元素位宽变化的拼名规则。

## 哪些入口能发出 LLVM 调用

固定 CCEDialect 提交 `5639e581`。默认列表有 1,234 个完整 LLVM 名称。每个名称至少有一个入口满足 Op 定义、已核对的 verifier 和翻译分支。详情给出入口、条件、定义位置和翻译位置。同名目标按名称计一次。本次从语义 Op 直接确认 916 个，从可独立编写的 `cce.intr.*` 入口确认 318 个。第二组的上层 memref 转换需要另外追踪。

例如 `llvm.hivm.atom.ADD.G.s16` 的上层原子 verifier 拒绝 i16，底层入口接受 GM 指针和 i16，能发出这个名字。详情分别标出语义入口与底层入口的条件。`llvm.hivm.atom.ADD.S.s16` 在两个入口都受到约束。另一个例子是 `cce.vrec`，源码通过广播常数和除法实现倒数，因此映射表中的原生 vrec 名称不能用于统计该分支的输出。

固定源码中的 1,433 个候选名称已全部判定。1,234 个有入口能生成同名 LLVM 调用，199 个在这个独立翻译驱动的统计范围内排除。普通 LLVM 指令单列于「说明 / 覆盖」及 CLI 的 `ordinary-lowerings`。

### 最后一批 294 个名称的复核

此前已有 989 项确认、150 项排除。使用上述提交构建独立的 `cce-translate`（主机 LLVM 22.0.0git，启用断言），逐项提供 MLIR 输入，检查实际 LLVM 调用、替代调用或翻译诊断。所有 294 项都做了主机翻译，也逐项核对了分支与入口约束。失败样例只用于复现源码中找到的限制。

| 该批次的唯一名称 | 生成目标调用 | 排除 |
|---|---:|---:|
| 向量查表 | 175 | 22 |
| VCVT 与 SIMT FP8 转换 | 50 | 10 |
| 按名称映射的访存、谓词与计算 | 11 | 0 |
| 同步、屏障与打印辅助函数 | 9 | 17 |
| 合计 | 245 | 49 |

22 个向量排除项包括 12 个被 `vdup` 改写成 `m` 形式的名称、6 个 LLVM 无法直接表示 FP8 结果的名称、4 个交错操作的 FP8 查表键不匹配。另有 10 个 SIMT 转换因 FP8 结果类型被拒绝，15 个非零屏障分支依赖独立驱动未注册的 `arith.constant`。两个打印名称可以随开关出现在注入的辅助函数内；空 kernel 也会出现相同调用，本仓源码缺少从用户打印入口连到它们的调用边。

六个可达的 SIMT FP8 输入转换发出了带 `x2` 的名称，实测 LLVM 实参是 `<256 x i8>` 字节载体。这里计数的是能发出的**确切符号名**。核对 CANN 是否接受其参数签名、950 后端是否能生成机器码，需要独立证据。[294 项 MLIR 输入、实际调用与诊断](../data/cce_dialect/translation-audit.json)
