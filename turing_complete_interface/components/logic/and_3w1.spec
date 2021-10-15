name: AND_3W1
inputs: a, b, c
outputs: out

components: nand1: NAND_2W1, nand2: NAND_2W1, or: OR_2W1, not: NOT_1W1

wires: {
    a -> nand1.a,
    b -> nand1.b,
    a -> nand2.a,
    c -> nand2.b,
    nand1.out -> or.0,
    nand2.out -> or.1,
    or.out -> not.in,
    not.out -> out
}