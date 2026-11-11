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

## 列表中的接口组：合并展示声明

网页按 `group + namespace + name + kind` 四个字段组成分组身份。同一组的重载、条件分支与跨文件重复声明放入详情选择器，每条记录仍保留自己的来源与签名。

当前 5,714 条接口声明记录组成 1,818 个列表组。这两个数字均不是硬件指令数量。不同来源组、命名空间或接口形式的同名条目不会被合成一组；“重载”列包含该组全部声明记录，不等于唯一签名数。

实现见 [makeGroups](../web/app.js)。设备支持必须另有编译或运行证据，见 [扫描范围](scope.md)。
