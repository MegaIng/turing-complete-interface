name: ADDER_2W8

inputs: a[8], b[8], carry_in
outputs: out[8], carry_out

components: adder1: ADDER_2W4, adder2: ADDER_2W4, _: CONST

wires: {
    carry_in -> adder1.carry_in,
    adder1.carry_out -> adder2.carry_in,
    adder1.carry_out -> carry_out,

    a[0:4] -> adder1.a,
    b[0:4] -> adder1.b,
    adder1.out -> out[0:4],

    a[4:8] -> adder2.a,
    b[4:8] -> adder2.b,
    adder2.out -> out[4:8],
}