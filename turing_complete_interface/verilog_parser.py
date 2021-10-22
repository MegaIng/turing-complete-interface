import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from frozendict import frozendict
from lark import Lark, Transformer, v_args, Discard, Tree
from lark.visitors import Interpreter
from lark.lexer import Token

from turing_complete_interface.logic_nodes import CombinedLogicNode, InputPin, OutputPin, Wire, NodePin
from turing_complete_interface.tc_components import get_component

parser = Lark(r"""

WS: /[ \t\n\f]+/
ONE_LINE_COMMENT: /\/\/[^\n]+/
BLOCK_COMMENT: /\/\*([^*]|\*(?!\/))*\*\//
BLOCK_PAREN_COMMENT: /\(\*([^*]|\*(?!\)))*\*\)/
%ignore WS
%ignore ONE_LINE_COMMENT
%ignore BLOCK_COMMENT
%ignore BLOCK_PAREN_COMMENT
NAME: /[a-zA-Z_][a-zA-Z0-9_$]*/ | "\\" /[^ \t\n\f]+/


NUMBER: DECIMAL
DECIMAL: /\d+/

start: module+

module: "module" NAME port_list ";" module_item* "endmodule"
port_list: "(" port ("," port)* ")"
?port: [port_expression] | "." NAME "(" [port_expression] ")" -> named_port
port_expression: NAME [range_expression]
range_expression: "[" INT [":" INT] "]"

module_item: "input" [range_expression] NAME ";"-> input_decl
           | "wire" [range_expression] NAME ";" -> wire_decl
           | "output" [range_expression] NAME ";" -> output_decl
           | NAME NAME port_list ";" -> sub_decl
           | "assign" port "=" port ";" -> assign_decl

INT: /\d+/

""", parser="lalr", maybe_placeholders=True)


def _build_wires(selected_bits: tuple[int, int], target: NodePin, target_bits: tuple[int, int],
                 sources: list[tuple[tuple[int, int], NodePin, tuple[int, int]]]) -> Iterable[Wire]:
    assert selected_bits[0] < selected_bits[1]
    assert target_bits[1] - target_bits[0] == selected_bits[1] - selected_bits[0]
    offset = target_bits[0] - selected_bits[0]
    sections = [selected_bits]
    for output_bits, source, (wire_start, wire_end) in sources:
        assert output_bits[0] < output_bits[1]
        assert wire_start < wire_end
        new_sections = []
        for sec_start, sec_end in sections:
            if sec_start >= wire_end or sec_end <= wire_start:
                new_sections.append((sec_start, sec_end))
                continue
            if wire_start > sec_start:
                new_sections.append((sec_start, wire_start))
            if wire_end < sec_end:
                new_sections.append((wire_end, sec_end))
            overlap_start = max(wire_start, sec_start)
            overlap_end = min(wire_end, sec_end)
            wire = Wire(source, target,
                        (output_bits[0] + overlap_start - wire_start, output_bits[1] + overlap_end - wire_end),
                        (offset + overlap_start, offset + overlap_end))
            yield wire
        sections = new_sections


