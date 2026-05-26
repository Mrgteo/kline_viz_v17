"""
K线相似度匹配系统 v2.0 - Streamlit 可视化前端
参考 ArvinLovegood/go-stock 的 K 线样式。

运行：
    cd C:/Users/KaiPanLa/Desktop/File/Code/kline_viz_v17
    streamlit run viz_app.py
"""
from __future__ import annotations

from datetime import date
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_echarts import st_echarts

import data_layer as _dl_v17
import data_layer_v23 as _dl_v23
from kline_chart import build_kline_option
from waterfall import build_waterfall_option
from micro_compare import build_micro_compare_option
from micro_compare_v23 import build_micro_compare_html_v23


def _get_dl(algo_key: str):
    return _dl_v17 if algo_key == "v1.7" else _dl_v23


# 默认指向 v1.7，模块顶部静态引用保持兼容
dl = _dl_v17

SHOW_SCORE_DEBUG_SECTIONS = False

st.set_page_config(
    page_title="K线相似度匹配 v2.0",
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

# ============== 日期选择器中文化（替换 BaseWeb calendar 的英文月份/星期/AM-PM 等） ==============
components.html(
    """
    <script>
    (function() {
      const doc = (window.parent && window.parent.document) || document;
      const MONTHS = {
        'January':'1月','February':'2月','March':'3月','April':'4月','May':'5月','June':'6月',
        'July':'7月','August':'8月','September':'9月','October':'10月','November':'11月','December':'12月',
        'Jan':'1月','Feb':'2月','Mar':'3月','Apr':'4月','Jun':'6月','Jul':'7月',
        'Aug':'8月','Sep':'9月','Sept':'9月','Oct':'10月','Nov':'11月','Dec':'12月'
      };
      const WEEKDAYS = {
        'Sunday':'周日','Monday':'周一','Tuesday':'周二','Wednesday':'周三',
        'Thursday':'周四','Friday':'周五','Saturday':'周六',
        'Sun':'日','Mon':'一','Tue':'二','Wed':'三','Thu':'四','Fri':'五','Sat':'六',
        'Su':'日','Mo':'一','Tu':'二','We':'三','Th':'四','Fr':'五','Sa':'六',
        'S':'日','M':'一','T':'二','W':'三','F':'五'
      };
      const ARIA_TIPS = {
        'Previous Month':'上一月','Next Month':'下一月',
        'Previous Year':'上一年','Next Year':'下一年',
        'Choose date':'选择日期','Choose a date':'选择日期','Open calendar':'打开日历',
        'Select a month':'选择月份','Select a year':'选择年份'
      };

      function transform(t) {
        if (!t) return null;
        const s = t.trim();
        if (!s) return null;
        // "January 2026" / "January, 2026" → "2026年1月"
        let m = s.match(/^([A-Za-z]+)[,\\s]+(\\d{4})$/);
        if (m && MONTHS[m[1]]) return s.replace(s, m[2] + '年' + MONTHS[m[1]]);
        // 纯英文月名
        if (MONTHS[s]) return MONTHS[s];
        // 纯英文星期
        if (WEEKDAYS[s]) return WEEKDAYS[s];
        return null;
      }

      function walkTextNodes(root) {
        if (!root || !root.ownerDocument) return;
        const d = root.ownerDocument;
        try {
          const walker = d.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
          const nodes = [];
          let cur;
          while ((cur = walker.nextNode())) nodes.push(cur);
          nodes.forEach(n => {
            const v = n.nodeValue;
            if (!v) return;
            const rep = transform(v);
            if (rep !== null && rep !== v.trim()) {
              n.nodeValue = v.replace(v.trim(), rep);
            }
          });
        } catch (e) {}
      }

      function translateAria(root) {
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll('[aria-label]').forEach(el => {
          const a = el.getAttribute('aria-label');
          if (!a) return;
          if (ARIA_TIPS[a]) { el.setAttribute('aria-label', ARIA_TIPS[a]); return; }
          for (const k in ARIA_TIPS) {
            if (a.includes(k)) {
              el.setAttribute('aria-label', a.replace(k, ARIA_TIPS[k]));
              break;
            }
          }
          // aria-label 里嵌入了 "January 2026" 的情况
          for (const k in MONTHS) {
            if (a.includes(k)) {
              el.setAttribute('aria-label',
                a.replace(new RegExp('\\\\b' + k + '\\\\b'), MONTHS[k]));
              break;
            }
          }
        });
      }

      function translateAll() {
        // 日历本体可能挂在 body 上（BaseWeb Layer / popover）
        const targets = doc.querySelectorAll(
          '[data-baseweb="calendar"], [data-baseweb="popover"], [data-baseweb="datepicker"], ' +
          '[data-baseweb="menu"], [data-baseweb="list"]'
        );
        targets.forEach(t => { walkTextNodes(t); translateAria(t); });
      }

      // 首次 + 持续观察 + 定时兜底
      translateAll();
      try {
        const mo = new MutationObserver(() => translateAll());
        mo.observe(doc.body, { childList: true, subtree: true, characterData: true });
      } catch (e) {}
      setInterval(translateAll, 300);
    })();
    </script>
    """,
    height=0,
)


@st.cache_resource(show_spinner="加载股票列表...")
def cached_stock_list(algo_key: str = "v1.7"):
    return _get_dl(algo_key).load_stock_list()


@st.cache_resource(show_spinner="加载日K数据（首次较慢，命中缓存秒开）...")
def cached_daily_data(start_date: str, end_date: str, algo_key: str = "v1.7"):
    _dl = _get_dl(algo_key)
    si = cached_stock_list(algo_key)
    ad = _dl.load_daily_data(si, start_date, end_date)
    return ad, si


@st.cache_resource(show_spinner="加载/构建案例库（首次需数分钟，建议先在终端跑 prebuild_case_library.py）...")
def cached_case_library(start_date: str, end_date: str, algo_key: str = "v1.7"):
    _dl = _get_dl(algo_key)
    ad, si = cached_daily_data(start_date, end_date, algo_key)
    return _dl.load_case_library(ad, si)


@st.cache_data(show_spinner="执行匹配...")
def cached_match(stock_code: str, cut_date_str: str,
                  start_date: str, end_date: str, top_n: int,
                  algo_key: str = "v1.7"):
    _dl = _get_dl(algo_key)
    ad, si = cached_daily_data(start_date, end_date, algo_key)
    cl = cached_case_library(start_date, end_date, algo_key)
    return _dl.match(stock_code, cut_date_str, ad, si, cl, top_n=top_n)


with st.sidebar:
    st.title("📈 K线相似匹配")
    st.caption("参考 go-stock 配色 · 红涨绿跌 · ECharts")

    algo_choice = st.radio(
        "算法版本",
        ["v2.0 (断板版)", "v2.3 (连板版)"],
        horizontal=True,
        index=0,
        key="algo_choice",
    )
    algo_key = "v1.7" if algo_choice.startswith("v2.0") else "v2.3"
    dl = _get_dl(algo_key)

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
            si_list = cached_stock_list(algo_key)
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
        result = cached_match(stock_code, cut_date_str, start_str, end_str, top_n, algo_key)
        st.session_state["match_result"] = result
        st.session_state["match_args"] = {
            "stock_code": stock_code, "cut_date_str": cut_date_str,
            "start_date": start_str, "end_date": end_str,
            "algo_key": algo_key,
        }
        st.session_state["selected_cand_idx"] = 0
        st.session_state["active_view"] = "main"
    except Exception as e:
        st.error(f"匹配失败：{e}")
        st.stop()

result = st.session_state["match_result"]
args = st.session_state["match_args"]
# 渲染阶段沿用执行匹配时的算法版本，避免侧边栏切换后字段不一致
algo_key = args.get("algo_key", algo_key)
dl = _get_dl(algo_key)
tc = result["target_case"]
ranked = result["ranked"]
filter_log = result["filter_log"]

if "active_view" not in st.session_state:
    st.session_state["active_view"] = "main"
if st.session_state["active_view"] == "grid":
    st.session_state["active_view"] = "detail"
if "selected_cand_idx" not in st.session_state:
    st.session_state["selected_cand_idx"] = 0


# ============ 顶部信息条 ============
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("标的", f"{tc['stock_code']}", tc.get("stock_name", ""))
c2.metric("切面日", str(tc["cut_date"])[:10])
if algo_key == "v1.7":
    c3.metric("距D1", f"{tc['cut_to_d1_days']} 天",
              tc.get("d1_distance_cat", tc.get("cut_to_d1_category", "")))
    c4.metric("最大涨幅", f"{tc['max_rise']:.1%}", tc["max_rise_category"])
else:
    c3.metric("连板高度", f"{tc['board_height']} 板", tc.get("height_category", ""))
    c4.metric("启动位置", f"{tc.get('pre_rally', 0):.1%}",
              tc.get("pre_rally_category", ""))
c5.metric("候选总数", f"{len(ranked)}")

st.write("")

# ============ 顶部导航（按钮形式 + session_state 切换） ============
nav_cols = st.columns(2)
nav_items = [
    ("main", "📊 标的K线主图"),
    ("detail", "🎯 相似匹配对比"),
]
for col, (key, label) in zip(nav_cols[:len(nav_items)], nav_items):
    is_active = st.session_state["active_view"] == key
    btn_type = "primary" if is_active else "secondary"
    if col.button(label, key=f"nav_{key}", use_container_width=True, type=btn_type):
        st.session_state["active_view"] = key
        st.rerun()

st.divider()

view = st.session_state["active_view"]


# ====================== 视图1: 标的主图 ======================
if view == "main":
    ad, si = cached_daily_data(args["start_date"], args["end_date"], algo_key)
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
        show_research_range=False,
    )
    st_echarts(options=option, height="640px", theme="dark" if dark else "white")

    with st.expander("案例字段一览（target_case）", expanded=False):
        import json as _json
        excluded = {"micro", "history_special", "label_sequence",
                    "special_position_seq", "break_d3plus_special_forms",
                    "history_special_types", "volume_label_per_day"}
        meta = {k: v for k, v in tc.items() if k not in excluded}
        st.code(_json.dumps(meta, ensure_ascii=False, indent=2, default=str),
                language="json")
        if algo_key == "v1.7" and "micro" in tc:
            st.caption("微型结构 micro")
            st.code(_json.dumps(tc["micro"], ensure_ascii=False, indent=2, default=str),
                    language="json")
        else:
            extras = {
                "special_position_seq": tc.get("special_position_seq", []),
                "history_special": tc.get("history_special", {}),
                "history_special_types": list(tc.get("history_special_types", []) or []),
                "label_sequence": tc.get("label_sequence", []),
            }
            st.caption("板型/序列字段")
            st.code(_json.dumps(extras, ensure_ascii=False, indent=2, default=str),
                    language="json")


