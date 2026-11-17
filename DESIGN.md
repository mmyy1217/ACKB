---
name: ACKB
description: CCEC / PTX 目标知识库的黑白灰紧凑视觉约定
colors:
  ink: "#171717"
  muted: "#626262"
  accent: "#171717"
  focus: "#171717"
  selected: "#e8e8e8"
  surface: "#fff"
  nav: "#f7f7f7"
  subtle: "#f5f5f5"
  line: "#d4d4d4"
  row-line: "#ededed"
  input-line: "#bdbdbd"
  hover: "#efefef"
  nav-active: "#e2e2e2"
typography:
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
  button:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: "18px"
  caption:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.5
  title-mono:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.4
  row-mono:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: "20px"
  code:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.6
  reader-title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "23px"
    fontWeight: 650
    lineHeight: 1.35
  reader-body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.85
  reader-code:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.75
rounded:
  default: "2px"
  flat: "0px"
  term: "4px"
  topbar-control: "6px"
spacing:
  micro: "2px"
  compact: "3px"
  gap: "4px"
  tight: "6px"
  content: "8px"
  panel: "10px"
  section: "16px"
components:
  reader:
    textColor: "{colors.ink}"
    typography: "{typography.reader-body}"
    padding: "16px 24px 32px"
  term-button:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.ink}"
    rounded: "{rounded.term}"
    padding: "3px 6px"
  topbar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "0 10px"
    height: "40px"
  button-quiet:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.default}"
    padding: "3px 7px"
  button-text:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.default}"
    padding: "2px 0"
  search:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.topbar-control}"
    padding: "0 6px"
    height: "26px"
  filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.topbar-control}"
    padding: "0 3px"
    height: "26px"
    width: "112px"
  button-topbar:
    rounded: "{rounded.topbar-control}"
  navigation-item:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.default}"
    padding: "3px 5px"
  navigation-item-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.ink}"
  catalog-row-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.ink}"
    typography: "{typography.row-mono}"
    height: "26px"
  detail-tab:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.flat}"
    padding: "6px 0"
  code-block:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.default}"
    padding: "7px 8px"
  callout:
    backgroundColor: "{colors.subtle}"
    textColor: "#505050"
    rounded: "{rounded.flat}"
    padding: "7px 8px"
  splitter:
    width: "5px"
  load-status:
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
    padding: "6px 8px"
  scroll-navigation:
    backgroundColor: "{colors.surface}"
    width: "16px"
  progress-summary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "0 8px"
    height: "30px"
---

# Design System: ACKB

## Overview

**Creative North Star: "器件规格表"**

白色内容面、浅灰导航与黑色文字构成高密度的技术阅读界面。细线、字号与对齐区分信息层级，接口标识符和签名采用等宽字体。视觉服务于 Huawei Ascend CCEC 声明与 PTX 文档条目、条件和来源的核对。

本文件记录 `web/style.css`、`web/index.html`、`web/app.js`、`web/knowledge.js`、`web/ptx-reader.js` 和 `web/ccec-static.js`、`web/ccec-ops.js`、`web/ccec-a5.js` 的实际系统，并与生成的 `dist/index.html` 及桌面、平板、窄屏截图核对；令牌以前置 YAML 为准。页面构成与检索策略见 `.impeccable/surface-catalog.md`，产品边界见 `PRODUCT.md`。

**Key Characteristics:**

- 索引采用单行接口表与窄幅详情；PTX 阅读采用正文与随手查并置。
- 系统中文字体与技术等宽字体并用。
- 黑白灰、细线分区、文字说明状态。
- 原生控件、可见键盘焦点、离线自包含。

## Colors

### Primary

`accent` 与正文 `ink` 同为黑色，`focus` 也沿用黑色；系统不使用装饰色。选中接口行使用 `selected`，导航当前项使用 `nav-active`；加重文字与浅灰背景共同表示选择。当前标签页使用黑色文字及底边线。

### Neutral

`surface` 是内容底色，`nav` 区分侧栏，`subtle` 承载表头、代码、条件及证据说明。`ink` 表示主要内容，`muted` 表示说明和元数据。`line` 划分区域，`row-line` 划分紧凑表格行，`input-line` 表达控件边界。`hover` 用于按钮与导航悬停，表格悬停使用 `subtle`。证据说明使用灰色文字，不依赖彩色提示。

