from turing_complete_interface.scripts import *

l = logic_expression_to_node(
    "(!A7&!A6&!A5&!A4&!A3&!A2&!A1&!A0)+(!A7&!A6&!A5&!A4&!A3&!A2&!A1&A0)+(!A7&!A6&!A5&!A4&!A3&!A2&A1&!A0)")

c = node_to_circuit_pydot(l)

save_custom_component(c, "test_circuit")
