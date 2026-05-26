"""
K 线图 ECharts option 构造器。
参考 ArvinLovegood/go-stock 的 KLineChart.vue：
- 红涨 #ec0000 / 绿跌 #00da3c（A 股配色）
- 双 grid 联动（上 50% K 线 + 下 15% 成交量）
- MA5/10/20/30 均线
- 成交量 visualMap 按涨跌染色
- dataZoom inside + slider，可拉伸放大
- axisPointer cross 跨图联动

在原版基础上叠加算法标注：
- 涨停段 segments → 绿色背景 markArea
- 断板期 break_periods → 红色背景 markArea
- D1 / D2 / 切面日 → markLine 竖线 + 标签
- 每根 K 线挂 form 文本（一字板/大阳线/十字星 等）
"""
from __future__ import annotations

import pandas as pd

UP_COLOR = "#ec0000"
DOWN_COLOR = "#00da3c"
SEG_AREA_COLOR = "rgba(239,68,68,0.18)"
BREAK_AREA_COLOR = "rgba(16,185,129,0.18)"
D1_LINE_COLOR = "#f59e0b"
D2_LINE_COLOR = "#a78bfa"
CUT_LINE_COLOR = "#fbbf24"
MCUT_AREA_COLOR = "rgba(251,191,36,0.20)"
MSTART_AREA_COLOR = "rgba(96,165,250,0.18)"
RESEARCH_AREA_COLOR = "rgba(255,255,255,0.02)"
RESEARCH_AREA_BORDER = "rgba(255,255,255,0.78)"


def _fmt_date(d) -> str:
    return str(pd.Timestamp(d).date())


def _calc_ma(day_count: int, values: list[list[float]]) -> list:
    result = []
    n = len(values)
    for i in range(n):
        if i < day_count - 1:
            result.append("-")
            continue
        s = sum(float(values[i - j][1]) for j in range(day_count))
        result.append(round(s / day_count, 2))
    return result


def _rows_to_arrays(rows: list[dict], start: int = 0, end: int | None = None):
    if end is None:
        end = len(rows) - 1
    sub = rows[start:end + 1]
    categories = [_fmt_date(r["date"]) for r in sub]
    values = []
    volumes = []
    forms = []
    for i, r in enumerate(sub):
        flag = 1 if r["close"] >= r["open"] else -1
        values.append([
            round(float(r["open"]), 2),
            round(float(r["close"]), 2),
            round(float(r["low"]), 2),
            round(float(r["high"]), 2),
        ])
        volumes.append([i, round(float(r["volume"]) / 10000, 2), flag])
        forms.append(r.get("form", ""))
    return categories, values, volumes, forms, sub


