module adder
#(parameter DATA_WIDTH = 16)(
    input clk,
    input rst_n,
    input [DATA_WIDTH-1:0] a_in,
    input [DATA_WIDTH-1:0] b_in,
    output reg [DATA_WIDTH:0] out
  );
  reg [DATA_WIDTH-1:0] sum;
  always @(posedge clk or negedge rst_n)begin
    if(rst_n == 'd0)begin
      sum <= 'd0;
      out <= 'd0;
    end
    else begin
      sum <= a_in + b_in;
      out <= sum;
    end
  end
endmodule
