name: COUNTER_4

inputs: ?save, ?in[4]
outputs: out[4]

components: adder: ADDER_2W4, reg: REGISTER_4, _: CONST, mux: MUX_2W4

wires: {

    save -> mux.control,
    adder.out -> mux.a,
    in -> mux.b,

    _.true -> reg.save,
    mux.out -> reg.in,

    reg.out -> adder.a,
    _.true -> adder.carry_in,

    reg.out -> out

}