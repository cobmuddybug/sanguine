"""The Court: pinned files joined by red string.

Click a pin to open it, drag to pan, scroll (or +/-) to zoom between overview and
detail, arrow keys move between pins. Hovering a pin highlights its string.
"""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widget import Widget

from .theme import PAL
from .widgets import DIM, GREEN, RED

CARD_W, CARD_H = 30, 4
ZOOMS = (0.4, 1.0)


class Corkboard(Widget):
    can_focus = False

    class Open(Message):
        def __init__(self, dossier_id: str) -> None:
            super().__init__()
            self.dossier_id = dossier_id

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.zoom = 1                # index into ZOOMS
        self.pan = [0.0, 0.0]        # world coords of the top-left corner
        self.sel: str | None = None
        self.hover: str | None = None
        self._drag = None            # (screen x, y) of last drag point
        self._moved = False
        self._centered = False

    # -- data ----------------------------------------------------------------
    @property
    def game(self):
        return self.app.game  # type: ignore[attr-defined]

    @property
    def dossiers(self) -> list[dict]:
        return self.game.c.dossiers

    def _by_id(self, did: str) -> dict:
        return next(d for d in self.dossiers if d["id"] == did)

    @property
    def scale(self) -> float:
        return ZOOMS[self.zoom]

    def _size_of(self) -> tuple[int, int]:
        return (CARD_W, CARD_H) if self.zoom == 1 else (14, 1)

    def _rect(self, d: dict) -> tuple[int, int, int, int]:
        """Screen rect (x, y, w, h) of a pin."""
        w, h = self._size_of()
        sc = self.scale
        return (int((d["x"] - self.pan[0]) * sc), int((d["y"] - self.pan[1]) * sc), w, h)

    def _center(self, d: dict) -> tuple[int, int]:
        x, y, w, h = self._rect(d)
        return x + w // 2, y + h // 2

    def pin_at(self, x: int, y: int) -> str | None:
        for d in reversed(self.dossiers):
            rx, ry, w, h = self._rect(d)
            if rx <= x < rx + w and ry <= y < ry + h:
                return d["id"]
        return None

    # -- view ----------------------------------------------------------------
    def _world_extent(self) -> tuple[float, float]:
        return (max(d["x"] for d in self.dossiers) + CARD_W + 6, max(d["y"] for d in self.dossiers) + CARD_H + 3)

    def _clamp_pan(self) -> None:
        ww, wh = self._world_extent()
        sc = self.scale
        vw, vh = self.size.width / sc, self.size.height / sc
        self.pan[0] = max(-4.0, min(self.pan[0], max(-4.0, ww - vw)))
        self.pan[1] = max(-2.0, min(self.pan[1], max(-2.0, wh - vh)))

    def center_on(self, did: str) -> None:
        d = self._by_id(did)
        sc = self.scale
        self.pan[0] = d["x"] + CARD_W / 2 - self.size.width / sc / 2
        self.pan[1] = d["y"] + CARD_H / 2 - self.size.height / sc / 2
        self._clamp_pan()

    def ensure_visible(self, did: str) -> None:
        x, y, w, h = self._rect(self._by_id(did))
        if x < 1 or y < 0 or x + w > self.size.width or y + h > self.size.height:
            self.center_on(did)

    def set_zoom(self, level: int, anchor: tuple[int, int] | None = None) -> None:
        level = max(0, min(1, level))
        if level == self.zoom:
            return
        ax, ay = anchor or (self.size.width // 2, self.size.height // 2)
        old = self.scale
        wx, wy = self.pan[0] + ax / old, self.pan[1] + ay / old   # world point under the anchor
        self.zoom = level
        self.pan = [wx - ax / self.scale, wy - ay / self.scale]
        self._clamp_pan()
        self.refresh()

    def on_resize(self, event: events.Resize) -> None:
        if not self._centered and self.size.width > 0:
            self._centered = True
            self.sel = self.sel or self.dossiers[0]["id"]
            self.center_on(self.sel)
        self._clamp_pan()

    # -- keyboard --------------------------------------------------------------
    def move_selection(self, dx: int, dy: int) -> None:
        cur = self._by_id(self.sel or self.dossiers[0]["id"])
        cx, cy = cur["x"] + CARD_W / 2, cur["y"] + CARD_H / 2
        best, best_score = None, None
        for d in self.dossiers:
            if d is cur:
                continue
            vx, vy = d["x"] + CARD_W / 2 - cx, (d["y"] + CARD_H / 2 - cy) * 2.0  # cells are ~2x taller
            along = vx * dx + vy * dy
            if along <= 0:
                continue
            across = abs(vx * dy - vy * dx)
            score = along + 1.5 * across
            if best_score is None or score < best_score:
                best, best_score = d, score
        if best:
            self.sel = best["id"]
            self.ensure_visible(self.sel)
        self.refresh()

    def open_selected(self) -> None:
        if self.sel:
            self.post_message(self.Open(self.sel))

    # -- mouse -----------------------------------------------------------------
    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self._drag = (event.screen_x, event.screen_y)
            self._moved = False
            self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag is not None:
            dx, dy = event.screen_x - self._drag[0], event.screen_y - self._drag[1]
            if dx or dy:
                self._moved = True
                self.pan[0] -= dx / self.scale
                self.pan[1] -= dy / self.scale
                self._clamp_pan()
                self._drag = (event.screen_x, event.screen_y)
                self.refresh()
            return
        pin = self.pin_at(event.x, event.y)
        if pin != self.hover:
            self.hover = pin
            self.refresh()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag is not None:
            self._drag = None
            self.release_mouse()

    def on_leave(self, event: events.Leave) -> None:
        if self.hover is not None and self._drag is None:
            self.hover = None
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        if self._moved:
            self._moved = False
            return
        pin = self.pin_at(event.x, event.y)
        if pin:
            self.sel = pin
            self.refresh()
            self.post_message(self.Open(pin))

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.set_zoom(1, (event.x, event.y))

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.set_zoom(0, (event.x, event.y))

    # -- info ------------------------------------------------------------------
    def hover_info(self) -> Text:
        g = self.game
        did = self.hover or self.sel
        if not did:
            return Text("THE COURT", style=f"bold {GREEN}")
        d = self._by_id(did)
        t = Text()
        if g.dossier_unlocked(did):
            t.append(f"{d['title']}\n", style=f"bold {GREEN}")
            t.append(f"{d['faction']}\n", style=DIM)
            bonus = g.dossier_bonus_text(d)
            t.append(f"Passive: {bonus}\n" if bonus else "No passive bonus.\n")
            if "choice" in d and did not in g.s.dossier_choices:
                t.append("A decision awaits. Click to open.", style=f"bold {RED}")
            else:
                t.append("Click to read.", style=DIM)
        else:
            t.append("SEALED\n", style=f"bold {DIM}")
            t.append(f"Unseal: {g.dossier_hint(d)}", style="")
        return t

    # -- render ----------------------------------------------------------------
    def _line(self, grid, x0, y0, x1, y1, hot: bool) -> None:
        w, h = self.size.width, self.size.height
        style = f"bold {RED}" if hot else PAL["red_dim"]
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        x, y = x0, y0
        for _ in range(dx + dy + 2):
            nx, ny = x, y
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                nx += sx
            if e2 < dx:
                err += dx
                ny += sy
            ch = "─" if ny == y else "│" if nx == x else ("╲" if (sx * sy) > 0 else "╱")
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = (ch, style)
            x, y = nx, ny
            if (x, y) == (x1, y1):
                break

    def _put(self, grid, x, y, text, style) -> None:
        w, h = self.size.width, self.size.height
        if not (0 <= y < h):
            return
        for i, ch in enumerate(text):
            if 0 <= x + i < w:
                grid[y][x + i] = (ch, style)

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w <= 0 or h <= 0:
            return Text("")
        g = self.game
        grid = [[(" ", "")] * w for _ in range(h)]
        # faint grid so panning reads as motion
        sc = self.scale
        for gy in range(h):
            for gx in range(w):
                wx, wy = int(self.pan[0] + gx / sc), int(self.pan[1] + gy / sc)
                if wx % 10 == 0 and wy % 6 == 0 and (gx == int((wx - self.pan[0]) * sc) or sc == 1.0):
                    grid[gy][gx] = ("·", PAL["line"])
        active = self.hover or self.sel
        hot = set()
        if self.hover:
            hot = {self.hover, *self._by_id(self.hover)["links"]}
        # strings first
        for d in self.dossiers:
            cx, cy = self._center(d)
            for lid in d["links"]:
                if d["id"] < lid:
                    o = self._by_id(lid)
                    ox, oy = self._center(o)
                    is_hot = bool(self.hover) and self.hover in (d["id"], lid)
                    if g.dossier_unlocked(d["id"]) or g.dossier_unlocked(lid) or is_hot:
                        self._line(grid, cx, cy, ox, oy, is_hot)
        # pins
        for d in self.dossiers:
            x, y, pw, ph = self._rect(d)
            unlocked = g.dossier_unlocked(d["id"])
            is_sel = d["id"] == self.sel
            is_hover = d["id"] == self.hover
            pending = unlocked and "choice" in d and d["id"] not in g.s.dossier_choices
            edge = (f"bold {GREEN}" if is_hover or is_sel else (GREEN if unlocked else PAL["off_fg2"]))
            if self.zoom == 0:
                label = ("● " + (d["title"] if unlocked else "???"))[:pw]
                mark = "!" if pending else ""
                self._put(grid, x, y, (label + mark).ljust(pw)[:pw],
                          ("reverse " if is_hover or is_sel else "") + (edge if unlocked else PAL["off_fg2"]))
                continue
            top = "┌" + "─" * (pw - 2) + "┐"
            self._put(grid, x, y, top, edge)
            self._put(grid, x + pw // 2, y, "●", f"bold {RED}")
            bg = f"on {PAL['hover']}" if (is_hover or is_sel) else f"on {PAL['panel']}"
            if unlocked:
                fac = d["faction"][:pw - 4]
                ttl = d["title"] if len(d["title"]) <= pw - 4 else d["title"][:pw - 5] + "…"
                rows = [(fac, f"{DIM} {bg}"), (ttl + (" !" if pending else ""), f"bold {PAL['fg']} {bg}")]
            else:
                rows = [("▒▒▒ SEALED ▒▒▒", f"{PAL['off_fg2']} {bg}"), ("? ? ?", f"{PAL['off_fg2']} {bg}")]
            for i, (txt, st) in enumerate(rows):
                self._put(grid, x, y + 1 + i, "│", edge)
                self._put(grid, x + 1, y + 1 + i, (" " + txt).ljust(pw - 2)[:pw - 2], st)
                self._put(grid, x + pw - 1, y + 1 + i, "│", edge)
            self._put(grid, x, y + ph - 1, "└" + "─" * (pw - 2) + "┘", edge)
        out = Text(no_wrap=True, overflow="crop")
        for ri, row in enumerate(grid):
            run, style = "", None
            for ch, st in row:
                if st != style and run:
                    out.append(run, style=style or "")
                    run = ""
                style = st
                run += ch
            if run:
                out.append(run, style=style or "")
            if ri < h - 1:
                out.append("\n")
        return out
