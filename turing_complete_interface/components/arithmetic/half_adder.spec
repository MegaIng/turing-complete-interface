name: HALF_ADDER

inputs: a, b
outputs: result, carry_out


components: nand1: NAND_2W1, nand2: NAND_2W1,  nand3: NAND_2W1, nand4: NAND_2W1, not: NOT_1W1

wires: {
    a -> nand1.a,
    b -> nand1.b,
    nand1.out -> nand2.b,
    nand1.out -> nand3.a,
    a -> nand2.a,
    b -> nand3.b,

    nand2.out -> nand4.a,
    nand3.out -> nand4.b,
    nand4.out -> result,

    nand1.out -> not.in,
    not.out -> carry_out
}