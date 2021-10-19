from abc import ABC
from argparse import ArgumentParser
from graphlib import CycleError
from pprint import pprint
from typing import Callable

import pygame as pg
from bitarray import bitarray
import tkinter as tk

from turing_complete_interface.tc_assembler import assemble
from .circuit_compiler import build_connections, build_gate
from .tc_components import screens, AsciiScreen, get_component
from . import tc_components
from .circuit_parser import CircuitWire, Circuit, GateShape, GateReference, SCHEMATICS_PATH
from .logic_nodes import file_safe_name
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


def draw_gate(view: WorldView, gate: GateReference, gate_shape: GateShape,
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
        view.draw.rect(gate_shape.color, ((tl[0] - 0.5, tl[1] - 0.5),
                                          size))
    for dp in gate_shape.blocks:
        p = gate.translate(dp)
        view.draw.rect(gate_shape.color, (p[0] - 0.5, p[1] - 0.5, 1, 1))
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
        view.draw.circle((255 * p.is_byte, 255 * p.is_delayed, 255 * p.is_input),
                         xy, 0.25)
        if hover_text is not None:
            hover_text[xy] = f"{gate.id}.{name}: {value.to01()[::-1]}"
    view.draw.text((255, 255, 255), pos, gate_shape.text(gate), size=1, background=((255, 0, 0) if highlight else None))


def draw_wire(view: WorldView, wire: CircuitWire):
    color = (BIT_COLORS, BYTE_COLORS)[wire.is_byte].get(wire.color, (0, 0, 0))
    if len(wire.positions) > 1:
        view.draw.lines(color, False, wire.positions, 0.5)
    view.draw.circle(color, wire.positions[0], 0.5)
    view.draw.circle(color, wire.positions[-1], 0.5)
    if wire.label and len(wire.positions) > 1:
        mid = len(wire.positions) // 2
        if len(wire.positions) % 2 == 0:
            dr = pg.Vector2(wire.positions[mid + 1]) - wire.positions[mid]
            pos = (pg.Vector2(wire.positions[mid]) + wire.positions[mid + 1]) / 2 - dr / 2
        else:
            dr = pg.Vector2(wire.positions[mid + 1]) - wire.positions[mid - 1]
            pos = wire.positions[mid]
        view.draw.text((255, 255, 255), pos, str(wire.label), angle=dr.angle_to((1, 0)))


def view_circuit(level_name, save_name, assembly_name=None,
                 output_handler: Callable[[pg.Surface], WorldHandler] = None):
    pg.init()
    W, H = 640, 480
    FLAGS = pg.RESIZABLE
    FONT_SIZE = 30

    screen = pg.display.set_mode((W, H), FLAGS)
    if output_handler is not None:
        output_handler = output_handler(screen)
    font = pg.font.Font("turing_complete_interface/Px437_IBM_BIOS.ttf", FONT_SIZE)
    W, H = screen.get_size()
    view = WorldView.centered(screen, scale_x=40)
    circuit = Circuit.parse((SCHEMATICS_PATH / level_name / save_name / "circuit.data").read_text())
    if level_name == "architecture" and assembly_name is not None:
        assembly_path = (SCHEMATICS_PATH / level_name / save_name / assembly_name).with_suffix(".assembly")
        assembled = assemble(SCHEMATICS_PATH / level_name / save_name, assembly_path)
        tc_components.program.clear()
        tc_components.program.frombytes(assembled)
    node = build_gate(save_name, circuit)
    print(node.to_spec(file_safe_name))

    current_state = node.create_state()

    root = tk.Tk()
    bit_widgets: dict[str, BitsInput] = {}
    for name, pin in node.inputs.items():
        w = bit_widgets[name] = BitsInput(root, name, pin.bits, delayed=pin.delayed)
        w.pack()
    for name, pin in node.outputs.items():
        w = bit_widgets[name] = BitsInput(root, name, pin.bits, locked=True)
        w.pack()

    wire_values = {}

    cycle = None
    pg.key.set_repeat(100, 50)

    def step(state):
        args = {}
        for name in node.inputs:
            args[name] = bit_widgets[name].value
        if output_handler is not None:
            args["3.value"] = output_handler.get_input()
        try:
            state, values, wire_values = node.calculate(state, **args)
        except CycleError as e:
            print(e)
            return state, {}, [exe.node for exe in e.args[-1]]
        for name, v in values.items():
            bit_widgets[name].value = v
        if output_handler is not None:
            if values["3.control"]:
                output_handler.took_input()
            if values["4.control"]:
                output_handler.got_output(values["4.value"])
        return state, wire_values, None

    show_circuit = True

    connections = build_connections(circuit)
    clock = pg.time.Clock()
    running = True
    Event = pg.event.EventType
    while running:
        root.update()
        try:
            if not root.winfo_exists():
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
            current_state, wire_values, cycle = step(current_state)
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
            for wire in circuit.wires:
                draw_wire(view, wire)
            for gate in circuit.gates:
                shape, _ = get_component(gate)
                draw_gate(view, gate, shape, hover_text, wire_values, (gate.id in cycle if cycle else False))
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
    arg_parser.add_argument("--fast-bot-turtle", action="store_true")

    ns = arg_parser.parse_args()
    if ns.level is None:
        options = [d.name for d in SCHEMATICS_PATH.iterdir() if d.is_dir()]
        ns.level = prompt("Enter level name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))
    if ns.save is None:
        options = [d.name for d in (SCHEMATICS_PATH / ns.level).iterdir() if d.is_dir()]
        ns.save = prompt("Enter save name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))
    if ns.assembly is None and ns.level == "architecture":
        options = []
        for actual_level in (SCHEMATICS_PATH / ns.level / ns.save).iterdir():
            if actual_level.is_dir():
                for assembly in actual_level.iterdir():
                    if assembly.suffix == ".bytes":
                        options.append(actual_level.stem + "/" + assembly.stem)
        ns.assembly = prompt("Enter assembly name> ", completer=FuzzyCompleter(WordCompleter(options, sentence=True)))

    view_circuit(ns.level, ns.save, ns.assembly or None,
                 FastBotTurtle if ns.fast_bot_turtle else None
                 )
