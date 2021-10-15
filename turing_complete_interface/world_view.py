from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import overload, TypeVar

import pygame as pg
import pygame.transform

POINT_COMPATIBLE = pg.Vector2 | tuple[float, float]
RECT_COMPATIBLE = tuple[POINT_COMPATIBLE, POINT_COMPATIBLE] | tuple[float, float, float, float] | pg.Rect


def _get_point(point: POINT_COMPATIBLE) -> tuple[float, float]:
    if hasattr(point, "x") and hasattr(point, "y"):
        return point.x, point.y
    else:
        x, y = point
        return (x, y)


def _get_rect_corners(rect: RECT_COMPATIBLE) -> tuple[tuple[float, float], tuple[float, float]]:
    if isinstance(rect, pg.Rect):
        return rect.topleft, rect.bottomright
    elif len(rect) == 2:
        (x, y), (w, h) = _get_point(rect[0]), _get_point(rect[1])
    else:
        x, y, w, h = rect
    return (x, y), (x + w, y + h)


@dataclass
class WorldView:
    screen: pg.Surface
    offset_x: float = 0  # These are in world coordinates
    offset_y: float = 0
    scale_x: float = 1
    scale_y: float = 1

    drag_buttons: tuple[int, ...] = (2,)
    zoom_factor: float = 1 / 0.9
    _grabbed: tuple[float, float] | None = None
    _grabbed_button: int | None = None
    draw: BoundDrawer = field(init=False, repr=False)

    def __post_init__(self):
        self.draw = BoundDrawer(self)

    def w2s(self, point: POINT_COMPATIBLE) -> tuple[float, float]:
        x, y = _get_point(point)
        return (x + self.offset_x) * self.scale_x, (y + self.offset_y) * self.scale_y

    def s2w(self, point: POINT_COMPATIBLE) -> tuple[float, float]:
        x, y = _get_point(point)
        return (x / self.scale_x - self.offset_x), (y / self.scale_y - self.offset_y)

    def mw2s(self, points: list[POINT_COMPATIBLE]) -> list[tuple[float, float]]:
        return [self.w2s(p) for p in points]

    def ms2w(self, points: list[POINT_COMPATIBLE]) -> list[tuple[float, float]]:
        return [self.s2w(p) for p in points]

    def move(self, grabbed: POINT_COMPATIBLE, mouse_position: POINT_COMPATIBLE):
        grabbed, mouse_position = _get_point(grabbed), self.s2w(mouse_position)
        self.offset_x += mouse_position[0] - grabbed[0]
        self.offset_y += mouse_position[1] - grabbed[1]

    def zoom(self, fixed: POINT_COMPATIBLE, scale_x: float, scale_y: float = None):
        if scale_y is None:
            scale_y = scale_x
        p = self.s2w(fixed)
        self.scale_x *= scale_x
        self.scale_y *= scale_y
        self.move(p, fixed)

    def handle_event(self, event: pg.event.Event) -> bool:
        Event = pg.event.EventType
        match event:
            case Event(type=pg.MOUSEBUTTONDOWN, pos=pos, button=b) if b in self.drag_buttons:
                if self._grabbed is None:
                    self._grabbed = self.s2w(pos)
                    self._grabbed_button = b
            case Event(type=pg.MOUSEBUTTONUP, button=self._grabbed_button):
                self._grabbed = None
            case Event(type=pg.MOUSEWHEEL, y=y):
                self.zoom(pg.mouse.get_pos(), self.zoom_factor ** y)

    def update(self, dt: int):
        if self._grabbed is not None:
            self.move(self._grabbed, pg.mouse.get_pos())

    @classmethod
    def centered(cls, screen: pg.Surface, world_center: POINT_COMPATIBLE = (0, 0), scale_x: float = 1,
                 scale_y: float = None) -> WorldView:
        view = WorldView(screen, scale_x=scale_x, scale_y=(scale_x if scale_y is None else scale_y))
        view.move(world_center, (screen.get_width() / 2, screen.get_height() / 2))
        return view

    def rw2s(self, rect_like: RECT_COMPATIBLE) -> tuple[tuple[float, float], tuple[float, float]]:
        tl, br = _get_rect_corners(rect_like)
        tl, br = self.w2s(tl), self.w2s(br)
        return tl, (br[0] - tl[0], br[1] - tl[1])

    def sw2s(self, size: float) -> float:
        return size * (self.scale_y + self.scale_x) / 2


_T = TypeVar("_T")


