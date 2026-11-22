# 洞察维护

首页顶部“洞察”进入 `#insights`；文章使用稳定深链接 `#insight=<slug>`。目录和正文随页面构建，不下载数据库，在线与离线内容相同。数据库链接继续经过已有下载门控。

新增文章时，在 `web/insights/index.json` 添加 slug、title、date、summary，并创建同名 `.html` 正文片段。列表顺序即目录顺序。正文用中文原创说明，保留来源链接、版本、统计口径与未知边界；历史数字标明快照，不随数据重建静默变化。不得把名称出现或候选映射写成硬件支持结论。

`scripts/insights.py` 构建目录、文章页及未找到状态，拒绝重复或非法 slug。重新构建在线和离线页面，运行 `node tests/insights-browser.cjs` 与 `npm run test:site`。浏览器环境变量同 AGENTS.md。

A5 差距洞察按包内默认 A5 名称集合减去独立 Dialect 静态映射名称集合生成。执行 `python scripts/dialect_gap_snapshot.py` 可复算网页和 Excel 明细；反方向只计数。来源筛选按包内文件精确匹配。

方向切换使用同一快照。Dialect → CANN 逐名连接整个包内索引，显示静态操作键、映射文件位置与所有命中的包文件。反向列表的 lowering 注解取自固定提交的 [直接调用复核](https://github.com/mmyy1217/tilelang-ascend-docs/releases/tag/ackb-cce-dialect-a5-audit-20261117)，覆盖 259 个已复核名称和 7 个额外字面量。更新版本时需重新核对注解；当前 Excel 下载范围仍是 802 条 A5 差集。
