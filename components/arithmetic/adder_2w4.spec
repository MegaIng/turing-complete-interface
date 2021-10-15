name: ADDER_2W4

inputs: a[4], b[4], carry_in
outputs: result[4], carry_out

components: adder1: ADDER_2W1, adder2: ADDER_2W1, adder3: ADDER_2W1, adder4: ADDER_2W1

wires: {
    carry_in -> adder1.c,
    adder1.carry_out -> adder2.c,
    adder2.carry_out -> adder3.c,
    adder3.carry_out -> adder4.c,
    adder4.carry_out -> carry_out,

    a[0] -> adder1.a,
    b[0] -> adder1.b,
    adder1.result -> result[0],

    a[1] -> adder2.a,
    b[1] -> adder2.b,
    adder2.result -> result[1],

    a[2] -> adder3.a,
    b[2] -> adder3.b,
    adder3.result -> result[2],

    a[3] -> adder4.a,
    b[3] -> adder4.b,
    adder4.result -> result[3],

}