# ====================== 视图2: 相似匹配对比（瀑布卡片） ======================
elif view == "detail":
    if not ranked:
        st.warning("无候选案例")
    else:
        # 仅展示 final_score >= 60 的候选，并按分数从高到低排序
        ranked_filtered = [(i, c) for i, c in enumerate(ranked)
                           if c.get("final_score", 0) >= 60]
        ranked_filtered.sort(key=lambda x: x[1].get("final_score", 0), reverse=True)
        st.markdown(
            f"<p style='color:var(--text-sub); font-size:14px; margin-bottom:8px;'>"
            f"已筛选得分 ≥ 60 的候选 {len(ranked_filtered)} 条 / 全部 {len(ranked)} 条 · "
            f"在下方下拉框中选择候选可快速跳转至对应卡片"
            f"</p>",
            unsafe_allow_html=True,
        )
        if not ranked_filtered:
            st.info("暂无得分 ≥ 60 的候选。")
        else:
            # 选择候选 → 锚点跳转
            options_idx = [orig_i for orig_i, _ in ranked_filtered]
            default_orig = st.session_state.get("selected_cand_idx", options_idx[0])
            if default_orig not in options_idx:
                default_orig = options_idx[0]

            def _fmt_choice(orig_i: int) -> str:
                c = ranked[orig_i]
                return (f"#{orig_i+1} {c['stock_code']} "
                        f"{c.get('stock_name','')} "
                        f"得分 {c['final_score']:.1f}")

            sel_orig = st.selectbox(
                "选择候选案例（跳转至卡片）",
                options_idx,
                index=options_idx.index(default_orig),
                format_func=_fmt_choice,
                key="cand_jump_select",
            )
            st.session_state["selected_cand_idx"] = sel_orig

            # 注入 scrollIntoView：把 sel_orig 对应的锚点滚动到视口
            components.html(
                f"""
                <script>
                (function() {{
                  const doc = (window.parent && window.parent.document) || document;
                  const t = doc.getElementById('cand_anchor_{sel_orig}');
                  if (t) {{
                    t.scrollIntoView({{behavior:'smooth', block:'start'}});
                  }}
                }})();
                </script>
                """,
                height=0,
            )

            ad3, _ = cached_daily_data(args["start_date"], args["end_date"], algo_key)

            # 标的 K 线（每张卡片都用，先算一次）
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
            tgt_title = f"{tc['stock_code']} {tc.get('stock_name','')}"

            # ===== 渲染每张候选卡片 =====
            for orig_i, cand in ranked_filtered:
                # 锚点（HTML id），用于下拉跳转
                st.markdown(
                    f"<div id='cand_anchor_{orig_i}' style='position:relative; top:-12px;'></div>",
                    unsafe_allow_html=True,
                )

                # M-cut 对比 payload（v1.7 才有 m_cut；v2.3 没有则回退 None）
                mcut_payload = None
                if algo_key == "v1.7" and tc.get("m_cut") and cand.get("m_cut"):
                    try:
                        mcut_payload = dl.get_mcut_compare_payload(tc, cand)
                    except Exception:
                        mcut_payload = None

                # 顶部 4 个 metric
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("候选代码", cand["stock_code"], cand.get("stock_name", ""))
                m2.metric("最终得分", f"{cand['final_score']:.2f}",
                          f"结构 {cand.get('structure_score', 0):.1f}")
                m3.metric("距离扣分", f"-{cand.get('distance_penalty', 0):.1f}")
                nx = (f"{cand['next_day_pct']:.2%}"
                      if cand["next_day_pct"] is not None else "-")
                m4.metric("次日表现", nx,
                          "涨停" if cand.get("next_day_is_zt") else "")

                st.write("")

                # 候选 K 线推导
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

                # ===== M-cut 3 天微型结构对比横条 =====
                if mcut_payload and mcut_payload["target"]:
                    _color_label = {
                        "match": ("精确匹配", "#10b981"),
                        "approx": ("近似", "#3b82f6"),
                        "emotion": ("情绪同", "#a78bfa"),
                        "mismatch": ("不匹配", "#ef4444"),
                        "missing": ("一方无", "#fb923c"),
                        "none": ("双方无", "#94a3b8"),
                    }
                    cells = []
                    for td, cd in zip(mcut_payload["target"], mcut_payload["cand"]):
                        kind = td.get("diff_kind", "mismatch")
                        name, color = _color_label.get(kind, ("?", "#94a3b8"))
                        ds = td.get("day_score", 0)
                        sign = "+" if ds >= 0 else ""
                        cells.append(
                            f"<div style='flex:1; min-width:0; border:1.5px solid {color}; "
                            f"border-radius:8px; padding:8px 10px; "
                            f"background:rgba(15,23,42,0.45);'>"
                            f"<div style='font-size:11px;color:#94a3b8;'>M-cut · {td['label']}</div>"
                            f"<div style='font-size:13px;color:#f1f5f9;font-weight:600;margin-top:2px;'>"
                            f"标 {td.get('subdivision','-')}</div>"
                            f"<div style='font-size:13px;color:#cbd5e1;'>候 {cd.get('subdivision','-')}</div>"
                            f"<div style='font-size:11px;color:{color};margin-top:4px;font-weight:700;'>"
                            f"{name} {sign}{ds}</div>"
                            f"</div>"
                        )
                    total_b = mcut_payload.get("total_bonus", 0)
                    total_p = mcut_payload.get("total_penalty", 0)
                    net = total_b - total_p
                    net_color = "#10b981" if net >= 0 else "#ef4444"
                    st.markdown(
                        f"<div style='display:flex; gap:10px; align-items:stretch; "
                        f"margin-bottom:10px;'>"
                        f"<div style='flex:0 0 110px; display:flex; flex-direction:column; "
                        f"justify-content:center; border:1.5px solid {net_color}; "
                        f"border-radius:8px; padding:8px 10px; background:rgba(15,23,42,0.45);'>"
                        f"<div style='font-size:11px;color:#94a3b8;'>M-cut 净分</div>"
                        f"<div style='font-size:20px;color:{net_color};font-weight:800;'>"
                        f"{'+' if net>=0 else ''}{net}</div>"
                        f"<div style='font-size:10px;color:#64748b;'>+{total_b} / -{total_p}</div>"
                        f"</div>"
                        f"{''.join(cells)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                # 标的 K 线 / 候选 K 线 左右并排
                kline_left, kline_right = st.columns(2)
                with kline_left:
                    st.subheader("🎯 标的 K 线")
                    tgt_opt = build_kline_option(
                        tgt_rows, title=tgt_title,
                        seq_start=tgt_seq_start, cut_idx=tgt_cut_idx,
                        segments=tgt_segments, break_periods=tgt_bps,
                        d1_idx=tgt_d1, d2_idx=tgt_d2,
                        annotate_forms=annotate_forms, dark=dark, k_days=90,
                        mcut_daily=(mcut_payload["target"] if mcut_payload else None),
                        show_research_range=True,
                    )
                    st_echarts(options=tgt_opt, height="520px",
                               theme="dark" if dark else "white",
                               key=f"detail_target_kline_{orig_i}")
                with kline_right:
                    st.subheader("📈 候选 K 线")
                    opt = build_kline_option(
                        cand_rows,
                        title=f"{cand['stock_code']} {cand.get('stock_name','')}",
                        seq_start=cand_seq_start, cut_idx=cand_cut_idx,
                        segments=cand_segments, break_periods=cand_bps,
                        d1_idx=cand_d1, d2_idx=cand_d2,
                        annotate_forms=annotate_forms, dark=dark, k_days=90,
                        mcut_daily=(mcut_payload["cand"] if mcut_payload else None),
                        show_research_range=True,
                    )
                    st_echarts(options=opt, height="520px",
                               theme="dark" if dark else "white",
                               key=f"detail_cand_kline_{orig_i}")

                st.write("")

                # 微型结构 / 基本指标对比（保留代码，默认隐藏）
                SHOW_MICRO_AND_INDICATORS = False
                if SHOW_MICRO_AND_INDICATORS:
                    left, right = st.columns([1, 1])
                    with left:
                        st.subheader("🧩 微型结构对比")
                        if algo_key == "v1.7":
                            mc_opt = build_micro_compare_option(tc, cand, dark=dark)
                            st_echarts(options=mc_opt, height="320px",
                                       theme="dark" if dark else "white",
                                       key=f"micro_cmp_{orig_i}")
                        else:
                            st.markdown(
                                build_micro_compare_html_v23(tc, cand, dark=dark),
                                unsafe_allow_html=True,
                            )
                    with right:
                        st.subheader("📋 基本指标对比")
                        if algo_key == "v1.7":
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
                        else:
                            def _row(case, key, fmt=None):
                                v = case.get(key)
                                if v is None:
                                    return "-"
                                return fmt.format(v) if fmt else str(v)
                            cmp_df = pd.DataFrame({
                                "项": ["连板高度", "高度档位", "末端形态", "加速次数",
                                       "最大加速持续", "加速持续档位", "加速密度",
                                       "首日振幅", "首日状态", "启动位置", "启动档位",
                                       "综合高度", "综合高度档位", "切面板型",
                                       "封板强度", "振幅档位", "开盘涨幅档位", "量能状态"],
                                "标的": [
                                    f"{tc.get('board_height', '-')}板", tc.get("height_category", "-"),
                                    tc.get("end_pattern", "-"), str(tc.get("accel_count", "-")),
                                    f"{tc.get('max_accel_duration', '-')}天",
                                    tc.get("max_accel_category", "-"),
                                    _row(tc, "accel_density", "{:.1%}"),
                                    _row(tc, "first_day_amplitude", "{:.2%}"),
                                    tc.get("first_day_state", "-"),
                                    _row(tc, "pre_rally", "{:.2%}"),
                                    tc.get("pre_rally_category", "-"),
                                    _row(tc, "combined_height", "{:.1%}"),
                                    tc.get("combined_height_category", "-"),
                                    tc.get("cut_special", "-"), tc.get("board_strength", "-"),
                                    tc.get("amplitude_category", "-"),
                                    tc.get("open_pct_category", "-"), tc.get("volume_state", "-"),
                                ],
                                "候选": [
                                    f"{cand.get('board_height', '-')}板", cand.get("height_category", "-"),
                                    cand.get("end_pattern", "-"), str(cand.get("accel_count", "-")),
                                    f"{cand.get('max_accel_duration', '-')}天",
                                    cand.get("max_accel_category", "-"),
                                    _row(cand, "accel_density", "{:.1%}"),
                                    _row(cand, "first_day_amplitude", "{:.2%}"),
                                    cand.get("first_day_state", "-"),
                                    _row(cand, "pre_rally", "{:.2%}"),
                                    cand.get("pre_rally_category", "-"),
                                    _row(cand, "combined_height", "{:.1%}"),
                                    cand.get("combined_height_category", "-"),
                                    cand.get("cut_special", "-"), cand.get("board_strength", "-"),
                                    cand.get("amplitude_category", "-"),
                                    cand.get("open_pct_category", "-"), cand.get("volume_state", "-"),
                                ],
                            })
                        st.dataframe(cmp_df, hide_index=True,
                                     use_container_width=True, height=520)

                if SHOW_SCORE_DEBUG_SECTIONS:
                    # 打分瀑布（默认折叠）
                    with st.expander("💯 打分瀑布", expanded=False):
                        wf_opt = build_waterfall_option(
                            cand.get("penalty_details", []),
                            final_score=cand["final_score"],
                            dark=dark,
                        )
                        st_echarts(options=wf_opt, height="400px",
                                   theme="dark" if dark else "white",
                                   key=f"wf_{orig_i}")
                        st.markdown(
                            "<p style='color:var(--text-sub); font-size:13px;'>"
                            "绿色为加分 / 得分基线，红色为扣分。鼠标悬停查看每段数值。"
                            "</p>",
                            unsafe_allow_html=True,
                        )

                    # 打分明细原文（默认折叠）
                    with st.expander("📝 打分明细原文", expanded=False):
                        st.code("；".join(cand.get("penalty_details", [])), language="text")

                # 卡片之间的分隔线
                st.markdown(
                    "<hr style='border:none; border-top:1px solid var(--border); "
                    "margin:28px 0 28px 0;' />",
                    unsafe_allow_html=True,
                )