**The Evidence Rule.** 选择状态与证据状态必须有对应文字；静态声明不能以颜色暗示已通过编译、运行或设备验证。

## Typography

中文说明使用系统无衬线栈，标识符、签名、路径与哈希使用系统等宽栈；不加载在线字体。正文使用 `body`，搜索沿用正文大小；控件与导航使用 `label`，表头和元数据使用 `caption`。顶栏视图标题使用 `headline`，与正文同尺寸、以字重区分。品牌名称为（15px / 750），字距（−0.03em）。

详情名称使用 `title-mono`，列表名称使用 `row-mono`，代码块使用 `code`；选中接口名加重（700），导航和当前标签页加重（650）。详情小标题为（11px / 650）；来源、条件及重载选项为（10px）等宽文字。前置令牌分别保留正文（12px）、列表（11px）、详情标题（14px）及代码（11px）的实际层级，CCEC 与索引继续沿用此层级。PTX 阅读使用 `reader-title`、`reader-body` 与 `reader-code`，二级标题（16px）、三级标题（13px）；正文行宽至多（74ch），为连续解释与教学代码留出阅读空间。

## Layout

桌面顶栏高（40px）并吸附在页面顶端，ACKB、层级 / 后端选择器、PTX 视图标题、当前后端筛选、搜索及元信息同处一行，JSON 导出位于最后。主列表随主文档纵向连续展开，不设固定高内滚动容器；结果摘要与表头依次吸附在顶栏下方。两侧栏吸附在顶栏下方，高 `calc(100vh - var(--header-height))`，内容超出时在栏内滚动；主区左右留白（8px），无外层卡片。

左右分隔区域宽（5px），中央为（1px）竖线。CCEC 左栏默认（136px）、PTX 章节左栏默认（210px），范围（128–360px）；右栏默认（330px）、范围（260–720px）。实际最大值随窗口收紧，为中间列表保留至少（300px）；允许时以 `localStorage` 记住宽度。

有结果的索引视图在页面最左侧固定显示（16px）定位轨道，工作区同步让出（16px）；空结果和扫描报告隐藏轨道并收回留白。结果摘要实时显示当前视口名称组范围 / 当前指令族或筛选结果总数，并标明范围标签；范围采用（11px / 600）等宽文字。列表容器宽度至多（560px）时，仅视觉隐藏冗余总计，保留可见范围、范围标签和重置操作及总计的辅助技术语义。

结果摘要高（30px），表头高（25px），数据行高（26px）；CCEC 的名称、指令族、950 条件、形式或声明数同一行。后三列分别为（108px / 66px / 44px），名称列弹性占满。名称按钮高（25px）、内边距（2px 8px）；其余单元格横向内边距（8px）。详情标题区内边距（8px 10px），正文为（8px 10px 16px）。

- 宽度至多（1220px）：隐藏版本号，顶栏仍保持单行；未保存宽度偏好时，详情默认为（300px），文件筛选收至（160px）。
- 宽度（801–1100px）：隐藏顶栏视图标题与版本 / 仓库元信息，文件筛选宽（120px）；PTX 侧栏仍显示当前阅读入口，CCEC 侧栏保持指令族。
- 宽度至多（800px）：顶栏紧凑换行，品牌、层级 / 后端、PTX 视图与导出在首行，当前后端筛选随后，搜索独占末行；搜索和筛选高（28px）。CCEC 侧栏替换为原生指令族选择器，PTX 保留原生浏览与分类选择器，主区左右留白（6px）。列表与详情同在主文档中顺序展开，不限制列表高度；分隔线隐藏，详情取消吸附和栏内滚动。数据行高（29px），名称按钮高（28px）、名称文字（10px）。后三列收至（88px / 48px / 32px），详情名称仍为（14px）。搜索快捷键提示隐藏，重载选择器高（28px）。

PTX 指令速查与官方手册目录沿用同一列表和详情布局，列表后三列为类别、文档条件、章节，桌面宽（90px / 72px / 88px），窄屏为（62px / 64px / 62px）。章节号使用（10px）等宽文字，过长时单行省略，完整章节号仍在详情中展示。顶栏实际高度由观察器同步至吸附偏移，适配换行后的搜索与筛选。

