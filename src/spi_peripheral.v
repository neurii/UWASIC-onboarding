/*
 * Copyright (c) 2024 Hanna Park
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input wire clk, //system clock = 10MHz
    input wire rst_n,

    //input assignments for peripheral
    input wire sclk,
    input wire copi,
    input wire ncs,
    
    //five registers from the register map in section 2. about out design
    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);

// two ff synchronizers
reg sclk_ff1;
reg sclk_ff2;
reg copi_ff1;
reg copi_ff2;
reg ncs_ff1;
reg ncs_ff2;

// prev regs for edge detection
// sclk is edge sensitive + need ncs to detect start/end of transaction
reg sclk_prev;
reg ncs_prev;

wire sclk_posedge = sclk_ff2 && !sclk_prev;
wire sclk_negedge = !sclk_ff2 && sclk_prev;
wire ncs_posedge = ncs_ff2 && !ncs_prev;
wire ncs_negedge = !ncs_ff2 && ncs_prev;

//copi transaction
reg [15:0] msg; // RW 1 bit reg addr 7 bit data 8 bit
reg [4:0] bit_count;

// decode
wire rw_bit; // read write 1 bit
wire [6:0] addr; // addr 7 bits
wire [7:0] data; // data 8 bits

assign rw_bit = msg[15];
assign addr = msg[14:8];
assign data = msg[7:0];

assign is_valid;

assign is_valid = rw_bit && (addr <= 7'04) && (bit_count == 5'd16);

//reset logic??
//ff logic(clock) sequential -> non blocking
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin // reset
        en_reg_out_7_0 <= 8'h00;
        en_reg_out_15_8 <= 8'h00;
        en_reg_pwm_7_0 <= 8'h00;
        en_reg_pwm_15_8 <= 8'h00;
        pwm_duty_cycle <= 8'h00;

        // two ff synchronizers
        sclk_ff1 <= 1'b0;
        sclk_ff2 <= 1'b0;
        copi_ff1 <= 1'b0;
        copi_ff2 <= 1'b0;
        ncs_ff1 <= 1'b0;
        ncs_ff2 <= 1'b0;

        sclk_prev <= 1'b0;
        ncs_prev <= 1'b0;

        msg <= 16'h0000;
        bit_count <= 5'b0;

    end else begin // no reset
        sclk_ff1 <= sclk;
        sclk_ff2 <= sclk_ff1;
        copi_ff1 <= copi;
        copi_ff2 <= copi_ff1;
        ncs_ff1 <= ncs;
        ncs_ff2 <= ncs_ff1;

        sclk_prev <= sclk_ff2;
        ncs_prev <= ncs_ff2;

        //start of transaction
        if (ncs_negedge) begin
            msg <= 16'h0000;
            bit_count <= 5'b0;
        end else if (sclk_posedge) begin // rst is high nCS is low AND system clk is rising
            msg <= {msg[14:0], copi_ff2};
            bit_count <= bit_count + 5'd1;
        end else if (ncs_posedge) begin // during transaction
            if (is_valid) begin
                case (addr)
                    7'h00: en_reg_out_7_0 <= data;
                    7'h01: en_reg_out_15_8 <= data;
                    7'h02: en_reg_pwm_7_0 <= data;
                    7'h03: en_reg_pwm_15_8 <= data;
                    7'h04: pwm_duty_cycle <= data;

                endcase
            end
        end
    end
end

endmodule