# ACKB · Agent 工作入口

## 目标与入口

构建面向 AI as Compiler 的 CCEC / PTX 目标知识库，以 Huawei Ascend CCEC 为主。术语见 [CONTEXT.md](CONTEXT.md)，双后端入口见 [知识索引](docs/knowledge.md)。开工先读 [范围](docs/scope.md)、[流程](docs/workflow.md)、[路线](docs/roadmap.md)；页面约定见 [PRODUCT.md](PRODUCT.md)、[DESIGN.md](DESIGN.md) 与 [.impeccable/surface-catalog.md](.impeccable/surface-catalog.md)。README 面向外部读者；执行命令在本文件，详细规程放 docs。

## 必须遵守

- 先核对版本、来源与用户修改；只读 CANN 安装目录。以 CCE intrinsic / builtin 为主体，不自动扩展 PTO、高层 API 全集或硬件 ISA 逆向。
- 保留签名、重载、命名空间、原始条件、宏定义与调用位置；未解析及条件宏歧义必须报告。不得把声明出现等同于设备支持，也不得静默丢弃失败项。
- AI 解释须有依据；静态声明、编译验证、运行验证、性能测量分别记录。本地只做静态提取与网页验证，设备实验遵循上层工作区远程规则。
- 生成页面必须离线可用，真实数据驱动；改数据或网页后重新构建。页面先检查 PRODUCT / DESIGN，再按 impeccable 验证桌面、窄屏与交互。
- 文档和交流中文；代码、代码注释及 commit message 英文。说明文字使用 Huawei Ascend 全称，技术标识符保留原拼写。
- 阶段完成后检查并本地提交，无 AI 作者 trailer；不向 upstream push。不提交原始包、完整 Toolkit、设备库和大型实验产物。
- 未获用户针对本次操作、指定仓库和具体 PR 的直接明确允许，不得新建、重新打开或发布 PR（含 draft / mark ready），不得通过工具或委派绕过。默认仅准备本地可审阅材料。`tile-ai/tilelang#3651` 不得重新打开。

## 构建与验证

在仓库根目录执行；日常构建只需 Python 3.10+ 标准库，无前端运行依赖。

```sh
python scripts/build.py
python -m unittest discover -s tests -v
python scripts/catalog.py validate
```

生成 `dist/index.html`，可直接在浏览器打开。`dist/` 不入库。更换数据可使用构建参数 `--data <catalog.json> --output <index.html>`。

## 从本地工具链重新提取

已核对原包内 23 个扫描头文件。显式指定版本目录，不使用 latest；重新提取会重置包校验状态，须再次核验。

```sh
export CCE_OPS_TOOLKIT=/home/zuomin/Ascend/cann-weekly-9.3.0-20261104.01/cann-9.3.0
python scripts/catalog.py extract --toolkit "$CCE_OPS_TOOLKIT"
python scripts/catalog.py validate --toolkit "$CCE_OPS_TOOLKIT"
export CCE_OPS_PACKAGE=/home/zuomin/downloads/cann-weekly-20261104.01/Ascend-cann-toolkit_9.3.0~weekly.20261104.01_linux-x86_64.run
python scripts/verify_package.py --package "$CCE_OPS_PACKAGE" --work-dir /home/zuomin/Projects/Compiler/work/experiments/cce-ops/package-verification
python scripts/build.py
```

提取器目前固定本轮版本，接入新版本需先扩展版本参数与数据隔离，不可只换目录。提取器的可选 `--package <path>` 仅记录包哈希；`verify_package.py` 才执行嵌套归档的头文件比对，不运行安装脚本。

## 浏览器回归（开发依赖）

```sh
npm ci
npx playwright install chromium
npm run test:browser
```

可设置 `CCE_OPS_CHROME` 使用已有 Chrome；`CCE_OPS_PLAYWRIGHT` 可指定已有 Playwright 模块路径。双后端测试另覆盖 PTX 全量章节、支持条件、笔记关联、导出和 CCEC 主题跳转。测试覆盖可见范围、全结果轨道定位、连续追加、栏宽拖动与键盘调整、宽度记忆、离线无网络请求、搜索、组合筛选、重载、来源、深链接、空状态、报告、导出及 1440/1024/390/320 宽度；截图写入 `.impeccable/review/`，不入库。

```sh
git diff --check
git status --short
```

## 架构元数据与版本差异

口径和限制见 [兼容性证据](docs/compatibility.md)。构建自动读取数据旁的同版本 `targets.json`；可选，缺失时仅提供宏条件场景。

