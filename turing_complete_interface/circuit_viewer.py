import json
import os
from abc import ABC
from argparse import ArgumentParser
from dataclasses import dataclass, field
from graphlib import CycleError
from pathlib import Path
from pprint import pprint
from typing import Callable

import pygame as pg
from bitarray import bitarray
import tkinter as tk

from turing_complete_interface.circuit_builder import build_circuit, IOPosition, Space
from turing_complete_interface.level_layouts import get_layout
from turing_complete_interface.tc_assembler import assemble
from turing_complete_interface.verilog_parser import parse_verilog
from .circuit_compiler import build_connections, build_gate
from .tc_components import screens, AsciiScreen, get_component, compute_gate_shape
from . import tc_components
from .circuit_parser import CircuitWire, Circuit, GateShape, GateReference, SCHEMATICS_PATH
from .logic_nodes import file_safe_name, LogicNodeType
from .specification_tester import BitsInput
from .world_view import WorldView

BIT_COLORS = {
    0: (227, 158, 69),
    1: (219, 227, 69),
    2: (150, 227, 69),
    3: (69, 227, 150),
    4: (68, 220, 228),
    5: (68, 68, 228),
    6: (152, 68, 228),
    7: (227, 69, 201),
    8: (227, 110, 79),
    9: (255, 255, 255),
    10: (122, 122, 122),
    11: (54, 54, 54),
}
BYTE_COLORS = {
    0: (61, 154, 204),
    1: (219, 227, 69),
    2: (150, 227, 69),
    3: (69, 227, 150),
    4: (68, 220, 228),
    5: (68, 68, 228),
    6: (152, 68, 228),
    7: (227, 69, 201),
    8: (227, 110, 79),
    9: (255, 255, 255),
    10: (122, 122, 122),
    11: (54, 54, 54),
}


class WorldHandler(ABC):
    def handle_event(self, event: pg.event.Event):
        pass

    def update(self, dt: int):
        pass

    def draw(self, screen: pg.Surface):
        pass

    def get_input(self) -> int:
        return 0

    def took_input(self):
        pass

    def got_output(self, v: int):
        pass


class FastBotTurtle(WorldHandler):
    def __init__(self, screen):
        self.pos = (0, 0)
        self.line = [(0, 0)]
        self.view = WorldView(screen, scale_x=20, scale_y=20)

    def handle_event(self, event: pg.event.Event):
        return self.view.handle_event(event)

    def update(self, dt: int):
        self.view.update(dt)

    def draw(self, screen: pg.Surface):
        screen.fill((255, 255, 255))
        if len(self.line) >= 2:
            self.view.draw.lines((0, 0, 0), False, self.line, width=0.1)
        self.view.draw.circle((255, 0, 0), self.pos, 0.2)

    def got_output(self, v: int):
        dx, dy = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}.get(v, (0, 0))
        if dx != dy:
            self.pos = self.pos[0] + dx, self.pos[1] + dy
            self.line.append(self.pos)


