name: ADDER_2W1

inputs: a, b, c
outputs: out, carry_out

components: half1: HALF_ADDER, half2: HALF_ADDER, or1: OR_2W1

wires: {
    a -> half1.a,
    b -> half1.b,

    half1.out -> half2.a,
    c -> half2.b,

    half1.carry_out -> or1.0,
    half2.carry_out -> or1.1,

    half2.out -> out,
    or1.out -> carry_out
}