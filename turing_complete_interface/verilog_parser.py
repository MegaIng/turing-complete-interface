import json
from pathlib import Path

from frozendict import frozendict
from lark import Lark, Transformer, v_args, Discard, Tree
from lark.visitors import Interpreter
from lark.lexer import Token

from turing_complete_interface.logic_nodes import CombinedLogicNode, InputPin, OutputPin, Wire
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
?port_expression: port_reference
port_reference: NAME

module_item: "input" NAME ";"-> input_decl
           | "wire" NAME ";" -> wire_decl
           | "output" NAME ";" -> output_decl
           | NAME NAME port_list ";" -> sub_decl
           | "assign" port "=" port ";" -> assign_decl

""", parser="lalr")


class Verilog2LogicNode(Interpreter):
    nodes = None
    inputs = None
    outputs = None
    wires = None

    current_id = None
    current_component = None
    current_pin_mapping = None

    def __default__(self, *args):
        raise NotImplementedError(args)

    @property
    def constant_true(self):
        if "_" not in self.nodes:
            self.nodes["_"] = get_component("On", "")[1]
            self.wires["_on_"] = (("_", "true"), [])
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
        for wire_name, (source, targets) in self.wires.items():
            assert source is not None, wire_name
            if source != (None, "clk"):
                for target in targets:
                    wires.append(Wire(source, target))
        node = CombinedLogicNode(name.value, frozendict(self.nodes), frozendict(self.inputs), frozendict(self.outputs),
                                 tuple(wires))
        self.nodes = None
        self.inputs = None
        self.outputs = None
        self.wires = None
        return node

    @v_args(inline=True)
    def wire_decl(self, name: Token):
        assert name not in self.wires
        self.wires[name.value] = (None, [])

    @v_args(inline=True)
    def input_decl(self, name: Token):
        assert name not in self.wires
        if name.value != "clk":
            self.inputs[name.value] = InputPin(1)
        self.wires[name.value] = ((None, name.value), [])

    @v_args(inline=True)
    def output_decl(self, name: Token):
        assert name not in self.wires
        self.outputs[name.value] = OutputPin(1)
        self.wires[name.value] = (None, [(None, name.value)])

    @v_args(inline=True)
    def sub_decl(self, component: Token, name: Token, ports):
        assert self.current_component is None
        self.current_id = name.value
        d = component_mapping[component.value]
        self.current_pin_mapping = d["pins"]
        self.current_component = get_component(d["tc"], "")[1]
        self.nodes[name.value] = self.current_component
        self.visit_children(ports)
        for p, v in d.get("fix", {}).items():
            if v:
                self.constant_true.append((name.value, p))
        self.current_component = None
        self.current_id = None
        self.current_pin_mapping = None

    @v_args(inline=True)
    def named_port(self, port_name: Token, ref):
        tc_name = self.current_pin_mapping['.' + port_name.value]
        if tc_name is None:  # This is a clk pin
            return
        match ref:
            case Tree("port_reference", [wire_name]):
                assert wire_name.value in self.wires, wire_name
                wire_name = wire_name.value
            case _:
                raise ValueError(ref)
        if tc_name in self.current_component.inputs:
            self.wires[wire_name][1].append((self.current_id, tc_name))
        else:
            assert tc_name in self.current_component.outputs, (tc_name, self.current_component)
            assert self.wires[wire_name][0] is None, f"multiple outputs feeding into wire {wire_name}, {tc_name}"
            self.wires[wire_name] = (self.current_id, tc_name), self.wires[wire_name][1]

    @v_args(inline=True)
    def assign_decl(self, target, source):
        match target:
            case Tree("port_reference", [wire_name]):
                assert wire_name.value in self.wires, wire_name
                target = wire_name.value
            case _:
                raise ValueError(target)
        match source:
            case Tree("port_reference", [wire_name]):
                assert wire_name.value in self.wires, wire_name
                source = wire_name.value
            case _:
                raise ValueError(source)
        assert self.wires[target][0] is None, target
        assert self.wires[source][0] is not None, source
        self.wires[target] = (self.wires[source][0], self.wires[target][1])


component_mapping = json.load(Path(__file__).with_name("verilog_components.json").open())


def parse_verilog(text: str) -> CombinedLogicNode:
    tree = parser.parse(text)
    ln, = Verilog2LogicNode().visit(tree)
    return ln