PTX 学习正文沿主文档滚动，隐藏结果摘要、表头与结果进度轨道；正文内边距由 `reader` 定义。右侧随手查沿用详情栏宽度，可收起并由右下角入口展开；章节使用原生折叠分组。至多（800px）时正文内边距（12px 10px 24px），标题（20px）、段落（13px）；随手查在正文后顺序显示，概念图由三列变为单列。顶栏紧凑结构不变。

CCEC 顶栏隐藏重复视图标题，固定目标以只读“950 / A5”显示，紧邻“显示待确认”复选框；“说明 / 覆盖”位于导出之前。CCEC 左侧和窄屏导航仅显示指令族。

间距使用既有紧凑步长，不强行套用统一倍数网格。列表中的过长名称单行省略，名称按钮保留完整限定名提示；详情名称、条件、路径与哈希允许折行。代码保留原始空白，长行在代码块内横向滚动；报告表格也在自身容器滚动。

## Elevation & Depth

不使用投影。浅灰底、单像素边界与选中背景承担层级。搜索聚焦时使用（1px）黑色描边并加深边框；全局键盘焦点为（2px）描边、外偏移（1px），列表按钮及详情区域的焦点向内偏移（−2px）。底部通知使用黑底白字，无阴影。

交互状态即时切换，无过渡、位移或缩放动画。用户启用减少动态效果时保持即时滚动。

## Shapes

全局按钮、输入框、选择器和代码块保持 `default` 小圆角；顶栏搜索、选择器、导出按钮局部使用 `topbar-control`。表格、接口名称按钮、详情标签页及说明块保持平直轮廓。以直线边界组织工作区，不为每条接口加独立卡片。当前界面不使用装饰图标或状态圆点。

## Components

### Buttons

操作使用白底细边框的安静按钮；常规内边距（3px 7px），字行高（18px）。悬停使用 `hover` 并加深边框。详情操作收至（0 5px）、字号（10px）。重置筛选为灰色文字按钮，内边距（2px 0），悬停变黑并加下划线。禁用按钮透明度（0.45），取消手形光标；保留可见焦点。

### Inputs / Fields

桌面搜索与筛选高（26px）。搜索由边框容器包住原生输入和快捷键提示，横向内边距（6px），无搜索图标；焦点作用于整个容器。域选择器宽（112px），文件选择器宽（186px）。筛选和重载均使用原生 `select`；重载选项使用（10px）等宽文字，桌面高（25px），宽度限制在详情区内。

### Backend selector / PTX filters

ACKB 后紧邻“CCEC 编程接口 / CCEC Builtins / PTX”原生选择器，高（26px）、字号（11px / 600）、横向内边距（5px），复用浅灰底、控件细边框与（6px）圆角。切换同步更新导航、搜索提示、筛选和来源信息；CCEC 编程接口进入封装层，CCEC Builtins 进入唯一 builtin 层，PTX 进入全景学习正文。CCEC 使用域、文件、只读目标与待确认开关；PTX 默认 NVIDIA B300 / sm_103a，原生目标选择器宽（138px），可切换 sm_103、sm_103f、sm_103a。文档条件选择器宽（104px），窄屏（96px），学习阅读时隐藏。

PTX 条件为“全部状态 / 文档支持 / 部分形式 / 文档排除 / 待确认”；它们是文档判断，继续以文字和灰阶呈现，不表达设备验证结论。

### Fixed target / Unknown conditions

CCEC 目标为只读文字“950 / A5”，沿用筛选标签的紧凑样式。待确认开关使用带可见文字标签的原生 checkbox，`accent-color` 直接引用既有 `ink`；默认关闭，以选中状态表达是否加入未知条目。它不表示支持判定，不新增颜色或视觉令牌。

“说明 / 覆盖”沿用安静按钮，打开主区中的两层条件计数和证据说明；来源覆盖与知识说明使用原生折叠块。静态状态、条件、弃用及未验证边界继续用文字表达；详情的引用、声明宏与架构矩阵保留原生折叠块、等宽路径及浅灰底。旧架构菜单与其面板样式已移除。

### Navigation

CCEC 侧栏只含指令族；PTX 保留章节与阅读入口。侧栏是纵向文字列表，行高至少（26px），内边距（3px 5px）；右侧数字为（10px），使用等宽数字排列。当前项以灰底和加重文字区分。移动端使用带文字标签的选择器。详情标签页采用（11px）文字、间距（14px），当前项以下沿（2px）黑线及加重表示；支持左右箭头、Home 与 End 切换，并保留焦点。

