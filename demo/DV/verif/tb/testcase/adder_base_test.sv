class adder_base_test extends uvm_test;
    
    `uvm_component_utils(adder_base_test)  
    
    /** Class Constructor */
    function new(string name = "adder_base_test", uvm_component parent=null);
        super.new(name,parent);
    endfunction: new

    virtual function void build_phase(uvm_phase phase);
        super.build_phase(phase);
    endfunction : build_phase

    virtual task main_phase(uvm_phase phase);
        super.main_phase(phase);
        `uvm_info(get_full_name(), "Main phase entered", UVM_LOW)
    endtask : main_phase

endclass
