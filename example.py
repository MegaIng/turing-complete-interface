from turing_complete_interface.scripts import *

l = logic_expression_to_node("(A1&!A0) | (!A1&A0)")
# l = logic_expression_to_node("""
# Q7 = (A7&!A6&!A5&!A4&!A3&!A2&!A1&!A0) | (!A7&A0) | (!A7&A1) | (!A7&A2) | (!A7&A3) | (!A7&A4) | (!A7&A6) | (!A7&A5)
# Q6 = (A6&!A5&!A4&!A3&!A2&!A1&!A0) | (!A6&A0) | (!A6&A1) | (!A6&A2) | (!A6&A3) | (!A6&A4) | (!A6&A5)
# Q5 = (A5&!A4&!A3&!A2&!A1&!A0) | (!A5&A0) | (!A5&A1) | (!A5&A2) | (!A5&A4) | (!A5&A3)
# Q4 = (A4&!A3&!A2&!A1&!A0) | (!A4&A0) | (!A4&A1) | (!A4&A2) | (!A4&A3)
# Q3 = (A3&!A2&!A1&!A0) | (!A3&A0) | (!A3&A2) | (!A3&A1)
# Q2 = (A2&!A1&!A0) | (!A2&A1) | (!A2&A0)
# Q1 = (A1&!A0) | (!A1&A0)
# Q0 = (A0)
# """)
# tt = TruthTable.from_function(("A", "B", "C"), ("R", "C"),
#                               lambda a, b, c: ((a+b+c)!=0, (a+b+c)==0)
#                               )
#
# print(tt, end='\n\n')
# print(*tt.to_sopes(), sep='\n', end='\n\n')
# print(*tt.to_poses(), sep='\n', end='\n\n')
# layout_pos(tt, use_buffer=True)
c = node_to_circuit_pydot(l)
#
save_custom_component(c, "test_circuit")
