"""
打分瀑布图：解析 penalty_details（中文条目列表）→ ECharts waterfall。
penalty_details 形如 ['A类-10', '涨幅跨1档-20', 'D1精确+6', '微切面精确+15', '距离-3.2']
"""
from __future__ import annotations

import re

_DETAIL_RE = re.compile(r"^(.+?)([+\-])([0-9]+(?:\.[0-9]+)?)$")


def parse_details(details: list[str]) -> list[tuple[str, float]]:
    """每条 → (label, signed_value)。+ 为加分，- 为扣分（保留负号）。"""
    parsed = []
    for d in details or []:
        m = _DETAIL_RE.match(d.strip())
        if not m:
            continue
        label = m.group(1).strip()
        sign = m.group(2)
        val = float(m.group(3))
        if sign == "-":
            val = -val
        parsed.append((label, val))
    return parsed


def build_waterfall_option(
    details: list[str],
    *,
    final_score: float,
    dark: bool = True,
    base: float = 100.0,
) -> dict:
    """ECharts waterfall（堆叠 bar 实现）。"""
    items = parse_details(details)
    text_color = "#f1f5f9" if dark else "#1f2937"
    bg = "#1a2236" if dark else "#ffffff"
    grid_color = "#334155" if dark else "#e5e7eb"

    labels = ["初始 100"]
    placeholders = [0.0]
    incomes = [base]
    expenses = [0.0]
    cum = base

    for label, v in items:
        labels.append(label)
        if v >= 0:
            placeholders.append(cum)
            incomes.append(v)
            expenses.append(0.0)
        else:
            placeholders.append(cum + v)
            incomes.append(0.0)
            expenses.append(-v)
        cum += v

    labels.append(f"最终 {final_score:.1f}")
    placeholders.append(0.0)
    incomes.append(max(final_score, 0.0))
    expenses.append(0.0)

    return {
        "darkMode": dark,
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "backgroundColor": bg,
            "borderColor": grid_color,
            "textStyle": {"color": text_color, "fontSize": 13},
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "22%", "top": "8%", "containLabel": True},
        "xAxis": {
            "type": "category", "data": labels,
            "axisLabel": {"color": text_color, "rotate": 35, "fontSize": 12,
                          "fontWeight": 500, "margin": 12, "interval": 0},
            "axisLine": {"lineStyle": {"color": grid_color}},
            "axisTick": {"lineStyle": {"color": grid_color}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": text_color, "fontSize": 12},
            "axisLine": {"show": True, "lineStyle": {"color": grid_color}},
            "splitLine": {"lineStyle": {"color": grid_color, "opacity": 0.3}},
        },
        "series": [
            {
                "name": "__base", "type": "bar", "stack": "total",
                "itemStyle": {"borderColor": "transparent", "color": "transparent"},
                "emphasis": {"itemStyle": {"borderColor": "transparent", "color": "transparent"}},
                "data": placeholders,
            },
            {
                "name": "加分/得分", "type": "bar", "stack": "total",
                "itemStyle": {"color": "#22c55e", "borderRadius": [3, 3, 0, 0]},
                "label": {"show": True, "position": "top", "color": "#22c55e",
                          "fontSize": 12, "fontWeight": 600, "formatter": "+{c}"},
                "data": [v if v > 0 else None for v in incomes],
            },
            {
                "name": "扣分", "type": "bar", "stack": "total",
                "itemStyle": {"color": "#ef4444", "borderRadius": [3, 3, 0, 0]},
                "label": {"show": True, "position": "top", "color": "#ef4444",
                          "fontSize": 12, "fontWeight": 600, "formatter": "-{c}"},
                "data": [v if v > 0 else None for v in expenses],
            },
        ],
    }
