"""Deterministic SVG renderer for diagram specs.

Produces polished, professional system-design diagrams with:
- Drop shadows and soft glows
- Gradient fills on components
- Rich icons (user, gateway, shield, database, server)
- Animated dashed-arrow highlighting for active flow paths
- Strong dim/focus contrast for walkthrough states
- Status badges, example labels, side panels
- Flow-path legend with colored indicators
- Algorithm overlay cards
"""

from __future__ import annotations

import html
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_WIDTH = 1400
_DEFAULT_HEIGHT = 750
_COMPONENT_RX = 14
_FONT_FAMILY = "'Inter','Segoe UI','Roboto',system-ui,sans-serif"
_FONT_SIZE_LABEL = 13
_FONT_SIZE_SUBLABEL = 10
_FONT_SIZE_CONN = 10
_FONT_SIZE_ANNOTATION = 10
_ARROW_SIZE = 9
_DIM_OPACITY = 0.10
_SHADOW_ID = "shadow"
_GLOW_ALLOWED = "glow-allowed"
_GLOW_BLOCKED = "glow-blocked"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _center(comp: dict) -> tuple[float, float]:
    return comp["x"] + comp["w"] / 2, comp["y"] + comp["h"] / 2


def _edge_point(comp: dict, target_cx: float, target_cy: float) -> tuple[float, float]:
    cx, cy = _center(comp)
    dx = target_cx - cx
    dy = target_cy - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = comp["w"] / 2, comp["h"] / 2
    abs_dx, abs_dy = abs(dx), abs(dy)
    if abs_dx * hh > abs_dy * hw:
        t = hw / abs_dx
    else:
        t = hh / abs_dy
    return cx + dx * t, cy + dy * t


# ── Icons ────────────────────────────────────────────────────────────

