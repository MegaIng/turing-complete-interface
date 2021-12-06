from os import PathLike
from typing import Literal, overload

from turing_complete_interface.circuit_builder import build_circuit, IOPosition, layout_with_pydot
from turing_complete_interface.circuit_compiler import build_gate
from turing_complete_interface.circuit_parser import Circuit, SCHEMATICS_PATH
from turing_complete_interface.circuit_viewer import view_circuit
from turing_complete_interface.from_logic_expression import from_logic_expression
from turing_complete_interface.from_truth_table import CompactTruthTableGenerator, Pattern, ComponentTemplate, SortPins, \
    FromGates, GatesByKind, CustomByName, FilterPins, Concatenate
from turing_complete_interface.truth_table import TruthTable, PoS, SoP, LUT, LUTVariable
from turing_complete_interface.level_layouts import LevelLayout, get_layout
from turing_complete_interface.logic_nodes import LogicNodeType
from turing_complete_interface.verilog_parser import parse_verilog, generate_verilog

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


def load_circuit(path: PathLike | str) -> Circuit:
    assert selected_level is not None
    circuit_file = SCHEMATICS_PATH / selected_level / path / "circuit.data"
    return Circuit.parse(circuit_file.read_bytes())


def logic_expression_to_node(expression: str) -> LogicNodeType:
    if selected_level is not None:
        name = selected_level[-1]
    else:
        name = "LogicExpr"
    return from_logic_expression(name, expression)


def verilog_to_node(verilog: str, module_name: _NameSources | str = USE_MODULE_NAME):
    return parse_verilog(verilog)


def node_to_verilog(node: LogicNodeType, top_module_name: str = None) -> str:
    return generate_verilog(node, top_module_name or node.name)


def node_to_circuit(node: LogicNodeType) -> Circuit:
    return build_circuit(node, level_layout.fixed_io or IOPosition.from_node(node), level_layout.new_space())


def node_to_circuit_pydot(node: LogicNodeType) -> Circuit:
    return layout_with_pydot(node, level_layout.fixed_io or IOPosition.from_node(node), level_layout.new_space())


def save_custom_component(circuit: Circuit, name: str):
    save_level(circuit, "component_factory", name)


@overload
def save_level(circuit: Circuit, save_name: str): ...


@overload
def save_level(circuit: Circuit, level_name: str, save_name: str): ...


def save_level(circuit: Circuit, level_name: str, save_name: str = None):
    if save_name is None:
        assert selected_level is not None
        level_name, save_name = selected_level, level_name
    s = circuit.to_bytes()
    path = (SCHEMATICS_PATH / level_name / save_name)
    path.mkdir(exist_ok=True, parents=True)
    (path / "circuit.data").write_bytes(s)


def layout_pos(arg: TruthTable | PoS | tuple[PoS, ...], use_buffer) -> Circuit:
    if isinstance(arg, TruthTable):
        arg = arg.to_poses()
    elif isinstance(arg, PoS):
        arg = arg,
    assert isinstance(arg, tuple) and all(isinstance(a, PoS) for a in arg), arg
    raise NotImplementedError


def layout_sop(arg: TruthTable | SoP | tuple[SoP, ...], use_buffer) -> Circuit:
    if isinstance(arg, TruthTable):
        arg = arg.to_sopes()
    elif isinstance(arg, SoP):
        arg = arg,
    assert isinstance(arg, tuple) and all(isinstance(a, SoP) for a in arg), arg
    raise NotImplementedError


def show_circuit(circuit: Circuit, no_simulation=False):
    view_circuit(circuit,
                 build_gate(selected_level or "main", circuit) if not no_simulation else None,
                 get_layout(selected_level).new_space())


def lut_from_bytes(raw: bytes, in_bits: int, out_bits: int):
    assert out_bits == 8, "Different out sizes not supported"
    lut = LUT((LUTVariable("address", in_bits),), (LUTVariable("out", out_bits),))
    for i, v in enumerate(raw):
        if i > 2 ** in_bits:
            break
        lut.set(i, v)
    return lut

