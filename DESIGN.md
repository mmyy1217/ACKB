---
name: CCE OPS
description: Huawei Ascend CCE 指令接口离线手册的黑白灰紧凑视觉约定
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
rounded:
  default: "2px"
  flat: "0px"
spacing:
  micro: "2px"
  compact: "3px"
  gap: "4px"
  tight: "6px"
  content: "8px"
  panel: "10px"
  section: "16px"
components:
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
    rounded: "{rounded.default}"
    padding: "0 6px"
    height: "26px"
  filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.default}"
    padding: "0 3px"
    height: "26px"
    width: "112px"
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
---

# Design System: CCE OPS

## Overview

**Creative North Star: "器件规格表"**

白色内容面、浅灰导航与黑色文字构成高密度的技术阅读界面。细线、字号与对齐区分信息层级，接口标识符和签名采用等宽字体。视觉服务于 Huawei Ascend CCE 接口、条件与来源的核对。

本文件记录 `web/style.css`、`web/index.html` 和 `web/app.js` 的实际系统，并与生成的 `dist/index.html` 及桌面、平板、窄屏截图核对；令牌以前置 YAML 为准。页面构成与检索策略见 `.impeccable/surface-catalog.md`，产品边界见 `PRODUCT.md`。

**Key Characteristics:**

- 单行接口表与窄幅详情并置。
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

详情名称使用 `title-mono`，列表名称使用 `row-mono`，代码块使用 `code`；选中接口名加重（700），导航和当前标签页加重（650）。详情小标题为（11px / 650）；来源、条件及重载选项为（10px）等宽文字。前置令牌分别保留正文（12px）、列表（11px）、详情标题（14px）及代码（11px）的实际层级，不恢复旧版大标题。

## Layout

桌面顶栏高（40px）并吸附在页面顶端，CCE OPS、视图标题、搜索、域和文件筛选、JSON 导出及元信息同处一行。主列表随主文档纵向连续展开，不设固定高内滚动容器；结果摘要与表头依次吸附在顶栏下方。两侧栏吸附在顶栏下方，高 `calc(100vh - var(--header-height))`，内容超出时在栏内滚动；主区左右留白（8px），无外层卡片。

左右分隔区域宽（5px），中央为（1px）竖线。左栏默认（136px）、范围（128–360px）；右栏默认（330px）、范围（260–720px）。实际最大值随窗口收紧，为中间列表保留至少（300px）；允许时以 `localStorage` 记住宽度。

结果摘要高（30px），表头高（25px），数据行高（26px）；名称、指令族、域、重载数同一行。后三列分别为（108px / 66px / 44px），名称列弹性占满。名称按钮高（25px）、内边距（2px 8px）；其余单元格横向内边距（8px）。详情标题区内边距（8px 10px），正文为（8px 10px 16px）。

- 宽度至多（1220px）：隐藏版本号，顶栏仍保持单行；未保存宽度偏好时，详情默认为（300px），文件筛选收至（160px）。
- 宽度至多（800px）：顶栏紧凑换行，搜索独占一行、域与文件筛选共享下一行；搜索和筛选高（28px）。侧栏替换为原生浏览与指令族选择器，主区左右留白（6px）。列表与详情同在主文档中顺序展开，不限制列表高度；分隔线隐藏，详情取消吸附和栏内滚动。数据行高（29px），名称按钮高（28px）、名称文字（10px）。后三列收至（88px / 48px / 32px），详情名称仍为（14px）。搜索快捷键提示隐藏，重载选择器高（28px）。

间距使用既有紧凑步长，不强行套用统一倍数网格。列表中的过长名称单行省略，名称按钮保留完整限定名提示；详情名称、条件、路径与哈希允许折行。代码保留原始空白，长行在代码块内横向滚动；报告表格也在自身容器滚动。

## Elevation & Depth

