name: OR_2W16
inputs: a[16], b[16]
outputs: out[16]
components: or_w1:OR_2W4, or2:OR_2W4, or3:OR_2W4, or4:OR_2W4

wires: {
    a[0:4] -> or_w1.a,
    b[0:4] -> or_w1.b,
    or_w1.out -> out[0:4],

    a[4:8] -> or2.a,
    b[4:8] -> or2.b,
    or2.out -> out[4:8],

    a[8:12] -> or3.a,
    b[8:12] -> or3.b,
    or3.out -> out[8:12],

    a[12:16] -> or4.a,
    b[12:16] -> or4.b,
    or4.out -> out[12:16],
}