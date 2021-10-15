name: TC_BYTE_EQUAL

inputs: 1[8], 2[8]
outputs: 3

components: {
    4: XNOR_2W1,
    9: XNOR_2W1,
    10: XNOR_2W1,
    11: XNOR_2W1,
    12: XNOR_2W1,
    13: XNOR_2W1,
    14: XNOR_2W1,
    15: XNOR_2W1,
    18: TC_BYTE_SPLITTER,
    19: TC_BYTE_SPLITTER,
    20: NAND_2W1,
    21: NOT_1W1,
    22: NAND_2W1,
    23: NAND_2W1,
    24: NAND_2W1,
    25: NAND_2W1,
    26: NAND_2W1,
    27: NAND_2W1,
    OR18: OR_7W1
}

wires: {
    1 -> 18.in,
    2 -> 19.in,
    21.out -> 3,
    19.r0 -> 4.a,
    18.r0 -> 4.b,
    4.out -> 20.b,
    19.r1 -> 9.a,
    18.r1 -> 9.b,
    9.out -> 20.a,
    9.out -> 22.b,
    19.r2 -> 10.a,
    18.r2 -> 10.b,
    10.out -> 22.a,
    10.out -> 23.b,
    19.r3 -> 11.a,
    18.r3 -> 11.b,
    11.out -> 23.a,
    11.out -> 24.b,
    19.r4 -> 12.a,
    18.r4 -> 12.b,
    12.out -> 24.a,
    12.out -> 25.b,
    19.r5 -> 13.a,
    18.r5 -> 13.b,
    13.out -> 25.a,
    13.out -> 26.b,
    19.r6 -> 14.a,
    18.r6 -> 14.b,
    14.out -> 26.a,
    14.out -> 27.b,
    19.r7 -> 15.a,
    18.r7 -> 15.b,
    15.out -> 27.a,
    20.out -> OR18.0,
    22.out -> OR18.1,
    23.out -> OR18.2,
    24.out -> OR18.3,
    25.out -> OR18.4,
    26.out -> OR18.5,
    27.out -> OR18.6,
    OR18.out -> 21.in}