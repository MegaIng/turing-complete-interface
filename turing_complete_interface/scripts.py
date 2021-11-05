from typing import Literal

from turing_complete_interface.circuit_builder import build_circuit, IOPosition, layout_with_pydot
from turing_complete_interface.circuit_parser import Circuit, SCHEMATICS_PATH
from turing_complete_interface.from_logic_expression import from_logic_expression
from turing_complete_interface.level_layouts import LevelLayout
from turing_complete_interface.logic_nodes import LogicNodeType
from turing_complete_interface.verilog_parser import parse_verilog

selected_level: str | None = None
level_layout: LevelLayout = LevelLayout((-31, -31, 62, 62), None)


class _NamedConstant:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class _NameSources(_NamedConstant):
    pass


USE_MODULE_NAME = _NameSources("USE_MODULE_NAME")
USE_LEVEL_NAME = _NameSources("USE_LEVEL_NAME")
USE_SAVE_NAME = _NameSources("USE_SAVE_NAME")


def select_level(name: str):
    global selected_level
    selected_level = name


def logic_expression_to_node(expression: str) -> LogicNodeType:
    if selected_level is not None:
        name = selected_level[-1]
    else:
        name = "LogicExpr"
    return from_logic_expression(name, expression)


def verilog_to_node(verilog: str, module_name: _NameSources | str = USE_MODULE_NAME):
    return parse_verilog(verilog)


def node_to_circuit(node: LogicNodeType) -> Circuit:
    return build_circuit(node, level_layout.fixed_io or IOPosition.from_node(node), level_layout.new_space())


def node_to_circuit_pydot(node: LogicNodeType) -> Circuit:
    return layout_with_pydot(node, level_layout.fixed_io or IOPosition.from_node(node), level_layout.new_space())


def save_custom_component(circuit: Circuit, name: str):
    save_level(circuit, "component_factory", name)


def save_level(circuit: Circuit, level_name: str, save_name: str):
    s = circuit.to_string()
    path = (SCHEMATICS_PATH / level_name / save_name)
    path.mkdir(exist_ok=True, parents=True)
    (path / "circuit.data").write_text(s)
