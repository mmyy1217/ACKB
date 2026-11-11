---
name: CCE OPS
description: Huawei Ascend CCE 指令接口离线手册的现行视觉约定
colors:
  ink: "#202b30"
  muted: "#596970"
  accent: "#086b61"
  focus: "#128276"
  selected: "#eaf4f1"
  surface: "#fff"
  nav: "#f4f6f6"
  subtle: "#f8faf9"
  line: "#dce3e2"
  nav-active: "#e0eeea"
  nav-active-ink: "#075b51"
  nav-hover: "#e7edeb"
  row-hover: "#f2f7f5"
  row-line: "#edf0ef"
  input-line: "#bac9c5"
  button-hover-line: "#a7bab4"
  signature: "#234b43"
  callout-bg: "#f8f5ed"
  callout-ink: "#6d5126"
typography:
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "24px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.6
  button:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  caption:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.6
  title-mono:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.45
    letterSpacing: "-0.025em"
  row-mono:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.6
  code:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.9
rounded:
  default: "5px"
  compact: "3px"
spacing:
  micro: "4px"
  tight: "8px"
  control: "12px"
  cell: "14px"
  section: "16px"
  content: "20px"
  detail: "22px"
  group: "24px"
  page: "28px"
components:
  button-quiet:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.default}"
    padding: "6px 11px"
  button-text:
    textColor: "{colors.accent}"
    typography: "{typography.caption}"
    padding: "{spacing.micro}"
  search:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.default}"
    padding: "0 11px"
    height: "38px"
  navigation-item:
    textColor: "{colors.ink}"
    rounded: "{rounded.default}"
    padding: "9px 12px"
  navigation-item-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.nav-active-ink}"
  tag:
    backgroundColor: "{colors.nav}"
    textColor: "{colors.muted}"
    rounded: "{rounded.compact}"
    padding: "1px 6px"
  catalog-container:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.default}"
  catalog-row-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.accent}"
    typography: "{typography.row-mono}"
    padding: "9px 14px"
  detail-tab:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "10px 0"
  code-block:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.signature}"
    typography: "{typography.code}"
    rounded: "{rounded.default}"
    padding: "{spacing.cell}"
  callout:
    backgroundColor: "{colors.callout-bg}"
    textColor: "{colors.callout-ink}"
    rounded: "{rounded.default}"
    padding: "12px 14px"
---

# Design System: CCE OPS

## Overview

**Creative North Star: "器件规格表"**

冷白内容面、雾灰导航和深青选择色构成紧凑的技术阅读界面。细线、字号与对齐区分信息层级，接口标识符和签名采用等宽字体。视觉服务于 Huawei Ascend CCE 接口、条件与来源的核对。

本文件记录 `web/style.css`、`web/index.html` 和 `web/app.js` 的实际系统；令牌以前置 YAML 为准。页面构成与检索策略见 `.impeccable/surface-catalog.md`，产品边界见 `PRODUCT.md`。

**Key Characteristics:**

- 紧凑表格与按需阅读详情。
- 系统中文字体与技术等宽字体并用。
- 细线分区、浅色层次、文字说明状态。
- 原生控件、可见键盘焦点、离线自包含。

## Colors

### Primary

深青 `accent` 用于链接、选中接口名、当前标签页下划线与声明状态点；`focus` 专用于键盘焦点。`selected` 和 `nav-active` 分别承载表格与导航的选择背景，导航选中文字使用 `nav-active-ink`。

### Neutral

`surface` 是内容底色，`nav` 区分侧栏与标签，`subtle` 承载表头及代码。`ink` 表示主要内容，`muted` 表示说明和元数据。`line` 划分区域，`row-line` 划分紧凑表格行；`input-line` 和 `button-hover-line` 表达控件边界。`nav-hover`、`row-hover` 只反馈悬停。

暖灰黄 `callout-bg` 配合 `callout-ink` 说明证据限制；签名使用 `signature`。这些是内容语义色，不是第二套品牌强调色。

**The Evidence Rule.** 状态点、选中底色和提示色必须有对应文字；声明状态不能以颜色暗示已通过设备验证。

## Typography

中文说明使用系统无衬线栈，标识符、签名、路径与哈希使用系统等宽栈；不加载在线字体。基础正文使用 `body`，常见说明使用 `label`，元数据使用 `caption`。详情说明段落行高（1.8），最长（72ch）。

