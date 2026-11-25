# Ascend C 体系与知识库入口

首页链接为 `#ascendc-map`；源码 `web/ascendc-map.html` 同时内联在线与离线版本。使用用户确认的结构图，保留抽象层级和能力分区，不展示具体函数或功能矩阵。

8 个唯一入口：AscendC 基础 C++ API、C / SIMT API、CCEC 编程接口、CCEC Builtins、LLVM IR、A5 Intrinsic 定义、CCE Dialect 语义 Ops、Dialect LLVM Intrinsics。C / SIMT 共享数据库入口，外部 Dialect 与 CANN 编译器分区，PTX 位于独立的 NVIDIA CUDA 分区。其余区域仅提供体系背景，不表示已经建立数据库或完整收录。

概念层级不表示固定逐层调用链。基础 C++ 库包含有界的 Tensor / Reg / SIMT C++ 函数，名称不应与官方高阶算法 API 混淆。历史目录与样例来源保留于 `ascendc-api-map-sources.json`，不据此提升为目标支持结论。

回归覆盖 8 个入口、线上下载门控、离线跳转、深链接和窄屏。修改图后重建在线及离线页面。

## 结构图首页与下载

无 fragment、`#home` 和旧 `#ascendc-map` 均进入结构图首页。8 个 Huawei Ascend 相关知识库在图内链接，PTX 位于右侧 NVIDIA CUDA 体系图内。入口旁小圆钮负责下载／更新，悬停提示状态和体积，下载时显示百分比，完成后解锁链接；同库双层共用状态。离线单文件直接打开，无下载控件。统一名称为 AscendC 基础 C++ API、AscendC C / SIMT API、CCEC 编程接口、CCEC Builtins、LLVM IR、A5 Intrinsic 定义、CCE Dialect 语义 Ops、CCE Dialect LLVM Intrinsics；URL 与数据 ID 保持兼容。

## NVIDIA CUDA 分区

桌面宽度超过 1100px 时，Huawei Ascend 在左、NVIDIA 在右，中间虚线分隔；较窄视口上下排列。分区内部独立排版，不按行建立等价关系。保留 8 个 Huawei Ascend 入口，PTX 为第 8 个入口，继续使用同一下载与更新机制。

CUDA 侧展示计算库、模板与 C++ 类库、CUDA C++ 设备编程，以及 NVVM IR → PTX → 机器码。nvcc 是编译驱动，不是一种 IR；Host Runtime / Driver API 是运行支撑，不是中间表示层。ptxas 与 Driver JIT 是两种 PTX 编译路径，兼容 cubin 可以直接加载。图不是固定调用链，也不包含所有 Python / DSL 前端；仅 PTX 已收录为知识库。没有增加扫描范围或更改架构支持数据。

来源：[NVCC 13.4.3](https://docs.nvidia.com/cuda/archive/13.4.3/cuda-compiler-driver-nvcc/index.html)、[NVVM IR 13.4.3](https://docs.nvidia.com/cuda/archive/13.4.3/nvvm-ir-spec/index.html)、[CUTLASS / CuTe](https://docs.nvidia.com/cutlass/latest/overview.html)、[CCCL](https://nvidia.github.io/cccl/unstable/cccl/index.html)。页面仅保留来源链接，构建和打开不依赖在线文档。

## A5 Intrinsic 定义

`#backend=hivm-defs` 与 LLVM IR 并列。数据来自 Issue-33-A5-Intrinsics.xlsx 工作簿「全量条目」的 C 列，保留定义名、签名、标签、原序号、行号和 B 列分类。「待补签名」按原序号及名称补充工作簿报告的探针结果。定义记录不参与 CANN 9.3 包内证据统计。仓库内的机器可读快照为 `data/hivm_defs/index.json`，其中保存工作簿 SHA-256。