不使用投影。浅灰底、单像素边界与选中背景承担层级。搜索聚焦时使用（1px）黑色描边并加深边框；全局键盘焦点为（2px）描边、外偏移（1px），列表按钮及详情区域的焦点向内偏移（−2px）。底部通知使用黑底白字，无阴影。

交互状态即时切换，无过渡、位移或缩放动画。用户启用减少动态效果时保持即时滚动。

## Shapes

按钮、输入框、选择器和代码块使用 `default` 小圆角；表格、接口名称按钮、详情标签页及说明块保持平直轮廓。以直线边界组织工作区，不为每条接口加独立卡片。当前界面不使用装饰图标或状态圆点。

## Components

### Buttons

操作使用白底细边框的安静按钮；常规内边距（3px 7px），字行高（18px）。悬停使用 `hover` 并加深边框。详情操作收至（0 5px）、字号（10px）。重置筛选为灰色文字按钮，内边距（2px 0），悬停变黑并加下划线。禁用按钮透明度（0.45），取消手形光标；保留可见焦点。

### Inputs / Fields

桌面搜索与筛选高（26px）。搜索由边框容器包住原生输入和快捷键提示，横向内边距（6px），无搜索图标；焦点作用于整个容器。域选择器宽（112px），文件选择器宽（186px）。筛选和重载均使用原生 `select`；重载选项使用（10px）等宽文字，桌面高（25px），宽度限制在详情区内。

### Navigation

侧栏是纵向文字列表，行高至少（26px），内边距（3px 5px）；右侧数字为（10px），使用等宽数字排列。当前项以灰底和加重文字区分。移动端使用带文字标签的选择器。详情标签页采用（11px）文字、间距（14px），当前项以下沿（2px）黑线及加重表示；支持左右箭头、Home 与 End 切换，并保留焦点。

### Interface rows / Detail

接口行的名称、分类、域和右对齐重载数保持单行，分类直接显示为表格文字，不使用标签组件。选中行使用 `selected`，名称加重。列表每批追加（60）个名称组，接近末尾时继续追加并保留已加载行；搜索与筛选重置为首批，深链接预先加载至选中行并定位。末尾以（10px）灰色文字说明已显示数量或全部加载完成，不使用分页控件。

选择接口后更新详情并聚焦详情区域，窄屏同时滚动到详情并暂停追加；“返回列表”回到选中行并恢复追加。切换重载后保留选择器焦点。详情按名称、操作、标签页、重载与正文组织，来源位置和完整签名保持可读、可复制。

### Resizable separators

分隔线可拖动、聚焦，悬停、键盘焦点与拖动时中央竖线变黑。左右方向键每次沿对应方向移动（10px），按住 Shift 时为（40px）；Home / End 设置当前允许的最小 / 最大宽度，Enter 或双击恢复默认值。使用 `separator` 语义、竖向方向与当前宽度属性；窄屏隐藏。

### Code / Evidence

代码块采用（11px / 1.6）等宽文字，内边距（7px 8px），保留换行及原始空白；长行在块内滚动。条件采用（10px / 1.6）等宽文字、内边距（4px 6px）并允许折行。证据说明使用浅灰平面、内边距（7px 8px）与（10px / 1.6）灰色文字；不使用暖色或成功色。报告中的待处理项使用原生 `details` 折叠。

## Do's and Don'ts

### Do:

- **Do** 复用前置令牌和原生控件，保持离线可用。
- **Do** 保持桌面统一顶栏、单行接口表与窄幅详情，并检查窄屏顺序阅读。
- **Do** 保留文字状态、可见焦点、选中反馈及完整可复制来源。
- **Do** 使用细线、灰阶浅底、字重与对齐组织紧凑信息。

### Don't:

- **Don't** 用装饰卡片、渐变或大图替代接口表格。
- **Don't** 用彩色状态或选中反馈暗示编译、运行或设备支持结论。
- **Don't** 引入在线字体、CDN 图标或运行依赖。
- **Don't** 因单行列表或窄详情而截断实际签名、条件和来源内容。
