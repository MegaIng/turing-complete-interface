name: COUNTER_8

inputs: ?save, ?in[8]
outputs: out[8]

components: adder: ADDER_2W8, reg: REGISTER_8, _: CONST, mux: MUX_2W8

wires: {

    save -> mux.control,
    adder.out -> mux.a,
    in -> mux.b,

    _.true -> reg.save,
    mux.out -> reg.value,

    reg.out -> adder.a,
    _.true -> adder.carry_in,
    _.false -> adder.b[0],
    _.false -> adder.b[1],
    _.false -> adder.b[2],
    _.false -> adder.b[3],
    _.false -> adder.b[4],
    _.false -> adder.b[5],
    _.false -> adder.b[6],
    _.false -> adder.b[7],

    reg.out -> out

}