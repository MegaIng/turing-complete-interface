name: XOR_2W16
inputs: a[16], b[16]
outputs: out[16]
components: xor_w1:XOR_2W4, xor2:XOR_2W4, xor3:XOR_2W4, xor4:XOR_2W4

wires: {
    a[0:4] -> xor_w1.a,
    b[0:4] -> xor_w1.b,
    xor_w1.out -> out[0:4],

    a[4:8] -> xor2.a,
    b[4:8] -> xor2.b,
    xor2.out -> out[4:8],

    a[8:12] -> xor3.a,
    b[8:12] -> xor3.b,
    xor3.out -> out[8:12],

    a[12:16] -> xor4.a,
    b[12:16] -> xor4.b,
    xor4.out -> out[12:16],
}