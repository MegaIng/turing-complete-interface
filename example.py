from turing_complete_interface.scripts import *


l = logic_expression_to_node(open("less_than.txt").read())

print(l.to_spec())
c = node_to_circuit(l)

save_custom_component(c, "test_circuit")
