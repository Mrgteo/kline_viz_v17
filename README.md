# K线相似度匹配可视化 v1.7

基于 [`ArvinLovegood/go-stock`](https://github.com/ArvinLovegood/go-stock) 的 `KLineChart.vue` 配色与布局，
用 Streamlit + streamlit-echarts 包装 `../app.py`（断板版 v1.7），无侵入接入。

## 目录结构

```
kline_viz_v17/
├── viz_app.py          # Streamlit 主入口（4视图：主图/缩略卡/详情/过滤树）
├── data_layer.py       # 动态加载 ../app.py，捕获 hard_filter 日志
├── kline_chart.py      # ECharts K 线（移植 go-stock 样式 + 算法标注）
├── waterfall.py        # 打分瀑布图
├── micro_compare.py    # 微型结构 5 格对比（graph 横向节点）
├── filter_tree.py      # 硬过滤降级树（bar + line 阶梯图）
└── requirements.txt    # streamlit / streamlit-echarts / pandas / akshare
```

## 快速开始

```bash
cd C:/Users/KaiPanLa/Desktop/File/Code/kline_viz_v17
pip install -r requirements.txt
streamlit run viz_app.py
```

默认浏览器打开 `http://localhost:8501`，左侧栏输入：

- 标的代码：`002342`
- 切面日：`2026-01-21`
- 数据区间：`20230101` ~ `20260331`

点击「执行匹配」即可。

## 核心模块

### viz_app.py — Streamlit 前端

4 个视图通过 session_state 切换：

| 视图 | 入口按钮 | 内容 |
|------|---------|------|
| 标的主图 | 📊 标的K线主图 | K线 + 涨停段绿背景 / 断板期红背景 / D1·D2·切面竖线 |
| 候选缩略卡栅格 | 🗂 候选缩略卡栅格 | 4列N行迷你K线卡片，标注得分/次日表现 |
| 详情对比 | 🎯 详情对比 | 标的/候选K线并排 + 微型结构图 + 指标表 + 打分瀑布 |
| 硬过滤降级树 | 🌳 硬过滤降级树 | bar+line 阶梯图展示每步剩余案例数 |

侧边栏还支持数据下载（逐只进度回调）和主题/形态标注切换。

### data_layer.py — 数据接入层

- `importlib` 动态加载同级 `app.py`，避免与 `klinesm/app.py` 命名冲突
- `download_daily_data_with_progress()` 逐只下载，通过回调实时报告进度
- `match()` 执行完整匹配，捕获 `hard_filter_with_downgrade` 的 stdout 日志
- `parse_filter_log()` 正则解析日志为结构化条目（过滤步骤 / 剩余数 / 扣分）

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

- `markArea`：涨停段绿背景 `SEG_AREA_COLOR` / 断板期红背景 `BREAK_AREA_COLOR`
- `markLine`：D1 橙黄竖线 / D2 紫色竖线 / 切面金黄竖线
- `markPoint`：重要形态标签（一字板/T字板/地天板/大阳线/十字星等）

`build_thumbnail_option()` 生成缩略卡极简 option（无MA/无成交量/保留切面线）。

### waterfall.py — 打分瀑布图

解析 `penalty_details`（形如 `['A类-10', '涨幅跨1档-20', 'D1精确+6']`），
用堆叠 bar 实现瀑布：
- 绿色柱 = 加分/得分基线
- 红色柱 = 扣分
- 起点"初始 100"，终点"最终 {final_score}"

### micro_compare.py — 微型结构 5 格对比

使用 `graph` 类型横向排列 5 个节点（最近涨停 / 中间特殊 / 前置前 / 前置 / 切面），
标的行蓝色，候选行红色，匹配则绿色。

### filter_tree.py — 硬过滤降级树

每根 bar 代表一个过滤步骤，红色 = 触发降级（A类扣分），
叠加 dashed line 展示剩余案例数趋势。

## app.py（父目录）— K线相似度匹配核心算法

完整断板匹配系统，包含：

- **CONFIG**：所有阈值/扣分/加分参数（`zt_threshold: 0.098` 等）
- **precompute_stock_data()**：预计算每根K线的形态/情绪/细分/量能状态
- **find_break_sequences()**：识别涨停段 + 断板期
- **build_break_case()**：构建单个断板案例（含微型结构、D1/D2/D3+指标）
- **build_all_break_cases()**：多进程构建案例库，缓存至 `case_library_break_v17.pkl`
- **hard_filter_with_downgrade()**：硬过滤（回撤比/距D1/中间涨停/微型结构/密度/D1）
- **calc_final_score()**：计算结构分（加分封顶40）
- **apply_distance_score()**：距离惩罚，输出最终得分

关键分类函数：
- `classify_cut_to_d1()` → 1天 / 2~3天 / 4~7天 / >7天
- `classify_max_rise()` → 低位 / 中位 / 高位 / 超高位
- `classify_height_retracement()` → 未回撤 / 小幅回撤 / 大幅回撤
- `classify_mid_zt_type()` → 无涨停 / 不连续涨停 / 连板
- `classify_density()` → 大涨主导 / 冷淡 / 极端博弈 / 大跌主导

## 缓存机制

- **日K缓存**：`./stock_cache/daily_{code}_{start}_{end}.pkl`
- **案例库缓存**：`./stock_cache/case_library_break_v17.pkl`
- Streamlit 端 `@st.cache_resource` / `@st.cache_data` 二级缓存
- 命中缓存时下载进度显示 `status: 'cache'`

## 算法标注图例

| 标注类型 | 颜色 | 说明 |
|---------|------|------|
| 涨停段 | 绿色半透明背景 | markArea，板块连续涨停区间 |
| 断板期 | 红色半透明背景 | markArea，D1到切面的整理期 |
| D1 | 橙黄虚线 | markLine，第一根断板日 |
| D2 | 紫色虚线 | markLine，D1次日 |
| 切面 | 金黄实线 | markLine，匹配切面日 |
| 形态标签 | 酒红 Pin 标记 | markPoint，重要K线形态名称 |