from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Callable, TypedDict

try:
    import nimporter
except ImportError:
    print("Couldn't import nimporter. Assuming that save_monger is available anyway.")
from turing_complete_interface import save_monger


def pre_parse(text: str) -> list[list[list[list[str]]]]:
    return [[
        [
            part.split(",") if "," in part else part
            for part in element.split("`")
        ] for element in section.split(";")
    ] for section in text.split("|")]


class NimPoint(TypedDict):
    x: int
    y: int


@dataclass
class GateReference:
    name: str
    pos: tuple[int, int]
    rotation: int
    id: str
    custom_data: str

    def translate(self, dp: tuple[int, int]):
        dp = self.rot(dp)
        return self.pos[0] + dp[0], self.pos[1] + dp[1]

    def rot(self, dp: tuple[int, int]):
        (a, b), (c, d) = [
            ((1, 0), (0, 1)),
            ((0, -1), (1, 0)),
            ((-1, 0), (0, -1)),
            ((0, 1), (-1, 0)),
        ][self.rotation]
        return a * dp[0] + b * dp[1], c * dp[0] + d * dp[1]

    @classmethod
    def from_nim(cls,
                 kind: str,
                 position: NimPoint,
                 rotation: int,
                 permanent_id: int,
                 custom_string: str) -> GateReference | None:
        if save_monger.is_virtual(kind):
            return None
        return GateReference(
            kind, (position["x"], position["y"]), rotation, str(permanent_id), custom_string
        )

    def to_nim(self):
        return {
            "kind": self.name,
            "position": {"x": self.pos[0], "y": self.pos[1]},
            "rotation": self.rotation,
            "permanent_id": int(self.id),
            "custom_string": self.custom_data
        }


@dataclass
class CircuitWire:
    id: int
    is_byte: bool
    color: int
    label: str
    positions: list[tuple[int, int]]

    @classmethod
    def from_nim(cls,
                 permanent_id: int,
                 path: list[NimPoint],
                 kind: str,
                 color: int,
                 comment: str) -> CircuitWire:
        assert kind in ("ck_bit", "ck_byte"), kind
        return CircuitWire(
            permanent_id, kind == "ck_byte", color, comment, [(p["x"], p["y"]) for p in path]
        )

    def to_nim(self):
        return {
            "permanent_id": self.id,
            "path": [{"x": p[0], "y": p[1]} for p in self.positions],
            "kind": ["ck_bit", "ck_byte"][self.is_byte],
            "color": self.color,
            "comment": self.label
        }


@dataclass
class Circuit:
    gates: list[GateReference]
    wires: list[CircuitWire]
    nand_cost: int
    delay: int
    level_version: int = 0
    shape: GateShape = None

    @property
    def score(self):
        return self.nand_cost + self.delay

    @classmethod
    def parse(cls, text: str) -> Circuit:
        components, circuits, nand, delay, level_version = save_monger.py_parse_state(text)
        return Circuit(
            [GateReference.from_nim(**c) for c in components],
            [CircuitWire.from_nim(**c) for c in circuits],
            nand, delay, level_version
        )

    def to_string(self) -> str:
        return save_monger.parse_state_to_string(
            [g.to_nim() for g in self.gates],
            [w.to_nim() for w in self.wires],
            self.nand_cost, self.delay, self.level_version
        )


@dataclass
class BigShape:
    tl: tuple[int, int]
    size: tuple[int, int]

    @property
    def br(self):
        return self.tl[0] + self.size[0], self.tl[1] + self.size[1]


@dataclass
class CircuitPin:
    pos: tuple[int, int]
    is_input: bool
    is_byte: bool = False
    is_delayed: bool = False


@dataclass
class GateShape:
    name: str
    color: tuple[int, int, int]
    pins: dict[str | int, CircuitPin]
    blocks: list[tuple[int, int]]
    is_io: bool = False
    text: Callable[[GateReference], str] = staticmethod(lambda gate: str(gate.custom_data or gate.name))
    big_shape: BigShape = None

    @property
    def bounding_box(self):
        min_x = min_y = float("inf")
        max_x = max_y = -float("inf")
        for p in (
                *(p.pos for p in self.pins.values()),
                *(self.blocks),
                *((self.big_shape.tl, self.big_shape.br) if self.big_shape is not None else ())
        ):
            if p[0] < min_x:
                min_x = p[0]
            if p[0] > max_x:
                max_x = p[0]

            if p[1] < min_y:
                min_y = p[1]
            if p[1] > max_y:
                max_y = p[1]
        assert all((isfinite(min_x), isfinite(max_x), isfinite(min_y), isfinite(max_y))), (min_x, max_x, min_y, max_y)
        return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1

    def pin_position(self, gate_ref: GateReference, pin_name: str):
        p = self.pins[pin_name]
        return gate_ref.pos[0] + p.pos[0], gate_ref.pos[1] + p.pos[1]


SPECIAL = (206, 89, 107)
NORMAL = (28, 95, 147)
CUSTOM = (30, 165, 174)


def get_path():
    match sys.platform:
        case "Windows" | "win32":
            base_path = Path(os.environ["APPDATA"], r"Godot\app_userdata\Turing Complete")
        case "darwin":
            base_path = Path("~/Library/Application Support/Godot/app_userdata/Turing Complete").expanduser()
        case "Linux":
            base_path = Path("~/.local/share/godot/app_userdata/Turing Complete").expanduser()
        case _:
            print(f"Don't know where to find Turing Complete save on {sys.platform=}")
            return None
    if not base_path.exists():
        print("You need Turing Complete installed to use everything here")
        return None
    return base_path


BASE_PATH = get_path()

SCHEMATICS_PATH = BASE_PATH / "schematics" if BASE_PATH is not None else None
