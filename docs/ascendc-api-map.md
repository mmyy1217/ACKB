# AscendC API 全景

入口 `#ascendc-map`，从首页访问；源码为 `web/ascendc-map.html`，构建同时内联到在线与离线版本。它是概念阅读层，不新增 API 全量扫描或设备支持结论。

官方参考检出的四类为 SIMD / SIMT / Utils / AI CPU。功能行与抽象列由 ACKB 整理；Tensor API 来自固定 CANN 包的目录，不冒充官方总览的一级分类。CCEC 接口、Builtins、LLVM 分层保留，不以“几跳”归并；目录出现、样例调用、完整 C++ 解析与目标可用性分别处理。

核对来源、SHA-256、样例行号保存于 [来源快照](ascendc-api-map-sources.json)。参考文档固定 commit，CANN 固定 weekly；两个来源不假定完全同步。新增样例仅核对本地安装文件，未重新核验原包。

维护时先核对来源，再修改矩阵和来源快照；不从未知或未列示推断不支持。当前有界索引明确排除部分 Tensor / TPipe / 类型与工具文件；Tensor API、adv_api、Host 工具和 AI CPU 没有专项数据库。浏览器回归检查无下载阅读、深链接刷新、功能筛选、窄屏和原有数据库入口。
