"""
v2.3 微型结构对比：按板高度横向 N 格展示标的 / 候选的特殊板型位置序列。

为什么用 HTML/CSS 而不是 ECharts graph：
- 断板版固定 5 格 + 320px 半屏容器恰好不挤；v2.3 板数 2~10+ 不固定，
  ECharts `graph layout:"none"` 用逻辑像素绝对坐标，容器变窄时整体缩放，
  文字与卡片会被压扁（实测半屏容器装 8 格直接看不清）。
- 改用 CSS Grid（auto-fit + minmax），N 格按容器宽度自适应；超 6 板自动换行。

颜色规则：
    * 板型完全相同 → 绿色
    * 同组（ACCEL_GROUP / SWAP_GROUP）近似 → 蓝色
    * 不同 → 红色
    * 某一行没有此格（板高不足）→ 灰色"无"
标的 / 候选最后一格（cut_special 所在格）金色描边。
"""
from __future__ import annotations

from html import escape

try:
    from data_layer_v23 import APP as _APP_V23
    SPECIAL_TYPES = set(_APP_V23.SPECIAL_TYPES)
    ACCEL_GROUP = set(_APP_V23.ACCEL_GROUP)
    SWAP_GROUP = set(_APP_V23.SWAP_GROUP)
except Exception:
    SPECIAL_TYPES = {'一字板', 'T字板', '地天板', '大长腿', '秒板'}
    ACCEL_GROUP = {'一字板', 'T字板', '秒板'}
    SWAP_GROUP = {'普通涨停', '大长腿', '地天板'}


def _same_group(a: str, b: str) -> bool:
    if a in ACCEL_GROUP and b in ACCEL_GROUP:
        return True
    if a in SWAP_GROUP and b in SWAP_GROUP:
        return True
    return False


def _cell_color(t_val: str, c_val: str) -> tuple[str, str]:
    if t_val == "无" and c_val == "无":
        return "#475569", "#475569"
    if t_val == "无":
        return "#475569", "#ef4444"
    if c_val == "无":
        return "#ef4444", "#475569"
    if t_val == c_val:
        return "#22c55e", "#22c55e"
    if _same_group(t_val, c_val):
        return "#3b82f6", "#3b82f6"
    return "#ef4444", "#ef4444"


def build_micro_compare_html_v23(target_case: dict, cand_case: dict,
                                  *, dark: bool = True) -> str:
    """生成 v2.3 微型结构对比的 HTML 片段（直接喂给 st.markdown unsafe_allow_html=True）。"""
    t_seq = list(target_case.get("special_position_seq") or [])
    c_seq = list(cand_case.get("special_position_seq") or [])
    t_h = int(target_case.get("board_height") or len(t_seq))
    c_h = int(cand_case.get("board_height") or len(c_seq))
    n_cells = max(t_h, c_h, len(t_seq), len(c_seq), 1)

    def _get(seq, i, total):
        if i >= total:
            return "无"
        if i < len(seq):
            return seq[i] or "无"
        return "无"

    tcode = f"{target_case.get('stock_code','')} {target_case.get('stock_name','')}".strip()
    ccode = f"{cand_case.get('stock_code','')} {cand_case.get('stock_name','')}".strip()

    title_t = escape(f"标的：{tcode}（{t_h}板）")
    title_c = escape(f"候选：{ccode}（{c_h}板）")

    title_t_color = "#fbbf24"
    title_c_color = "#60a5fa"
    bg_card = "#1a2236" if dark else "#f8fafc"
    text_main = "#ffffff"
    border_default = "rgba(255,255,255,0.18)" if dark else "rgba(15,23,42,0.18)"
    border_last = "#fbbf24"

    def _row_cells(seq, total, is_target):
        items = []
        for i in range(n_cells):
            t_val = _get(t_seq, i, t_h)
            c_val = _get(c_seq, i, c_h)
            ct, cc = _cell_color(t_val, c_val)
            color = ct if is_target else cc
            val = t_val if is_target else c_val
            is_last = (i == (t_h if is_target else c_h) - 1) and (
                (t_h if is_target else c_h) > 0
            )
            border = border_last if is_last else border_default
            border_w = "3px" if is_last else "2px"
            cell_html = (
                f"<div class='mc23-cell' style="
                f"\"background:{color};border:{border_w} solid {border};"
                f"color:{text_main};\">"
                f"<div class='mc23-idx'>第{i+1}板</div>"
                f"<div class='mc23-val'>{escape(str(val))}</div>"
                f"</div>"
            )
            items.append(cell_html)
        return "".join(items)

    css = f"""
    <style>
    .mc23-wrap {{
        background: {bg_card};
        border-radius: 10px;
        padding: 14px 16px 18px;
        border: 1px solid {border_default};
    }}
    .mc23-row-title {{
        font-size: 13px;
        font-weight: 700;
        margin: 4px 0 8px;
    }}
    .mc23-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
        gap: 8px;
        margin-bottom: 12px;
    }}
    .mc23-cell {{
        border-radius: 8px;
        padding: 10px 6px;
        text-align: center;
        line-height: 1.3;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
        min-height: 60px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        word-break: break-all;
    }}
    .mc23-idx {{
        font-size: 11px;
        opacity: 0.85;
        font-weight: 500;
        margin-bottom: 2px;
    }}
    .mc23-val {{
        font-size: 13px;
        font-weight: 700;
    }}
    </style>
    """

    html = (
        f"{css}"
        f"<div class='mc23-wrap'>"
        f"<div class='mc23-row-title' style='color:{title_t_color};'>{title_t}</div>"
        f"<div class='mc23-grid'>{_row_cells(t_seq, t_h, True)}</div>"
        f"<div class='mc23-row-title' style='color:{title_c_color};'>{title_c}</div>"
        f"<div class='mc23-grid'>{_row_cells(c_seq, c_h, False)}</div>"
        f"</div>"
    )
    return html
