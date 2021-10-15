name: NOT_1W1
inputs: in
outputs: out

components: nand: NAND_2W1

wires: {
    in -> nand.a,
    in -> nand.b,
    nand.out -> out
}