@dataclass(kw_only=True)
class CircuitView(WorldView):
    circuit: Circuit
    extra_info: dict[tuple[int, int], dict[str, str]] = field(default_factory=dict)

    def draw_gate(self, gate: GateReference, gate_shape: GateShape,
                  hover_text: dict[tuple[int, int], str] = None, wire_values: dict = None, highlight: bool = False):
        pos = gate.pos
        if wire_values is None:
            wire_values = {}

        if gate_shape.big_shape is not None:
            tl = gate.translate(gate_shape.big_shape.tl)
            size = gate.rot(gate_shape.big_shape.size)
            if size[0] < 0:
                size = abs(size[0]), size[1]
                tl = tl[0] - size[0], tl[1]
            if size[1] < 0:
                size = size[0], abs(size[1])
                tl = tl[0], tl[1] - size[1]
            self.draw.rect(gate_shape.color, ((tl[0] - 0.5, tl[1] - 0.5),
                                              size))
        for dp in gate_shape.blocks:
            p = gate.translate(dp)
            self.draw.rect(gate_shape.color, (p[0] - 0.5, p[1] - 0.5, 1, 1))
            if hover_text is not None:
                hover_text[p] = f"{gate.id}"
        for name, p in gate_shape.pins.items():
            xy = gate.translate(p.pos)
            if gate_shape.is_io:
                pin_source = None, str(gate.id)
                if pin_source not in wire_values:
                    pin_source = None, f"{gate.id}.{name}"
            else:
                pin_source = str(gate.id), name
            value = wire_values.get(pin_source, bitarray())
            self.draw.circle((255 * p.is_byte, 255 * p.is_delayed, 255 * p.is_input),
                             xy, 0.25)
            if hover_text is not None:
                hover_text[xy] = f"{gate.id}.{name}: {value.to01()[::-1]}"
        self.draw.text((255, 255, 255), pos, gate_shape.text(gate), size=1,
                       background=((255, 0, 0) if highlight else None))

    def draw_wire(self, wire):
        color = wire.screen_color
        if len(wire.positions) > 1:
            self.draw.lines(color, False, wire.positions, 0.5)
        self.draw.circle(color, wire.positions[0], 0.5)
        self.draw.circle(color, wire.positions[-1], 0.5)
        if wire.label and len(wire.positions) > 1:
            mid = len(wire.positions) // 2
            if len(wire.positions) % 2 == 0:
                dr = pg.Vector2(wire.positions[mid + 1]) - wire.positions[mid]
                pos = (pg.Vector2(wire.positions[mid]) + wire.positions[mid + 1]) / 2 - dr / 2
            else:
                dr = pg.Vector2(wire.positions[mid + 1]) - wire.positions[mid - 1]
                pos = wire.positions[mid]
            self.draw.text((255, 255, 255), pos, str(wire.label), angle=dr.angle_to((1, 0)))

    def draw_circuit(self):
        pass


