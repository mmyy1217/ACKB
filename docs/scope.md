# 扫描范围与数据约定

## 输入边界

目标包：`Ascend-cann-toolkit_9.3.0~weekly.20261104.01_linux-x86_64.run`。

首要对象是 CCE 源码层指令接口。以该包实际内容为准，保留全部架构条件；优先验证 Huawei Ascend 950PR，不将主机平台 `x86_64` 误作设备架构。

已发现对应版本安装目录，但尚未核验原始安装包哈希及包与安装目录的一致性。

## 首批文件

以下路径相对 `tools/bisheng_compiler/lib/clang/15.0.5/include/`，它们是扫描种子，实际扫描继续追踪包含关系与关联声明。

| 类别 | 文件 |
| --- | --- |
| AI Core | `cce_aicore_intrinsics.h`、`__clang_cce_aicore_intrinsics.h`、`__clang_cce_aicore_functions.h` |
| 向量 | `__clang_cce_ave.h`、`__clang_cce_vector_intrinsics_legacy.h` |
| SIMT | `__clang_cce_simt.h`、`__clang_cce_simt_intrinsics.h`、`__clang_cce_simt_dav3510_intrinsic.h` |
| 原子操作与寄存器 | `__clang_cce_simt_atomic.h`、`__clang_cce_simt_spr.h` |
| 数据类型相关操作 | `__clang_cce_simt_fp16.h`、`__clang_cce_simt_bf16.h`、`__clang_cce_simt_fp8.h`、`__clang_cce_simt_fp4.h` |
| 类型与宏 | `__clang_cce_types.h`、`__clang_cce_vector_types.h`、`__clang_cce_defines.h` |
| 内建变量 | `__clang_cce_aicore_builtin_vars.h`、`__clang_cce_simt_builtin_vars.h` |
| 包含关系 | `__clang_cce_runtime.h`、`__clang_cce_runtime_wrapper.h`；按引用追踪 DPP 等辅助定义 |

在工具链内补充搜索 `__builtin_cce_*`、builtin alias 和相关声明。二进制名称只用于发现候选，不直接计入已确认接口。类型、常量、内建变量和辅助函数分别建类，不混入指令数量。

AI CPU NEON、主机 x86 指令、运行时启动与调试辅助函数不计入 AI Core 指令全集。LLVM IR、汇编可以作为后续实验附件；硬件编码恢复、AscendC 高层 API 全集和 PTO 不属于当前范围。

## 每条记录的最小信息

- 身份：接口名、所属层次、指令族、完整签名与重载身份。
- 类型：返回类型、参数、地址空间、模板参数、引用的类型与常量。
- 条件：原始条件编译表达式；经证据确认后再关联设备型号。
- 关联：alias / wrapper / builtin 关系，允许一对多和多对一。
- 来源：完整版本、相对路径、行号范围、文件哈希、提取器版本。
- 说明：事实、源码推导、待确认解释分开标记。
- 验证：静态来源与实验记录分开保存；实验包含目标、命令、结果及附件。

同名重载不得合并丢失；跨文件重复声明保留全部来源。AI 生成的解释不能覆盖原始声明。

## 完整性口径

分别统计扫描文件、成功解析声明、未解析项、排除项及验证覆盖。任何“完整”声明必须绑定版本、文件范围和计数口径；头文件接口完整不代表硬件 ISA 完整。未找到、解析失败、目标不支持是不同状态。