```sh
python scripts/targets.py --toolkit "$CCE_OPS_TOOLKIT" --version '9.3.0~weekly.20261104.01' --output 'data/9.3.0~weekly.20261104.01/targets.json'
node tests/compatibility-browser.cjs
python scripts/compare.py <before.json> <after.json> --output <diff.json>
```

## AI 查询入口

先读 [AI 使用入口](docs/ai-entry.md) 与 [数据库规范](docs/database.md)。无需读取整份 catalog；全局分页参数放子命令前。将下列 ID 占位符替换为查询返回值。

```sh
python scripts/query.py info
python scripts/query.py --limit 5 targets --name 950PR_9579
python scripts/query.py --limit 5 search --name copy_gm_to_cbuf --chip Ascend950PR_9579 --condition possible
python scripts/query.py search --builtin __builtin_cce_abs_bf16x2
python scripts/query.py get <symbol_or_variant_or_record_id>
python scripts/query.py relations <symbol_or_variant_or_record_id>
python scripts/query.py evidence <record_id>
python scripts/query.py --offset 5 --limit 5 search --name copy_gm_to_cbuf
python scripts/query.py schema
```

## 双后端知识索引

原有 CCEC 声明命令保持兼容；PTX `--data` 接受索引目录。范围、字段与限制见 [知识索引](docs/knowledge.md) 和 [PTX 来源](docs/ptx-index.md)。

```sh
python scripts/ccec_knowledge.py
python scripts/ptx_index.py extract --help
python scripts/ptx_index.py validate
python scripts/query.py topics
python scripts/query.py builtins __builtin_cce_abs
python scripts/query.py get ccec_topic_synchronization
python scripts/query.py --backend ptx info
python scripts/query.py --backend ptx topics
python scripts/query.py --backend ptx search --name mma --architecture sm_103a
python scripts/query.py --backend ptx search --kind all
python scripts/query.py --backend ptx get warp-level-matrix-instructions-mma
python scripts/query.py --backend ptx schema
```

## PTX 阅读层与部署

数据规则见 [PTX 阅读层](docs/ptx-learning.md)。`learning.json` 为原创解释；`syntax.json` 只从固定哈希手册重建，不重新抓取未固定的 latest。设备信息见 `device.json`。

```sh
python scripts/ptx_learning.py --html /home/zuomin/Projects/Compiler/work/experiments/ackb/ptx-index/source/ptx-isa-13.4.3-index.html
python scripts/ptx_taxonomy.py
python scripts/ptx_guides.py
python scripts/ptx_build_learning.py
python scripts/query.py --backend ptx categories
python scripts/query.py --backend ptx search --category 9.7.18
python scripts/query.py --backend ptx get learn_tcgen05_pipeline
python scripts/query.py --backend ptx get tcgen05-mma-instructions-mma --architecture sm_103a
```

GitHub Pages 通过 main 上的 `.github/workflows/pages.yml` 构建 `dist/` 并部署；无需提交 dist。线上入口 https://mmyy1217.github.io/ACKB/ 。推送和发布仍须遵循本次用户授权边界；不得把自动部署流程视为未来发布授权。

## CCEC 架构支持追踪

静态判定口径与可选编译边界见 [支持证据追踪](docs/ccec-support.md)。只读提取、引用分页与矩阵：

```sh
python scripts/ccec_support.py extract --toolkit "$CCE_OPS_TOOLKIT"
python scripts/ccec_static.py build
python scripts/ccec_static.py validate
python scripts/ccec_support.py report --chip Ascend950PR_9579
python scripts/query.py support 960c673e040dc702bc0a --chip Ascend950PR_9579 --core dav-c310-cube
python scripts/ccec_support.py get 960c673e040dc702bc0a --offset 5 --limit 5
python scripts/ccec_support.py matrix 960c673e040dc702bc0a
python scripts/verify_static_package.py --package "$CCE_OPS_PACKAGE" --work-dir ../work/experiments/ackb/static-package-verification
python scripts/build.py
```

`ccec_probe.py run` 仅在已授权远程编译机运行，不能在本地执行；完整参数见 `--help`。不运行生成的 kernel。远端二进制、版本元数据和 23 个资源头文件哈希不匹配时拒绝执行，不自动升级远端环境。

## CCEC 唯一 op 层

主入口与分层规则见 [op 模型](docs/ccec-ops.md)。原 search 为声明查询，op 不继承封装支持。构建自动从原 catalog 派生同一模型。

```sh
python scripts/ccec_ops.py build
python scripts/ccec_ops.py validate
python scripts/query.py ops --name copy_gm_to_ubuf --chip Ascend950PR_9579
python scripts/query.py get ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2
python scripts/query.py relations ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2
python scripts/query.py schema --layer ops
```
