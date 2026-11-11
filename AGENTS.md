# CCE OPS · Agent 工作入口

## 目标与入口

构建 AI 原生的 Huawei Ascend CCE 指令接口可视化仓库：提取 intrinsic / builtin，保存证据，生成高密度、可离线阅读的原生 HTML 手册。

- 开工先读 [扫描范围](docs/scope.md) 与 [执行流程](docs/workflow.md)。
- 功能顺序与完成条件见 [建设路线](docs/roadmap.md)。
- README 面向外部读者；执行命令集中在本文件，详细规程放在 docs，避免本文件膨胀。

## 必须遵守

- 先核对版本与用户修改。不得修改 CANN 安装目录或覆盖用户文件。
- 以 CCE 接口为主体；不自动扩展到 PTO、AscendC 高层 API 全集或硬件 ISA 逆向。
- 每条接口保留来源、完整签名、重载及架构条件；未解析内容显式报告，不静默丢弃。
- 区分静态声明、二进制候选、编译验证和运行验证；不得把名字出现当成硬件支持。
- 本地进行静态提取和网页验证；设备编译与运行按上层工作区规则在对应远程环境进行，先核对版本和资源权限。不得声称本地验证了 NPU 正确性或性能。
- 文档与交流使用中文；代码、代码注释及 commit message 使用英文。说明文字使用 Huawei Ascend 全称，保留技术标识符原拼写。
- 阶段完成后检查并本地提交；不添加 AI 作者 trailer。不向 upstream push。
- 未获用户针对本次操作、指定仓库和具体 PR 的直接明确允许，不得新建、重新打开或发布 PR（含 draft / mark ready）；不得通过工具或委派绕过。默认仅准备本地可审阅材料。`tile-ai/tilelang#3651` 不得重新打开。

## 当前可用命令

在仓库根目录执行：

```sh
git status --short
git diff --check
```

本地已发现的目标版本可用于只读盘点（安装包来源与哈希仍待核验）：

```sh
export CCE_OPS_TOOLKIT=/home/zuomin/Ascend/cann-weekly-9.3.0-20261104.01/cann-9.3.0
export CCE_OPS_INCLUDE="$CCE_OPS_TOOLKIT/tools/bisheng_compiler/lib/clang/15.0.5/include"
rg --files "$CCE_OPS_INCLUDE" -g '*cce*' -g '*dpp*'
rg -n '__builtin_cce_|clang_builtin_alias' "$CCE_OPS_INCLUDE"
```

提取、数据校验、网页构建命令尚未实现；实现后在此添加真实入口与运行条件，不使用占位命令冒充可用功能。`git diff --check` 仅检查空白格式，不替代后续功能或页面验证。
