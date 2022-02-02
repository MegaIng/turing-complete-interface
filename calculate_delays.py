from pathlib import Path

from turing_complete_interface.logic_nodes import CombinedLogicNode
from turing_complete_interface.scripts import *

select_level("architecture")

lut_circuit = load_circuit("ASIC/HilbertFullLut")
other_circuit = load_circuit("ASIC/hilbert")

lut_node = circuit_to_node(lut_circuit, "LUT")
other_node = circuit_to_node(other_circuit, "Other")

# show_circuit(lut_circuit, True)
# show_circuit(other_circuit, True)

def calculate_delay(node: CombinedLogicNode) -> int:
    known_delays = {}
    for layer in node.execution_order:
        for action in layer:
            current = node.nodes[action.node]
            current.inputs
            non_delayed = {i: p for i, p in current.inputs.items() if not p.delayed}
            
