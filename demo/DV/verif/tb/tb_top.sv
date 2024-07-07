`include "uvm_macros.svh"
import uvm_pkg::*;   


module tb_top;

  adder u_adder();

  initial begin
    run_test();
  end

endmodule
