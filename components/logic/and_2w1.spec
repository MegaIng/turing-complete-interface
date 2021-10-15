name: AND_2W1
inputs: a, b
outputs: out

components: nand: NAND_2W1, not: NOT_1W1

wires: {
    a -> nand.a,
    b -> nand.b,
    nand.out -> not.in,
    not.out -> out
}