页面标题使用 `headline`；详情名称使用 `title-mono`，列表名称使用 `row-mono`，代码块使用 `code`。侧栏主项加重（650），标签页选中加重（600）。表头和次级提示为（10px）；不要将这一层级扩展到正文。品牌字重（750），用于名称本身。

## Layout

顶部栏高（64px）；工作区由侧栏（184px）与弹性主区组成。主区留白为上（26px）、左右（28px）。接口容器用一条外边界划分列表与详情，列宽为 `minmax(300px,.92fr)` / `minmax(360px,1.08fr)`；高度 `calc(100vh - 270px)`，最小（600px），两区独立滚动。表头固定，列表行内边距（9px 14px），详情主要内边距（20px 22px 26px）。

- 宽度至少（1600px）：主区左右留白（36px），列表与详情最小宽度调整为（420px / 550px）。
- 宽度至多（1180px）：侧栏（160px），主区左右留白（18px）；搜索独占一行，筛选同行；表格暂时隐藏“域”列，详情左右留白（18px）。
- 宽度至多（800px）：顶部（58px），侧栏替换为原生选择器；主区左右留白（16px），列表与详情顺序排列。列表滚动区高（180–360px），详情随页面展开；“域”列恢复。主标题（22px），详情名称（19px）；隐藏搜索快捷键提示。

间距是既有紧凑步长的组合，不强行套用统一的倍数网格。长标识符、条件、签名与哈希允许换行；报告表格可在自身容器横向滚动。

## Elevation & Depth

常态不使用投影。导航底色、代码浅底、单像素边界和选中底色承担层级。搜索聚焦时的 `0 0 0 1px var(--accent)` 是边界加粗；全局键盘焦点为（2px）描边、外偏移（3px）。底部通知使用深色实底，无阴影。

按钮仅过渡背景色（0.15s ease）；不移动或缩放。用户启用减少动态效果时禁用过渡并使用即时滚动。

## Shapes

控件、导航项、主容器、代码块与说明框使用 `default` 圆角；小标签和快捷键提示使用 `compact` 圆角。表格本身保持平直分隔线。状态点是直径（6px）的实心圆。图标为线性内联 SVG，不引入字体图标或位图依赖。

## Components

### Buttons

操作使用白底细边框的安静按钮；悬停变为导航浅底并加深边框。文字操作无边框，深青色，悬停加下划线。禁用按钮透明度（0.45），取消手形光标；保留可见焦点。

### Inputs / Fields

搜索框与筛选选择器高（38px）。搜索由边框容器包住图标、无边框输入和快捷键提示；焦点反馈作用于整个容器。筛选和重载均使用原生 `select`；重载选项采用等宽字体并限制在详情宽度内。

### Navigation

侧栏是纵向文字列表，右侧数字使用等宽数字排列。当前项以浅青底、深青字及加重区分。移动端使用带文字标签的选择器。详情标签页以文字和底边线表示当前项；支持左右箭头、Home 与 End 切换，并保留焦点。

### Tags / Containers

标签是不可交互的浅灰小矩形，补充接口族信息。主容器是细边框的列表和详情组合；不把每条接口包装成独立卡片。扫描报告沿用表格、分隔线和说明框。

### Interface rows / Detail

每行显示等宽接口名、次级说明及右对齐重载数；选中行使用 `selected`，名称加重并变为深青。选择接口后更新详情并聚焦详情区域，窄屏同时滚动到详情；切换重载后保留选择器焦点。详情按名称、操作、标签页、重载与正文组织，来源位置和完整签名保持可读、可复制。

### Code / Evidence

代码块保持换行及空白语义，长内容在块内折行。条件使用更紧凑的细边框浅底块。暖色说明框只解释尚未核验的边界，不代替具体状态文字。报告中的待处理项使用原生 `details` 折叠。

## Do's and Don'ts

### Do:

- **Do** 复用前置令牌和原生控件，保持离线可用。
- **Do** 为长技术标识符保留换行，并同时检查桌面与窄屏。
- **Do** 保留文字状态、可见焦点和选中反馈。
- **Do** 使用细线、浅底与字号组织紧凑信息。

### Don't:

- **Don't** 用装饰卡片、渐变或大图替代接口表格。
- **Don't** 仅凭绿色状态点表达编译、运行或设备支持结论。
- **Don't** 引入在线字体、CDN 图标或运行依赖。
- **Don't** 隐藏无法换行的签名、条件或来源以迁就列宽。
