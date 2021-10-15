name: MUX_2W4

inputs: control, a[4], b[4]

outputs: out[4]

components: switch_a: SWITCH_1W4, switch_b: SWITCH_1W4, not: NOT_1W1, or: OR_2W4

wires: {
    control -> not.in, not.out -> switch_a.control,
    control -> switch_b.control,

    a -> switch_a.in,
    b -> switch_b.in,

    switch_a.out -> or.a,
    switch_b.out -> or.b,

    or.out -> out
}