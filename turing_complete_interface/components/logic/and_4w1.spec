name: AND_4W1
inputs: a, b, c, d
outputs: out

components: {
    nand1: NAND_2W1,
    nand2: NAND_2W1,
    nand3: NAND_2W1,
    or: OR_1W4,
    not: NOT_1W1,
    _: CONST
}

wires: {
    a -> nand1.a,
    b -> nand1.b,
    b -> nand2.a,
    c -> nand2.b,
    c -> nand3.a,
    d -> nand3.b,
    nand1.out -> or.in[0],
    nand2.out -> or.in[1],
    nand3.out -> or.in[2],
    _.false -> or.in[3],
    or.out -> not.in,
    not.out -> out
}