import json
from dataclasses import dataclass
from pathlib import Path

from turing_complete_interface.circuit_builder import IOPosition, Space


@dataclass
class LevelLayout:
    area: tuple[int, int, int, int]
    fixed_io: None | list[IOPosition]

    def new_space(self, **extra):
        return Space(*self.area, **extra)


default_size = (-31, -31, 62, 62)
json_data = json.loads(Path(__file__).with_name("level_layouts.json").read_text())


def get_layout(name: str) -> LevelLayout:
    if name in json_data:
        data = json_data[name]
        d = data["inputs"]
        return LevelLayout(
            tuple(data.get("size", default_size)),
            d if d is None else [IOPosition(io["type"], io["pins"], io["id"]) for io in d]
        )
    else:
        return LevelLayout(default_size, None)
