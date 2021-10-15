from argparse import ArgumentParser
from graphlib import CycleError
from pprint import pprint

import pygame as pg
from bitarray import bitarray
import tkinter as tk

from .circuit_compiler import build_connections, build_gate
from .circuit_parser import CircuitWire, Circuit, GateShape, DEFAULT_GATES, GateReference, load_custom, SCHEMATICS_PATH, \
    find_gate
from .logic_nodes import NAND_2W1, file_safe_name
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
        view.draw.circle((255 * p.is_bytes, 255 * p.is_delayed, 255 * p.is_input),
                         xy, 0.25)
        if hover_text is not None:
            hover_text[xy] = f"{gate.id}.{name}: {value.to01()}"
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


def view_circuit(level_name, save_name):
    pg.init()
    W, H = 640, 480
    FLAGS = pg.RESIZABLE

    screen = pg.display.set_mode((W, H), FLAGS)
    W, H = screen.get_size()
    view = WorldView.centered(screen, scale_x=40)
    # circuit = Circuit.parse((SCHEMATICS_PATH / "architecture" / "LEG" / "circuit.data").read_text())
    circuit = Circuit.parse((SCHEMATICS_PATH / level_name / save_name / "circuit.data").read_text())
    node = build_gate(save_name, circuit)
    print(node.to_spec(file_safe_name))
    # pprint(node)
    # pprint(node.execution_order)

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

    hover_text = {}
    cycle = None

    def step(state):
        args = {}
        for name in node.inputs:
            args[name] = bit_widgets[name].value
        try:
            state, values, wire_values = node.calculate(state, **args)
        except CycleError as e:
            print(e)
            return state, {}, [exe.node for exe in e.args[-1]]
        for name, v in values.items():
            bit_widgets[name].value = v
        return state, wire_values, None

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
                case event if view.handle_event(event):
                    pass
                case Event(type=pg.KEYDOWN, key=pg.K_SPACE):
                    current_state, wire_values, cycle = step(current_state)
        # Logic
        dt = clock.tick()
        view.update(dt)

        # Render
        hover_text = {}
        screen.fill((127, 127, 127))
        for wire in circuit.wires:
            draw_wire(view, wire)
        for gate in circuit.gates:
            _, shape = find_gate(gate)
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
    arg_parser = ArgumentParser()
    arg_parser.add_argument("level_name")
    arg_parser.add_argument("save_name")
    arg_parser.add_argument("assembly_name", nargs="?")

    ns = arg_parser.parse_args()

    view_circuit(ns.level_name, ns.save_name)
