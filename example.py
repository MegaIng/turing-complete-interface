from turing_complete_interface.scripts import *


# l = logic_expression_to_node(open("less_than.txt").read())
l = logic_expression_to_node("(!A7&!A6&!A5&!A4&!A3&!A2&!A1&!A0)+(!A7&!A6&!A5&!A4&!A3&!A2&!A1&A0)+(!A7&!A6&!A5&!A4&!A3&!A2&A1&!A0)")

print(l.to_spec())
c = node_to_circuit(l)

save_custom_component(c, "test_circuit")