### Interface rows / Detail

CCEC 编程接口行的名称、指令族、950 条件和右对齐计数保持单行；CCEC Builtins 显示有类型声明形式数，未确定时显示破折号；CCEC 编程接口按命名空间与名称分组并显示来源声明数，分类直接显示为表格文字，不使用标签组件。选中行使用 `selected`，名称加重。列表每批追加（60）个名称组，接近末尾时继续追加并保留已加载行；搜索与筛选重置为首批，深链接预先加载至选中行并定位。末尾以（10px）灰色文字说明已显示数量或全部加载完成，不使用分页控件。

CCEC Builtins 详情沿用名称标题、复制链接和窄屏返回入口；正文按身份、架构条件、参数形式、入口来源和上层调用者排列，以既有小标题、原生折叠块和关联文字按钮组织，不新增视觉令牌。原始记录继续使用标签页与来源声明选择器。

选择接口后更新详情并聚焦详情区域，窄屏同时滚动到详情并暂停追加；“返回列表”回到选中行并恢复追加。切换重载后保留选择器焦点。详情按名称、操作、标签页、重载与正文组织，来源位置和完整签名保持可读、可复制。

### Knowledge detail / Related entries

CCEC 知识主题沿用详情标题、操作与三标签页结构：条目为“条件与关联”，主题为“主题解读”，另有“来源证据”和“验证状态”。标题下显示后端和类别；原始章节标题与列表名不同时，以（11px）灰色文字补充并允许折行。操作提供复制完整记录和复制链接，窄屏保留返回列表。

规则与来源证据以细线分隔，每项上下内边距（6px），长标识符可折行；完整结构化规则与完整索引记录使用原生 `details` 展开。主题正文保留换行，行高（1.85），并列出尚待确认及引用。关联条目使用文字按钮，跳转到对应视图和详情并清除可能遮挡目标的筛选；CCEC 主题连接具体声明。PTX 完整条目在主阅读区展示解释、官方语法、原生折叠的架构与版本条件、父子章节和来源；学习主题按章节组织，术语与代码旁的查阅按钮更新右侧随手查，不替换正文。只有完整条目操作才导航主阅读区；返回正文将焦点归还原查阅入口，窄屏同时滚回该入口。

来源保留官方锚点、头文件位置和哈希。PTX 官方原文链接明确需要联网；官方语法与原创解释离线可读，完整手册正文未复制入库。验证状态分别展示编译、运行、性能未执行。JSON 导出包含当前后端、筛选、来源及验证状态；报告视图导出对应后端记录。

### Resizable separators

分隔线可拖动、聚焦，悬停、键盘焦点与拖动时中央竖线变黑。左右方向键每次沿对应方向移动（10px），按住 Shift 时为（40px）；Home / End 设置当前允许的最小 / 最大宽度，Enter 或双击恢复默认值。使用 `separator` 语义、竖向方向与当前宽度属性；窄屏隐藏。

### Scroll navigation / Visible range

轨道为（1px）灰线，滑块宽（6px）、最小高（28px），悬停、焦点或拖动时变黑；提示为（10px）等宽范围文字，上下内联 SVG 首尾按钮各高（22px）。滑块按全部筛选结果数与视口容量映射，不受已加载批次数影响。点击、拖动或首尾按钮直接追加至目标并保留已有行；方向键移动一行，Page Up / Down 移动一视口，Home / End 到首尾。轨道使用可聚焦的 `scrollbar` 语义及当前范围文字；窄屏明确阅读详情时，范围显示“详情 n / N”。

### Code / Evidence

代码块采用（11px / 1.6）等宽文字，内边距（7px 8px），保留换行及原始空白；长行在块内滚动。条件采用（10px / 1.6）等宽文字、内边距（4px 6px）并允许折行。证据说明使用浅灰平面、内边距（7px 8px）与（10px / 1.6）灰色文字；不使用暖色或成功色。报告中的待处理项使用原生 `details` 折叠。

## Do's and Don'ts

### Do:

