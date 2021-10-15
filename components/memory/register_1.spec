name: REGISTER_1

inputs: save, ?in
outputs: out

components: and_a: AND_2W1, and_b: AND_2W1, not: NOT_1W1, latch: SR_LATCH

wires: {
    save -> and_a.a,
    save -> and_b.a,

    in -> not.in,
    not.out -> and_a.b,
    in -> and_b.b,

    and_a.out -> latch.write_neg,
    and_b.out -> latch.write_pos,

    latch.pos -> out
}