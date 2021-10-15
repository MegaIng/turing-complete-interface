name: NOR_2W1
inputs: a, b
outputs: out

components: nand: NAND_2W1, a_not: NOT_1W1, b_not: NOT_1W1, r_not: NOT_1W1

wires: {
    a -> a_not.in,
    b -> b_not.in,
    a_not.out -> nand.a,
    b_not.out -> nand.b,
    nand.out -> r_not.in,
    r_not.out -> out,
}