# Ascend C 体系与知识库入口

首页链接为 `#ascendc-map`；源码 `web/ascendc-map.html` 同时内联在线与离线版本。使用用户确认的结构图，保留抽象层级和能力分区，不展示具体函数或功能矩阵。

7 个唯一入口：AscendC 基础 C++ API、C / SIMT API、CCEC 编程接口、CCEC Builtins、LLVM IR、CCE Dialect 语义 Ops、Dialect LLVM Intrinsics。C / SIMT 共享数据库入口，外部 Dialect 与 CANN 编译器分区，PTX 不在本图。其余区域仅提供体系背景，不表示已经建立数据库或完整收录。

概念层级不表示固定逐层调用链。基础 C++ 库包含有界的 Tensor / Reg / SIMT C++ 函数，名称不应与官方高阶算法 API 混淆。历史目录与样例来源保留于 `ascendc-api-map-sources.json`，不据此提升为目标支持结论。

回归覆盖 7 个入口、线上下载门控、离线跳转、深链接和窄屏。修改图后重建在线及离线页面。
