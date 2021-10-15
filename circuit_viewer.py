import os
import sys
from itertools import product
from pathlib import Path
from pprint import pprint

import pygame as pg
from bitarray import bitarray

from circuit_compiler import build_connections, build_gate
from circuit_parser import CircuitWire, Circuit, GateShape, DEFAULT_GATES, GateReference, load_custom, SCHEMATICS_PATH, \
    find_gate
from logic_nodes import NAND_2W1, file_safe_name
from specification_tester import BitsInput
from world_view import WorldView
import tkinter as tk

pg.init()

W, H = 640, 480
FLAGS = pg.RESIZABLE

screen = pg.display.set_mode((W, H), FLAGS)
W, H = screen.get_size()

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
}
level_name = "component_factory"
save_name = "LEG ALU"
# level_name = "architecture"
# save_name = "LEG"
# level_name = "demux_3"
# save_name = "Default"
view = WorldView.centered(screen, scale_x=40)
# circuit = Circuit.parse((SCHEMATICS_PATH / "architecture" / "LEG" / "circuit.data").read_text())
circuit = Circuit.parse((SCHEMATICS_PATH / level_name / save_name / "circuit.data").read_text())
node = build_gate(save_name, circuit)
print(node.to_spec(file_safe_name))
# pprint(node)
pprint(node.execution_order)

current_state = node.create_state()

root = tk.Tk()
bit_widgets: dict[str, BitsInput] = {}
for name, pin in node.inputs.items():
    w = bit_widgets[name] = BitsInput(root, name, pin.bits)
    w.pack()
for name, pin in node.outputs.items():
    w = bit_widgets[name] = BitsInput(root, name, pin.bits, locked=True)
    w.pack()


# for t in product((0, 1), repeat=4):
#     args = dict(zip(("1.a", "1.b", "1.c", "1.d"), t))
#     print(args)
#     print(t, tuple(node.calculate(**args)[1].values()))


# print(node.calculate(**{'1.a': 0, '1.b': 0}))
# print(node.calculate(**{'1.a': 0, '1.b': 1}))
# print(node.calculate(**{'1.a': 1, '1.b': 0}))
# print(node.calculate(**{'1.a': 1, '1.b': 1}))


def draw_wire(view: WorldView, wire: CircuitWire):
    color = (BIT_COLORS, BYTE_COLORS)[wire.is_byte][wire.color]
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


wire_values = {}

hover_text = {}


def draw_gate(view: WorldView, gate: GateReference, gate_shape: GateShape):
    pos = gate.pos

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
        view.draw.circle((255 * (value.any()), 255 * p.is_delayed, 255 * p.is_input),
                         xy, 0.25)
        hover_text[xy] = f"{gate.id}.{name}: {value.to01()}"
    view.draw.text((255, 255, 255), pos, gate_shape.text(gate), size=1)


def step():
    global current_state, wire_values
    args = {}
    for name in node.inputs:
        args[name] = bit_widgets[name].value
    current_state, values, wire_values = node.calculate(current_state, **args)
    for name, v in values.items():
        bit_widgets[name].value = v
    print(wire_values)


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
                step()
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
        draw_gate(view, gate, shape)
    p = view.s2w(pg.mouse.get_pos())
    p = int(round(p[0])), int(round(p[1]))
    if p in connections:
        for q in connections[p]:
            view.draw.circle((255, 255, 0), q, 0.75)
            # view.draw.rect((255,255,0), (q[0] - 0.5, q[1] - 0.5, 1, 1))

    view.draw.text((0, 0, 0), p, str(p), anchor="bottomleft", background=(127, 127, 127))
    if t := hover_text.get(p, None):
        view.draw.text((0, 0, 0), p, t, anchor="topleft", background=(127, 127, 127))

    pg.display.update()
    pg.display.set_caption(f"FPS: {clock.get_fps():.2f}")
