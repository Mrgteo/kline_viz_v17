"""
微型结构 5 格对比：涨停 → 中间 → 前置前 → 前置 → 切面
返回 ECharts option，使用 graph 类型横向排列 5 个节点 + 标的/候选两行。
"""
from __future__ import annotations


MICRO_KEYS = [
    ("nearest_zt_subdivision", "最近涨停"),
    ("mid_special_subdivision", "中间特殊"),
    ("pre_prev_subdivision", "前置前"),
    ("nearest_special_subdivision", "前置"),
    ("cut_subdivision", "切面"),
]


def build_micro_compare_option(target_case: dict, cand_case: dict, *, dark: bool = True) -> dict:
    tm = target_case.get("micro", {})
    cm = cand_case.get("micro", {})
    text_color = "#f1f5f9" if dark else "#1f2937"
    bg = "#1a2236" if dark else "#ffffff"

    nodes = []
    edges = []
    spacing = 180
    y_target = 80
    y_cand = 210

    tcode = f"{target_case.get('stock_code','')} {target_case.get('stock_name','')}"
    ccode = f"{cand_case.get('stock_code','')} {cand_case.get('stock_name','')}"

    for i, (key, label) in enumerate(MICRO_KEYS):
        t_val = tm.get(key, "无")
        c_val = cm.get(key, "无")
        match = t_val == c_val
        color_t = "#22c55e" if match else "#3b82f6"
        color_c = "#22c55e" if match else "#ef4444"
        x = 90 + i * spacing
        nodes.append({
            "name": f"T-{label}", "x": x, "y": y_target,
            "symbolSize": [160, 56],
            "itemStyle": {"color": color_t, "borderColor": "#ffffff", "borderWidth": 2,
                          "shadowBlur": 6, "shadowColor": "rgba(0,0,0,0.3)"},
            "label": {"show": True, "formatter": f"{label}\n{t_val}",
                      "color": "#ffffff", "fontSize": 13, "fontWeight": "bold",
                      "lineHeight": 18},
        })
        nodes.append({
            "name": f"C-{label}", "x": x, "y": y_cand,
            "symbolSize": [160, 56],
            "itemStyle": {"color": color_c, "borderColor": "#ffffff", "borderWidth": 2,
                          "shadowBlur": 6, "shadowColor": "rgba(0,0,0,0.3)"},
            "label": {"show": True, "formatter": f"{label}\n{c_val}",
                      "color": "#ffffff", "fontSize": 13, "fontWeight": "bold",
                      "lineHeight": 18},
        })

    for i in range(len(MICRO_KEYS) - 1):
        ta, tb = MICRO_KEYS[i][1], MICRO_KEYS[i + 1][1]
        edges.append({"source": f"T-{ta}", "target": f"T-{tb}",
                      "lineStyle": {"color": "#94a3b8", "width": 1.5}})
        edges.append({"source": f"C-{ta}", "target": f"C-{tb}",
                      "lineStyle": {"color": "#94a3b8", "width": 1.5}})

    return {
        "darkMode": dark,
        "backgroundColor": "transparent",
        "title": [
            {"text": f"标的：{tcode}", "left": 16, "top": 50,
             "textStyle": {"color": "#fbbf24", "fontSize": 13, "fontWeight": "bold"}},
            {"text": f"候选：{ccode}", "left": 16, "top": 160,
             "textStyle": {"color": "#60a5fa", "fontSize": 13, "fontWeight": "bold"}},
        ],
        "tooltip": {"backgroundColor": bg, "borderColor": "#334155",
                    "textStyle": {"color": text_color, "fontSize": 13}},
        "series": [{
            "type": "graph", "layout": "none", "coordinateSystem": None,
            "symbol": "rect", "symbolSize": [160, 56],
            "roam": False, "data": nodes, "links": edges,
            "label": {"show": True, "color": "#ffffff"},
            "edgeSymbol": ["none", "arrow"],
            "edgeSymbolSize": 8,
        }],
    }