def build_kline_option(
    rows: list[dict],
    *,
    title: str = "",
    seq_start: int | None = None,
    cut_idx: int | None = None,
    segments: list[tuple[int, int]] | None = None,
    break_periods: list[tuple[int, int]] | None = None,
    d1_idx: int | None = None,
    d2_idx: int | None = None,
    annotate_forms: bool = True,
    dark: bool = True,
    k_days: int = 60,
    chart_height: int = 560,
    mcut_daily: list[dict] | None = None,
    mstart_daily: list[dict] | None = None,
    start_idx: int | None = None,
    show_research_range: bool = True,
) -> dict:
    """构造 ECharts option dict。

    rows 为 precompute_stock_data 返回的完整列表，
    seq_start / cut_idx 等索引基于 rows 原始下标。
    内部会以 view_start 为起点裁切，确保上下文足够（默认前后各留 10 根）。
    """
    n = len(rows)
    if n == 0:
        return {}

    if seq_start is not None and cut_idx is not None:
        pad = 10
        view_start = max(0, seq_start - pad)
        view_end = min(n - 1, cut_idx + pad)
    else:
        view_start, view_end = 0, n - 1

    categories, values, volumes, forms, sub = _rows_to_arrays(rows, view_start, view_end)
    text_color = "#f1f5f9" if dark else "#1f2937"
    sub_text = "#cbd5e1" if dark else "#475569"
    border = "#334155" if dark else "#cbd5e1"
    bg = "#1a2236" if dark else "#ffffff"
    grid_color = "#334155" if dark else "#e5e7eb"

    def _shift(idx: int | None) -> int | None:
        if idx is None:
            return None
        if idx < view_start or idx > view_end:
            return None
        return idx - view_start

    seg_shift = []
    if segments:
        for s, e in segments:
            ss, ee = _shift(s), _shift(e)
            if ss is not None and ee is not None:
                seg_shift.append((ss, ee))
    bp_shift = []
    if break_periods:
        for s, e in break_periods:
            ss, ee = _shift(s), _shift(e)
            if ss is not None and ee is not None:
                bp_shift.append((ss, ee))
    d1_s = _shift(d1_idx)
    d2_s = _shift(d2_idx)
    cut_s = _shift(cut_idx)
    research_start_idx = seq_start if show_research_range else None
    if show_research_range and research_start_idx is None and cut_idx is not None and segments:
        for s, e in segments:
            if s <= cut_idx <= e:
                research_start_idx = s
                break
        if research_start_idx is None:
            prior_segments = [(s, e) for s, e in segments if s <= cut_idx]
            if prior_segments:
                research_start_idx = prior_segments[-1][0]
    research_start_s = _shift(research_start_idx)

    mark_areas = []
    if research_start_s is not None and cut_s is not None and research_start_s <= cut_s:
        mark_areas.append([
            {"xAxis": categories[research_start_s],
             "itemStyle": {"color": RESEARCH_AREA_COLOR,
                           "borderColor": RESEARCH_AREA_BORDER,
                           "borderWidth": 1},
             "label": {"show": False}},
            {"xAxis": categories[cut_s]},
        ])
    for ss, ee in seg_shift:
        mark_areas.append([
            {"xAxis": categories[ss],
             "itemStyle": {"color": SEG_AREA_COLOR},
             "label": {"show": False}},
            {"xAxis": categories[ee]},
        ])
    for ss, ee in bp_shift:
        mark_areas.append([
            {"xAxis": categories[ss],
             "itemStyle": {"color": BREAK_AREA_COLOR},
             "label": {"show": False}},
            {"xAxis": categories[ee]},
        ])

    mark_lines = []

    # D1 / D2 / 切面：不画竖线，用 markPoint 在该日 K 线最高点上方放置纯文字气泡
    cut_points = []
    def _mk_anchor(idx_s: int, text: str, color: str, offset_y: int):
        if idx_s is None:
            return
        cut_points.append({
            "name": text,
            "coord": [categories[idx_s], sub[idx_s]["high"]],
            "value": text,
            "symbol": "rect",
            "symbolSize": [1, 1],
            "symbolOffset": [0, offset_y],
            "itemStyle": {"color": "transparent", "borderColor": "transparent"},
            "label": {
                "show": True,
                "formatter": text,
                "color": color,
                "fontSize": 12,
                "fontWeight": "bold",
                "backgroundColor": "rgba(15,23,42,0.85)",
                "borderColor": color,
                "borderWidth": 1,
                "borderRadius": 4,
                "padding": [2, 6],
            },
        })

    # 三个标记沿 Y 方向错开，避免相邻日同时存在时叠到一起
    _mk_anchor(d1_s, "D1", D1_LINE_COLOR, -18)
    _mk_anchor(d2_s, "D2", D2_LINE_COLOR, -36)
    _mk_anchor(cut_s, "切面", CUT_LINE_COLOR, -54)

    form_points = []
    if annotate_forms:
        important = {"一字板", "T字板", "地天板", "大长腿涨停", "秒板", "普通涨停",
                     "一字跌停", "倒T字跌停", "天地板", "大长腿跌停", "秒跌停", "普通跌停",
                     "大阳线", "大阴线", "低开高走", "高开低走"}
        for i, f in enumerate(forms):
            if not f or f not in important:
                continue
            is_up = sub[i]["close"] >= sub[i]["open"]
            form_points.append({
                "name": f,
                "coord": [categories[i], sub[i]["high"] if is_up else sub[i]["low"]],
                "value": f,
                "symbol": "pin",
                "symbolSize": 28,
                "symbolOffset": [0, "-50%"] if is_up else [0, "50%"],
                "itemStyle": {"color": UP_COLOR if is_up else DOWN_COLOR, "opacity": 0.92},
                "label": {"color": "#ffffff", "fontSize": 11, "fontWeight": "bold",
                          "formatter": f},
            })

    # ===== M-cut / M-start 3 天窗口标注 =====
    # 仅保留金色 markArea 表示"切面 3 天窗口"，日徽章移除（避免互相覆盖；
    # 详情见顶部 M-cut 卡片）。
    if mcut_daily and cut_s is not None:
        anchor_view = cut_s
        mcut_start_view = max(0, anchor_view - 2)
        mcut_end_view = anchor_view
        if mcut_end_view <= len(categories) - 1 and mcut_start_view <= mcut_end_view:
            mark_areas.append([
                {"xAxis": categories[mcut_start_view],
                 "itemStyle": {"color": MCUT_AREA_COLOR,
                               "borderColor": "rgba(251,191,36,0.55)",
                               "borderWidth": 1},
                 "label": {"show": False}},
                {"xAxis": categories[mcut_end_view]},
            ])

    if mstart_daily and start_idx is not None:
        anchor_view = _shift(start_idx)
        if anchor_view is not None:
            mstart_start_view = max(0, anchor_view - 2)
            if mstart_start_view <= anchor_view:
                mark_areas.append([
                    {"xAxis": categories[mstart_start_view],
                     "itemStyle": {"color": MSTART_AREA_COLOR,
                                   "borderColor": "rgba(96,165,250,0.55)",
                                   "borderWidth": 1},
                     "label": {"show": False}},
                    {"xAxis": categories[anchor_view]},
                ])

    option = {
        "title": {
            "text": title,
            "left": 20,
            "textStyle": {"color": text_color, "fontSize": 16, "fontWeight": "bold"},
        },
        "darkMode": dark,
        "backgroundColor": "transparent",
        "animation": False,
        "legend": {
            "right": 20,
            "top": 4,
            "data": ["日K", "MA5", "MA10", "MA20", "MA30"],
            "textStyle": {"color": text_color, "fontSize": 13, "fontWeight": 500},
            "itemGap": 16,
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {
                "type": "cross",
                "lineStyle": {"color": "#fbbf24", "width": 1, "opacity": 0.9},
                "label": {"backgroundColor": "#fbbf24", "color": "#0b1220",
                          "fontWeight": "bold"},
            },
            "borderWidth": 1,
            "borderColor": border,
            "backgroundColor": bg,
            "padding": 12,
            "textStyle": {"color": text_color, "fontSize": 13},
        },
        "axisPointer": {
            "link": [{"xAxisIndex": "all"}],
            "label": {"backgroundColor": "#fbbf24", "color": "#0b1220"},
        },
        "visualMap": {
            "show": False,
            "seriesIndex": 5,
            "dimension": 2,
            "pieces": [
                {"value": -1, "color": DOWN_COLOR},
                {"value": 1, "color": UP_COLOR},
            ],
        },
        "grid": [
            {"left": "8%", "right": "8%", "height": "50%", "top": "14%"},
            {"left": "8%", "right": "8%", "top": "70%", "height": "15%"},
        ],
        "xAxis": [
            {
                "type": "category", "data": categories, "boundaryGap": False,
                "axisLine": {"onZero": False, "lineStyle": {"color": grid_color}},
                "axisLabel": {"color": sub_text, "fontSize": 11},
                "axisTick": {"lineStyle": {"color": grid_color}},
                "splitLine": {"show": False},
                "min": "dataMin", "max": "dataMax",
                "axisPointer": {"z": 100},
            },
            {
                "type": "category", "gridIndex": 1, "data": categories,
                "boundaryGap": False,
                "axisLine": {"onZero": False, "lineStyle": {"color": grid_color}},
                "axisTick": {"show": False}, "splitLine": {"show": False},
                "axisLabel": {"show": False},
                "min": "dataMin", "max": "dataMax",
                "axisPointer": {"label": {"show": False}},
            },
        ],
        "yAxis": [
            {
                "scale": True, "splitArea": {"show": False},
                "axisLabel": {"color": sub_text, "fontSize": 11},
                "axisLine": {"show": True, "lineStyle": {"color": grid_color}},
                "splitLine": {"lineStyle": {"color": grid_color, "opacity": 0.3}},
            },
            {
                "scale": True, "gridIndex": 1, "splitNumber": 2,
                "axisLabel": {"show": False}, "axisLine": {"show": False},
                "axisTick": {"show": False}, "splitLine": {"show": False},
            },
        ],
        "dataZoom": [
            {"type": "inside", "xAxisIndex": [0, 1],
             "start": max(0, 100 - k_days * 100 // max(len(categories), 1)), "end": 100},
            {"show": True, "xAxisIndex": [0, 1], "type": "slider",
             "top": "92%", "height": 22,
             "start": max(0, 100 - k_days * 100 // max(len(categories), 1)),
             "end": 100,
             "textStyle": {"color": sub_text, "fontSize": 11},
             "borderColor": grid_color,
             "fillerColor": "rgba(251,191,36,0.18)",
             "handleStyle": {"color": "#fbbf24"}},
        ],
        "series": [
            {
                "name": "日K",
                "type": "candlestick",
                "z": 3,
                "data": values,
                "itemStyle": {
                    "color": UP_COLOR, "color0": DOWN_COLOR,
                    "borderColor": UP_COLOR, "borderColor0": DOWN_COLOR,
                },
                "markArea": {"silent": True, "z": -1, "data": mark_areas}
                if mark_areas else None,
                "markLine": {"symbol": ["none", "none"], "data": mark_lines, "silent": True}
                if mark_lines else None,
                "markPoint": (
                    {"data": cut_points + form_points, "silent": True}
                    if (cut_points or form_points) else None
                ),
            },
            {"name": "MA5", "type": "line", "data": _calc_ma(5, values),
             "smooth": True, "showSymbol": False,
             "lineStyle": {"opacity": 0.7, "width": 1, "color": "#fbbf24"}},
            {"name": "MA10", "type": "line", "data": _calc_ma(10, values),
             "smooth": True, "showSymbol": False,
             "lineStyle": {"opacity": 0.7, "width": 1, "color": "#60a5fa"}},
            {"name": "MA20", "type": "line", "data": _calc_ma(20, values),
             "smooth": True, "showSymbol": False,
             "lineStyle": {"opacity": 0.7, "width": 1, "color": "#a78bfa"}},
            {"name": "MA30", "type": "line", "data": _calc_ma(30, values),
             "smooth": True, "showSymbol": False,
             "lineStyle": {"opacity": 0.7, "width": 1, "color": "#f472b6"}},
            {
                "name": "成交量(万手)",
                "type": "bar",
                "xAxisIndex": 1, "yAxisIndex": 1,
                "data": volumes,
                "itemStyle": {"color": "#7fbe9e"},
            },
        ],
    }

    # 移除值为 None 的字段，避免 ECharts 报警
    series0 = option["series"][0]
    for k in list(series0.keys()):
        if series0[k] is None:
            del series0[k]

    # ===== 固定色块图例（替代 markArea 顶部的文字标签）=====
    legend_items: list[tuple[str, str, str]] = []  # (label, fill, border)
    if research_start_s is not None and cut_s is not None and research_start_s <= cut_s:
        legend_items.append(("研究范围", RESEARCH_AREA_COLOR, RESEARCH_AREA_BORDER))
    if seg_shift:
        legend_items.append(("涨停段", SEG_AREA_COLOR, "rgba(239,68,68,0.55)"))
    if bp_shift:
        legend_items.append(("断板期", BREAK_AREA_COLOR, "rgba(16,185,129,0.55)"))
    if mcut_daily and cut_s is not None:
        legend_items.append(("M-cut 切面窗口", MCUT_AREA_COLOR, "rgba(251,191,36,0.55)"))
    if mstart_daily and start_idx is not None:
        legend_items.append(("M-start 启动窗口", MSTART_AREA_COLOR, "rgba(96,165,250,0.55)"))
    if legend_items:
        children = []
        x = 0
        for label, fill, border in legend_items:
            children.append({
                "type": "rect",
                "left": x,
                "top": 4,
                "shape": {"width": 14, "height": 12},
                "style": {"fill": fill, "stroke": border, "lineWidth": 1},
            })
            children.append({
                "type": "text",
                "left": x + 18,
                "top": 5,
                "style": {"text": label, "fill": text_color, "font": "12px sans-serif"},
            })
            x += 18 + len(label) * 14 + 18
        option["graphic"] = [{
            "type": "group",
            "right": 20,
            "top": 30,
            "children": children,
        }]

    return option


def build_thumbnail_option(rows: list[dict], cut_idx: int, *,
                            title: str = "", dark: bool = True,
                            window: int = 30) -> dict:
    """构造候选缩略卡的极简 K 线 option，无 MA、无成交量、保留切面标注。"""
    n = len(rows)
    if n == 0 or cut_idx is None:
        return {}
    start = max(0, cut_idx - window)
    end = min(n - 1, cut_idx + 3)
    categories, values, _vol, _f, _ = _rows_to_arrays(rows, start, end)
    cut_s = cut_idx - start if 0 <= cut_idx - start < len(categories) else None
    mark_lines = []
    if cut_s is not None:
        mark_lines.append({
            "xAxis": categories[cut_s],
            "lineStyle": {"width": 0, "opacity": 0},
            "label": {"formatter": "切", "color": CUT_LINE_COLOR,
                      "fontWeight": "bold"},
        })
    text_color = "#f1f5f9" if dark else "#1f2937"
    return {
        "title": {"text": title, "left": "center", "top": 2,
                  "textStyle": {"color": text_color, "fontSize": 12, "fontWeight": "bold"}},
        "darkMode": dark,
        "backgroundColor": "transparent",
        "animation": False,
        "grid": {"left": "4%", "right": "4%", "top": "20%", "bottom": "8%"},
        "xAxis": {
            "type": "category", "data": categories,
            "axisLabel": {"show": False}, "axisTick": {"show": False},
            "splitLine": {"show": False},
        },
        "yAxis": {
            "scale": True, "axisLabel": {"show": False},
            "axisLine": {"show": False}, "axisTick": {"show": False},
            "splitLine": {"show": False},
        },
        "series": [{
            "type": "candlestick", "data": values,
            "itemStyle": {"color": UP_COLOR, "color0": DOWN_COLOR,
                          "borderColor": UP_COLOR, "borderColor0": DOWN_COLOR},
            "markLine": {"symbol": ["none", "none"], "data": mark_lines, "silent": True}
            if mark_lines else None,
        }],
    }
