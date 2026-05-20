"""
K线相似度匹配系统 v1.7 - Streamlit 可视化前端
参考 ArvinLovegood/go-stock 的 K 线样式。

运行：
    cd C:/Users/KaiPanLa/Desktop/File/Code/kline_viz_v17
    streamlit run viz_app.py
"""
from __future__ import annotations

import math
from datetime import date
import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts

import data_layer as dl
from kline_chart import build_kline_option, build_thumbnail_option
from waterfall import build_waterfall_option
from micro_compare import build_micro_compare_option

st.set_page_config(
    page_title="K线相似度匹配 v1.7",
    page_icon="📈",
    layout="wide",
)

# ============== 全局 CSS：提升对比度、字号、按钮可点击范围 ==============
st.markdown(
    """
    <style>
        :root {
            --bg-page: #0b1220;
            --bg-card: #1a2236;
            --bg-card-hi: #232c44;
            --text-main: #f1f5f9;
            --text-sub: #cbd5e1;
            --text-muted: #94a3b8;
            --accent: #fbbf24;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-blue: #60a5fa;
            --border: #334155;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background-color: var(--bg-page) !important;
            color: var(--text-main) !important;
            font-size: 15px;
        }
        .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1600px; }

        /* 顶部白色 toolbar / Deploy 按钮整条隐藏 */
        [data-testid="stHeader"], header[data-testid="stHeader"] {
            background: transparent !important;
            height: 0 !important;
        }
        [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
        #MainMenu, footer { display: none !important; }

        /* 标题颜色 */
        h1, h2, h3, h4, h5, h6 { color: var(--text-main) !important; font-weight: 600 !important; }
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.4rem !important; }
        h3 { font-size: 1.2rem !important; }
        p, span, div, label, .stMarkdown { color: var(--text-main) !important; }

        /* caption 加深 */
        [data-testid="stCaptionContainer"], .caption, small {
            color: var(--text-sub) !important;
            font-size: 13px !important;
        }

        /* metric 卡片 */
        [data-testid="stMetric"] {
            background: var(--bg-card) !important;
            padding: 12px 16px !important;
            border-radius: 8px !important;
            border: 1px solid var(--border) !important;
        }
        [data-testid="stMetricLabel"] {
            color: var(--text-sub) !important;
            font-size: 13px !important;
            font-weight: 500 !important;
        }
        [data-testid="stMetricValue"] {
            color: var(--accent) !important;
            font-size: 22px !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricDelta"] {
            color: var(--text-sub) !important;
            font-size: 12px !important;
        }

        /* 侧边栏 */
        [data-testid="stSidebar"] {
            background-color: #0e1729 !important;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] * { color: var(--text-main) !important; }
        [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
            font-size: 14px !important;
        }
        [data-testid="stSidebar"] label { font-size: 13px !important; color: var(--text-sub) !important; }

        /* 按钮 */
        .stButton > button {
            background: var(--bg-card-hi) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 8px 14px !important;
            border-radius: 6px !important;
            transition: all 0.15s ease;
        }
        .stButton > button:hover {
            background: var(--accent) !important;
            color: #0b1220 !important;
            border-color: var(--accent) !important;
        }
        .stButton > button[kind="primary"] {
            background: var(--accent) !important;
            color: #0b1220 !important;
            border-color: var(--accent) !important;
            font-weight: 700 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: #f59e0b !important;
        }

        /* 选择框/输入框 */
        .stSelectbox > div > div, .stTextInput > div > div > input {
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
            font-size: 14px !important;
        }

        /* 日期选择器 */
        [data-testid="stDateInput"] input,
        [data-testid="stDateInput"] button {
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
            font-size: 14px !important;
        }
        [data-testid="stDateInput"] button:hover {
            background: var(--bg-card-hi) !important;
            border-color: var(--accent) !important;
        }
        [data-testid="stDateInput"] input::-webkit-calendar-picker-indicator {
            filter: invert(0.85);
            cursor: pointer;
        }
        /* 日期选择器下拉面板（Chrome/Safari） */
        input[type="date"] {
            color-scheme: dark;
        }

        /* DataFrame 表格 */
        [data-testid="stDataFrame"] {
            background: var(--bg-card) !important;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        [data-testid="stDataFrame"] * {
            color: var(--text-main) !important;
            font-size: 13px !important;
        }
        [data-testid="stDataFrame"] thead th {
            background: var(--bg-card-hi) !important;
            color: var(--accent) !important;
            font-weight: 600 !important;
        }

        /* expander */
        [data-testid="stExpander"] {
            background: var(--bg-card) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }
        [data-testid="stExpander"] summary, [data-testid="stExpander"] p {
            color: var(--text-main) !important;
            font-size: 14px !important;
        }
        [data-testid="stExpander"] details > div {
            background: var(--bg-card) !important;
        }
        [data-testid="stExpander"] * {
            color: var(--text-main) !important;
        }

        /* JSON 代码块（案例字段一览） */
        [data-testid="stJson"] {
            background: #0e1729 !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            padding: 10px !important;
        }
        [data-testid="stJson"] * {
            color: var(--text-main) !important;
            font-size: 13px !important;
            font-family: "JetBrains Mono", "Consolas", "Menlo", monospace !important;
        }
        /* react-json-view 的键/字符串/数字单独着色 */
        [data-testid="stJson"] .object-key,
        [data-testid="stJson"] .object-key-val span:first-child {
            color: var(--accent) !important;
        }
        [data-testid="stJson"] .string-value { color: #86efac !important; }
        [data-testid="stJson"] .number-value { color: #93c5fd !important; }
        [data-testid="stJson"] .boolean-value { color: #f472b6 !important; }
        [data-testid="stJson"] .null-value { color: #fca5a5 !important; }
        [data-testid="stJson"] .node-ellipsis { color: var(--text-sub) !important; }

        code, pre {
            background: #0e1729 !important;
            color: var(--accent) !important;
            font-size: 13px !important;
        }

        /* 顶部导航栏 */
        .nav-bar {
            display: flex;
            gap: 8px;
            background: var(--bg-card);
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 16px;
            border: 1px solid var(--border);
        }

        /* 候选卡片包装 */
        .cand-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 12px;
        }
        .cand-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 4px;
        }
        .cand-score-high { color: #22c55e !important; }
        .cand-score-mid { color: #fbbf24 !important; }
        .cand-score-low { color: #ef4444 !important; }
        .cand-meta {
            color: var(--text-sub);
            font-size: 12px;
            margin-top: 4px;
        }

        /* divider */
        hr { border-color: var(--border) !important; }

        /* tooltip / info 提示 */
        [data-testid="stAlert"] {
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            border-left: 4px solid var(--accent-blue) !important;
            font-size: 14px !important;
        }

        /* ========== date_input 触发框 + 弹出日历（深色） ========== */
        /* 触发框 */
        [data-testid="stDateInput"] > div,
        [data-testid="stDateInput"] input,
        [data-baseweb="input"] {
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
            font-size: 14px !important;
        }
        [data-testid="stDateInput"] input::placeholder { color: var(--text-muted) !important; }
        [data-testid="stDateInput"] svg { fill: var(--text-sub) !important; color: var(--text-sub) !important; }

        /* 弹出层根容器（覆盖 BaseWeb popover / calendar 的所有内部 div / button） */
        [data-baseweb="popover"],
        [data-baseweb="popover"] *,
        [data-baseweb="calendar"],
        [data-baseweb="calendar"] *,
        [data-baseweb="datepicker"],
        [data-baseweb="datepicker"] * {
            background-color: transparent !important;
            color: var(--text-main) !important;
            border-color: var(--border) !important;
        }
        /* 弹层最外层背景：必须实色，否则透出页面白色 */
        [data-baseweb="popover"] > div,
        [data-baseweb="popover"] [role="dialog"],
        [data-baseweb="calendar"] {
            background-color: var(--bg-card) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            box-shadow: 0 6px 24px rgba(0,0,0,0.4) !important;
        }
        /* 日期月份网格容器（占位格也在内）强制深底 */
        [data-baseweb="calendar"] [role="grid"],
        [data-baseweb="calendar"] [role="row"],
        [data-baseweb="calendar"] [role="presentation"],
        [data-baseweb="calendar"] [role="row"] > *,
        [data-baseweb="calendar"] [role="grid"] > *,
        [data-baseweb="calendar"] [role="grid"] * {
            background-color: var(--bg-card) !important;
        }

        /* header（月份/年份/切换箭头）——它通常是 calendar 第一个直接子 div */
        [data-baseweb="calendar"] > div:first-child {
            background-color: var(--bg-card-hi) !important;
            border-bottom: 1px solid var(--border) !important;
            padding: 6px 8px !important;
        }
        [data-baseweb="calendar"] > div:first-child * {
            background-color: transparent !important;
            color: var(--text-main) !important;
        }
        /* 月/年切换 button */
        [data-baseweb="calendar"] button,
        [data-baseweb="popover"] button {
            background-color: transparent !important;
            color: var(--text-main) !important;
            border: none !important;
            box-shadow: none !important;
        }
        [data-baseweb="calendar"] button:hover,
        [data-baseweb="popover"] button:hover {
            background-color: var(--accent) !important;
            color: #0b1220 !important;
        }
        [data-baseweb="calendar"] button svg,
        [data-baseweb="popover"] button svg {
            fill: var(--text-main) !important;
            color: var(--text-main) !important;
        }
        [data-baseweb="calendar"] button:hover svg,
        [data-baseweb="popover"] button:hover svg {
            fill: #0b1220 !important;
        }

        /* 星期表头 */
        [data-baseweb="calendar"] [role="columnheader"] {
            color: var(--text-sub) !important;
            background-color: transparent !important;
            font-weight: 600 !important;
        }

        /* 日期格 */
        [data-baseweb="calendar"] [role="gridcell"] {
            background-color: transparent !important;
            color: var(--text-main) !important;
            border-radius: 6px !important;
        }
        [data-baseweb="calendar"] [role="gridcell"]:hover {
            background-color: var(--bg-card-hi) !important;
            color: var(--accent) !important;
        }
        /* 选中日：金色（覆盖 BaseWeb 默认红色） */
        [data-baseweb="calendar"] [aria-selected="true"],
        [data-baseweb="calendar"] [aria-selected="true"] *,
        [data-baseweb="calendar"] [data-selected="true"],
        [data-baseweb="calendar"] [data-selected="true"] * {
            background-color: var(--accent) !important;
            color: #0b1220 !important;
            font-weight: 700 !important;
            border-radius: 50% !important;
        }
        /* 今天 */
        [data-baseweb="calendar"] [aria-current="date"]:not([aria-selected="true"]) {
            border: 1px solid var(--accent) !important;
            color: var(--accent) !important;
        }
        /* 非本月 / 禁用 */
        [data-baseweb="calendar"] [aria-disabled="true"] {
            color: var(--text-muted) !important;
            opacity: 0.4 !important;
        }

        /* 月/年下拉 select 列表 */
        [data-baseweb="select"] > div,
        [data-baseweb="menu"],
        [data-baseweb="list"] {
            background-color: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border) !important;
        }
        [data-baseweb="menu"] li:hover,
        [data-baseweb="list"] li:hover {
            background-color: var(--bg-card-hi) !important;
            color: var(--accent) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="加载股票列表...")
def cached_stock_list():
    return dl.load_stock_list()


@st.cache_resource(show_spinner="加载日K数据（首次较慢，命中缓存秒开）...")
def cached_daily_data(start_date: str, end_date: str):
    si = cached_stock_list()
    ad = dl.load_daily_data(si, start_date, end_date)
    return ad, si


@st.cache_resource(show_spinner="加载/构建案例库...")
def cached_case_library(start_date: str, end_date: str):
    ad, si = cached_daily_data(start_date, end_date)
    return dl.load_case_library(ad, si)


@st.cache_data(show_spinner="执行匹配...")
def cached_match(stock_code: str, cut_date_str: str,
                  start_date: str, end_date: str, top_n: int):
    ad, si = cached_daily_data(start_date, end_date)
    cl = cached_case_library(start_date, end_date)
    return dl.match(stock_code, cut_date_str, ad, si, cl, top_n=top_n)


with st.sidebar:
    st.title("📈 K线相似匹配 v1.7")
    st.caption("参考 go-stock 配色 · 红涨绿跌 · ECharts")

    stock_code = st.text_input("标的股票代码", value="002342")
    cut_date = st.date_input("切面日", value=date(2026, 1, 21))
    cut_date_str = cut_date.strftime("%Y-%m-%d")
    start_date = st.date_input("数据起始日", value=date(2023, 1, 1))
    end_date = st.date_input("数据结束日", value=date(2026, 5, 19))
    top_n = st.slider("Top N 候选", 10, 100, 50, step=5)

    st.divider()
    dark = st.toggle("深色主题", value=True)
    annotate_forms = st.toggle("标注 K 线形态", value=False)

    run = st.button("🚀 执行匹配", type="primary", use_container_width=True)

    st.divider()
    st.markdown("#### ⬇️ 下载/更新缓存数据")
    dl_start = st.date_input("下载起始日", value=date(2023, 1, 1), key="dl_start")
    dl_end = st.date_input("下载结束日", value=date(2026, 5, 19), key="dl_end")
    do_download = st.button("📥 下载数据", use_container_width=True, key="btn_download")
    dl_prog_slot = st.empty()
    dl_status_slot = st.empty()
    dl_msg_slot = st.empty()

if do_download:
    with st.sidebar:
        try:
            si_list = cached_stock_list()
            total = len(si_list)
            bar = dl_prog_slot.progress(0.0, text=f"准备下载 {total} 只股票...")

            def _cb(done, total, code, status, success, failed, from_cache):
                pct = done / max(total, 1)
                bar.progress(pct, text=f"{done}/{total}  当前 {code} [{status}]")
                dl_status_slot.caption(
                    f"成功 {success}（缓存 {from_cache}） · 失败 {failed} · 进度 {pct:.1%}"
                )

            dl_start_str = dl_start.strftime("%Y%m%d")
            dl_end_str = dl_end.strftime("%Y%m%d")
            stats = dl.download_daily_data_with_progress(
                si_list, dl_start_str, dl_end_str, progress_cb=_cb
            )
            bar.progress(1.0, text="✅ 下载完成")
            dl_msg_slot.success(
                f"下载完成：成功 {stats['success']}（缓存 {stats['from_cache']}） / 失败 {stats['failed']}"
            )
            cached_daily_data.clear()
            cached_case_library.clear()
        except Exception as e:
            dl_msg_slot.error(f"下载失败：{e}")

if not run and "match_result" not in st.session_state:
    st.info("⬅️ 请在左侧输入标的并点击「执行匹配」")
    st.stop()

if run:
    try:
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        result = cached_match(stock_code, cut_date_str, start_str, end_str, top_n)
        st.session_state["match_result"] = result
        st.session_state["match_args"] = {
            "stock_code": stock_code, "cut_date_str": cut_date_str,
            "start_date": start_str, "end_date": end_str,
        }
        st.session_state["selected_cand_idx"] = 0
        st.session_state["active_view"] = "main"
    except Exception as e:
        st.error(f"匹配失败：{e}")
        st.stop()

result = st.session_state["match_result"]
args = st.session_state["match_args"]
tc = result["target_case"]
ranked = result["ranked"]
filter_log = result["filter_log"]

if "active_view" not in st.session_state:
    st.session_state["active_view"] = "main"
if "selected_cand_idx" not in st.session_state:
    st.session_state["selected_cand_idx"] = 0


# ============ 顶部信息条 ============
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("标的", f"{tc['stock_code']}", tc.get("stock_name", ""))
c2.metric("切面日", str(tc["cut_date"])[:10])
c3.metric("距D1", f"{tc['cut_to_d1_days']} 天", tc["cut_to_d1_category"])
c4.metric("最大涨幅", f"{tc['max_rise']:.1%}", tc["max_rise_category"])
c5.metric("候选总数", f"{len(ranked)}")

st.write("")

# ============ 顶部导航（按钮形式 + session_state 切换） ============
nav_cols = st.columns(3)
nav_items = [
    ("main", "📊 标的K线主图"),
    ("grid", "🗂 候选缩略卡栅格"),
    ("detail", "🎯 详情对比"),
]
for col, (key, label) in zip(nav_cols, nav_items):
    is_active = st.session_state["active_view"] == key
    btn_type = "primary" if is_active else "secondary"
    if col.button(label, key=f"nav_{key}", use_container_width=True, type=btn_type):
        st.session_state["active_view"] = key
        st.rerun()

st.divider()

view = st.session_state["active_view"]


# ====================== 视图1: 标的主图 ======================
if view == "main":
    ad, si = cached_daily_data(args["start_date"], args["end_date"])
    rows, seq_start, segments, break_periods = dl.find_segments_and_breaks(
        args["stock_code"], args["cut_date_str"], ad
    )
    cut_idx = next(
        (i for i, r in enumerate(rows) if pd.Timestamp(r["date"]) == pd.Timestamp(args["cut_date_str"])),
        None,
    )
    d1_idx = None
    d2_idx = None
    if break_periods:
        for bp in break_periods:
            if bp[0] <= cut_idx:
                d1_idx = bp[0]
                if bp[0] + 1 < len(rows) and bp[0] + 1 <= cut_idx:
                    d2_idx = bp[0] + 1

    title = f"{tc['stock_code']}  {tc.get('stock_name','')}  切面={str(tc['cut_date'])[:10]}"
    option = build_kline_option(
        rows, title=title,
        seq_start=seq_start, cut_idx=cut_idx,
        segments=segments, break_periods=break_periods,
        d1_idx=d1_idx, d2_idx=d2_idx,
        annotate_forms=annotate_forms, dark=dark, k_days=90,
    )
    st_echarts(options=option, height="640px", theme="dark" if dark else "white")

    with st.expander("案例字段一览（target_case）", expanded=False):
        import json as _json
        meta = {k: v for k, v in tc.items() if k not in ("micro", "history_special",
                                                          "label_sequence", "special_position_seq",
                                                          "break_d3plus_special_forms")}
        st.code(_json.dumps(meta, ensure_ascii=False, indent=2, default=str),
                language="json")
        st.caption("微型结构 micro")
        st.code(_json.dumps(tc["micro"], ensure_ascii=False, indent=2, default=str),
                language="json")


# ====================== 视图2: 候选缩略卡栅格 ======================
elif view == "grid":
    if not ranked:
        st.warning("无候选案例")
    else:
        # 仅展示得分 >= 60 的候选；保留原索引以便跳转详情对应同一条
        grid_items = [(i, c) for i, c in enumerate(ranked) if c["final_score"] >= 60]
        st.markdown(
            f"<p style='color:var(--text-sub); font-size:14px;'>"
            f"已筛选得分 ≥ 60 的候选 {len(grid_items)} 条 / 全部 {len(ranked)} 条 · "
            f"点击卡片下方「查看详情 ➜」按钮即可跳转至详情对比页"
            f"</p>",
            unsafe_allow_html=True,
        )
        if not grid_items:
            st.info("暂无得分 ≥ 60 的候选；可在「详情对比」中查看完整列表。")
        ad2, _ = cached_daily_data(args["start_date"], args["end_date"])
        per_row = 4
        rows_n = math.ceil(len(grid_items) / per_row)
        for r in range(rows_n):
            cols = st.columns(per_row)
            for j in range(per_row):
                pos = r * per_row + j
                if pos >= len(grid_items):
                    break
                idx, c = grid_items[pos]
                with cols[j]:
                    score = c["final_score"]
                    if score >= 80:
                        cls, grade = "cand-score-high", "🟢"
                    elif score >= 60:
                        cls, grade = "cand-score-mid", "🟡"
                    else:
                        cls, grade = "cand-score-low", "🔴"
                    cut_d = str(c["cut_date"])[:10]
                    next_pct = (f"次日 {c['next_day_pct']:.1%}"
                                if c["next_day_pct"] is not None else "次日 -")
                    st.markdown(
                        f"""<div class='cand-card'>
                          <div class='cand-title'>
                            #{idx+1} {grade} {c['stock_code']} {c.get('stock_name','')}
                            <span class='{cls}' style='float:right;font-size:16px;font-weight:700;'>
                              {score:.1f}
                            </span>
                          </div>
                          <div class='cand-meta'>
                            切面 {cut_d} · 距D1 {c['cut_to_d1_days']}天 · {next_pct}
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    cand_rows = dl.precompute_rows(c["stock_code"], ad2)
                    cand_cut_idx = next(
                        (i for i, rr in enumerate(cand_rows)
                         if pd.Timestamp(rr["date"]) == pd.Timestamp(c["cut_date"])),
                        None,
                    )
                    if cand_cut_idx is not None:
                        thumb = build_thumbnail_option(
                            cand_rows, cand_cut_idx,
                            title="", dark=dark, window=30,
                        )
                        st_echarts(options=thumb, height="170px",
                                   theme="dark" if dark else "white",
                                   key=f"thumb_{idx}_{c['stock_code']}")
                    if st.button(f"查看详情 ➜ #{idx+1}", key=f"view_{idx}",
                                 use_container_width=True):
                        st.session_state["selected_cand_idx"] = idx
                        st.session_state["active_view"] = "detail"
                        st.rerun()


# ====================== 视图3: 详情对比 ======================
elif view == "detail":
    if not ranked:
        st.warning("无候选案例")
    else:
        default_idx = st.session_state.get("selected_cand_idx", 0)
        default_idx = max(0, min(default_idx, len(ranked) - 1))
        sel = st.selectbox(
            "选择候选案例",
            range(len(ranked)),
            index=default_idx,
            format_func=lambda i: f"#{i+1} {ranked[i]['stock_code']} "
                                  f"{ranked[i].get('stock_name','')} "
                                  f"得分 {ranked[i]['final_score']:.1f}",
        )
        st.session_state["selected_cand_idx"] = sel
        cand = ranked[sel]
        ad3, _ = cached_daily_data(args["start_date"], args["end_date"])

        # 顶部对比信息条
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("候选代码", cand["stock_code"], cand.get("stock_name", ""))
        m2.metric("最终得分", f"{cand['final_score']:.2f}",
                  f"结构 {cand.get('structure_score', 0):.1f}")
        m3.metric("距离扣分", f"-{cand.get('distance_penalty', 0):.1f}")
        nx = (f"{cand['next_day_pct']:.2%}" if cand["next_day_pct"] is not None else "-")
        m4.metric("次日表现", nx,
                  "涨停" if cand.get("next_day_is_zt") else "")

        st.write("")

        # ==== 标的 K 线（左） / 候选 K 线（右）左右并排 ====
        # 标的：复用主图相同的索引推导
        tgt_rows, tgt_seq_start, tgt_segments, tgt_bps = dl.find_segments_and_breaks(
            args["stock_code"], args["cut_date_str"], ad3,
        )
        tgt_cut_idx = next(
            (i for i, rr in enumerate(tgt_rows)
             if pd.Timestamp(rr["date"]) == pd.Timestamp(args["cut_date_str"])),
            None,
        )
        tgt_d1, tgt_d2 = None, None
        if tgt_bps and tgt_cut_idx is not None:
            for bp in tgt_bps:
                if bp[0] <= tgt_cut_idx:
                    tgt_d1 = bp[0]
                    if bp[0] + 1 < len(tgt_rows) and bp[0] + 1 <= tgt_cut_idx:
                        tgt_d2 = bp[0] + 1

        # 候选
        cand_rows = dl.precompute_rows(cand["stock_code"], ad3)
        cand_cut_idx = next(
            (i for i, rr in enumerate(cand_rows)
             if pd.Timestamp(rr["date"]) == pd.Timestamp(cand["cut_date"])),
            None,
        )
        cand_seq_start, cand_segments, cand_bps = None, None, None
        if cand_cut_idx is not None:
            cand_rows2, cand_seq_start, cand_segments, cand_bps = dl.find_segments_and_breaks(
                cand["stock_code"],
                str(pd.Timestamp(cand["cut_date"]).date()),
                ad3,
            )
            if cand_rows2:
                cand_rows = cand_rows2
        cand_d1, cand_d2 = None, None
        if cand_bps and cand_cut_idx is not None:
            for bp in cand_bps:
                if bp[0] <= cand_cut_idx:
                    cand_d1 = bp[0]
                    if bp[0] + 1 < len(cand_rows) and bp[0] + 1 <= cand_cut_idx:
                        cand_d2 = bp[0] + 1

        kline_left, kline_right = st.columns(2)
        with kline_left:
            st.subheader("🎯 标的 K 线")
            tgt_opt = build_kline_option(
                tgt_rows,
                title=f"{tc['stock_code']} {tc.get('stock_name','')} "
                      f"切面={str(tc['cut_date'])[:10]}",
                seq_start=tgt_seq_start, cut_idx=tgt_cut_idx,
                segments=tgt_segments, break_periods=tgt_bps,
                d1_idx=tgt_d1, d2_idx=tgt_d2,
                annotate_forms=annotate_forms, dark=dark, k_days=90,
            )
            st_echarts(options=tgt_opt, height="520px",
                       theme="dark" if dark else "white",
                       key=f"detail_target_kline_{sel}")

        with kline_right:
            st.subheader("📈 候选 K 线")
            opt = build_kline_option(
                cand_rows,
                title=f"{cand['stock_code']} {cand.get('stock_name','')} "
                      f"切面={str(cand['cut_date'])[:10]}",
                seq_start=cand_seq_start, cut_idx=cand_cut_idx,
                segments=cand_segments, break_periods=cand_bps,
                d1_idx=cand_d1, d2_idx=cand_d2,
                annotate_forms=annotate_forms, dark=dark, k_days=90,
            )
            st_echarts(options=opt, height="520px",
                       theme="dark" if dark else "white",
                       key=f"detail_kline_{sel}")

        st.write("")

        # ==== 微型结构对比 / 基本指标对比 左右并排 ====
        left, right = st.columns([1, 1])
        with left:
            st.subheader("🧩 微型结构对比")
            mc_opt = build_micro_compare_option(tc, cand, dark=dark)
            st_echarts(options=mc_opt, height="320px",
                       theme="dark" if dark else "white",
                       key=f"micro_cmp_{sel}")

        with right:
            st.subheader("📋 基本指标对比")
            cmp_df = pd.DataFrame({
                "项": ["最大涨幅", "涨幅档", "回撤比", "回撤档",
                       "D1形态", "D1情绪", "D2形态", "中间涨停",
                       "断板天数", "距D1天数", "密度", "跌停强度",
                       "波段", "切面形态"],
                "标的": [
                    f"{tc['max_rise']:.1%}", tc["max_rise_category"],
                    f"{tc['height_retracement']:.1%}", tc["height_retracement_category"],
                    tc["break_d1_form"], tc["break_d1_emotion"], tc["break_d2_form"],
                    tc.get("mid_zt_type", "无涨停"),
                    f"{tc['break_actual_days']}天", f"{tc['cut_to_d1_days']}天",
                    tc["density_category"], tc["dt_intensity"],
                    tc["wave_category"], tc["cut_form"],
                ],
                "候选": [
                    f"{cand['max_rise']:.1%}", cand["max_rise_category"],
                    f"{cand['height_retracement']:.1%}", cand["height_retracement_category"],
                    cand["break_d1_form"], cand["break_d1_emotion"], cand["break_d2_form"],
                    cand.get("mid_zt_type", "无涨停"),
                    f"{cand['break_actual_days']}天", f"{cand['cut_to_d1_days']}天",
                    cand["density_category"], cand["dt_intensity"],
                    cand["wave_category"], cand["cut_form"],
                ],
            })
            st.dataframe(cmp_df, hide_index=True, use_container_width=True, height=520)

        st.subheader("💯 打分瀑布")
        wf_opt = build_waterfall_option(
            cand.get("penalty_details", []),
            final_score=cand["final_score"],
            dark=dark,
        )
        st_echarts(options=wf_opt, height="400px",
                   theme="dark" if dark else "white",
                   key=f"wf_{sel}")
        st.markdown(
            "<p style='color:var(--text-sub); font-size:13px;'>"
            "绿色为加分 / 得分基线，红色为扣分。鼠标悬停查看每段数值。"
            "</p>",
            unsafe_allow_html=True,
        )

        with st.expander("打分明细原文"):
            st.code("；".join(cand.get("penalty_details", [])), language="text")