- **Do** 复用前置令牌和原生控件，保持离线可用。
- **Do** 保持桌面统一顶栏、索引单行表与 PTX 正文 / 随手查分工，并检查窄屏顺序阅读。
- **Do** 保留文字状态、可见焦点、选中反馈及完整可复制来源。
- **Do** 使用细线、灰阶浅底、字重与对齐组织紧凑信息。

### Don't:

- **Don't** 用装饰卡片、渐变或大图替代接口表格。
- **Don't** 用彩色状态或选中反馈暗示编译、运行或设备支持结论。
- **Don't** 引入在线字体、CDN 图标或运行依赖。
- **Don't** 因单行列表或窄详情而截断实际签名、条件和来源内容。

## CCEC 参数选择与搬运路径补充

Intrinsic 详情顶部使用既有 `.overloads` 原生选择器，直接显示所选签名与参数表；无完整签名时禁用并解释。关联封装参数独立选择并标明与 builtin 参数的区别，选择写入深链接。入口来源和全部调用来源仍保留折叠证据。

左栏恢复 DMA、矩阵、访存等大类，不设搬运路径子项；列表同一行保留路径，搜索支持 GM2UB / GM2L1。CCEC 编程接口新增已追踪的搬运直连入口，名称后显示“直连”，与封装同处调用接口层。详情顶部使用原生选择器展示“950 源码调用形式”，逐项列出实参表达式与源码类型，折叠块提供调用源码、文件哈希、核保护与架构 include 路径；这些不是编译器正式形参或设备验证。

## AscendC / CCE Dialect 阅读入口

沿用黑白灰高密度列表、原生选择器和详情布局，不新增视觉令牌。顶栏增加 AscendC 高层 API / 底层接口、CCE Dialect 语义 Op / Intrinsics，左栏仍只保留大类。AscendC 保留完整声明形式与当前形式的条件来源，选择写入深链接。跨层名称关联明确为候选；局部条件符合不等于实现或设备支持。Dialect 仅计具体 LLVM 符号，5 个没有静态映射的 MLIR 条目在覆盖页独立展开。所有形式、来源、限制和未解析项离线可读且可导出。

## 首页阅读索引

首页为 Read 模式。沿用灰阶、系统中文字体和代码等宽字体，标题 24px；语义化路径框图在窄屏纵向重排，数据库入口以紧凑表格排列。桌面并列图与链接表，窄屏纵向排列。无装饰色、卡片或外部字体。LLVM 索引沿用 26px 行、现有栏宽、原生筛选和类型选择器。

## 数据库下载入口

线上首页与左上角切换共用下载／更新门控；按钮、字节进度和校验状态采用既有灰阶紧凑控件。未就绪入口不可进入，错误可重试；上下两层共享同库状态。已缓存库和离线单文件直接可读，版本变化遵循 docs/loading.md。

## 首页路径语义修正

两套 AscendC 源码入口并列，分别说明经 CCEC 封装与直达 builtin 的可选路径；普通表达式可直接生成普通 LLVM IR。外部 Dialect lowering 与 LLVM 符号关联分开标注，两端后端代码生成均注明索引范围之外。框图使用语义化 HTML，窄屏转纵向，完整内容无需横向滚动；沿用下载门控与灰阶控件。图示不提升为逐接口已验证调用关系。

## Ascend C 体系与知识库入口

`#ascendc-map` 使用已确认的黑白结构图，Read 模式；上方按模板库、高阶 API、基础 API、语言扩展分区，下方展开编译器，外部 CCE Dialect 单独放置。7 个入口分别链接 AscendC 两层、CCEC 两层、LLVM、Dialect 两层；Huawei Ascend 分区不含 PTX，不再显示功能矩阵、具体接口或筛选器。结构图无需下载数据；点击后统一经过下载门控。窄屏纵向重排。

## 结构图首页与下载

无 fragment、`#home` 和旧 `#ascendc-map` 均进入结构图首页。7 个 Huawei Ascend 相关知识库在图内链接，PTX 位于右侧 NVIDIA CUDA 体系图内。入口旁小圆钮负责下载／更新，悬停提示状态和体积，下载时显示百分比，完成后解锁链接；同库双层共用状态。离线单文件直接打开，无下载控件。统一名称为 AscendC 基础 C++ API、AscendC C / SIMT API、CCEC 编程接口、CCEC Builtins、LLVM IR、CCE Dialect 语义 Ops、CCE Dialect LLVM Intrinsics；URL 与数据 ID 保持兼容。
