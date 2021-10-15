name: XOR_2W8
inputs: a[8], b[8]
outputs: out[8]
components: xor_w1:XOR_2W4, xor2:XOR_2W4

wires: {
    a[0:4] -> xor_w1.a,
    b[0:4] -> xor_w1.b,
    xor_w1.out -> out[0:4],

    a[4:8] -> xor2.a,
    b[4:8] -> xor2.b,
    xor2.out -> out[4:8],
}