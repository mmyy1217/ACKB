# 分类与分组依据

本页说明当前 `9.3.0~weekly.20261104.01` 数据集的分类口径。分类由本仓库提取器生成，不能用来判定设备支持或硬件 opcode。

## 域：按来源头文件分组

页面“域”对应数据字段 `group`，是本项目的来源分组名称。提取器对源文件名按下表顺序检查，命中第一条即停止；不是从编译器查询到的设备域，也没有求值架构条件。

| 优先级 | 文件名规则 | 分组 |
| --- | --- | --- |
| 1 | 含 `legacy` | Legacy SIMD |
| 2 | 含 `simt` | SIMT |
| 3 | 含 `_ave` | Vector / AVE |
| 4 | 含 `types`、`defines`、`builtin_vars`、`runtime` 或 `dpp` | 配套定义 |
| 5 | 其他扫描文件 | AI Core |

例如 `__clang_cce_simt_fp8.h` 属于 SIMT，`__clang_cce_ave.h` 属于 Vector / AVE，`__clang_cce_aicore_functions.h` 走默认 AI Core 分支。`__clang_cce_simt_builtin_vars.h` 先命中 SIMT；不能将规则理解为所有类型或变量文件必然落在“配套定义”域。记录的接口、类型、宏等身份另外由 `kind` 保存。

实现见 [group_for](../scripts/catalog.py)。

## 指令族：按接口名称关键词归类

页面左栏与表格“指令族”对应 `family`。接口名先转小写并移除开头下划线，再依下表顺序取第一个匹配。除注明的前缀规则外，均为子串匹配；非接口记录的族统一为“配套定义”。

| 优先级 | 名称关键词 | 指令族 |
| --- | --- | --- |
| 1 | `copy`、`load2d`、`load3d`、`dma`、`mov_`、`load_cbuf`、`img2col` | 搬运 / DMA |
| 2 | `flag`、`barrier`、`sync`、`fence`、`wait`、`pipe` | 同步 / 流水 |
| 3 | `cvt`、`conv_`、`convert`、`dequant`、`quant`、`cast` | 类型转换 |
| 4 | `mad`、`mmad`、`matmul`、`gemm`、`winograd`、`mx` | 矩阵 / Cube |
| 5 | 含 `atomic`，或以 `atom_` 开头 | 原子操作 |
| 6 | `spr`、`ctrl`、`get_`、`set_`、`read_`、`write_` | 控制 / 寄存器 |
| 7 | `ld`、`st`、`gather`、`scatter`、`alloc`、`free`、`prefetch` | 访存 / 布局 |
| 8 | 未命中以上规则 | 计算 / 其他 |

这是便于导航的启发式分类，并非 Huawei Ascend 官方分类或已核对的语义分类。短关键词、规则顺序和默认分支可能造成误分；例如 `mx`、`ld`、`st` 的子串命中本身不足以证明操作语义。理解具体接口仍须核对原始声明、函数体和架构条件。

实现见 [family_for](../scripts/catalog.py)。

## 搬运路径：从明确名称提取

在“搬运 / DMA”下面增加路径入口，表格同一行显示 GM → UB、GM → L1、UB → GM 等。`gm` 显示为 GM、`ubuf` 为 UB、`cbuf` 为 L1；保留原始名称和端点拼写。只匹配明确的 `<源>_to_<目标>`，`copy_data`、`load2d` 等没有明确端点的名称不猜测路径。搜索支持 GM2UB、GM2L1 等别名。路径导航也包含名称明确的 gather / scatter；“搬运 / DMA”入口因此包含这些路径项，与原有“访存 / 布局”导航可以交叉，原始 family 不改写。

派生字段 `transfer` 包含路径 ID、显示名、搜索别名、原始端点、名称依据；网页、接口查询与 op 查询共用 [transfer_for](../scripts/ccec_transfer.py)。它不修改原始 catalog，不代表官方硬件分类或设备支持。

两层独立按 950 条件筛选。某路径没有符合条件的封装时，仍可选择该路径，并从空状态显式显示待确认项，或跳到同路径 Intrinsics。例如 `copy_gm_to_cbuf` 封装当前包含未求值的 `__DAV_L311__ / __DAV_L311_EFF__` 条件；对应 builtin 的入口条件单独判断。不能把某层无结果解释为没有 GM → L1 搬运。

## 列表中的接口组：保留层级身份

CCEC 接口只列带实现的封装，按 `namespace + name` 分组；CCEC Intrinsics 按完整 builtin 标识符唯一化。950 默认分别显示 357 个接口和 1514 个 op。原始声明及条件保留，待确认项通过显式开关加入。两层不合并计数，也不是硬件 ISA 全集。

封装详情保留来源声明选择器。Intrinsic 详情顶部提供“参数形式”选择器和参数表；缺少完整签名时禁用并说明原因。“关联封装参数”使用独立选择器，按命名空间、名称及词法参数形式合并重复展示，原始调用来源仍全部保留。它只用于理解调用，不能冒充 builtin 参数。选择写入深链接，刷新可恢复。

实现见 [makeGroups](../web/app.js) 和 [op 模型](ccec-ops.md)。设备支持必须另有编译或运行证据，见 [扫描范围](scope.md)。
