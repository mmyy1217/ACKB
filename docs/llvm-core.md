# LLVM IR 目标核心

ACKB 以 Huawei Ascend 的 LLVM IR 目标能力层为核心，向上关联 CCEC Builtins 与外部 CCE Dialect。它是 CANN 可观测的编译器表示层，不是硬件机器指令全集。当前来源固定为 `9.3.0~weekly.20261104.01`，主关注目标为 950 / A5。

## 这次取得了什么

| 范围 | 实测结果 | 能证明什么 |
| --- | ---: | --- |
| `libbisheng-llc.so` 的 `IntrinsicNameTable` | 23,447 个全目标注册项，其中 12,363 个 `llvm.hivm.*` | 此构建注册了这些名称；不证明 950 接受每一项 |
| `hivmc-a5` 名称扫描 | 918 个精确拼写 | A5 工具中出现过名称；不是注册、类型或支持证明 |
| `ccec` + `libbisheng-llc.so` 名称扫描 | 12,376 个 | 与 A5 工具交集 757；仅 A5 161；仅 CCEC / LLC 11,619 |
| 8 个 `meta_op.*.c310.{O0,O2}.bc` + `malloc.bc` | 535 种去重具体声明类型；487 个目标名称有 c310 声明 | 这些模块内存在函数声明或定义的类型；不证明实际调用、运行或全目标适用 |

完整快照包括 12,737 个目标名称和 36 个标准 LLVM intrinsic 名称。「950 包内证据」为 522 条（487 个目标 intrinsic、35 个标准 intrinsic），均在 c310 模块中有直接调用。网页默认打开「A5 相关线索」，共 1,136 条。列表第二列可筛选来源，相邻列表头之间可拖动调整宽度；**这些数字都不是经过目标编译或运行验证的指令数**。默认隐藏 全部范围中的 168 个仅字符串候选；全部范围可查看其他跨架构注册项。页面、CLI 的筛选口径相同。

12 个实际读取的 CANN 文件（三个编译器文件、九个 Bitcode）已通过流式读取外层与内层 Makeself / tar 归档核对 SHA-256，不执行安装脚本。每个来源保留包成员路径、内层包哈希、外层包哈希。外部 Dialect 只在包内名称集合固定后按名称建立导航关系，不参与入库、分类、类型或 A5 判定。

## 取得方式与边界

`scripts/llvm_sources.py` 只读解析 ELF64 little-endian 节、符号与相对重定位，取得名称表、IIT 类型表、长编码表及重载位表。完整名称原样作为身份；注册序号仅用于这个构建的证据定位，不作稳定 ID。名称表、类型表长度与哨兵均核验。没有反汇编机器码，也没有恢复硬件 ISA。

