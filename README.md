# K线相似度匹配可视化

基于 [`ArvinLovegood/go-stock`](https://github.com/ArvinLovegood/go-stock) 的 `KLineChart.vue` 配色与布局，
用 Streamlit + streamlit-echarts 包装核心算法，**双版本共存**，支持断板版（v2.0）和连板版（v2.3）一键切换。

## 目录结构

```
kline_viz_v17/
├── viz_app.py              # Streamlit 主入口（2视图：主图 + 详情对比）
├── app.py                  # 【v2.0 断板版】核心算法
├── app1.py                 # 【v2.3 连板版】核心算法
├── data_layer.py           # 【v2.0】数据接入层（动态加载 app.py）
├── data_layer_v23.py       # 【v2.3】数据接入层（动态加载 app1.py）
│
├── kline_chart.py          # ECharts K 线构造器（go-stock 样式 + 算法标注）
├── waterfall.py            # 打分瀑布图
├── micro_compare.py        # 【v2.0】微型结构 5 格横向对比（ECharts graph）
├── micro_compare_v23.py    # 【v2.3】板型位置序列对比 N 格（HTML/CSS Grid）
├── filter_tree.py          # 硬过滤降级树（bar + line 阶梯图）
│
├── prebuild_case_library.py        # 离线预构建断板版案例库
├── _build_case_library_v22.py      # 从日K缓存构建 v22 案例库（多进程）
├── _build_recommend_pool_v22.py    # 构建推荐池 v22 静态匹配缓存
│
├── 断板v2.py / 断板v2(1).py / 断板v2(2).py   # 断板版算法的迭代版本参考
├── app_project_backup_before_v2_2.py         # v2.2 之前的项目备份
├── app_v17_backup.py / app_v20_backup.py     # 历史版本备份
│
├── stock_cache/            # 日K缓存 + 案例库缓存 + 推荐池静态缓存
├── requirements.txt        # 依赖
└── README.md               # 本文档
```

## 快速开始

```bash
cd C:/Users/KaiPanLa/Desktop/File/Code/kline_viz_v17
pip install -r requirements.txt
streamlit run viz_app.py
```

默认浏览器打开 `http://localhost:8501`，左侧栏选择算法版本后输入：

- 标的代码：`002342`
- 切面日：`2026-01-21`（v2.0）/ `2025-04-09`（v2.3）
- 数据区间：`20230101` ~ `20260601`

点击「执行匹配」即可。

## 算法版本

| 版本 | 定位 | 核心理念 | 案例库缓存 |
|------|------|---------|-----------|
| **v2.0 断板版** | 涨停后断板股 | 找"断板后再度表现"的相似股 | `case_library_break_v22.pkl` |
| **v2.3 连板版** | 连续涨停股 | 找"连板过程中结构高度相似"的股 | `case_library_v23c.pkl` |

侧边栏 **v2.0 (断板版)** / **v2.3 (连板版)** 单选切换，清空缓存重新匹配。

---

## 核心模块

### viz_app.py — Streamlit 前端（2视图）

| 视图 | 入口按钮 | 内容 |
|------|---------|------|
| 标的主图 | 📊 标的K线主图 | K线 + 研究范围背景 + 切面标注 + MA均线 + 成交量 |
| 详情对比 | 🎯 相似匹配对比 | 标的/候选K线瀑布卡片（得分≥60优先展示），支持下拉跳转锚点 |

侧边栏功能：
- **推荐池**（仅v2.0）：10个预标注高质量样本，快捷填入标的+切面日
- **数据下载**：逐只下载日K，回调进度条
- **缓存管理**：一键清空 Streamlit 内存缓存（不删磁盘pkl）
- **主题/形态标注**：深色主题切换 + K线形态标签开关

UI 设计包含完整的深色主题 CSS（`#0b1220` 底色），覆盖 BaseWeb 组件（侧边栏、按钮、日期选择器、日历弹出层、DataFrame 等），并注入 JS 将日历中文化。

### app.py — v2.0 断板版核心算法

**匹配逻辑**：标的找"某次断板"的切面日，在案例库中搜索结构高度相似的历史断板案例。

关键函数：
- `precompute_stock_data()` — 预计算每根K线的形态v2 / 情绪 / 细分 / 量能状态
- `find_break_sequences()` — 识别涨停段 + 断板期 + 研究范围
- `build_break_case()` — 构建单个断板案例（含M-cut/M-start微型结构、D1指标等）
- `build_target_break_case()` — 构造标的断板案例
- `build_all_break_cases()` — 多进程构建案例库（Streamlit下强制单进程）
- `hard_filter_with_downgrade()` — 硬过滤+降级（A类/B类/C类逐级降级扣分）
- `calc_a_score()` ~ `calc_e_score()` — A~E 五组结构评分
- `calc_final_score()` — 汇总A~E分并应用封顶
- `apply_distance_score()` — 距离惩罚，输出最终得分

关键分类函数：
- `classify_d1_distance()` → **4档**：1天 / 2~3天 / 4~7天 / >7天
- `classify_max_rise()` → 低位 / 中位 / 高位 / 超高位
- `classify_height_retracement()` → 未回撤 / 小幅回撤 / 大幅回撤
- `classify_density()` → 大涨主导 / 冷淡 / 极端博弈 / 大跌主导
- `classify_volume_v2()` → 缩量 / 平量 / 温和放量 / 明显放量 / 巨量
- `classify_kline_v2()` → K线形态v2分类（含开盘涨幅、实体比例、振幅等多维）
- `match_kline_v2()` → K线v2匹配（精确/近似/情绪/不匹配）

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
- `classify_open_pct()` → 低开 / 正常开 / 高开（v2.3新增开盘涨幅匹配）
- `classify_first_day_state()` → 强势首板 / 分歧首板
- `classify_pre_rally()` → 低位启动 / 中位启动 / 高位启动
- `classify_combined_height()` → 综合高度低位 / 高位

### data_layer.py — v2.0 数据接入层

通过 `importlib` 动态加载 `app.py`，避免命名冲突。关键设计：

- `_load_app_module()` → 注册为 `matcher_app_v17` 和 `app`（兼容多进程 pickle）
- **路径解析**：自动将相对路径转为绝对路径，适配 Streamlit 非项目根目录启动
- **config 同步**：确保 `CONFIG` 改动回写到 `APP.CONFIG`
- **兼容补丁**：为缺失的 `match_subdivision` / `match_approx` / `match_emotion` / `get_d1_decay` / `get_mcut_weight` 提供默认实现
- `load_daily_data()` — 纯缓存快路，只读不改
- `download_daily_data_with_progress()` — 逐只下载+进度回调
- `match()` — 执行完整匹配，捕获 stdout 日志并解析
- `get_mcut_compare_payload()` — M-cut 3天窗口对比载荷
- `find_segments_and_breaks()` — 返回(rows, seq_start, segments, break_periods)

### data_layer_v23.py — v2.3 数据接入层

与 `data_layer.py` 接口完全同形（同名同参数），通过侧边栏切换。关键差异：

- 动态加载 `app1.py`，注册为 `matcher_app_v23`
- 打补丁兼容新版 `daily_{code}.pkl` 命名（原 app1.py 只认旧命名）
- 打补丁 `batch_download_daily_data` 避免缓存命中时空 sleep
- `precompute_rows()` → 用 `identify_zt_days` + `classify_special_board` 自行拼装
- `find_segments_and_breaks()` → 无断板期，返回 `(rows, seq_start, [(seq_start, seq_end)], None)`

### kline_chart.py — K线 ECharts 构造器

参考 go-stock 配色方案：

| go-stock 元素 | 本项目实现 |
|---|---|
| `upColor #ec0000` / `downColor #00da3c` | `UP_COLOR` / `DOWN_COLOR`（A股红涨绿跌） |
| 双 grid（K线 54% + 成交量 15%） | `option.grid[0/1]` 上54% / 下15% |
| `MA5/10/20/30` | `_calc_ma(n, values)` 平滑曲线 |
| `visualMap` 成交量染色 | `seriesIndex=5`，涨跌对应红绿 |
| `dataZoom` inside + slider | 双 zoom，slider 位于 `top:92%` |
| `axisPointer.link` 十字线联动 | `xAxisIndex: all` 跨图联动 |

算法标注（通过开关控制显隐）：

| 标注 | 开关 | 颜色 |
|------|------|------|
| 研究范围框 | `show_research_range`（默认True） | 白色半透明 + 阴影 |
| 切面标注 | `_SHOW_CUT_ANCHOR`（默认True） | 金黄气泡标签 |
| 涨停段背景 | `_SHOW_SEG_AREAS`（默认False） | 红半透明 markArea |
| 断板期背景 | `_SHOW_BREAK_AREAS`（默认False） | 绿半透明 markArea |
| D1/D2标注 | `_SHOW_D1_ANCHOR` / `_SHOW_D2_ANCHOR`（默认False） | 橙黄/紫色气泡 |
| M-cut窗口 | `_SHOW_MCUT_AREA`（默认False） | 金黄半透明 |
| M-start窗口 | `_SHOW_MSTART_AREA`（默认False） | 蓝半透明 |
| 形态标签 | `annotate_forms`（UI开关） | pin标记 |

`build_thumbnail_option()` 生成缩略卡极简 option（无MA/无成交量/保留切面线）。

### waterfall.py — 打分瀑布图

解析 `penalty_details`（形如 `['A类-10', 'D1精确+6']`），用堆叠 bar 实现瀑布：
- 绿色柱 = 加分/得分基线
- 红色柱 = 扣分
- 起点"初始 100"，终点"最终 {final_score}"

### micro_compare.py — v2.0 微型结构 5 格对比

使用 ECharts `graph` 类型横向排列 5 个节点：

| 节点 | 对应字段 |
|------|---------|
| 最近涨停 | `nearest_zt_subdivision` |
| 中间特殊 | `mid_special_subdivision` |
| 前置前 | `pre_prev_subdivision` |
| 前置 | `nearest_special_subdivision` |
| 切面 | `cut_subdivision` |

标的行蓝色，候选行红色，匹配则绿色。

### micro_compare_v23.py — v2.3 板型位置序列对比

使用 HTML/CSS Grid（`auto-fit + minmax`）自适应宽度。按**板高度（N格）**横向排列：

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

## 推荐池系统（v2.0 专属）

侧边栏「⭐ 推荐池」提供 10 个预标注高质量样本：

| 代码 | 名称 | 切面日 | 标签 |
|------|------|--------|------|
| 601991 | 大唐发电 | 2026-05-15 | 高位断板反抽 |
| 002421 | 达实智能 | 2026-05-28 | 高位断板反抽 |
| 002918 | 蒙娜丽莎 | 2026-05-20 | 高位断板A杀 |
| 601991 | 大唐发电 | 2026-05-20 | 高位异动大跌 |
| 002081 | 金螳螂 | 2026-05-18 | 人气股多波 |
| 002342 | 巨力索具 | 2026-01-19 | 中位断板止跌 |
| 002342 | 巨力索具 | 2026-01-21 | 中位断板反抽 |
| 600439 | 瑞贝卡 | 2024-10-31 | 低位断板反包 |
| 002114 | 罗平 | 2025-12-01 | 低位断板反抽 |
| 000066 | 中国长城 | 2026-05-11 | 低位断板止跌 |

**静态缓存机制**：推荐池样本第一次匹配后结果写入 `stock_cache/recommend_pool_v22/{code}_{date}.pkl`，下次点击秒出（毫秒级）。

`_build_recommend_pool_v22.py` 可离线批量生成全部推荐池静态缓存。

---

## v2.0 与 v2.3 核心差异

| 维度 | v2.0 断板版 | v2.3 连板版 |
|------|------------|------------|
| 匹配场景 | 断板后再度表现 | 连板进行中 |
| 案例单位 | 每次断板事件 | 每次连板事件 |
| 核心概念 | 涨停段 + 断板期 + D1 + M-cut/M-start | 连续涨停段 + 板高度 + 特殊板型 |
| 距D1分档 | **4档**：1天/2~3天/4~7天/>7天 | 无此概念 |
| 连板高度 | 无 | **3档**：低位≤3/中位4~6/高位>6 |
| 中间涨停 | 有 | 无 |
| 开盘涨幅 | 无 | 有（v2.3新增） |
| 微型结构 | 5格横向对比（M-cut 3天窗口） | N格板型位置序列 |
| 特殊板型 | K线v2细分（64种） | 一字板/T字板/地天板/大长腿/秒板 |
| 过滤流程 | 硬过滤→降级→A~E打分→距离 | 预过滤→硬过滤→条件过滤→打分→距离 |
| K线匹配 | `match_kline_v2()` 精确/近似/情绪/不匹配 | `classify_special_board()` 板型6分类 |

---

## 缓存机制

| 类型 | 文件 | 说明 |
|------|------|------|
| 日K缓存 | `stock_cache/daily_{code}.pkl` | akshare 原始数据，无日期段命名 |
| v2.0 案例库 | `stock_cache/case_library_break_v22.pkl` | 断板版案例 |
| v2.3 案例库 | `stock_cache/case_library_v23c.pkl` | 连板版案例 |
| 推荐池静态缓存 | `stock_cache/recommend_pool_v22/{code}_{date}.pkl` | 推荐池匹配结果秒开 |
| Streamlit 缓存 | `@st.cache_resource` / `@st.cache_data` | 内存二级缓存（股票列表/日K/案例库/匹配结果） |

切换算法版本时需点击"清空缓存"或重新下载数据刷新 Streamlit 缓存。

---

## 预构建脚本

| 脚本 | 用途 | 输出 |
|------|------|------|
| `prebuild_case_library.py` | 离线预构建断板版案例库 | `case_library_break_v20.pkl` |
| `_build_case_library_v22.py` | 从日K缓存构建 v22 案例库（多进程） | `case_library_break_v22.pkl` |
| `_build_recommend_pool_v22.py` | 批量构建推荐池静态缓存 | `recommend_pool_v22/{code}_{date}.pkl` |

预构建脚本在普通终端运行（非 Streamlit），可正常使用多进程。Streamlit 下 `build_all_break_cases` 被强制设为单进程以避免 Windows spawn 死锁。

---

## 隐藏功能（代码保留，通过开关恢复）

- **M-cut 3天横条对比**：详情对比页面的微型结构彩色条（`_SHOW_MCUT_BAR = False`）
- **M-cut / M-start 窗口标记**：K线图上的半透明背景区域（`_SHOW_MCUT_AREA / _SHOW_MSTART_AREA = False`）
- **涨停段/断板期背景**：K线图的红绿 markArea（`_SHOW_SEG_AREAS / _SHOW_BREAK_AREAS = False`）
- **D1/D2 标注**：橙黄/紫色气泡标签（`_SHOW_D1_ANCHOR / _SHOW_D2_ANCHOR = False`）
- **微型结构对比图**：ECharts graph 5格图（`SHOW_MICRO_AND_INDICATORS = False`）
- **打分瀑布图**：详情卡片的瀑布打分（`SHOW_SCORE_DEBUG_SECTIONS = False`）
- **顶部 metric 卡片**：候选代码/得分/距离扣分/次日表现（`_SHOW_TOP_METRICS = False`）

将对应变量改为 `True` 即可恢复显示。
