name: COUNTER_8

inputs: save, ?in[4]
outputs: out[4]

components: adder: ADDER_2W8, reg: REGISTER_8, _: CONST, mux: MUX_2W8

wires: {

    save -> mux.control,
    adder.result -> mux.a,
    in -> mux.b,

    _.true -> reg.save,
    mux.out -> reg.in,

    reg.out -> adder.a,
    _.true -> adder.carry_in,

    reg.out -> out

}