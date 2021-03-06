name: BYTE_LESS_U

inputs: 1[8], 2[8]
outputs: 3

components: {
    4: TC_BYTE_SPLITTER,
    5: TC_BYTE_SPLITTER,
    6: XOR_2W1,
    7: AND_2W1,
    8: NOT_1W1,
    9: NOT_1W1,
    13: NOT_1W1,
    10: XOR_2W1,
    12: NOT_1W1,
    14: AND_3W1,
    16: NOT_1W1,
    15: XOR_2W1,
    17: NOT_1W1,
    18: AND_3W1,
    39: AND_2W1,
    43: AND_3W1,
    44: AND_2W1,
    41: XOR_2W1,
    40: NOT_1W1,
    42: NOT_1W1,
    48: AND_3W1,
    45: NOT_1W1,
    47: NOT_1W1,
    46: XOR_2W1,
    49: AND_2W1,
    54: AND_2W1,
    53: AND_3W1,
    51: XOR_2W1,
    52: NOT_1W1,
    50: NOT_1W1,
    58: AND_3W1,
    56: XOR_2W1,
    59: AND_2W1,
    57: NOT_1W1,
    55: NOT_1W1,
    60: NOT_1W1,
    64: AND_2W1,
    63: AND_3W1,
    61: XOR_2W1,
    62: NOT_1W1,
    OR40: OR_8W1
}

wires: {
    1 -> 4.in,
    2 -> 5.in,
    7.out -> OR40.0,
    14.out -> OR40.1,
    18.out -> OR40.2,
    43.out -> OR40.3,
    48.out -> OR40.4,
    53.out -> OR40.5,
    58.out -> OR40.6,
    63.out -> OR40.7,
    OR40.out -> 3,
    4.r0 -> 60.in,
    4.r0 -> 61.b,
    4.r1 -> 56.b,
    4.r1 -> 55.in,
    4.r2 -> 51.b,
    4.r2 -> 50.in,
    4.r3 -> 45.in,
    4.r3 -> 46.b,
    4.r4 -> 41.b,
    4.r4 -> 40.in,
    4.r5 -> 16.in,
    4.r5 -> 15.b,
    4.r6 -> 10.b,
    4.r6 -> 12.in,
    4.r7 -> 6.b,
    4.r7 -> 8.in,
    5.r0 -> 61.a,
    5.r1 -> 56.a,
    5.r2 -> 51.a,
    5.r3 -> 46.a,
    5.r4 -> 41.a,
    5.r5 -> 15.a,
    5.r6 -> 10.a,
    5.r7 -> 6.a,
    6.out -> 7.a,
    6.out -> 9.in,
    8.out -> 7.b,
    9.out -> 14.b,
    9.out -> 39.a,
    10.out -> 13.in,
    10.out -> 14.a,
    13.out -> 39.b,
    12.out -> 14.c,
    16.out -> 18.c,
    15.out -> 17.in,
    15.out -> 18.a,
    17.out -> 44.b,
    39.out -> 18.b,
    39.out -> 44.a,
    41.out -> 43.a,
    41.out -> 42.in,
    44.out -> 43.b,
    44.out -> 49.a,
    40.out -> 43.c,
    42.out -> 49.b,
    46.out -> 48.a,
    46.out -> 47.in,
    49.out -> 48.b,
    49.out -> 54.a,
    45.out -> 48.c,
    47.out -> 54.b,
    54.out -> 53.b,
    54.out -> 59.a,
    51.out -> 53.a,
    51.out -> 52.in,
    50.out -> 53.c,
    52.out -> 59.b,
    56.out -> 58.a,
    56.out -> 57.in,
    59.out -> 58.b,
    59.out -> 64.a,
    55.out -> 58.c,
    57.out -> 64.b,
    60.out -> 63.c,
    64.out -> 63.b,
    61.out -> 63.a,
    61.out -> 62.in
}