def _icon_user(cx: float, cy: float, color: str = "#546E7A") -> str:
    return (
        f'<circle cx="{cx}" cy="{cy - 8}" r="7" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<path d="M{cx - 11},{cy + 10} C{cx - 11},{cy - 2} {cx + 11},{cy - 2} {cx + 11},{cy + 10}" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    )


def _icon_gateway(cx: float, cy: float, color: str = "#546E7A") -> str:
    return (
        f'<rect x="{cx - 12}" y="{cy - 10}" width="24" height="8" rx="2" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<rect x="{cx - 12}" y="{cy + 2}" width="24" height="8" rx="2" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<circle cx="{cx - 6}" cy="{cy - 6}" r="1.5" fill="{color}"/>'
        f'<circle cx="{cx - 6}" cy="{cy + 6}" r="1.5" fill="{color}"/>'
    )


def _icon_shield(cx: float, cy: float, color: str = "#1565C0") -> str:
    return (
        f'<path d="M{cx},{cy - 14} L{cx + 12},{cy - 6} L{cx + 12},{cy + 4} '
        f'Q{cx},{cy + 16} {cx - 12},{cy + 4} L{cx - 12},{cy - 6} Z" '
        f'fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.8"/>'
        f'<path d="M{cx - 4},{cy + 1} L{cx - 1},{cy + 4} L{cx + 5},{cy - 3}" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _icon_database(cx: float, cy: float, color: str = "#546E7A") -> str:
    return (
        f'<ellipse cx="{cx}" cy="{cy - 8}" rx="13" ry="5" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<path d="M{cx - 13},{cy - 8} V{cy + 6}" stroke="{color}" stroke-width="1.8"/>'
        f'<path d="M{cx + 13},{cy - 8} V{cy + 6}" stroke="{color}" stroke-width="1.8"/>'
        f'<ellipse cx="{cx}" cy="{cy + 6}" rx="13" ry="5" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<ellipse cx="{cx}" cy="{cy - 1}" rx="13" ry="5" fill="none" stroke="{color}" stroke-width="0.8" stroke-dasharray="2 2"/>'
    )


def _icon_server(cx: float, cy: float, color: str = "#546E7A") -> str:
    return (
        f'<rect x="{cx - 13}" y="{cy - 12}" width="26" height="10" rx="2" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<rect x="{cx - 13}" y="{cy + 2}" width="26" height="10" rx="2" fill="none" stroke="{color}" stroke-width="1.8"/>'
        f'<circle cx="{cx + 8}" cy="{cy - 7}" r="1.5" fill="{color}"/>'
        f'<circle cx="{cx + 8}" cy="{cy + 7}" r="1.5" fill="{color}"/>'
        f'<line x1="{cx - 8}" y1="{cy - 7}" x2="{cx + 3}" y2="{cy - 7}" stroke="{color}" stroke-width="1.2"/>'
        f'<line x1="{cx - 8}" y1="{cy + 7}" x2="{cx + 3}" y2="{cy + 7}" stroke="{color}" stroke-width="1.2"/>'
    )


_ICON_DISPATCH = {
    "user": _icon_user,
    "gateway": _icon_gateway,
    "shield": _icon_shield,
    "database": _icon_database,
    "server": _icon_server,
}


def _build_icon_svg(icon: str, cx: float, cy: float, color: str = "#546E7A") -> str:
    fn = _ICON_DISPATCH.get(icon)
    return fn(cx, cy, color) if fn else ""


# ── Text helpers ─────────────────────────────────────────────────────

def _multiline_text(
    x: float, y: float, text: str, font_size: int,
    anchor: str = "middle", cls: str = "", fill: str = "#333",
    font_weight: str = "normal",
) -> str:
    lines = text.split("\n")
    cls_attr = f' class="{cls}"' if cls else ""
    parts: list[str] = [
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{font_size}" '
        f'font-family="{_FONT_FAMILY}" fill="{fill}" font-weight="{font_weight}"{cls_attr}>'
    ]
    for i, line in enumerate(lines):
        dy = "0" if i == 0 else f"{font_size + 3}"
        parts.append(f'<tspan x="{x}" dy="{dy}">{_esc(line)}</tspan>')
    parts.append("</text>")
    return "\n".join(parts)


# ── Main renderer ────────────────────────────────────────────────────

def render_svg(
    spec: dict,
    *,
    highlight_paths: list[str] | None = None,
    focus_regions: list[str] | None = None,
    dim_regions: list[str] | None = None,
    overlay_mode: str | None = None,
    include_css_animation: bool = False,
) -> str:
    layout = spec.get("layout", {})
    w = layout.get("width", _DEFAULT_WIDTH)
    h = layout.get("height", _DEFAULT_HEIGHT)
    bg = layout.get("background", "#FAFBFC")
    components: list[dict] = spec.get("components", [])
    connections: list[dict] = spec.get("connections", [])
    annotations: list[dict] = spec.get("annotations", [])
    flow_paths: dict[str, dict] = spec.get("flow_paths", {})
    status_badges: list[dict] = spec.get("status_badges", [])
    side_panel: dict | None = spec.get("side_panel")

    comp_map: dict[str, dict] = {c["id"]: c for c in components}
    highlight_set = set(highlight_paths or [])
    focus_set = set(focus_regions) if focus_regions else None
    dim_set = set(dim_regions or [])

    has_highlight = bool(highlight_set)

    def _is_dimmed(comp_id: str) -> bool:
        if comp_id in dim_set:
            return True
        if focus_set is not None and comp_id not in focus_set:
            return True
        return False

    def _is_focused(comp_id: str) -> bool:
        if focus_set is not None and comp_id in focus_set and comp_id not in dim_set:
            return True
        return False

    P: list[str] = []

    P.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="{_FONT_FAMILY}">'
    )

    # ── CSS ──
    P.append(f"""<style>
  .comp-group {{ transition: opacity 0.5s ease, filter 0.5s ease; cursor: pointer; }}
  .comp-group:hover {{ filter: drop-shadow(0 0 6px rgba(99,102,241,0.4)); }}
  .comp-group.dimmed {{ opacity: {_DIM_OPACITY}; filter: grayscale(80%); }}
  .comp-group.dimmed:hover {{ filter: grayscale(80%) drop-shadow(0 0 4px rgba(99,102,241,0.3)); opacity: 0.4; }}
  .comp-group.focused {{ filter: drop-shadow(0 0 8px rgba(21,101,192,0.35)); }}
  .conn-line {{ transition: opacity 0.5s ease, stroke-width 0.3s ease; }}
  .conn-line.dimmed {{ opacity: {_DIM_OPACITY}; }}
  .conn-line.highlighted {{ stroke-width: 3.5; filter: drop-shadow(0 0 4px currentColor); }}
  .conn-label {{ fill: #555; font-size: {_FONT_SIZE_CONN}px; }}
  .conn-label.dimmed {{ opacity: {_DIM_OPACITY}; }}
  .annotation-text {{ fill: #78909C; font-size: {_FONT_SIZE_ANNOTATION}px; font-style: italic; }}
  .badge-text {{ font-size: 9px; font-weight: 600; }}
</style>""")

    if include_css_animation or has_highlight:
        P.append("""<style>
  @keyframes dash-flow { to { stroke-dashoffset: -24; } }
  @keyframes pulse-glow { 0%,100% { opacity: 0.7; } 50% { opacity: 1; } }
  .conn-line.highlighted {
    stroke-dasharray: 10 5;
    animation: dash-flow 0.7s linear infinite;
  }
  .comp-group.focused {
    animation: pulse-glow 2s ease-in-out infinite;
  }
</style>""")

    # ── Defs: shadows, gradients, markers ──
    P.append("<defs>")

    P.append(
        f'<filter id="{_SHADOW_ID}" x="-8%" y="-8%" width="116%" height="116%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#00000018"/>'
        '</filter>'
    )
    P.append(
        f'<filter id="{_GLOW_ALLOWED}" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#4CAF50" flood-opacity="0.5"/>'
        '</filter>'
    )
    P.append(
        f'<filter id="{_GLOW_BLOCKED}" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#F44336" flood-opacity="0.5"/>'
        '</filter>'
    )

    P.append(
        '<linearGradient id="bg-grad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#FFFFFF"/>'
        '<stop offset="100%" stop-color="#F0F4F8"/>'
        '</linearGradient>'
    )

    for cid, comp in ((c["id"], c) for c in components):
        fill = comp.get("fill", "#F8F9FA")
        stroke = comp.get("stroke", "#DEE2E6")
        P.append(
            f'<linearGradient id="grad-{_esc(cid)}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{fill}"/>'
            f'<stop offset="100%" stop-color="{stroke}" stop-opacity="0.15"/>'
            f'</linearGradient>'
        )

    P.append(
        f'<marker id="arrow-default" viewBox="0 0 {_ARROW_SIZE} {_ARROW_SIZE}" '
        f'refX="{_ARROW_SIZE}" refY="{_ARROW_SIZE / 2}" '
        f'markerWidth="{_ARROW_SIZE}" markerHeight="{_ARROW_SIZE}" orient="auto-start-reverse">'
        f'<path d="M0,1 L{_ARROW_SIZE},{_ARROW_SIZE / 2} L0,{_ARROW_SIZE - 1}" '
        f'fill="#90A4AE" stroke="none"/>'
        '</marker>'
    )
    for fp_id, fp in flow_paths.items():
        color = fp.get("color", "#888")
        P.append(
            f'<marker id="arrow-{_esc(fp_id)}" viewBox="0 0 {_ARROW_SIZE} {_ARROW_SIZE}" '
            f'refX="{_ARROW_SIZE}" refY="{_ARROW_SIZE / 2}" '
            f'markerWidth="{_ARROW_SIZE}" markerHeight="{_ARROW_SIZE}" orient="auto-start-reverse">'
            f'<path d="M0,1 L{_ARROW_SIZE},{_ARROW_SIZE / 2} L0,{_ARROW_SIZE - 1}" fill="{color}"/>'
            '</marker>'
        )

    P.append("</defs>")

    # ── Background ──
    P.append(f'<rect width="{w}" height="{h}" fill="url(#bg-grad)"/>')

    # ── Flow-path legends at top ──
    if flow_paths:
        for i, (fp_id, fp) in enumerate(flow_paths.items()):
            color = fp.get("color", "#888")
            label = fp.get("label", fp_id)
            desc = fp.get("description", "")
            lx = 30 + i * 320
            ly = 18
            P.append(
                f'<circle cx="{lx}" cy="{ly}" r="10" fill="{color}" opacity="0.9"/>'
            )
            P.append(
                f'<text x="{lx}" y="{ly + 4}" text-anchor="middle" font-size="11" '
                f'fill="white" font-weight="bold">{chr(65 + i)}</text>'
            )
            P.append(
                f'<text x="{lx + 16}" y="{ly + 4}" font-size="12" fill="#333" font-weight="600">'
                f'{_esc(label)}</text>'
            )
            if desc:
                P.append(
                    f'<rect x="{lx + 16}" y="{ly + 8}" width="{len(desc) * 5.5 + 16}" height="18" rx="9" '
                    f'fill="{color}" fill-opacity="0.1"/>'
                )
                P.append(
                    f'<text x="{lx + 24}" y="{ly + 21}" font-size="10" fill="{color}" font-weight="500">'
                    f'{_esc(desc)}</text>'
                )

    # ── Connections (drawn before components so arrows go behind boxes) ──
    for conn in connections:
        from_comp = comp_map.get(conn.get("from", ""))
        to_comp = comp_map.get(conn.get("to", ""))
        if not from_comp or not to_comp:
            continue

        pg = conn.get("path_group")
        fp = flow_paths.get(pg, {}) if pg else {}
        stroke = fp.get("color", "#90A4AE")
        marker = f"url(#arrow-{_esc(pg)})" if pg and pg in flow_paths else "url(#arrow-default)"

        is_highlighted = pg in highlight_set if pg else False
        from_dimmed = _is_dimmed(conn["from"])
        to_dimmed = _is_dimmed(conn["to"])
        conn_dimmed = from_dimmed and to_dimmed

        cls_parts = ["conn-line"]
        if is_highlighted:
            cls_parts.append("highlighted")
        if conn_dimmed and not is_highlighted:
            cls_parts.append("dimmed")

        sw = 3.5 if is_highlighted else 2
        filt = ""
        if is_highlighted:
            glow_id = _GLOW_ALLOWED if pg == "allowed" else _GLOW_BLOCKED if pg == "blocked" else ""
            if glow_id:
                filt = f' filter="url(#{glow_id})"'

        from_cx, from_cy = _center(from_comp)
        to_cx, to_cy = _center(to_comp)
        x1, y1 = _edge_point(from_comp, to_cx, to_cy)
        x2, y2 = _edge_point(to_comp, from_cx, from_cy)

        curve = conn.get("curve")
        if curve == "bottom":
            mid_y = max(y1, y2) + 90
            path_d = f"M{x1},{y1} Q{(x1 + x2) / 2},{mid_y} {x2},{y2}"
        elif curve == "top":
            mid_y = min(y1, y2) - 70
            path_d = f"M{x1},{y1} Q{(x1 + x2) / 2},{mid_y} {x2},{y2}"
        else:
            mx = (x1 + x2) / 2
            path_d = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}"

        P.append(
            f'<path d="{path_d}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" marker-end="{marker}" '
            f'class="{" ".join(cls_parts)}"{filt}/>'
        )

        label = conn.get("label", "")
        if label:
            mid_x = (x1 + x2) / 2
            mid_y_label = (y1 + y2) / 2
            if curve == "bottom":
                mid_y_label = max(y1, y2) + 45
            elif curve == "top":
                mid_y_label = min(y1, y2) - 35

            label_cls = "conn-label"
            if conn_dimmed and not is_highlighted:
                label_cls += " dimmed"

            lines = label.split("\n")
            for li, line in enumerate(lines):
                P.append(
                    f'<text x="{mid_x}" y="{mid_y_label - 3 + li * 13}" '
                    f'text-anchor="middle" class="{label_cls}">{_esc(line)}</text>'
                )

        annotation = conn.get("annotation")
        if annotation:
            ann_color = conn.get("annotation_color", "#666")
            ax = (x1 + x2) / 2
            ay = (y1 + y2) / 2 + 18
            tw = len(annotation) * 6 + 14
            P.append(
                f'<rect x="{ax - tw / 2}" y="{ay - 11}" width="{tw}" height="18" rx="9" '
                f'fill="{ann_color}" fill-opacity="0.15"/>'
            )
            P.append(
                f'<text x="{ax}" y="{ay + 2}" text-anchor="middle" font-size="11" '
                f'font-weight="700" fill="{ann_color}">{_esc(annotation)}</text>'
            )

    # ── Components ──
    for comp in components:
        cid = comp["id"]
        dimmed = _is_dimmed(cid)
        focused = _is_focused(cid) and has_highlight

        cls = "comp-group"
        if dimmed:
            cls += " dimmed"
        elif focused:
            cls += " focused"

        cx, cy = _center(comp)
        fill = comp.get("fill", "#F8F9FA")
        stroke = comp.get("stroke", "#CFD8DC")
        icon_color = comp.get("stroke", "#546E7A")

        P.append(f'<g class="{cls}" data-component="{_esc(cid)}">')

        style = comp.get("style", "rounded")
        shadow = f' filter="url(#{_SHADOW_ID})"'

        if style == "cylinder":
            ew = comp["w"] / 2
            eh = 14
            P.append(
                f'<rect x="{comp["x"]}" y="{comp["y"] + eh}" '
                f'width="{comp["w"]}" height="{comp["h"] - eh * 2}" '
                f'fill="url(#grad-{_esc(cid)})" stroke="{stroke}" stroke-width="1.5"{shadow}/>'
            )
            P.append(
                f'<ellipse cx="{cx}" cy="{comp["y"] + eh}" rx="{ew}" ry="{eh}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
            P.append(
                f'<ellipse cx="{cx}" cy="{comp["y"] + comp["h"] - eh}" rx="{ew}" ry="{eh}" '
                f'fill="url(#grad-{_esc(cid)})" stroke="{stroke}" stroke-width="1.5"/>'
            )
        else:
            P.append(
                f'<rect x="{comp["x"]}" y="{comp["y"]}" '
                f'width="{comp["w"]}" height="{comp["h"]}" '
                f'rx="{_COMPONENT_RX}" ry="{_COMPONENT_RX}" '
                f'fill="url(#grad-{_esc(cid)})" stroke="{stroke}" stroke-width="1.5"{shadow}/>'
            )

        icon = comp.get("icon")
        if icon:
            P.append(_build_icon_svg(icon, cx, comp["y"] + 30, icon_color))

        label = comp.get("label", cid)
        label_y = cy + 12 if icon else cy + 4
        P.append(_multiline_text(cx, label_y, label, _FONT_SIZE_LABEL, fill="#37474F", font_weight="600"))

        P.append("</g>")

    # ── Status badges (inside or near components) ──
    for badge in status_badges:
        anchor_comp = comp_map.get(badge.get("anchor", ""))
        if not anchor_comp:
            continue
        color = badge.get("color", "#888")
        text = badge.get("text", "")
        pos = badge.get("position", "inner-top")
        acx, acy = _center(anchor_comp)

        if pos == "inner-top":
            bx, by = acx, anchor_comp["y"] + 22
        elif pos == "inner-bottom":
            bx, by = acx, anchor_comp["y"] + anchor_comp["h"] - 14
        else:
            bx, by = acx, acy

        lines = text.split("\n")
        bh = len(lines) * 13 + 6
        bw = max(len(l) for l in lines) * 6 + 16

        dimmed_anchor = _is_dimmed(badge.get("anchor", ""))
        opacity = str(_DIM_OPACITY) if dimmed_anchor else "1"

        P.append(
            f'<g opacity="{opacity}">'
            f'<rect x="{bx - bw / 2}" y="{by - 8}" width="{bw}" height="{bh}" rx="6" '
            f'fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1" stroke-opacity="0.3"/>'
        )
        for li, line in enumerate(lines):
            P.append(
                f'<text x="{bx}" y="{by + 4 + li * 13}" text-anchor="middle" '
                f'class="badge-text" fill="{color}">{_esc(line)}</text>'
            )
        P.append("</g>")

    # ── Annotations ──
    for ann in annotations:
        anchor_comp = comp_map.get(ann.get("anchor", ""))
        if not anchor_comp:
            continue
        pos = ann.get("position", "top")
        acx, acy = _center(anchor_comp)
        if pos == "top":
            ax, ay = acx, anchor_comp["y"] - 22
        elif pos == "bottom":
            ax, ay = acx, anchor_comp["y"] + anchor_comp["h"] + 22
        elif pos == "left":
            ax, ay = anchor_comp["x"] - 12, acy
        else:
            ax, ay = anchor_comp["x"] + anchor_comp["w"] + 12, acy

        text = ann.get("text", "")
        ann_anchor = "end" if pos == "left" else "start" if pos == "right" else "middle"
        P.append(
            _multiline_text(ax, ay, text, _FONT_SIZE_ANNOTATION, anchor=ann_anchor, fill="#78909C")
        )

    # ── Side panel ──
    if side_panel:
        sp_x = side_panel.get("x", w - 220)
        sp_y = side_panel.get("y", 60)
        sp_w = side_panel.get("w", 200)
        sp_title = side_panel.get("title", "Internal Logic")
        sp_items: list[str] = side_panel.get("items", [])

        sp_h = len(sp_items) * 26 + 50
        P.append(
            f'<rect x="{sp_x}" y="{sp_y}" width="{sp_w}" height="{sp_h}" rx="10" '
            f'fill="white" stroke="#CFD8DC" stroke-width="1" filter="url(#{_SHADOW_ID})"/>'
        )
        P.append(
            f'<text x="{sp_x + sp_w / 2}" y="{sp_y + 22}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#37474F">{_esc(sp_title)}</text>'
        )
        P.append(
            f'<line x1="{sp_x + 12}" y1="{sp_y + 32}" x2="{sp_x + sp_w - 12}" y2="{sp_y + 32}" '
            f'stroke="#ECEFF1" stroke-width="1"/>'
        )
        for i, item in enumerate(sp_items):
            iy = sp_y + 48 + i * 26
            P.append(
                f'<rect x="{sp_x + 10}" y="{iy - 8}" width="{sp_w - 20}" height="22" rx="6" '
                f'fill="#E3F2FD" stroke="#90CAF9" stroke-width="0.8"/>'
            )
            P.append(
                f'<text x="{sp_x + sp_w / 2}" y="{iy + 6}" text-anchor="middle" '
                f'font-size="10" fill="#1565C0" font-weight="500">{_esc(item)}</text>'
            )

    # ── Algorithm overlay ──
    if overlay_mode:
        overlays = spec.get("algorithm_overlays", {})
        overlay_data = overlays.get(overlay_mode)
        if overlay_data:
            rl = comp_map.get("rate_limiter")
            if rl:
                ox = rl["x"] - 10
                oy = rl["y"] + rl["h"] + 20
                ow = rl["w"] + 20
                oh = 80
                P.append(
                    f'<rect x="{ox}" y="{oy}" width="{ow}" height="{oh}" rx="10" '
                    f'fill="#FFF8E1" stroke="#FFB300" stroke-width="1.5" filter="url(#{_SHADOW_ID})"/>'
                )
                P.append(
                    f'<text x="{ox + ow / 2}" y="{oy + 20}" text-anchor="middle" '
                    f'font-size="12" font-weight="700" fill="#E65100">'
                    f'{_esc(overlay_data.get("label", overlay_mode))}</text>'
                )
                desc_lines = overlay_data.get("description", "").split(";")
                for di, dl in enumerate(desc_lines):
                    P.append(
                        f'<text x="{ox + ow / 2}" y="{oy + 38 + di * 14}" text-anchor="middle" '
                        f'font-size="10" fill="#5D4037">{_esc(dl.strip())}</text>'
                    )

    # ── Example labels ──
    example_labels = spec.get("example_labels", [])
    for i, el in enumerate(example_labels):
        elx = el.get("x", 30 + i * 220)
        ely = el.get("y", h - 30)
        color = el.get("color", "#666")
        text = el.get("text", "")
        tw = len(text) * 5.8 + 16
        P.append(
            f'<rect x="{elx}" y="{ely - 12}" width="{tw}" height="20" rx="10" '
            f'fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-width="0.8"/>'
        )
        P.append(
            f'<text x="{elx + tw / 2}" y="{ely + 2}" text-anchor="middle" '
            f'font-size="10" fill="{color}" font-weight="600">{_esc(text)}</text>'
        )

    P.append("</svg>")
    return "\n".join(P)


def render_svg_for_state(
    spec: dict,
    state: dict,
    include_css_animation: bool = True,
) -> str:
    return render_svg(
        spec,
        highlight_paths=state.get("highlight_paths"),
        focus_regions=state.get("focus_regions"),
        dim_regions=state.get("dim_regions"),
        overlay_mode=state.get("overlay_mode"),
        include_css_animation=include_css_animation,
    )


def svg_to_png(svg_string: str, width: int = 1920, height: int = 1080) -> bytes:
    try:
        import cairosvg
        return cairosvg.svg2png(
            bytestring=svg_string.encode("utf-8"),
            output_width=width,
            output_height=height,
        )
    except ImportError:
        logger.warning("cairosvg not installed — falling back to PIL PNG")
        from PIL import Image
        img = Image.new("RGB", (width, height), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        logger.exception("SVG-to-PNG conversion failed")
        from PIL import Image
        img = Image.new("RGB", (width, height), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
