name: TC_PADDER

inputs: single
outputs: byte[8]

components: _: CONST

wires: {
    single -> byte[0],
    _.false -> byte[1],
    _.false -> byte[2],
    _.false -> byte[3],
    _.false -> byte[4],
    _.false -> byte[5],
    _.false -> byte[6],
    _.false -> byte[7],
}