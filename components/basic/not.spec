name: NOT1
inputs: in
outputs: out

components: nand: NAND1

wires: {
    in -> nand.a,
    in -> nand.b,
    nand.out -> out
}