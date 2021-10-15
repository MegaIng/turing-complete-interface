name: OR_2W4
inputs: a[4], b[4]
outputs: out[4]
components: or_w1:OR_2W1, or2:OR_2W1, or3:OR_2W1, or4:OR_2W1

wires: {
    a[0] -> or_w1.0,
    b[0] -> or_w1.1,
    or_w1.out -> out[0],

    a[1] -> or2.0,
    b[1] -> or2.1,
    or2.out -> out[1],

    a[2] -> or3.0,
    b[2] -> or3.1,
    or3.out -> out[2],

    a[3] -> or4.0,
    b[3] -> or4.1,
    or4.out -> out[3],
}