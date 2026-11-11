# CCE OPS · Agent 工作入口

## 目标与入口

构建 AI 原生的 Huawei Ascend CCE 指令接口可视化仓库。开工先读 [范围](docs/scope.md)、[流程](docs/workflow.md)、[路线](docs/roadmap.md)；页面约定见 [PRODUCT.md](PRODUCT.md)、[DESIGN.md](DESIGN.md) 与 [.impeccable/surface-catalog.md](.impeccable/surface-catalog.md)。README 面向外部读者；执行命令在本文件，详细规程放 docs。

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

可设置 `CCE_OPS_CHROME` 使用已有 Chrome；`CCE_OPS_PLAYWRIGHT` 可指定已有 Playwright 模块路径。测试覆盖可见范围、全结果轨道定位、连续追加、栏宽拖动与键盘调整、宽度记忆、离线无网络请求、搜索、组合筛选、重载、来源、深链接、空状态、报告、导出及 1440/1024/390/320 宽度；截图写入 `.impeccable/review/`，不入库。

```sh
git diff --check
git status --short
```
