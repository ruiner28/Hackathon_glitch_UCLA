import asyncio
import json
import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.providers.base import StorageProvider

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1920, 1080

STYLE_PRESETS = {
    "clean_academic": {
        "bg": (248, 250, 252),
        "fg": (30, 41, 59),
        "primary": (37, 99, 235),
        "secondary": (13, 148, 136),
        "accent": (245, 158, 11),
        "muted": (148, 163, 184),
        "card_bg": (255, 255, 255),
        "node_bg": (219, 234, 254),
        "node_border": (59, 130, 246),
        "edge_color": (100, 116, 139),
        "code_bg": (30, 41, 59),
        "code_fg": (248, 250, 252),
        "gradient_start": (239, 246, 255),
        "gradient_end": (248, 250, 252),
    },
    "modern_technical": {
        "bg": (15, 23, 42),
        "fg": (248, 250, 252),
        "primary": (56, 189, 248),
        "secondary": (129, 140, 248),
        "accent": (244, 114, 182),
        "muted": (100, 116, 139),
        "card_bg": (30, 41, 59),
        "node_bg": (30, 58, 95),
        "node_border": (56, 189, 248),
        "edge_color": (71, 85, 105),
        "code_bg": (2, 6, 23),
        "code_fg": (56, 189, 248),
        "gradient_start": (15, 23, 42),
        "gradient_end": (30, 41, 59),
    },
    "cinematic_minimal": {
        "bg": (24, 24, 27),
        "fg": (250, 250, 250),
        "primary": (167, 139, 250),
        "secondary": (52, 211, 153),
        "accent": (251, 146, 60),
        "muted": (113, 113, 122),
        "card_bg": (39, 39, 42),
        "node_bg": (63, 63, 70),
        "node_border": (167, 139, 250),
        "edge_color": (82, 82, 91),
        "code_bg": (9, 9, 11),
        "code_fg": (167, 139, 250),
        "gradient_start": (24, 24, 27),
        "gradient_end": (39, 39, 42),
    },
}

SCENE_TYPE_ICONS = {
    "deterministic_animation": "CONCEPT FLOW",
    "generated_still_with_motion": "VISUAL",
    "veo_cinematic": "CINEMATIC",
    "code_trace": "CODE TRACE",
    "system_design_graph": "ARCHITECTURE",
    "summary_scene": "SUMMARY",
}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if bold:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _get_mono_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, coords: tuple, radius: int, fill: tuple, outline: tuple | None = None, width: int = 0):
    x1, y1, x2, y2 = coords
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    draw.rounded_rectangle(coords, radius=r, fill=fill, outline=outline, width=width)