def translate(p):
    return (int((p[0] + 30) // 8 - 3), int((p[1] + 30) // 8 - 3))


def load_circuit(ns) -> tuple[Circuit, LogicNodeType, Space]:
    if ns.observe:
        view = WorldView(pg.display.set_mode((600, 600)))

        def observer(s):
            return _space_observer(view, s)
    else:
        observer = None
    space = get_layout(ns.level).new_space(_observer=observer)
    if ns.verilog is not None:
        node = parse_verilog(ns.verilog.read_text())
        circuit = build_circuit(node, IOPosition.from_node(node), space)
    else:
        save_name = SCHEMATICS_PATH / ns.level / ns.save
        circuit = Circuit.parse((save_name / "circuit.data").read_bytes())
        if ns.level == "architecture" and ns.assembly:
            assembly_path = (save_name / ns.assembly).with_suffix(".assembly")
            assembled = assemble(save_name, assembly_path)
            tc_components.program.clear()
            tc_components.program.frombytes(assembled)
        node = build_gate(save_name, circuit)
    return circuit, node, space


def _space_observer(view: WorldView, space: Space):
    running = True
    Event = pg.event.EventType
    while running:
        for event in pg.event.get():
            match event:
                case Event(type=pg.QUIT):
                    exit()
                case e if view.handle_event(e):
                    continue
                case Event(type=pg.KEYDOWN, key=pg.K_SPACE):
                    return
        view.update(1)
        view.screen.fill((127, 127, 127))
        for x in range(space.x, space.x + space.w):
            for y in range(space.y, space.y + space.h):
                r = (x - 0.5, y - 0.5, 1.1, 1.1)
                k = translate((x, y))
                if space.is_filled(x, y):
                    view.draw.rect((0, 0, 0), r)
                elif (k[0] + k[1]) % 2 == 1:
                    view.draw.rect((65, 65, 65), r)
                else:
                    view.draw.rect((127, 127, 127), r)
        for r in space._placed_boxes:
            view.draw.rect((255, 0, 0), (r[0] + space.x - 0.5, r[1] + space.y - 0.5, r[2], r[3]), 1)
        pg.display.update()


class Simulator(tk.Tk):
    def __init__(self, node: LogicNodeType, output_handler: WorldHandler):
        super(Simulator, self).__init__()
        self.node = node
        self.current_state = node.create_state()
        self.output_handler = output_handler

        self.bit_widgets: dict[str, BitsInput] = {}
        i = 0
        for name, pin in node.inputs.items():
            w = self.bit_widgets[name] = BitsInput(self, name, pin.bits, delayed=pin.delayed)
            w.grid(column=0, row=i)
            i += 1
        for name, pin in node.outputs.items():
            w = self.bit_widgets[name] = BitsInput(self, name, pin.bits, locked=True)
            w.grid(column=0, row=i)
            i += 1

    def step(self):
        args = {}
        for name in self.node.inputs:
            args[name] = self.bit_widgets[name].value
        if self.output_handler is not None:
            args["3.value"] = self.output_handler.get_input()
        try:
            new_state, values, wire_values = self.node.calculate(self.state, **args)
        except CycleError as e:
            print(e)
            return {}, [exe.node for exe in e.args[-1]]
        for name, v in values.items():
            self.bit_widgets[name].value = v
        if self.output_handler is not None:
            if values["3.control"]:
                self.output_handler.took_input()
            if values["4.control"]:
                self.output_handler.got_output(values["4.value"])
        self.state = new_state
        return wire_values, None


def view_circuit(circuit, node, space, output_handler: Callable[[pg.Surface], WorldHandler] = None):
    W, H = 640, 480
    # sdl_frame = tk.Frame(root, width=W, height=H)
    # sdl_frame.grid(column=1, row=0, rowspan=max(i, 1))
    # root.update()
    # os.environ["SDL_WINDOWID"] = str(sdl_frame.winfo_id())
    # wire_values = {}

    pg.init()
    FLAGS = pg.RESIZABLE
    FONT_SIZE = 30

    screen = pg.display.set_mode((W, H), FLAGS)
    if output_handler is not None:
        output_handler = output_handler(screen)
    font = pg.font.Font("turing_complete_interface/Px437_IBM_BIOS.ttf", FONT_SIZE)
    W, H = screen.get_size()
    view = CircuitView.centered(screen, scale_x=40, circuit=circuit)

    cycle = None
    pg.key.set_repeat(100, 50)

    if node is not None:
        simulator = Simulator(node, output_handler)
    else:
        simulator = None
    show_circuit = True

    connections = build_connections(circuit)
    clock = pg.time.Clock()
    running = True
    Event = pg.event.EventType
    hover_text = {}
    wire_values = {}
    while running:
        if simulator:
            simulator.update()
            try:
                if not simulator.winfo_exists():
                    running = False
            except tk.TclError:  # _tkinter.TclError: can't invoke "winfo" command: application has been destroyed
                running = False
        for event in pg.event.get():
            match event:
                case Event(type=pg.QUIT):
                    running = False
                case Event(type=pg.KEYDOWN, key=pg.K_ESCAPE):
                    running = False
                case Event(type=pg.VIDEORESIZE, size=size):
                    screen = pg.display.set_mode(size, FLAGS)
                    W, H = screen.get_size()
                case event if show_circuit and view.handle_event(event):
                    pass
                case event if not show_circuit and output_handler and output_handler.handle_event(event):
                    pass
                case Event(type=pg.KEYDOWN, key=pg.K_RETURN):
                    show_circuit = not show_circuit
                case Event(type=pg.KEYDOWN, key=key):
                    tc_components.last_key = key % 256
        # Logic
        dt = clock.tick()
        view.update(dt)
        if pg.key.get_pressed()[pg.K_SPACE]:
            wire_values, cycle = simulator.step()
        if output_handler is not None:
            output_handler.update(dt)

        # Render
        if not show_circuit:
            if output_handler is None:
                try:
                    ascii_screen: AsciiScreen = next(iter(screens.values()))
                except StopIteration:
                    pass
                else:
                    screen.fill(ascii_screen.background_color)
                    for y in range(14):
                        for x in range(18):
                            i = y * 18 + x
                            col, ch = ascii_screen.ascii_screen[2 * i:2 * i + 2]
                            if ch != 0:
                                col = (
                                    int(((col & 0b11100000) >> 5) * 255 / 8),
                                    int(((col & 0b00011100) >> 3) * 255 / 8),
                                    int(((col & 0b00000011) >> 0) * 255 / 4),
                                )
                                t = font.render(chr(ch), True, col)
                                screen.blit(t, (x * (FONT_SIZE), y * (FONT_SIZE)))
            else:
                output_handler.draw(screen)
        else:
            hover_text = {}
            screen.fill((127, 127, 127))
            for x in range(space.x, space.x + space.w):
                for y in range(space.y, space.y + space.h):
                    k = translate((x, y))
                    if (k[0] + k[1]) % 2 == 1:
                        view.draw.rect((65, 65, 65), (x - 0.5, y - 0.5, 1.1, 1.1))
                    else:
                        view.draw.rect((127, 127, 127), (x - 0.5, y - 0.5, 1.1, 1.1))
            for wire in circuit.wires:
                view.draw_wire(wire)
            for gate in circuit.gates:
                shape, _ = get_component(gate.name, gate.custom_data if gate.name != "Custom" else gate.custom_id, True)
                view.draw_gate(gate, shape, hover_text, wire_values, (gate.id in cycle if cycle else False))
            # shape = compute_gate_shape(circuit, "main")
            # draw_gate(view, GateReference("main", (0,0), 0, "-1", ""), shape)
            p = view.s2w(pg.mouse.get_pos())
            p = int(round(p[0])), int(round(p[1]))
            if p in connections:
                for q in connections[p]:
                    view.draw.circle((255, 255, 0), q, 0.75)

            view.draw.text((0, 0, 0), p, str(p), anchor="bottomleft", background=(127, 127, 127))
            if t := hover_text.get(p, None):
                view.draw.text((0, 0, 0), p, t, anchor="topleft", background=(127, 127, 127))
        pg.display.update()
        pg.display.set_caption(f"FPS: {clock.get_fps():.2f}")


if __name__ == '__main__':
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter, FuzzyCompleter

    arg_parser = ArgumentParser()
    arg_parser.add_argument("-l", "--level", action="store")
    arg_parser.add_argument("-s", "--save", action="store")
    arg_parser.add_argument("-a", "--assembly", action="store")
    arg_parser.add_argument("-v", "--verilog", action="store", type=Path)
    arg_parser.add_argument("--fast-bot-turtle", action="store_true")
    arg_parser.add_argument("--observe", action="store_true")

    ns = arg_parser.parse_args()
    if ns.level is None and SCHEMATICS_PATH is not None:
        options = [d.name for d in SCHEMATICS_PATH.iterdir() if d.is_dir()]
        ns.level = prompt("Enter level name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))
    if ns.save is None and SCHEMATICS_PATH is not None:
        options = [str(d.relative_to(SCHEMATICS_PATH / ns.level).parent) for d in
                   (SCHEMATICS_PATH / ns.level).rglob("circuit.data")]
        ns.save = prompt("Enter save name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))
    if ns.assembly is None and ns.level == "architecture":
        options = []
        for actual_level in (SCHEMATICS_PATH / ns.level / ns.save).iterdir():
            if actual_level.is_dir():
                for assembly in actual_level.iterdir():
                    if assembly.suffix == ".bytes":
                        options.append(actual_level.stem + "/" + assembly.stem)
        ns.assembly = prompt("Enter assembly name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))

    view_circuit(*load_circuit(ns),
                 FastBotTurtle if ns.fast_bot_turtle else None)
