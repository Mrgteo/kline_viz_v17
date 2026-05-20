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
SEG_AREA_COLOR = "rgba(16,185,129,0.18)"
BREAK_AREA_COLOR = "rgba(239,68,68,0.18)"
D1_LINE_COLOR = "#f59e0b"
D2_LINE_COLOR = "#a78bfa"
CUT_LINE_COLOR = "#fbbf24"


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

    mark_areas = []
    for ss, ee in seg_shift:
        mark_areas.append([
            {"xAxis": categories[ss], "itemStyle": {"color": SEG_AREA_COLOR},
             "name": "涨停段"},
            {"xAxis": categories[ee]},
        ])
    for ss, ee in bp_shift:
        mark_areas.append([
            {"xAxis": categories[ss], "itemStyle": {"color": BREAK_AREA_COLOR},
             "name": "断板期"},
            {"xAxis": categories[ee]},
        ])

    mark_lines = []
    if d1_s is not None:
        mark_lines.append({
            "xAxis": categories[d1_s],
            "lineStyle": {"color": D1_LINE_COLOR, "width": 2, "type": "dashed"},
            "label": {"formatter": "D1", "color": D1_LINE_COLOR, "position": "insideEndTop"},
        })
    if d2_s is not None:
        mark_lines.append({
            "xAxis": categories[d2_s],
            "lineStyle": {"color": D2_LINE_COLOR, "width": 2, "type": "dashed"},
            "label": {"formatter": "D2", "color": D2_LINE_COLOR, "position": "insideEndTop"},
        })
    if cut_s is not None:
        mark_lines.append({
            "xAxis": categories[cut_s],
            "lineStyle": {"color": CUT_LINE_COLOR, "width": 2.5},
            "label": {"formatter": "切面", "color": CUT_LINE_COLOR, "position": "insideEndTop"},
        })

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
            {"left": "8%", "right": "8%", "height": "55%", "top": "10%"},
            {"left": "8%", "right": "8%", "top": "72%", "height": "15%"},
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
                "data": values,
                "itemStyle": {
                    "color": UP_COLOR, "color0": DOWN_COLOR,
                    "borderColor": UP_COLOR, "borderColor0": DOWN_COLOR,
                },
                "markArea": {"silent": True, "data": mark_areas} if mark_areas else None,
                "markLine": {"symbol": ["none", "none"], "data": mark_lines, "silent": True}
                if mark_lines else None,
                "markPoint": {"data": form_points, "silent": True} if form_points else None,
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
            "lineStyle": {"color": CUT_LINE_COLOR, "width": 2},
            "label": {"formatter": "切", "color": CUT_LINE_COLOR},
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
