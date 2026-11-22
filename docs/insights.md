# 洞察维护

首页顶部“洞察”进入 `#insights`；文章使用稳定深链接 `#insight=<slug>`。目录和正文随页面构建，不下载数据库，在线与离线内容相同。数据库链接继续经过已有下载门控。

新增文章时，在 `web/insights/index.json` 添加 slug、title、date、summary，并创建同名 `.html` 正文片段。列表顺序即目录顺序。正文用中文原创说明，保留来源链接、版本、统计口径与未知边界；历史数字标明快照，不随数据重建静默变化。不得把名称出现或候选映射写成硬件支持结论。

`scripts/insights.py` 构建目录、文章页及未找到状态，拒绝重复或非法 slug。重新构建在线和离线页面，运行 `node tests/insights-browser.cjs` 与 `npm run test:site`。浏览器环境变量同 AGENTS.md。

「CCE Dialect 与 LLVM IR 的 A5 名称差距」使用稳定地址 #insight=dialect-a5-gap。2026-11-22 快照由 scripts/dialect_gap_snapshot.py 从两个已提交索引生成，684 行均为 CANN 一侧的目标名称。在线页进入文章时才取 JSON，离线页内嵌同一 JSON 与 Excel。更新快照时需同步正文计数、文件名和工作簿，逐行核对 JSON 与 Excel。
