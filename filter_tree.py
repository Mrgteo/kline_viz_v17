"""
硬过滤降级树：把 hard_filter_with_downgrade 的日志可视化为阶梯下落图。
每一步显示剩余案例数，触发降级的步骤标记扣分。
"""
from __future__ import annotations


def build_filter_tree_option(filter_log: list[dict], *, dark: bool = True) -> dict:
    text_color = "#f1f5f9" if dark else "#1f2937"
    bg = "#1a2236" if dark else "#ffffff"
    grid_color = "#334155" if dark else "#e5e7eb"

    labels = [item["label"] for item in filter_log]
    counts = [item["count"] for item in filter_log]
    penalties = [item["penalty"] for item in filter_log]

    bar_colors = ["#ef4444" if p > 0 else "#22c55e" for p in penalties]

    return {
        "darkMode": dark,
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "backgroundColor": bg, "borderColor": grid_color,
            "textStyle": {"color": text_color, "fontSize": 13},
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "25%", "top": "10%",
                 "containLabel": True},
        "xAxis": {
            "type": "category", "data": labels,
            "axisLabel": {"color": text_color, "rotate": 30, "fontSize": 12,
                          "fontWeight": 500, "interval": 0, "margin": 12},
            "axisLine": {"lineStyle": {"color": grid_color}},
            "axisTick": {"lineStyle": {"color": grid_color}},
        },
        "yAxis": {
            "type": "value", "name": "剩余案例数",
            "nameTextStyle": {"color": text_color, "fontSize": 12},
            "axisLabel": {"color": text_color, "fontSize": 12},
            "axisLine": {"show": True, "lineStyle": {"color": grid_color}},
            "splitLine": {"lineStyle": {"color": grid_color, "opacity": 0.3}},
        },
        "series": [
            {
                "type": "bar",
                "data": [{"value": c, "itemStyle": {"color": bc, "borderRadius": [4, 4, 0, 0]}}
                          for c, bc in zip(counts, bar_colors)],
                "label": {"show": True, "position": "top", "color": text_color,
                          "fontSize": 12, "fontWeight": 600,
                          "formatter": "{c}"},
                "barMaxWidth": 50,
            },
            {
                "type": "line", "data": counts, "smooth": True,
                "lineStyle": {"color": "#fbbf24", "width": 2.5, "type": "dashed"},
                "showSymbol": True, "symbol": "circle", "symbolSize": 9,
                "itemStyle": {"color": "#fbbf24"},
                "z": 10,
            },
        ],
    }