def _forward_to_pygame_draw(*, points: tuple[str | int, ...] = (), lists: tuple[str | int, ...] = (),
                            rects: tuple[str | int, ...] = (), sizes: tuple[str | int, ...] = ()):
    def wrapper(func: _T) -> _T:
        draw_func = getattr(pg.draw, func.__name__)

        @wraps(func)
        def wrap(self: BoundDrawer, *args, **kwargs):
            args = list(args)
            for f, t in (
                    (self.viewer.w2s, points),
                    (self.viewer.mw2s, lists),
                    (self.viewer.rw2s, rects),
                    (lambda s: max(int(round(self.viewer.sw2s(s))), 1), sizes)
            ):
                for a in t:
                    if isinstance(a, int):
                        args[a] = f(args[a])
                    elif a in kwargs:
                        kwargs[a] = f(kwargs[a])
            return draw_func(self.viewer.screen, *args, **kwargs)

        return wrap

    return wrapper


@dataclass
class BoundDrawer:
    viewer: WorldView
    font_name: str = None
    _font_cache: dict[tuple, pg.font.Font] = field(default_factory=dict, init=False, repr=False)

    def font(self, size: int):
        args = (self.font_name, size)
        if args not in self._font_cache:
            self._font_cache[args] = pg.font.SysFont(*args)
        return self._font_cache[args]

    @_forward_to_pygame_draw(points=(1, 2))
    def aaline(self, color, start_pos, end_pos, /, blend=1) -> pg.Rect:
        """
        aaline(color, start_pos, end_pos) -> Rect
        aaline(color, start_pos, end_pos, blend=1) -> Rect
        draw a straight antialiased line
        """
        pass

    @_forward_to_pygame_draw(lists=(2,))
    def aalines(self, color, closed, points, /, blend=1) -> pg.Rect:
        """
        aalines(color, closed, points) -> Rect
        aalines(color, closed, points, blend=1) -> Rect
        draw multiple contiguous straight antialiased line segments
        """
        pass

    @_forward_to_pygame_draw(rects=(1,), sizes=("width",))
    def arc(self, color, rect, start_angle, stop_angle, /, width=1) -> pg.Rect:
        """
        arc(color, rect, start_angle, stop_angle) -> Rect
        arc(color, rect, start_angle, stop_angle, width=1) -> Rect
        draw an elliptical arc
        """
        pass

    @_forward_to_pygame_draw(points=(1,), sizes=("width", "radius", 2))
    def circle(self, color, center, radius, /, width=0, draw_top_right=None, draw_top_left=None, draw_bottom_left=None,
               draw_bottom_right=None) -> pg.Rect:
        """
        circle(color, center, radius) -> Rect
        circle(color, center, radius, width=0, draw_top_right=None, draw_top_left=None, draw_bottom_left=None, draw_bottom_right=None) -> Rect
        draw a circle
        """
        pass

    @_forward_to_pygame_draw(rects=(1,))
    def ellipse(self, color, rect, /, width=0) -> pg.Rect:
        """
        ellipse(color, rect) -> Rect
        ellipse(color, rect, width=0) -> Rect
        draw an ellipse
        """
        pass

    @_forward_to_pygame_draw(points=(1, 2))
    def line(self, color, start_pos, end_pos, /, width=1) -> pg.Rect:
        """
        line(color, start_pos, end_pos) -> Rect
        line(color, start_pos, end_pos, width=1) -> Rect
        draw a straight line
        """
        pass

    @_forward_to_pygame_draw(lists=(2,), sizes=("width", 3))
    def lines(self, color, closed, points, /, width=1) -> pg.Rect:
        """
        lines(color, closed, points) -> Rect
        lines(color, closed, points, width=1) -> Rect
        draw multiple contiguous straight line segments
        """
        pass

    @_forward_to_pygame_draw(lists=(1,))
    def polygon(self, color, points, /, width=0) -> pg.Rect:
        """
        polygon(color, points) -> Rect
        polygon(color, points, width=0) -> Rect
        draw a polygon
        """
        pass

    @_forward_to_pygame_draw(rects=(1,))
    def rect(self, color, rect, /, width=0, boarder_radius=0, boarder_top_left_radius=-1, border_top_right_radius=-1,
             boarder_bottom_left_radius=-1,
             border_bottom_right_radius=-1) -> pg.Rect:
        """
        rect(color, rect) -> Rect
        rect(color, rect, width=0, border_radius=0, border_top_left_radius=-1, border_top_right_radius=-1, border_bottom_left_radius=-1, border_bottom_right_radius=-1) -> Rect
        draw a rectangle
        """
        pass

    def text(self, color, position, text, *, size: int = 1, anchor="center", angle: float = 0, background=None):
        size = max(int(self.viewer.sw2s(size)), 5)
        img = self.font(size).render(text, True, color, background)
        img = pygame.transform.rotate(img, angle)
        r = img.get_rect(**{anchor: self.viewer.w2s(position)})
        self.viewer.screen.blit(img, r)
