from __future__ import annotations

import tkinter as tk

from .theme import COLORS


class IconSet:
    """Small dependency-free line icon set rendered into Tk PhotoImages.

    Keeping the icons procedural means development checkouts and packaged
    releases always use the same artwork without external PNG/font assets.
    """

    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self._cache: dict[tuple[str, int, str], tk.PhotoImage] = {}

    def get(self, name: str, size: int = 16, color: str | None = None) -> tk.PhotoImage:
        color = color or COLORS["text_soft"]
        key = (name, size, color)
        if key not in self._cache:
            self._cache[key] = _render_icon(self.master, name, size, color)
        return self._cache[key]


def _render_icon(master: tk.Misc, name: str, size: int, color: str) -> tk.PhotoImage:
    image = tk.PhotoImage(master=master, width=size, height=size)
    scale = size / 16.0

    def p(value: float) -> int:
        return max(0, min(size - 1, int(round(value * scale))))

    def dot(x: int, y: int, c: str = color) -> None:
        if 0 <= x < size and 0 <= y < size:
            image.put(c, (x, y))

    def line(x0: float, y0: float, x1: float, y1: float, c: str = color, width: int = 1) -> None:
        x0i, y0i, x1i, y1i = p(x0), p(y0), p(x1), p(y1)
        dx = abs(x1i - x0i)
        sx = 1 if x0i < x1i else -1
        dy = -abs(y1i - y0i)
        sy = 1 if y0i < y1i else -1
        err = dx + dy
        while True:
            for ox in range(-(width // 2), width // 2 + 1):
                for oy in range(-(width // 2), width // 2 + 1):
                    dot(x0i + ox, y0i + oy, c)
            if x0i == x1i and y0i == y1i:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0i += sx
            if e2 <= dx:
                err += dx
                y0i += sy

    def rect(x0: float, y0: float, x1: float, y1: float, c: str = color) -> None:
        line(x0, y0, x1, y0, c)
        line(x1, y0, x1, y1, c)
        line(x1, y1, x0, y1, c)
        line(x0, y1, x0, y0, c)

    def circle(cx: float, cy: float, radius: float, c: str = color) -> None:
        import math

        points = []
        for step in range(24):
            angle = math.tau * step / 24
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        for first, second in zip(points, points[1:] + points[:1]):
            line(first[0], first[1], second[0], second[1], c)

    accent = COLORS.get("accent_hover", color)
    danger = COLORS.get("danger", color)

    if name == "folder":
        line(2, 5, 6, 5)
        line(6, 5, 7.5, 3.5)
        line(7.5, 3.5, 13.5, 3.5)
        line(13.5, 3.5, 14, 11.5)
        line(14, 11.5, 2, 11.5)
        line(2, 11.5, 2, 5)
    elif name == "folder_add":
        line(1.5, 5, 5.5, 5)
        line(5.5, 5, 7, 3.5)
        line(7, 3.5, 13.5, 3.5)
        line(13.5, 3.5, 14, 11.5)
        line(14, 11.5, 1.5, 11.5)
        line(1.5, 11.5, 1.5, 5)
        line(8, 6.5, 8, 10.5, accent)
        line(6, 8.5, 10, 8.5, accent)
    elif name == "scan":
        circle(8, 8, 5)
        line(11.2, 3.8, 14, 4.2, accent)
        line(14, 4.2, 13.2, 1.8, accent)
        line(4.8, 12.2, 2, 11.8, accent)
        line(2, 11.8, 2.8, 14.2, accent)
    elif name == "options":
        for y, knob in ((4, 10), (8, 6), (12, 11)):
            line(2, y, 14, y)
            circle(knob, y, 1.2, accent)
    elif name == "cache":
        line(3, 4, 3, 12)
        line(13, 4, 13, 12)
        line(3, 4, 13, 4)
        line(3, 8, 13, 8)
        line(3, 12, 13, 12)
        line(4, 3, 12, 3)
    elif name == "undo":
        line(7, 4, 3, 7, accent)
        line(3, 7, 7, 10, accent)
        line(3, 7, 10, 7)
        line(10, 7, 13, 9)
        line(13, 9, 13, 12)
    elif name == "export":
        rect(2.5, 6, 10.5, 13)
        line(8, 3, 13.5, 3, accent)
        line(13.5, 3, 13.5, 8.5, accent)
        line(13.5, 3, 7, 9.5, accent)
    elif name == "health":
        line(2, 8, 5, 8)
        line(5, 8, 6.5, 4.5, accent)
        line(6.5, 4.5, 9, 11, accent)
        line(9, 11, 10.5, 7, accent)
        line(10.5, 7, 14, 7)
    elif name == "engine":
        circle(8, 8, 4.5)
        circle(8, 8, 1.5, accent)
        for x0, y0, x1, y1 in (
            (8, 1.5, 8, 3),
            (8, 13, 8, 14.5),
            (1.5, 8, 3, 8),
            (13, 8, 14.5, 8),
            (3.2, 3.2, 4.2, 4.2),
            (11.8, 11.8, 12.8, 12.8),
            (11.8, 4.2, 12.8, 3.2),
            (3.2, 12.8, 4.2, 11.8),
        ):
            line(x0, y0, x1, y1)
    elif name == "trash":
        rect(4, 5, 12, 13, danger)
        line(3, 4, 13, 4, danger)
        line(6, 2.5, 10, 2.5, danger)
        line(6.5, 7, 6.5, 11, danger)
        line(9.5, 7, 9.5, 11, danger)
    elif name == "details":
        rect(3, 2.5, 12.5, 13.5)
        line(5, 5, 10.5, 5, accent)
        line(5, 8, 10.5, 8)
        line(5, 11, 9, 11)
    elif name == "app":
        # Compact document + rename arrows mark used for the title-bar icon.
        rect(3, 2, 11, 14, accent)
        line(8, 2, 11, 5, accent)
        line(8, 2, 8, 5, accent)
        line(8, 5, 11, 5, accent)
        line(5, 8, 13, 8)
        line(11, 6, 13, 8)
        line(13, 8, 11, 10)
        line(9, 12, 3, 12)
        line(5, 10, 3, 12)
        line(3, 12, 5, 14)
    else:
        rect(3, 3, 12, 12)

    return image


def apply_window_icon(window: tk.Tk) -> None:
    """Install a branded runtime icon without requiring external image files."""
    icons = getattr(window, "_runtime_icon_set", None)
    if icons is None:
        icons = IconSet(window)
        setattr(window, "_runtime_icon_set", icons)
    icon = icons.get("app", 32, COLORS.get("accent_hover", "#b68cff"))
    window.iconphoto(True, icon)
    setattr(window, "_runtime_app_icon", icon)