IIT 按 [LLVM 15.0.5 的 Intrinsic 类型编码](https://github.com/llvm/llvm-project/blob/llvmorg-15.0.5/llvm/lib/IR/Function.cpp)解释，保留原始整数、字节数组、ELF 偏移和文件哈希。`T(arg_info=N)` 保留 LLVM 的重载约束编码，不是 C/C++ 形参名；`ptr(as=N, element=...)` 是编码约束。具体签名要优先看 Bitcode 的类型形式。120 个厂商描述符无法按此格式解释，显式保留 `unparsed_vendor_encoding`；不会补造完整签名或参数数量。

普通 LLVM 15 / 18 / 20 读取器不能直接读取这些厂商 Bitcode（曾报告 `Invalid value`）。现采用标准库位流容器解析：校验块长、缩略码、VBR、字符串表、模块函数记录和类型表。模块类型解析与新增直接调用解析分开：后者按 LLVM 15 相对 value ID、函数类型、返回值及参数数目解析函数体，保留调用者、模块、精确类型形式和 bit 偏移；不恢复 debug 参数名。16 种签名包含未解释的厂商类型码，以 `UNRESOLVED_TYPE_*` 保留，标记 `partial_vendor_types`；原类型码与操作数保存于来源元数据。其余具体类型没有因此丢弃。

本轮没有执行本地 CCEC / hivmc 编译器、没有 LLVM JIT，也没有设备实验。未来合法 lowering 样例只能作为新增独立证据；MLIR LLVM dialect 输出不能直接标作 LLVM IR 验证。

## 数据模型

数据位置：`data/llvm/9.3.0~weekly.20261104.01/index.json`。日常 build / query 只消费已提交快照，不依赖 CANN 安装。

- `sources`：按来源 ID 唯一保存相对路径、哈希、原包核对状态。
- `ops`：按精确名称 + domain 生成稳定 ID。目标 intrinsic 与标准 intrinsic 分域；不擅自剥离类型后缀，也不把不同模式强并为一个 op。
- `forms`：独立、完整的类型形式。`registry_constraints` 是注册约束；`observed_signature` 是具体模块类型，后者仍可能含未解析厂商类型。不能把约束数当成已验证重载数。
- 原始库的 `relations` 只含包内名称关系。网页导航与 CLI 的 relations/gaps 查询在读取两个独立索引后再连接外部记录。`exact_llvm_symbol` 表示同一 LLVM 拼写；`dialect_mapping` 保留原映射中间节点；`naming_candidate` 只表示 CCEC 名称候选；`overload_name_candidate` 连接候选基名，绝不用于身份归并。
- `scans` / `coverage`：扫描方法、成功 / 失败、覆盖与集合差。失败不删除，不当成空扫描。

身份、签名、目标与实验分别记录。`identity_status=registered` 不推出 `target_status`；`c310_module_declaration` 也不是“950 已验证支持”。所有编译、运行、性能状态仍为 `unverified`。

`presence` 的三态为 `observed`、`scanned_absent`、`not_scanned`。例如工具名称正则只扫描 `llvm.hivm.*` / `llvm.cce.*`，不能把未扫描的标准 LLVM intrinsic 记成不存在。没有上游映射只能叫索引缺口，不能叫“没有公开 API 的隐藏硬件能力”。

地址空间以包内 Bitcode 具体签名中的 `ptr addrspace(N)` 为准。

## AI 查询契约

命令入口见 [AGENTS.md](../AGENTS.md)。`--backend llvm` 返回 `ackb.llvm.query.v1`，使用既有 `--offset` / `--limit` / `--max-chars` 分页边界；`schema` 返回 [Schema](../schemas/llvm-ir-v1.schema.json)，其中也定义查询 envelope。

| 操作 | 返回内容 |
| --- | --- |
| `info` | 来源、覆盖、扫描状态、原包核对与限制 |
| `search` | 简要身份、形式 ID、目标证据；默认 `a5-evidence` 且不含字符串候选 |
| `get` | 单条身份及 forms / relations / evidence 查询入口 |
| `forms` | 分页完整类型形式，含来源哈希与偏移 |
| `evidence` | 分页来源证据，不丢原始位置 |
| `unresolved` | 分页查询无法解析的调用者、位置、原因和来源 |
| `calls` | 按 op 分页读取 c310 直接调用，带精确类型形式、调用者、核模块、bit 偏移和来源哈希 |
| `relations` | 入边和出边，候选性质及中间节点完整保留 |
| `gaps` | 无 CCEC 映射、无可读类型、无 c310 声明、仅 A5 名称；均为知识缺口 |

搜索支持 `--scope a5-evidence|a5-sources|all`、`--include-candidates`、`--domain`、`--source`、`--evidence-kind`。来源 ID 可从 `info` 取得；不将旧 CCEC 的宏条件筛选错误套在 LLVM 证据上。既有后端 ID、原查询协议和深链接不变。

## 网页与离线交付

无 fragment 或 `#home` 打开首页，显示文字拓扑和八个数据库链接。`#backend=llvm` 打开 LLVM 核心，旧 `#layer=interfaces` / `#layer=intrinsics` 等链接仍有效。左侧保持大类；顶栏提供域、文件、范围、证据和候选筛选，右侧选择具体类型形式、查看来源矩阵与跨层关联。来源证据不依赖联网。

离线构建将 LLVM 表按列无损压紧，在浏览器恢复普通对象；不删除证据，也不需要 CDN、解压库或网络。导出的 JSON 恢复完整字段、当前记录相关的形式和来源闭包。首页和索引都沿用黑白高密度样式；桌面两栏可调，结果连续加载并显示全结果进度。

## 后续独立证据

仍可继续补充厂商类型描述符解释、间接调用解析、正式 builtin → LLVM lowering、逐目标接受性与运行测试。现阶段不能保证每一项的 950 支持、参数语义、内存效果或弃用历史已经确定。以上未知项不会阻断已取得的正式注册身份和具体模块类型查询。


## 950 / A5 静态判定（2026-11-16）

固定目标来自本地 CANN `Ascend950PR_9579.ini`：`NpuArch=3510`、`AIC-C-310`、`dav-c310-cube/vec`。该配置文件独立记录 SHA-256，原包比较仍标未核验；八个 c310 模块已核对原包。内部 `c310` 不是 Ascend 310 产品型号；本结果不自动覆盖每个 A5 产品。

新增 `static_target` 与旧 `target_status` 并存，旧字段保持兼容。身份、静态目标依据、实验仍是独立维度：

| 静态状态 | 含义 |
| --- | --- |
| `c310_direct_call` | 具体形式在 c310 模块的函数体内有已解析的直接调用 |
| `c310_declaration` | 模块有声明，尚无已解析调用；本次没有剩余项 |
| `a5_name_only` | A5 工具中出现名称，缺少 c310 模块依据 |
| `cross_arch_registry` | 跨架构编译器注册，缺少更强目标依据 |

八个模块共记录 308,558 个直接 intrinsic 调用位置，涉及 522 个精确 LLVM 名称；6,250 个间接或常量表达式调用未解析，保留调用者、偏移及原因。没有从间接调用猜测目标。未知函数记录或类型 / 参数数目冲突会丢弃该函数整段推断并报告，避免 value ID 偏移后产生错误关联。没有证明入口可达性、执行条件、参数取值约束或设备支持；AIC/AIV/mix 仅说明调用所在模块，不据此排除其他核。

源码核对范围为包内 bishengir / bisheng_compiler 的 h/hpp/td/cpp/json/ini 中 LLVM 名称字面量。只找到 builtin_vars 中的 IR 示例注释，未取得可逐项判定合法性的目标表；此扫描不能排除动态构造名称或未公开的 lowering 实现。CCEC 头文件条件、候选名称映射、外部 Dialect 均不传递为 LLVM 的支持或排除结论。当前没有具备充分证据的明确排除项，`support` / `exclusion` 均保持 `not_established`。

`a5_call_table` 用共享调用者 / 形式 / 来源字典与四整数行无损保存全部位置；CLI 解码为普通调用记录；网页 JSON 导出附带所选 op 的调用行及解码字典。网页只渲染当前形式的前 25 个位置，点击继续显示。普通构建不重新扫描 Bitcode；重新提取会重建调用与源哈希，网页按既有内容哈希缓存机制更新。

解析依据为 [LLVM 15 BitcodeReader](https://github.com/llvm/llvm-project/blob/llvmorg-15.0.5/llvm/lib/Bitcode/Reader/BitcodeReader.cpp) 与 [LLVMBitCodes](https://github.com/llvm/llvm-project/blob/llvmorg-15.0.5/llvm/include/llvm/Bitcode/LLVMBitCodes.h)。这些资料解释编码，不充当 Huawei Ascend 的目标支持规范。
