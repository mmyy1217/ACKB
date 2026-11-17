# ACKB 领域语言

ACKB（AI Compiler Knowledge Base）是 AI as Compiler 的目标知识层，提供接口、执行模型及可追溯的验证证据。

## 页面层级名称

| 页面入口 | 内容边界 | 稳定后端 / 层级标识 |
| --- | --- | --- |
| CCEC 编程接口 | 开发者可写的 CCE 源码函数：封装及已追踪的直连 alias 入口 | ccec / wrappers（网页）；interfaces（CLI 命令） |
| CCEC Builtins | 按完整 `__builtin_cce_*` 标识符去重的编译器内建操作 | ccec / interfaces（网页）或 ops（CLI） |
| AscendC 基础 C++ API | `basic_api` 的 Tensor、Reg、SIMT C++ 接口 | ascendc / basic |
| AscendC C / SIMT API | `c_api` 与 `simt_api` 的底层函数接口 | ascendc / capi |
| CCE Dialect 语义 Op | MLIR 语义操作 | cce-dialect / ops |
| CCE Dialect LLVM Intrinsics | 映射表出现的具体 `llvm.hivm.*` 符号及关联 Op | cce-dialect / intrinsics |
| PTX 虚拟指令集 | PTX 指令、执行模型和官方文档阅读层 | ptx |

这是不同编程层级与来源体系，不是七个仓库或七套硬件 ISA。“编程接口”比“上层接口”更准确：CCEC 这一层同时保留封装和直连入口，并非每个条目都有额外封装。Builtin 指编译器内建标识，intrinsic 是更宽泛的概念，也用于 LLVM IR 层。显示名称调整不改变既有 CLI、数据 ID 或深链接。

## 术语

**AI as Compiler**：由 AI 生成目标层级代码，再交给既有工具链完成后续编译。代码生成策略属于外部系统。

**目标知识库**：面向某种目标代码及硬件模型的事实、约束、来源和实验集合；文档覆盖与设备验证覆盖分别计算。

**CCEC 目标**：AI 输出 CCE 源码并交给 ccec 工具链的目标。CCEC 是编译器名称，不与硬件 ISA 画等号。

**PTX 目标**：AI 输出 NVIDIA PTX 虚拟指令代码的目标。PTX ISA 版本、CUDA 工具链版本和 SM 架构版本是独立维度。

**全面索引**：在明确来源快照范围内盘点全部入口、章节与未解析项，不意味着覆盖了所有硬件事实。

**重点深度**：对选定主题补充解释、约束、来源和未知项；没有实验时不提升为编译或运行验证。

**目标支持**：必须带适用范围和证据等级的结论。文档判定、声明条件、编译通过和运行正确是不同结论。

**CCEC op**：以明确出现的完整 builtin 标识符区分的编译器层操作。同一 op 可有多个 intrinsic 别名、声明来源和参数形式，不等于一条硬件指令。

**Intrinsic 入口**：通过显式 builtin alias 属性关联到 op 的源码声明；同名入口和封装并不必然关联。

**封装**：包含参数转换、控制流或底层调用的源码函数或宏。它与 op 是调用关系，不占用 op 身份。

**声明形式**：来源中保留的词法签名；不同声明记录或参数名差异不自动构成不同 C++ 重载。

**待解析入口**：尚无足够依据确定层级或 builtin 关联的来源记录，不按名称猜测归属。