def _draw_gradient_bg(img: Image.Image, colors: dict):
    draw = ImageDraw.Draw(img)
    c1 = colors["gradient_start"]
    c2 = colors["gradient_end"]
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Subtle radial accent in center for depth
    accent = colors["primary"]
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_r = 500
    for radius in range(max_r, 0, -4):
        alpha = int(4 * (1 - radius / max_r))
        spot_color = tuple(
            max(0, min(255, c1[i] + (accent[i] - c1[i]) * alpha // 255))
            for i in range(3)
        )
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)],
                     fill=spot_color)


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple, end: tuple, color: tuple, width: int = 2):
    draw.line([start, end], fill=color, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    arrow_len = 12
    px, py = -uy, ux
    tip = end
    left = (tip[0] - arrow_len * ux + arrow_len * 0.4 * px,
            tip[1] - arrow_len * uy + arrow_len * 0.4 * py)
    right = (tip[0] - arrow_len * ux - arrow_len * 0.4 * px,
             tip[1] - arrow_len * uy - arrow_len * 0.4 * py)
    draw.polygon([tip, left, right], fill=color)


def _draw_header(draw: ImageDraw.ImageDraw, scene_index: int, total_scenes: int,
                 lesson_title: str, colors: dict):
    font_small = _get_font(18)
    draw.rectangle([(0, 0), (WIDTH, 60)], fill=colors["card_bg"])
    draw.text((30, 18), "VisualCS", fill=colors["muted"], font=font_small)
    title_short = lesson_title[:50] + "..." if len(lesson_title) > 50 else lesson_title
    draw.text((160, 18), f"  |  {title_short}", fill=colors["muted"], font=font_small)
    progress = f"{scene_index + 1} / {total_scenes}"
    bbox = font_small.getbbox(progress)
    draw.text((WIDTH - (bbox[2] - bbox[0]) - 30, 18), progress, fill=colors["muted"], font=font_small)
    bar_w = int(WIDTH * (scene_index + 1) / max(total_scenes, 1))
    draw.rectangle([(0, 58), (WIDTH, 62)], fill=colors["edge_color"])
    draw.rectangle([(0, 58), (bar_w, 62)], fill=colors["primary"])


def _draw_title_section(draw: ImageDraw.ImageDraw, title: str, scene_type: str,
                        duration: float, colors: dict, y_start: int = 75,
                        learning_objective: str = "") -> int:
    font_title = _get_font(36, bold=True)
    font_badge = _get_font(13, bold=True)
    font_obj = _get_font(18)
    type_label = SCENE_TYPE_ICONS.get(scene_type, scene_type.upper())

    badge_text = f"  {type_label}  "
    bbx = font_badge.getbbox(badge_text)
    bw = bbx[2] - bbx[0] + 16
    bh = 26
    _draw_rounded_rect(draw, (30, y_start, 30 + bw, y_start + bh), 6, colors["primary"])
    contrast = (255, 255, 255) if sum(colors["primary"]) < 400 else (0, 0, 0)
    draw.text((38, y_start + 4), badge_text, fill=contrast, font=font_badge)

    dur_text = f" {int(duration)}s"
    draw.text((45 + bw, y_start + 5), dur_text, fill=colors["muted"], font=font_badge)

    title_y = y_start + bh + 10
    title_lines = _wrap_text(title, font_title, WIDTH - 80)
    for line in title_lines[:2]:
        draw.text((30, title_y), line, fill=colors["fg"], font=font_title)
        title_y += 46

    if learning_objective:
        obj_lines = _wrap_text(f"Goal: {learning_objective}", font_obj, WIDTH - 80)
        for line in obj_lines[:1]:
            draw.text((30, title_y), line, fill=colors["secondary"], font=font_obj)
            title_y += 26

    return title_y + 8


def _draw_narration_bar(draw: ImageDraw.ImageDraw, narration: str, colors: dict):
    if not narration:
        return
    font = _get_font(18)
    bar_h = 120
    bar_y = HEIGHT - bar_h
    draw.rectangle([(0, bar_y), (WIDTH, HEIGHT)], fill=colors["card_bg"])
    draw.rectangle([(0, bar_y), (WIDTH, bar_y + 2)], fill=colors["edge_color"])
    draw.rectangle([(0, bar_y), (6, HEIGHT)], fill=colors["primary"])
    icon_font = _get_font(14, bold=True)
    draw.text((18, bar_y + 10), "NARRATION", fill=colors["primary"], font=icon_font)
    lines = _wrap_text(narration, font, WIDTH - 40)
    y = bar_y + 32
    for nl in lines[:4]:
        draw.text((18, y), nl, fill=colors["fg"], font=font)
        y += 24


# ─── SCENE TYPE RENDERERS ───────────────────────────────────────────

def _render_concept_flow(img: Image.Image, draw: ImageDraw.ImageDraw,
                         spec: dict, colors: dict, content_y: int):
    """Draw key points as connected concept nodes in a flow diagram."""
    points = spec.get("on_screen_text", [])
    if not points:
        return

    font_node = _get_font(22, bold=True)
    font_desc = _get_font(17)
    n = len(points)

    area_top = content_y + 10
    area_bottom = HEIGHT - 130
    area_h = area_bottom - area_top
    area_w = WIDTH - 120

    if n <= 3:
        cols = n
        rows = 1
    elif n <= 6:
        cols = min(3, (n + 1) // 2)
        rows = 2
    else:
        cols = 3
        rows = (n + 2) // 3

    node_w = min(400, (area_w - 70 * (cols - 1)) // cols)
    node_h = min(160, (area_h - 50 * (rows - 1)) // rows)

    total_w = cols * node_w + (cols - 1) * 70
    total_h = rows * node_h + (rows - 1) * 50
    start_x = (WIDTH - total_w) // 2
    start_y = area_top + (area_h - total_h) // 2

    positions: list[tuple[int, int, int, int]] = []
    node_colors_list = [colors["primary"], colors["secondary"], colors["accent"]]

    for i, point in enumerate(points[:cols * rows]):
        row = i // cols
        col = i % cols
        x = start_x + col * (node_w + 70)
        y = start_y + row * (node_h + 50)

        nc = node_colors_list[i % len(node_colors_list)]

        _draw_rounded_rect(draw, (x, y, x + node_w, y + node_h), 14,
                           colors["node_bg"], outline=nc, width=3)
        draw.rectangle([(x + 1, y + 1), (x + node_w - 1, y + 6)], fill=nc)

        step_r = 18
        cx_s = x + 20 + step_r
        cy_s = y + 24 + step_r
        draw.ellipse([(cx_s - step_r, cy_s - step_r), (cx_s + step_r, cy_s + step_r)], fill=nc)
        step_font = _get_font(18, bold=True)
        step_text = str(i + 1)
        sbb = step_font.getbbox(step_text)
        sw = sbb[2] - sbb[0]
        step_contrast = (255, 255, 255) if sum(nc) < 400 else (0, 0, 0)
        draw.text((cx_s - sw // 2, cy_s - 10), step_text, fill=step_contrast, font=step_font)

        text_x = x + 20
        text_y = y + 24 + step_r * 2 + 12
        lines = _wrap_text(str(point), font_node, node_w - 40)
        for j, line in enumerate(lines[:3]):
            f = font_node if j == 0 else font_desc
            draw.text((text_x, text_y), line, fill=colors["fg"], font=f)
            text_y += 30 if j == 0 else 24

        positions.append((x, y, x + node_w, y + node_h))

    for i in range(len(positions) - 1):
        x1, y1, x2, y2 = positions[i]
        nx1, ny1, nx2, ny2 = positions[i + 1]

        row_curr = i // cols
        row_next = (i + 1) // cols
        if row_curr == row_next:
            start_pt = (x2 + 2, (y1 + y2) // 2)
            end_pt = (nx1 - 2, (ny1 + ny2) // 2)
        else:
            start_pt = ((x1 + x2) // 2, y2 + 2)
            end_pt = ((nx1 + nx2) // 2, ny1 - 2)
        _draw_arrow(draw, start_pt, end_pt, colors["primary"], 3)


def _render_code_trace(img: Image.Image, draw: ImageDraw.ImageDraw,
                       spec: dict, colors: dict, content_y: int):
    """Draw algorithm logic on left, step-by-step breakdown on right."""
    points = spec.get("on_screen_text", [])
    if not points:
        return

    font_mono = _get_mono_font(22)
    font_label = _get_font(15, bold=True)
    font_step = _get_font(19)
    font_step_b = _get_font(19, bold=True)

    code_x = 40
    code_y = content_y + 10
    code_w = WIDTH // 2 - 60
    code_h = HEIGHT - content_y - 140

    _draw_rounded_rect(draw, (code_x, code_y, code_x + code_w, code_y + code_h),
                       12, colors["code_bg"])

    for dx, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([(code_x + 16 + dx * 22, code_y + 14),
                      (code_x + 28 + dx * 22, code_y + 26)], fill=c)

    draw.text((code_x + 90, code_y + 12), "algorithm", fill=colors["muted"], font=font_label)

    line_y = code_y + 50
    line_h = 36
    sym_chars = set("→←=≥≤×÷+(){}[]<>:")

    max_lines = min(len(points), (code_h - 70) // line_h)
    for i, point in enumerate(points[:max_lines]):
        is_active = i == len(points) // 2

        if is_active:
            draw.rectangle([(code_x + 4, line_y - 4), (code_x + code_w - 4, line_y + line_h - 4)],
                           fill=(*colors["primary"][:3], 40))
            draw.rectangle([(code_x + 4, line_y - 4), (code_x + 8, line_y + line_h - 4)],
                           fill=colors["primary"])

        marker = "▸" if is_active else " "
        draw.text((code_x + 14, line_y), marker, fill=colors["accent"], font=font_mono)

        text = str(point)
        parts = text.split("→")
        wx = code_x + 44
        for pi, part in enumerate(parts):
            if pi > 0:
                draw.text((wx, line_y), " → ", fill=colors["accent"], font=font_mono)
                bb = font_mono.getbbox(" → ")
                wx += bb[2] - bb[0]
            for word in part.strip().split():
                is_sym = any(c in word for c in sym_chars)
                c = colors["accent"] if is_sym else colors["code_fg"]
                draw.text((wx, line_y), word + " ", fill=c, font=font_mono)
                bb = font_mono.getbbox(word + " ")
                wx += bb[2] - bb[0]

        line_y += line_h

    panel_x = WIDTH // 2 + 20
    panel_y = content_y + 10
    panel_w = WIDTH // 2 - 60
    panel_h = HEIGHT - content_y - 140

    _draw_rounded_rect(draw, (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
                       12, colors["card_bg"])

    draw.text((panel_x + 24, panel_y + 18), "HOW IT WORKS", fill=colors["primary"], font=font_label)
    draw.rectangle([(panel_x + 24, panel_y + 38), (panel_x + 160, panel_y + 40)], fill=colors["primary"])

    step_y = panel_y + 56
    step_h = max(60, min(80, (panel_h - 80) // max(len(points), 1)))
    step_colors = [colors["primary"], colors["secondary"], colors["accent"]]

    for i, point in enumerate(points[:min(len(points), (panel_h - 70) // step_h)]):
        sc = step_colors[i % len(step_colors)]

        draw.rectangle([(panel_x + 24, step_y), (panel_x + 28, step_y + step_h - 16)], fill=sc)

        sn_font = _get_font(14, bold=True)
        cx_c = panel_x + 44
        cy_c = step_y + 2
        draw.ellipse([(cx_c, cy_c), (cx_c + 24, cy_c + 24)], fill=sc)
        sn = str(i + 1)
        sbb = sn_font.getbbox(sn)
        draw.text((cx_c + 12 - (sbb[2] - sbb[0]) // 2, cy_c + 4), sn,
                  fill=(255, 255, 255), font=sn_font)

        lines = _wrap_text(str(point), font_step_b, panel_w - 100)
        draw.text((panel_x + 80, step_y + 4), lines[0], fill=colors["fg"], font=font_step_b)
        if len(lines) > 1:
            draw.text((panel_x + 80, step_y + 28), lines[1], fill=colors["muted"], font=font_step)
        step_y += step_h


def _render_architecture(img: Image.Image, draw: ImageDraw.ImageDraw,
                         spec: dict, colors: dict, content_y: int):
    """Draw an architecture/system design diagram with layered components."""
    points = spec.get("on_screen_text", [])
    if not points:
        return

    font_comp = _get_font(20, bold=True)
    font_detail = _get_font(15)
    n = len(points)

    area_top = content_y + 20
    area_bottom = HEIGHT - 140
    area_h = area_bottom - area_top
    area_w = WIDTH - 140

    if n <= 2:
        cols, rows = n, 1
    elif n <= 4:
        cols, rows = 2, 2
    else:
        cols, rows = min(3, n), (n + 2) // 3

    comp_w = min(360, (area_w - 90 * (cols - 1)) // cols)
    comp_h = min(140, (area_h - 70 * (rows - 1)) // rows)

    total_w = cols * comp_w + (cols - 1) * 90
    total_h = rows * comp_h + (rows - 1) * 70
    start_x = (WIDTH - total_w) // 2
    start_y = area_top + (area_h - total_h) // 2

    positions: list[tuple[int, int, int, int]] = []
    component_colors = [colors["primary"], colors["secondary"], colors["accent"]]

    for i, point in enumerate(points[:cols * rows]):
        row = i // cols
        col = i % cols
        x = start_x + col * (comp_w + 90)
        y = start_y + row * (comp_h + 70)
        cc = component_colors[i % len(component_colors)]

        # Shadow effect
        _draw_rounded_rect(draw, (x + 3, y + 3, x + comp_w + 3, y + comp_h + 3), 10,
                           colors["edge_color"])
        _draw_rounded_rect(draw, (x, y, x + comp_w, y + comp_h), 10,
                           colors["card_bg"], outline=cc, width=2)

        # Colored left accent bar
        draw.rectangle([(x + 2, y + 10), (x + 8, y + comp_h - 10)], fill=cc)

        # Component number badge
        badge_size = 32
        bx = x + comp_w - badge_size - 12
        by = y + 12
        draw.ellipse([(bx, by), (bx + badge_size, by + badge_size)], fill=cc)
        badge_font = _get_font(16, bold=True)
        badge_text = str(i + 1)
        bb = badge_font.getbbox(badge_text)
        bw = bb[2] - bb[0]
        draw.text((bx + badge_size // 2 - bw // 2, by + 7), badge_text,
                  fill=(255, 255, 255) if sum(cc) < 400 else (0, 0, 0), font=badge_font)

        # Component label
        text_x = x + 22
        text_y = y + 18
        lines = _wrap_text(str(point), font_comp, comp_w - 60)
        for j, line in enumerate(lines[:3]):
            f = font_comp if j == 0 else font_detail
            c = colors["fg"] if j == 0 else colors["muted"]
            draw.text((text_x, text_y), line, fill=c, font=f)
            text_y += 28 if j == 0 else 22

        positions.append((x, y, x + comp_w, y + comp_h))

    # Directional arrows between components
    for i in range(len(positions) - 1):
        x1, y1, x2, y2 = positions[i]
        nx1, ny1, nx2, ny2 = positions[i + 1]

        row_curr = i // cols
        row_next = (i + 1) // cols

        if row_curr == row_next:
            start_pt = (x2 + 4, (y1 + y2) // 2)
            end_pt = (nx1 - 4, (ny1 + ny2) // 2)
        else:
            start_pt = ((x1 + x2) // 2, y2 + 4)
            end_pt = ((nx1 + nx2) // 2, ny1 - 4)

        _draw_arrow(draw, start_pt, end_pt, colors["primary"], 3)


def _render_summary(img: Image.Image, draw: ImageDraw.ImageDraw,
                    spec: dict, colors: dict, content_y: int):
    """Draw a polished recap/checklist with numbered takeaways."""
    points = spec.get("on_screen_text", [])
    if not points:
        return

    font_point = _get_font(22, bold=True)
    font_detail = _get_font(17)

    col_count = 2 if len(points) > 3 else 1
    card_margin = 40
    card_gap = 24

    if col_count == 2:
        card_w = (WIDTH - card_margin * 2 - card_gap) // 2
        left_points = points[:len(points) // 2 + len(points) % 2]
        right_points = points[len(points) // 2 + len(points) % 2:]
        columns = [(card_margin, left_points), (card_margin + card_w + card_gap, right_points)]
    else:
        card_w = WIDTH - card_margin * 2
        columns = [(card_margin, points)]

    card_y = content_y + 10
    card_h = HEIGHT - content_y - 140

    label_font = _get_font(14, bold=True)
    draw.text((card_margin + 10, card_y + 4), "DESIGN CHECKLIST", fill=colors["primary"], font=label_font)
    draw.rectangle([(card_margin + 10, card_y + 24), (card_margin + 180, card_y + 26)], fill=colors["primary"])
    card_y += 36

    point_colors = [colors["primary"], colors["secondary"], colors["accent"]]
    global_idx = 0

    for col_x, col_points in columns:
        _draw_rounded_rect(draw, (col_x, card_y, col_x + card_w, card_y + card_h - 36),
                           14, colors["card_bg"])

        item_y = card_y + 18
        item_h = max(50, min(72, (card_h - 80) // max(len(col_points), 1)))

        for i, point in enumerate(col_points[:8]):
            pc = point_colors[global_idx % len(point_colors)]

            # Colored accent bar
            draw.rectangle([(col_x + 20, item_y + 4), (col_x + 24, item_y + item_h - 12)], fill=pc)

            # Number badge
            badge_r = 16
            bx = col_x + 38 + badge_r
            by = item_y + 12 + badge_r
            draw.ellipse([(bx - badge_r, by - badge_r), (bx + badge_r, by + badge_r)], fill=pc)
            badge_font = _get_font(15, bold=True)
            badge_text = str(global_idx + 1)
            bb = badge_font.getbbox(badge_text)
            bw = bb[2] - bb[0]
            draw.text((bx - bw // 2, by - 9), badge_text,
                      fill=(255, 255, 255) if sum(pc) < 400 else (0, 0, 0), font=badge_font)

            # Text
            tx = col_x + 80
            lines = _wrap_text(str(point), font_point, card_w - 100)
            draw.text((tx, item_y + 8), lines[0], fill=colors["fg"], font=font_point)
            if len(lines) > 1:
                draw.text((tx, item_y + 34), lines[1], fill=colors["muted"], font=font_detail)

            item_y += item_h
            global_idx += 1


def _render_cinematic(img: Image.Image, draw: ImageDraw.ImageDraw,
                      spec: dict, colors: dict, content_y: int):
    """Draw a cinematic intro scene with dramatic typography and key concepts."""
    points = spec.get("on_screen_text", [])
    title = spec.get("title", "")
    learning_obj = spec.get("learning_objective", "")
    font_hero = _get_font(64, bold=True)
    font_sub = _get_font(26)
    font_bullet = _get_font(22, bold=True)

    # Decorative line above title
    center_y = HEIGHT // 2 - 110
    draw.rectangle([(WIDTH // 2 - 80, center_y), (WIDTH // 2 + 80, center_y + 3)],
                   fill=colors["primary"])
    center_y += 24

    for line in _wrap_text(title, font_hero, WIDTH - 240)[:2]:
        bb = font_hero.getbbox(line)
        lw = bb[2] - bb[0]
        draw.text(((WIDTH - lw) // 2, center_y), line, fill=colors["fg"], font=font_hero)
        center_y += 78

    # Accent bar
    draw.rectangle([(WIDTH // 2 - 50, center_y + 6), (WIDTH // 2 + 50, center_y + 10)],
                   fill=colors["primary"])
    center_y += 36

    if learning_obj:
        obj_lines = _wrap_text(learning_obj, font_sub, WIDTH - 300)
        for line in obj_lines[:2]:
            bb = font_sub.getbbox(line)
            lw = bb[2] - bb[0]
            draw.text(((WIDTH - lw) // 2, center_y), line, fill=colors["secondary"], font=font_sub)
            center_y += 36
        center_y += 10

    bullet_colors = [colors["primary"], colors["secondary"], colors["accent"]]
    for i, point in enumerate(points[:3]):
        bc = bullet_colors[i % len(bullet_colors)]
        dot_y = center_y + 8
        draw.ellipse([(WIDTH // 2 - 220, dot_y), (WIDTH // 2 - 208, dot_y + 12)], fill=bc)
        lines = _wrap_text(str(point), font_bullet, WIDTH - 300)
        for line in lines[:1]:
            draw.text((WIDTH // 2 - 196, center_y + 2), line, fill=colors["fg"], font=font_bullet)
        center_y += 38


def _render_visual_card(img: Image.Image, draw: ImageDraw.ImageDraw,
                        spec: dict, colors: dict, content_y: int):
    """Draw a visual card layout — side icon + content cards for each key point."""
    points = spec.get("on_screen_text", [])
    if not points:
        _render_cinematic(img, draw, spec, colors, content_y)
        return

    font_item = _get_font(22, bold=True)
    font_detail = _get_font(17)
    point_colors = [colors["primary"], colors["secondary"], colors["accent"]]

    card_x = 80
    card_w = WIDTH - 160
    area_top = content_y + 16
    area_h = HEIGHT - content_y - 150
    card_h_each = min(100, (area_h - 20) // max(len(points), 1))

    y = area_top
    for i, point in enumerate(points[:6]):
        pc = point_colors[i % len(point_colors)]

        # Card background
        _draw_rounded_rect(draw, (card_x, y, card_x + card_w, y + card_h_each - 8),
                           10, colors["card_bg"], outline=colors["edge_color"], width=1)

        # Colored left strip
        draw.rectangle([(card_x, y + 4), (card_x + 6, y + card_h_each - 12)], fill=pc)

        # Icon circle
        icon_r = 20
        ix = card_x + 36 + icon_r
        iy = y + (card_h_each - 8) // 2
        draw.ellipse([(ix - icon_r, iy - icon_r), (ix + icon_r, iy + icon_r)], fill=pc)
        icon_font = _get_font(16, bold=True)
        sn = str(i + 1)
        sb = icon_font.getbbox(sn)
        draw.text((ix - (sb[2] - sb[0]) // 2, iy - 9), sn,
                  fill=(255, 255, 255) if sum(pc) < 400 else (0, 0, 0), font=icon_font)

        # Text
        tx = card_x + 86
        lines = _wrap_text(str(point), font_item, card_w - 120)
        line_y = y + (card_h_each - 8) // 2 - 14
        draw.text((tx, line_y), lines[0], fill=colors["fg"], font=font_item)
        if len(lines) > 1:
            draw.text((tx, line_y + 28), lines[1], fill=colors["muted"], font=font_detail)

        y += card_h_each


# ─── SCENE WATERMARK (TOPIC-SPECIFIC BACKGROUND DECORATION) ─────────

def _draw_scene_watermark(draw: ImageDraw.ImageDraw, lesson_title: str,
                          scene_index: int, colors: dict):
    """Draw subtle topic-specific background decoration."""
    font_wm = _get_font(200, bold=True)
    lt = lesson_title.lower()

    if "rate limit" in lt:
        symbols = ["429", "→", "⚡", "🛡"]
    elif "deadlock" in lt:
        symbols = ["⟳", "⊗", "⇌", "⚠"]
    elif "pars" in lt:
        symbols = ["⊢", "→", "⟨⟩", "AST"]
    else:
        symbols = ["◇", "△", "○", "□"]

    sym = symbols[scene_index % len(symbols)]
    try:
        bb = font_wm.getbbox(sym)
        sw = bb[2] - bb[0]
        sh = bb[3] - bb[1]
    except Exception:
        return

    # Tint: extremely subtle watermark in bottom-right
    wm_color = tuple(
        max(0, min(255, c + (20 if sum(colors["bg"]) > 400 else -15)))
        for c in colors["bg"]
    )
    draw.text((WIDTH - sw - 60, HEIGHT - sh - 160), sym, fill=wm_color, font=font_wm)


# ─── OVERLAY CHROME ON AI-GENERATED IMAGES ──────────────────────────

def _overlay_scene_chrome(
    img: Image.Image,
    scene_spec: dict,
    scene_index: int,
    total_scenes: int,
    style_name: str,
    lesson_title: str,
) -> None:
    """Add title bar, narration bar, and progress on top of an AI-generated image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    overlay_draw.rectangle([(0, 0), (WIDTH, 80)], fill=(0, 0, 0, 160))
    overlay_draw.rectangle([(0, HEIGHT - 100), (WIDTH, HEIGHT)], fill=(0, 0, 0, 160))

    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    img.paste(img_rgba.convert("RGB"))
    draw = ImageDraw.Draw(img)

    font_title = _get_font(28, bold=True)
    font_small = _get_font(16)
    font_narr = _get_font(18)

    title = scene_spec.get("title", f"Scene {scene_index + 1}")
    narration = scene_spec.get("narration_text", "")

    draw.text((30, 22), f"{scene_index + 1}/{total_scenes}  {title}",
              fill=(255, 255, 255), font=font_title)
    draw.text((WIDTH - 200, 28), lesson_title[:30], fill=(200, 200, 210), font=font_small)

    progress = (scene_index + 1) / max(total_scenes, 1)
    bar_w = int((WIDTH - 60) * progress)
    draw.rectangle([(30, 68), (WIDTH - 30, 74)], fill=(60, 60, 80))
    draw.rectangle([(30, 68), (30 + bar_w, 74)], fill=(56, 189, 248))

    if narration:
        short = narration[:200] + "..." if len(narration) > 200 else narration
        draw.text((30, HEIGHT - 80), short, fill=(230, 230, 240), font=font_narr)


# ─── MAIN RENDER FUNCTION ───────────────────────────────────────────

def _render_scene_image(
    scene_spec: dict,
    scene_index: int,
    total_scenes: int,
    style_name: str,
    lesson_title: str,
) -> Image.Image:
    colors = STYLE_PRESETS.get(style_name, STYLE_PRESETS["clean_academic"])
    img = Image.new("RGB", (WIDTH, HEIGHT), colors["bg"])
    _draw_gradient_bg(img, colors)
    draw = ImageDraw.Draw(img)

    title = scene_spec.get("title", f"Scene {scene_index + 1}")
    scene_type = scene_spec.get("scene_type", "deterministic_animation")
    narration = scene_spec.get("narration_text", "")
    duration = scene_spec.get("duration_sec", 30)
    learning_obj = scene_spec.get("learning_objective", "")

    _draw_scene_watermark(draw, lesson_title, scene_index, colors)
    _draw_header(draw, scene_index, total_scenes, lesson_title, colors)
    content_y = _draw_title_section(draw, title, scene_type, duration, colors,
                                     learning_objective=learning_obj)

    renderer_map = {
        "deterministic_animation": _render_concept_flow,
        "code_trace": _render_code_trace,
        "system_design_graph": _render_architecture,
        "summary_scene": _render_summary,
        "veo_cinematic": _render_cinematic,
        "generated_still_with_motion": _render_visual_card,
    }

    renderer = renderer_map.get(scene_type, _render_concept_flow)
    renderer(img, draw, scene_spec, colors, content_y)

    _draw_narration_bar(draw, narration, colors)

    return img


# ─── INTRO / TRANSITION / OUTRO FRAMES ──────────────────────────────

INTRO_DURATION = 3.0
TRANSITION_DURATION = 1.5
OUTRO_DURATION = 4.0


def _render_intro_card(lesson_title: str, scene_count: int,
                       total_duration: float, style_name: str) -> Image.Image:
    """Render a polished intro title card."""
    colors = STYLE_PRESETS.get(style_name, STYLE_PRESETS["clean_academic"])
    img = Image.new("RGB", (WIDTH, HEIGHT), colors["bg"])
    _draw_gradient_bg(img, colors)
    draw = ImageDraw.Draw(img)

    font_brand = _get_font(22, bold=True)
    font_title = _get_font(48, bold=True)
    font_meta = _get_font(16)

    # Brand
    draw.text((WIDTH // 2 - 60, 200), "VisualCS", fill=colors["primary"], font=font_brand)

    # Decorative line
    line_y = 245
    lw = 120
    draw.rectangle([(WIDTH // 2 - lw, line_y), (WIDTH // 2 + lw, line_y + 3)],
                   fill=colors["primary"])

    # Title
    title_lines = _wrap_text(lesson_title, font_title, WIDTH - 200)
    ty = 280
    for line in title_lines[:3]:
        bb = font_title.getbbox(line)
        tw = bb[2] - bb[0]
        draw.text(((WIDTH - tw) // 2, ty), line, fill=colors["fg"], font=font_title)
        ty += 60

    # Metadata
    meta = f"{scene_count} scenes  ·  ~{int(total_duration)}s"
    bb = font_meta.getbbox(meta)
    draw.text(((WIDTH - (bb[2] - bb[0])) // 2, ty + 30), meta,
              fill=colors["muted"], font=font_meta)

    # Bottom bar
    draw.rectangle([(0, HEIGHT - 50), (WIDTH, HEIGHT)], fill=colors["card_bg"])
    draw.text((30, HEIGHT - 38), "AI-Powered Visual Learning",
              fill=colors["muted"], font=font_meta)

    return img


def _render_transition_card(next_title: str, next_index: int,
                            total_scenes: int, style_name: str,
                            transition_note: str = "",
                            continuity_hint: str = "") -> Image.Image:
    """Render a brief scene transition card (coherence bridge)."""
    colors = STYLE_PRESETS.get(style_name, STYLE_PRESETS["clean_academic"])
    img = Image.new("RGB", (WIDTH, HEIGHT), colors["bg"])
    _draw_gradient_bg(img, colors)
    draw = ImageDraw.Draw(img)

    font_label = _get_font(16, bold=True)
    font_title = _get_font(32, bold=True)
    font_small = _get_font(18)

    # Center "UP NEXT" label
    label = f"SECTION {next_index + 1} OF {total_scenes}"
    bb = font_label.getbbox(label)
    lx = (WIDTH - (bb[2] - bb[0])) // 2
    draw.text((lx, HEIGHT // 2 - 50), label, fill=colors["primary"], font=font_label)

    # Next title
    title_lines = _wrap_text(next_title, font_title, WIDTH - 200)
    ty = HEIGHT // 2 - 5
    for line in title_lines[:2]:
        bb = font_title.getbbox(line)
        tw = bb[2] - bb[0]
        draw.text(((WIDTH - tw) // 2, ty), line, fill=colors["fg"], font=font_title)
        ty += 42

    if transition_note:
        note_lines = _wrap_text(transition_note, font_small, WIDTH - 240)
        ny = min(ty + 24, HEIGHT // 2 + 70)
        for line in note_lines[:2]:
            bb = font_small.getbbox(line)
            tw = bb[2] - bb[0]
            draw.text(((WIDTH - tw) // 2, ny), line, fill=colors["muted"], font=font_small)
            ny += 26
    if continuity_hint and not transition_note:
        ch = _wrap_text(continuity_hint[:120], font_small, WIDTH - 240)
        ny = HEIGHT // 2 + 70
        for line in ch[:1]:
            bb = font_small.getbbox(line)
            tw = bb[2] - bb[0]
            draw.text(((WIDTH - tw) // 2, ny), line, fill=colors["secondary"], font=font_small)

    # Progress bar
    bar_y = HEIGHT // 2 + 80
    bar_w = 400
    bx = (WIDTH - bar_w) // 2
    draw.rectangle([(bx, bar_y), (bx + bar_w, bar_y + 4)], fill=colors["edge_color"])
    fill_w = int(bar_w * (next_index) / max(total_scenes, 1))
    draw.rectangle([(bx, bar_y), (bx + fill_w, bar_y + 4)], fill=colors["primary"])

    return img


def _render_outro_card(lesson_title: str, scene_count: int,
                       style_name: str) -> Image.Image:
    """Render an outro/end card."""
    colors = STYLE_PRESETS.get(style_name, STYLE_PRESETS["clean_academic"])
    img = Image.new("RGB", (WIDTH, HEIGHT), colors["bg"])
    _draw_gradient_bg(img, colors)
    draw = ImageDraw.Draw(img)

    font_done = _get_font(36, bold=True)
    font_title = _get_font(22)
    font_meta = _get_font(16)

    # "Lesson Complete" message
    done_text = "Lesson Complete"
    bb = font_done.getbbox(done_text)
    draw.text(((WIDTH - (bb[2] - bb[0])) // 2, HEIGHT // 2 - 80),
              done_text, fill=colors["primary"], font=font_done)

    # Decorative line
    lw = 80
    draw.rectangle([(WIDTH // 2 - lw, HEIGHT // 2 - 30),
                     (WIDTH // 2 + lw, HEIGHT // 2 - 27)],
                   fill=colors["primary"])

    # Title
    title_lines = _wrap_text(lesson_title, font_title, WIDTH - 200)
    ty = HEIGHT // 2 - 5
    for line in title_lines[:2]:
        bb = font_title.getbbox(line)
        tw = bb[2] - bb[0]
        draw.text(((WIDTH - tw) // 2, ty), line, fill=colors["fg"], font=font_title)
        ty += 30

    # Footer
    footer = f"Covered {scene_count} sections  ·  Generated by VisualCS"
    bb = font_meta.getbbox(footer)
    draw.text(((WIDTH - (bb[2] - bb[0])) // 2, ty + 30),
              footer, fill=colors["muted"], font=font_meta)

    return img


def _generate_srt(scenes: list[dict], durations: list[float],
                  intro_dur: float) -> str:
    """Generate an SRT subtitle file from scene narration texts."""
    entries = []
    current_time = intro_dur

    for i, (spec, dur) in enumerate(zip(scenes, durations)):
        narration = spec.get("narration_text", "").strip()
        if not narration:
            current_time += dur + TRANSITION_DURATION
            continue

        # Split narration into chunks of ~120 chars for readable subtitles
        words = narration.split()
        chunks = []
        current_chunk = ""
        for word in words:
            if len(current_chunk) + len(word) + 1 > 120:
                chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk += " " + word
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        if not chunks:
            current_time += dur + TRANSITION_DURATION
            continue

        chunk_dur = dur / len(chunks)
        for ci, chunk in enumerate(chunks):
            start = current_time + ci * chunk_dur
            end = start + chunk_dur - 0.1
            entries.append(_srt_entry(len(entries) + 1, start, end, chunk))

        current_time += dur + TRANSITION_DURATION

    return "\n".join(entries)


def _srt_entry(index: int, start: float, end: float, text: str) -> str:
    """Format a single SRT entry."""
    def ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{index}\n{ts(start)} --> {ts(end)}\n{text}\n"


# ─── FFMPEG COMPOSITION ─────────────────────────────────────────────

def _get_wav_duration(wav_path: str) -> float:
    try:
        with open(wav_path, "rb") as f:
            data = f.read(44)
            if len(data) < 44:
                return 0
            data_size = struct.unpack_from("<I", data, 40)[0]
            sample_rate = struct.unpack_from("<I", data, 24)[0]
            block_align = struct.unpack_from("<H", data, 32)[0]
            if sample_rate > 0 and block_align > 0:
                return data_size / (sample_rate * block_align)
    except Exception:
        pass
    return 0


def _normalize_clip(input_path: str, output_path: str) -> bool:
    """Re-encode a clip to consistent resolution/codec for concatenation."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        return r.returncode == 0 and os.path.exists(output_path)
    except subprocess.TimeoutExpired:
        logger.warning("normalize_clip timed out for %s", input_path)
        return False


def _image_to_mp4(
    img_path: str,
    duration_sec: float,
    out_path: str,
    idx: int = 0,
) -> bool:
    """Convert a still image to a fixed-duration MP4 (no zoompan — fast)."""
    dur = max(0.1, duration_sec)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1",
        "-i", img_path,
        "-t", f"{dur:.2f}",
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-an",
        out_path,
    ]
    timeout = max(30, int(dur) + 30)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode == 0 and os.path.exists(out_path):
            return True
        err = (r.stderr or b"").decode(errors="replace")[:300]
        logger.warning("image_to_mp4 failed idx=%d rc=%d: %s", idx, r.returncode, err)
        return False
    except subprocess.TimeoutExpired:
        logger.warning("image_to_mp4 timed out idx=%d after %ds", idx, timeout)
        return False


def _compose_video_ffmpeg(
    image_paths: list[str],
    durations: list[float],
    audio_paths: list[str],
    output_path: str,
    video_clips: list[str] | None = None,
) -> bool:
    """Compose final video from images + optional Veo clips + audio.

    ``video_clips`` is parallel to ``image_paths``.  When a non-empty path
    exists, the Veo clip is spliced into the timeline before the
    corresponding static frame (which then shows for the remaining
    duration minus the clip length).
    """
    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg not found")
        return False

    clips = video_clips or [""] * len(image_paths)

    try:
        tmpdir = os.path.dirname(output_path)

        effective_durations = list(durations)
        for i, ap in enumerate(audio_paths):
            if ap and os.path.exists(ap):
                ad = _get_wav_duration(ap)
                if ad > 0.5:
                    effective_durations[i] = max(ad + 0.5, durations[i])

        segment_files: list[str] = []
        ok_count = 0
        for idx, (img_path, dur) in enumerate(zip(image_paths, effective_durations)):
            veo_clip = clips[idx] if idx < len(clips) else ""

            if veo_clip and os.path.exists(veo_clip) and os.path.getsize(veo_clip) > 500:
                norm_path = os.path.join(tmpdir, f"veo_norm_{idx:03d}.mp4")
                if _normalize_clip(veo_clip, norm_path):
                    segment_files.append(norm_path)
                    remaining = max(dur - 5.0, 2.0)
                else:
                    remaining = dur
            else:
                remaining = dur

            still_mp4 = os.path.join(tmpdir, f"still_{idx:03d}.mp4")
            if remaining > 0.02 and os.path.exists(img_path):
                if _image_to_mp4(img_path, remaining, still_mp4, idx):
                    ok_count += 1
                else:
                    logger.warning("Could not encode segment idx=%d", idx)
            if os.path.exists(still_mp4):
                segment_files.append(still_mp4)

        if not segment_files:
            return False

        logger.info(
            "Compose: encoded %d segments out of %d images",
            ok_count,
            len(image_paths),
        )

        # Concatenate all video segments
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for seg in segment_files:
                f.write(f"file '{seg}'\n")

        slideshow_path = os.path.join(tmpdir, "slideshow.mp4")
        cmd_video = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p",
            slideshow_path,
        ]
        subprocess.run(cmd_video, capture_output=True, text=True, timeout=180)

        if not os.path.exists(slideshow_path):
            return False

        has_any_audio = any(
            p and os.path.exists(p) and os.path.getsize(p) > 100
            for p in audio_paths
        )

        if not has_any_audio:
            os.rename(slideshow_path, output_path)
            logger.info("Video composed without audio: %s", output_path)
            return True

        # Build per-segment audio: silence for intro/transition/outro, real audio for scenes
        ordered_audio: list[str] = []
        for i, ap in enumerate(audio_paths):
            if ap and os.path.exists(ap) and os.path.getsize(ap) > 100:
                ordered_audio.append(ap)
            else:
                # Generate a short silence WAV for this segment
                dur = effective_durations[i] if i < len(effective_durations) else 1.0
                silence_path = os.path.join(tmpdir, f"silence_{i:03d}.wav")
                cmd_silence = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(dur),
                    "-c:a", "pcm_s16le",
                    silence_path,
                ]
                subprocess.run(cmd_silence, capture_output=True, timeout=10)
                if os.path.exists(silence_path):
                    ordered_audio.append(silence_path)

        if not ordered_audio:
            os.rename(slideshow_path, output_path)
            return True

        combined_audio = os.path.join(tmpdir, "combined_audio.wav")
        if len(ordered_audio) == 1:
            combined_audio = ordered_audio[0]
        else:
            audio_list = os.path.join(tmpdir, "audio_list.txt")
            with open(audio_list, "w") as f:
                for ap in ordered_audio:
                    f.write(f"file '{ap}'\n")

            cmd_audio = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", audio_list,
                "-c:a", "pcm_s16le", "-ar", "24000", "-ac", "1",
                combined_audio,
            ]
            subprocess.run(cmd_audio, capture_output=True, text=True, timeout=60)

        if not os.path.exists(combined_audio):
            os.rename(slideshow_path, output_path)
            return True

        # Embed SRT subtitles if provided
        srt_path = os.path.join(tmpdir, "subtitles.srt")
        has_srt = os.path.exists(srt_path) and os.path.getsize(srt_path) > 10

        cmd_mux = [
            "ffmpeg", "-y",
            "-i", slideshow_path,
            "-i", combined_audio,
        ]
        if has_srt:
            cmd_mux += ["-i", srt_path]
        cmd_mux += [
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
        ]
        if has_srt:
            cmd_mux += ["-c:s", "mov_text"]
        cmd_mux += [
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(cmd_mux, capture_output=True, text=True, timeout=120)

        if result.returncode != 0 or not os.path.exists(output_path):
            # Fallback without subtitles
            cmd_simple = [
                "ffmpeg", "-y",
                "-i", slideshow_path, "-i", combined_audio,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-shortest", "-movflags", "+faststart", output_path,
            ]
            result2 = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=120)
            if result2.returncode != 0 or not os.path.exists(output_path):
                logger.warning("Audio mux failed, using video-only: %s",
                               result.stderr[:200] if result.stderr else "")
                if os.path.exists(slideshow_path):
                    os.rename(slideshow_path, output_path)
                return os.path.exists(output_path)

        veo_count = sum(1 for c in clips if c and os.path.exists(c))
        logger.info("Video composed with audio + %d Veo clips: %s (%.1f KB)",
                    veo_count, output_path, os.path.getsize(output_path) / 1024)
        return True

    except Exception as e:
        logger.error("FFmpeg composition error: %s", e)
        return False


class RenderingService:
    def __init__(self, storage: StorageProvider):
        self.storage = storage

    async def render_scene(self, scene_spec: dict, style: str) -> str:
        scene_id = scene_spec.get("scene_id", str(uuid.uuid4()))
        manifest = {
            "scene_id": scene_id,
            "render_strategy": scene_spec.get("render_strategy", "default"),
            "style": style,
            "status": "rendered",
        }
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        path = f"renders/scenes/{scene_id}/manifest.json"
        url = await self.storage.put_file(path, manifest_bytes, "application/json")
        return url

    async def render_preview(self, scenes: list[dict], style: str,
                             lesson_id: str = "", audio_urls: list[str] | None = None) -> str:
        return await self._render_video(scenes, style, quality="preview",
                                        lesson_id=lesson_id, audio_urls=audio_urls)

    async def render_final(self, scenes: list[dict], style: str,
                           audio_urls: list[str], music_url: str | None,
                           lesson_id: str = "") -> str:
        return await self._render_video(scenes, style, quality="final",
                                        lesson_id=lesson_id, audio_urls=audio_urls)

    async def _render_video(self, scenes: list[dict], style: str,
                            quality: str = "final", lesson_id: str = "",
                            audio_urls: list[str] | None = None) -> str:
        render_id = str(uuid.uuid4())

        lesson_title = ""
        if scenes:
            lesson_title = scenes[0].get("title", "VisualCS Lesson")
            for s in scenes:
                lt = s.get("lesson_title", "")
                if lt:
                    lesson_title = lt
                    break

        resolved_audio: list[str] = []
        if audio_urls:
            for url in audio_urls:
                if url and url.startswith("file://"):
                    path = url[7:]
                    if os.path.exists(path):
                        resolved_audio.append(path)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._generate_video_sync,
            scenes, style, lesson_title, render_id, resolved_audio,
        )

        if result and result.get("video"):
            video_bytes = result["video"]
            path = f"renders/{quality}/{render_id}/lesson.mp4"
            url = await self.storage.put_file(path, video_bytes, "video/mp4")
            if lesson_id:
                canonical = f"output/{lesson_id}/lesson.mp4"
                await self.storage.put_file(canonical, video_bytes, "video/mp4")

                # Store SRT subtitles alongside video
                srt_content = result.get("srt", "")
                if srt_content:
                    srt_path = f"output/{lesson_id}/subtitles.srt"
                    await self.storage.put_file(
                        srt_path, srt_content.encode("utf-8"), "text/srt"
                    )

            logger.info(
                "RenderingService: %s video rendered (%d scenes, %.1f KB) -> %s",
                quality, len(scenes), len(video_bytes) / 1024, url,
            )
            return url

        manifest = {"render_id": render_id, "status": "fallback_manifest", "scene_count": len(scenes)}
        path = f"renders/{quality}/{render_id}/manifest.json"
        url = await self.storage.put_file(
            path, json.dumps(manifest).encode(), "application/json"
        )
        return url

    def _generate_video_sync(self, scenes: list[dict], style: str,
                             lesson_title: str, render_id: str,
                             audio_paths: list[str]) -> dict | None:
        tmpdir = tempfile.mkdtemp(prefix="visualcs_render_")
        try:
            all_image_paths: list[str] = []
            all_durations: list[float] = []
            all_video_clips: list[str] = []
            all_audio: list[str] = []

            total_scene_dur = sum(s.get("duration_sec", 5) for s in scenes)

            # --- Intro card ---
            intro_img = _render_intro_card(lesson_title, len(scenes), total_scene_dur, style)
            intro_path = os.path.join(tmpdir, "intro.png")
            intro_img.save(intro_path, "PNG")
            all_image_paths.append(intro_path)
            all_durations.append(INTRO_DURATION)
            all_video_clips.append("")
            all_audio.append("")

            padded_audio = list(audio_paths) + [""] * (len(scenes) - len(audio_paths))

            for i, spec in enumerate(scenes):
                # Transition card before each scene (except first)
                if i > 0:
                    trans_img = _render_transition_card(
                        spec.get("title", f"Scene {i+1}"),
                        i,
                        len(scenes),
                        style,
                        transition_note=str(spec.get("transition_note", "") or ""),
                        continuity_hint=str(spec.get("continuity_anchor", "") or ""),
                    )
                    trans_path = os.path.join(tmpdir, f"trans_{i:03d}.png")
                    trans_img.save(trans_path, "PNG")
                    all_image_paths.append(trans_path)
                    all_durations.append(TRANSITION_DURATION)
                    all_video_clips.append("")
                    all_audio.append("")

                # Scene frame: prefer AI-generated image, fall back to PIL render
                img_path = os.path.join(tmpdir, f"scene_{i:03d}.png")
                ai_image_url = spec.get("_image_asset_url", "")
                used_ai_image = False

                if ai_image_url and ai_image_url.startswith("file://"):
                    ai_path = ai_image_url[7:]
                    if os.path.exists(ai_path) and os.path.getsize(ai_path) > 500:
                        try:
                            ai_img = Image.open(ai_path).convert("RGB")
                            ai_img = ai_img.resize((WIDTH, HEIGHT), Image.LANCZOS)
                            _overlay_scene_chrome(ai_img, spec, i, len(scenes), style, lesson_title)
                            ai_img.save(img_path, "PNG")
                            used_ai_image = True
                            logger.info("Render: using AI-generated image for scene %d", i)
                        except Exception as e:
                            logger.warning("Render: AI image load failed for scene %d: %s", i, e)

                if not used_ai_image:
                    img = _render_scene_image(spec, i, len(scenes), style, lesson_title)
                    img.save(img_path, "PNG")

                all_image_paths.append(img_path)

                # Audio-driven duration: use audio length if available, with buffer
                scene_dur = max(spec.get("duration_sec", 5), 3)
                audio_file = padded_audio[i] if i < len(padded_audio) else ""
                if audio_file and os.path.exists(audio_file):
                    audio_dur = _get_wav_duration(audio_file)
                    if audio_dur > 0.5:
                        scene_dur = audio_dur + 1.0
                all_durations.append(scene_dur)

                # Veo clip
                veo_path = ""
                if spec.get("veo_eligible"):
                    for ar in spec.get("asset_requests", []):
                        if ar.get("type") == "video":
                            clip_url = spec.get("_video_asset_url", "")
                            if clip_url and clip_url.startswith("file://"):
                                candidate = clip_url[7:]
                                if os.path.exists(candidate) and os.path.getsize(candidate) > 500:
                                    veo_path = candidate
                            break
                all_video_clips.append(veo_path)
                all_audio.append(audio_file)

            # --- Outro card ---
            outro_img = _render_outro_card(lesson_title, len(scenes), style)
            outro_path = os.path.join(tmpdir, "outro.png")
            outro_img.save(outro_path, "PNG")
            all_image_paths.append(outro_path)
            all_durations.append(OUTRO_DURATION)
            all_video_clips.append("")
            all_audio.append("")

            if not all_image_paths:
                return None

            # --- Generate SRT subtitles ---
            scene_durations = []
            for spec in scenes:
                sd = max(spec.get("duration_sec", 5), 3)
                scene_durations.append(sd)
            srt_content = _generate_srt(scenes, scene_durations, INTRO_DURATION)
            srt_path = os.path.join(tmpdir, "subtitles.srt")
            with open(srt_path, "w") as f:
                f.write(srt_content)

            output_path = os.path.join(tmpdir, "output.mp4")
            success = _compose_video_ffmpeg(
                all_image_paths, all_durations,
                all_audio,
                output_path,
                video_clips=all_video_clips,
            )

            if success and os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    video_bytes = f.read()
                return {"video": video_bytes, "srt": srt_content}

            return None
        except Exception as e:
            logger.error("Video generation failed: %s", e)
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
