# K线相似度匹配可视化

基于 [`ArvinLovegood/go-stock`](https://github.com/ArvinLovegood/go-stock) 的 `KLineChart.vue` 配色与布局，
用 Streamlit + streamlit-echarts 包装核心算法，**双版本共存**，支持断板版（v1.7）和连板版（v2.3）一键切换。

## 目录结构

```
kline_viz_v17/
├── .claude/                # Claude Code 配置
├── .git/                   # Git 仓库
├── .gitattributes
├── .gitignore
├── __pycache__/           # Python 字节码缓存
├── stock_cache/           # 日K缓存 + 案例库缓存
│
├── app.py                  # 【v1.7 断板版】核心算法
├── app1.py                 # 【v2.3 连板版】核心算法
├── data_layer.py           # 【v1.7】数据接入层
├── data_layer_v23.py       # 【v2.3】数据接入层
│
├── kline_chart.py          # ECharts K 线构造器（go-stock 样式 + 算法标注）
├── waterfall.py            # 打分瀑布图
├── micro_compare.py        # 【v1.7】微型结构 5 格对比
├── micro_compare_v23.py    # 【v2.3】板型位置序列对比（N 格）
├── filter_tree.py          # 硬过滤降级树（bar + line 阶梯图）
│
├── viz_app.py              # Streamlit 主入口（3视图）
├── README.md               # 本文档
└── requirements.txt        # 依赖
```

## 快速开始

```bash
cd C:/Users/KaiPanLa/Desktop/File/Code/kline_viz_v17
pip install -r requirements.txt
streamlit run viz_app.py
```

默认浏览器打开 `http://localhost:8501`，左侧栏选择算法版本后输入：

- 标的代码：`002342`
- 切面日：`2026-01-21`（v1.7）/ `2025-04-09`（v2.3）
- 数据区间：`20230101` ~ `20260331`

点击「执行匹配」即可。

## 算法版本

| 版本 | 定位 | 核心理念 | 案例库缓存 |
|------|------|---------|-----------|
| **v1.7 断板版** | 涨停后断板股 | 找"断板后再度表现"的相似股 | `case_library_break_v17.pkl` |
| **v2.3 连板版** | 连续涨停股 | 找"连板过程中结构高度相似"的股 | `case_library_v23c.pkl` |

侧边栏 **v1.7 (断板版)** / **v2.3 (连板版)** 单选切换，清空缓存重新匹配。

---

## 核心模块

### viz_app.py — Streamlit 前端（3视图）

| 视图 | 入口按钮 | 内容 |
|------|---------|------|
| 标的主图 | 📊 标的K线主图 | K线 + 涨停段/断板期背景 + D1·D2·切面竖线 |
| 候选缩略卡栅格 | 🗂 候选缩略卡栅格 | 4列N行迷你K线卡片，标注得分/次日表现，点击跳转详情 |
| 详情对比 | 🎯 详情对比 | 标的/候选K线并排 + 微型结构图 + 指标表 + 打分瀑布 |

侧边栏还支持数据下载（逐只进度回调）和主题/形态标注切换。

### app.py — v1.7 断板版核心算法

**匹配逻辑**：标的找"某次断板"的切面日，在案例库中搜索结构高度相似的历史断板案例。

关键函数：
- `precompute_stock_data()` — 预计算每根K线的形态/情绪/细分/量能状态
- `find_break_sequences()` — 识别涨停段 + 断板期
- `build_break_case()` — 构建单个断板案例（含微型结构、D1/D2/D3+指标）
- `build_all_break_cases()` — 多进程构建案例库
- `hard_filter_with_downgrade()` — 硬过滤（回撤比/距D1/中间涨停/微型结构/密度/D1）
- `calc_final_score()` — 计算结构分（加分封顶40）
- `apply_distance_score()` — 距离惩罚，输出最终得分

关键分类函数：
- `classify_cut_to_d1()` → 1天 / 2~3天 / 4~7天 / >7天（**4档**，v1.7新）
- `classify_mid_zt_type()` → 无涨停 / 不连续涨停 / 连板（v1.7新增）
- `classify_max_rise()` → 低位 / 中位 / 高位 / 超高位
- `classify_height_retracement()` → 未回撤 / 小幅回撤 / 大幅回撤
- `classify_density()` → 大涨主导 / 冷淡 / 极端博弈 / 大跌主导

### app1.py — v2.3 连板版核心算法

**匹配逻辑**：标的找"某次连板"的切面日，在案例库中搜索连板结构高度相似的历史连板案例。

关键函数：
- `identify_zt_days()` — 标注涨停日
- `find_consecutive_zt_sequences()` — 找连续涨停段
- `classify_special_board()` — 特殊板型分类（一字板/T字板/地天板/大长腿/秒板/普通涨停）
- `build_case_from_sequence()` — 构建单个连板案例
- `build_all_cases()` — 构建案例库
- `pre_filter()` → `hard_filter()` → `conditional_filter()` → `calculate_final_score()` → `apply_distance_and_final_score()` — 五级过滤打分流程

关键分类函数：
- `classify_board_height()` → 低位(≤3板) / 中位(4~6板) / 高位(>6板)
- `classify_open_pct()` → 低开 / 正常开 / 高开（**v2.3新增开盘涨幅匹配**）
- `classify_first_day_state()` → 强势首板 / 分歧首板
- `classify_pre_rally()` → 低位启动 / 中位启动 / 高位启动
- `classify_combined_height()` → 综合高度低位 / 高位

### data_layer.py / data_layer_v23.py — 数据接入层

两套接口完全同形（同名同参数），通过 `viz_app.py` 侧边栏切换：

- `importlib` 动态加载对应 `app.py` / `app1.py`，避免命名冲突
- `download_daily_data_with_progress()` — 逐只下载，回调报告进度（status: 'cache' / 'ok' / 'fail'）
- `match()` — 执行完整匹配，捕获 stdout 日志并正则解析为结构化条目
- `find_segments_and_breaks()` — v1.7 返回 (rows, seq_start, segments, break_periods)；v2.3 无断板期，返回 (rows, seq_start, [(seq_start, seq_end)], None)

### kline_chart.py — K线 ECharts 构造器

参考 go-stock 配色方案：

| go-stock 元素 | 本项目实现 |
|---|---|
| `upColor #ec0000` / `downColor #00da3c` | `UP_COLOR` / `DOWN_COLOR`（A股红涨绿跌） |
| 双 grid（K线 50% + 成交量 15%） | `option.grid[0/1]` 上55% / 下15% |
| `MA5/10/20/30` | `_calc_ma(n, values)` 平滑曲线 |
| `visualMap` 成交量染色 | `seriesIndex=5`，涨跌对应红绿 |
| `dataZoom` inside + slider | 双 zoom，slider 位于 `top:92%` |
| `axisPointer.link` 十字线联动 | `xAxisIndex: all` 跨图联动 |

在 go-stock 基础上**新增算法标注**：

- `markArea`：涨停段绿背景 / 断板期红背景（v1.7）/ 连板段绿背景（v2.3）
- `markLine`：D1/D2/切面竖线（v1.7）/ 切面竖线（v2.3）
- `markPoint`：重要形态标签（一字板/T字板/地天板/大阳线等）

`build_thumbnail_option()` 生成缩略卡极简 option（无MA/无成交量/保留切面线）。

### waterfall.py — 打分瀑布图

解析 `penalty_details`（形如 `['A类-10', '涨幅跨1档-20', 'D1精确+6']`），
用堆叠 bar 实现瀑布：
- 绿色柱 = 加分/得分基线
- 红色柱 = 扣分
- 起点"初始 100"，终点"最终 {final_score}"

### micro_compare.py — v1.7 微型结构 5 格对比

使用 `graph` 类型横向排列 5 个节点：

| 节点 | 对应字段 |
|------|---------|
| 最近涨停 | `nearest_zt_subdivision` |
| 中间特殊 | `mid_special_subdivision` |
| 前置前 | `pre_prev_subdivision` |
| 前置 | `nearest_special_subdivision` |
| 切面 | `cut_subdivision` |

标的行蓝色，候选行红色，匹配则绿色。

### micro_compare_v23.py — v2.3 板型位置序列对比

使用 `graph` 类型按**板高度（N格）**横向排列：

- 节点数 = `max(target.board_height, cand.board_height)`
- 每格显示"第N板 + 板型"（一字板/T字板/地天板/大长腿/秒板/普通涨停）
- 颜色规则：
  - 完全相同 → 绿色
  - 同组（加速组 `一字板/T字板/秒板` 或 换手组 `普通涨停/大长腿/地天板`）→ 蓝色
  - 不同 → 红色
  - 板高不足该格 → 灰色"无"
- 最后一格（切面日）金色加粗边框

### filter_tree.py — 硬过滤降级树

每根 bar 代表一个过滤步骤，红色 = 触发降级，叠加 dashed line 展示剩余案例数趋势。

---

## v1.7 与 v2.3 核心差异

| 维度 | v1.7 断板版 | v2.3 连板版 |
|------|------------|------------|
| 匹配场景 | 断板后再度表现 | 连板进行中 |
| 案例单位 | 每次断板事件 | 每次连板事件 |
| 核心概念 | 涨停段 + 断板期 + D1/D2/D3 | 连续涨停段 + 板高度 + 特殊板型 |
| 距D1分档 | **4档**：1天/2~3天/4~7天/>7天 | 无此概念 |
| 连板高度 | 无 | **3档**：低位≤3/中位4~6/高位>6 |
| 中间涨停 | 有（新增于v1.7） | 无 |
| 开盘涨幅 | 无 | 有（新增于v2.3） |
| 微型结构 | 5格横向对比 | N格板型位置序列 |
| 特殊板型 | 无细分 | 一字板/T字板/地天板/大长腿/秒板 |
| 过滤流程 | 硬过滤→降级→打分→距离 | 预过滤→硬过滤→条件过滤→打分→距离 |

---

## 缓存机制

| 类型 | 文件 | 说明 |
|------|------|------|
| 日K缓存 | `stock_cache/daily_{code}_{start}_{end}.pkl` | akshare 原始数据 |
| v1.7 案例库 | `stock_cache/case_library_break_v17.pkl` | 断板版案例 |
| v2.3 案例库 | `stock_cache/case_library_v23c.pkl` | 连板版案例 |
| Streamlit 缓存 | `@st.cache_resource` / `@st.cache_data` | 内存二级缓存 |

切换算法版本时需点击"下载数据"清空 Streamlit 缓存。

---

## 算法标注图例（v1.7）

| 标注类型 | 颜色 | 说明 |
|---------|------|------|
| 涨停段 | 绿色半透明背景 | markArea，连续涨停区间 |
| 断板期 | 红色半透明背景 | markArea，D1到切面的整理期 |
| D1 | 橙黄虚线 | markLine，第一根断板日 |
| D2 | 紫色虚线 | markLine，D1次日 |
| 切面 | 金黄实线 | markLine，匹配切面日 |
| 形态标签 | Pin 标记 | markPoint，重要K线形态 |

## 算法标注图例（v2.3）

| 标注类型 | 颜色 | 说明 |
|---------|------|------|
| 连板段 | 绿色半透明背景 | markArea，连续涨停区间 |
| 切面 | 金黄实线 | markLine，匹配切面日 |
| 形态标签 | Pin 标记 | markPoint，重要K线形态 |