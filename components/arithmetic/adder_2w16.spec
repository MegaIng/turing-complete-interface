name: ADDER_2W16

inputs: a[16], b[16], carry_in
outputs: result[16], carry_out

components: adder1: ADDER_2W4, adder2: ADDER_2W4, adder3: ADDER_2W4, adder4: ADDER_2W4

wires: {
    carry_in -> adder1.carry_in,
    adder1.carry_out -> adder2.carry_in,
    adder2.carry_out -> adder3.carry_in,
    adder3.carry_out -> adder4.carry_in,
    adder4.carry_out -> carry_out,

    a[0:4] -> adder1.a,
    b[0:4] -> adder1.b,
    adder1.result -> result[0:4],

    a[4:8] -> adder2.a,
    b[4:8] -> adder2.b,
    adder2.result -> result[4:8],

    a[8:12] -> adder3.a,
    b[8:12] -> adder3.b,
    adder3.result -> result[8:12],

    a[12:16] -> adder4.a,
    b[12:16] -> adder4.b,
    adder4.result -> result[12:16],

}