class Verilog2LogicNode(Interpreter):
    nodes = None
    inputs = None
    outputs = None
    wires: dict[str, tuple[list[tuple[tuple[int, int], NodePin, tuple[int, int]]],
                           tuple[int, int],
                           list[tuple[tuple[int, int], NodePin, tuple[int, int]]]]] = None

    current_id = None
    current_component = None
    current_pin_mapping = None

    def __default__(self, *args):
        raise NotImplementedError(args)

    @property
    def constant_true(self):
        if "_" not in self.nodes:
            self.nodes["_"] = get_component("On", "")[1]
            self.wires["_on_"] = ([((0, 1), ("_", "true"), (0, 1))], (0, 1), [])
        return self.wires["_on_"][1]

    def start(self, tree):
        return [self.visit(c) for c in tree.children]

    def module(self, tree):
        assert self.nodes is None, self.nodes
        self.nodes = {}
        self.inputs = {}
        self.outputs = {}
        self.wires = {}
        name, ports, *items = tree.children
        for i in items:
            self.visit(i)
        wires = []
        for wire_name, (sources, size, targets) in self.wires.items():
            assert isinstance(sources, list) and isinstance(targets, list)
            for target_wire_bits, target, target_bits in targets:
                wires.extend(_build_wires(target_wire_bits, target, target_bits, sources))
            # if source != (None, "clk"):
            #     for target in targets:
            #         wires.append(Wire(source, target))
        node = CombinedLogicNode(name.value, frozendict(self.nodes), frozendict(self.inputs), frozendict(self.outputs),
                                 tuple(wires))
        self.nodes = None
        self.inputs = None
        self.outputs = None
        self.wires = None
        return node

    @v_args(inline=True)
    def wire_decl(self, range_decl, name: Token):
        assert name not in self.wires
        if range_decl is not None:
            range_decl = self.visit(range_decl)
        else:
            range_decl = (0, 1)
        self.wires[name.value] = ([], range_decl, [])

    @v_args(inline=True)
    def range_expression(self, start: Token, end: Token | None):
        start = int(start)
        if end is None:
            end = start + 1
        else:
            start += 1
            end = int(end)
        return tuple(sorted((start, end)))

    @v_args(inline=True)
    def input_decl(self, range_decl, name: Token):
        assert name not in self.wires
        if range_decl is not None:
            range_decl = self.visit(range_decl)
        else:
            range_decl = (0, 1)
        if name.value != "clk":
            self.inputs[name.value] = InputPin(max(range_decl) - min(range_decl))
        self.wires[name.value] = ([(range_decl, (None, name.value), range_decl)], range_decl, [])

    @v_args(inline=True)
    def output_decl(self, range_decl, name: Token):
        assert name not in self.wires
        if range_decl is not None:
            range_decl = self.visit(range_decl)
        else:
            range_decl = (0, 1)
        self.outputs[name.value] = OutputPin(max(range_decl) - min(range_decl))
        self.wires[name.value] = ([], range_decl, [(range_decl, (None, name.value), range_decl)])

    @v_args(inline=True)
    def sub_decl(self, component: Token, name: Token, ports):
        assert self.current_component is None
        self.current_id = name.value
        d = verilog_to_tc[component.value]
        self.current_pin_mapping = d["pins"]
        self.current_component = get_component(d["tc"], "")[1]
        self.nodes[name.value] = self.current_component
        self.visit_children(ports)
        self.current_component = None
        self.current_id = None
        self.current_pin_mapping = None

    @v_args(inline=True)
    def port_expression(self, wire_name, range_expr):
        if range_expr is not None:
            range_expr = self.visit(range_expr)
        else:
            range_expr = (0, 1)
        return wire_name.value, range_expr

    @v_args(inline=True)
    def named_port(self, port_name: Token, ref):
        tc_name = self.current_pin_mapping['.' + port_name.value]
        if tc_name is None:  # This is a clk pin
            return
        wire_name, bits = self.visit(ref)
        if tc_name in self.current_component.inputs:
            self.wires[wire_name][2].append(
                (bits, (self.current_id, tc_name), (0, self.current_component.inputs[tc_name].bits)))
        else:
            assert tc_name in self.current_component.outputs, (tc_name, self.current_component)
            self.wires[wire_name][0].append(((0, self.current_component.outputs[tc_name].bits),
                                             (self.current_id, tc_name),
                                             bits))

    @v_args(inline=True)
    def assign_decl(self, target, source):
        target, target_bits = self.visit(target)
        source, source_bits = self.visit(source)
        self.wires[target][0].append((source_bits, source, target_bits))


verilog_to_tc = json.load(Path(__file__).with_name("verilog_components.json").open())


def parse_verilog(text: str) -> CombinedLogicNode:
    tree = parser.parse(text)
    ln, = Verilog2LogicNode().visit(tree)
    return ln

# def generate_verilog(node: CombinedLogicNode) -> str:
