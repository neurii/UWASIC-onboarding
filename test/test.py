# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge # this!@!!!!!!!!!!!!!!
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)") # did i did this
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)") # range check in spi_peripheral needed
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # test if PWM freq is 3kHz, 3000 per sec, period = 1 / freq
    # period = second posedge - first posedge

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Write transaction, address 0x00, data 0x01") # uo_out[0] output enable
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Write transaction, address 0x02, data 0x01") # uo_out[0] PWM enable
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0x01") # pwm duty cycle
    await send_spi_transaction(dut, 1, 0x04, 0x80) # 50% duty cycle, max 256, 0x80 = 128
    await ClockCycles(dut.clk, 100)

    # find rising edge
    previous = int(dut.uo_out.value) & 1 # save uo_out[0] value
    first_rising_time = None

    for _ in range(5000):
        await RisingEdge(dut.clk)
        current = int(dut.uo_out.value) & 1

        if previous == 0 and current == 1:
            first_rising_time = cocotb.utils.get_sim_time(units="ns")
            break

        previous = current

    assert first_rising_time is not None, "DId not see first PWM rising edge"

    # find rising edge
    previous = int(dut.uo_out.value) & 1 # save uo_out[0] value
    second_rising_time = None

    for _ in range(5000):
        await RisingEdge(dut.clk)
        current = int(dut.uo_out.value) & 1

        if previous == 0 and current == 1:
            second_rising_time = cocotb.utils.get_sim_time(units="ns")
            break

        previous = current

    assert second_rising_time is not None, "DId not see first PWM rising edge"

    period_ns = second_rising_time - first_rising_time
    freq_hz = 1e9 / period_ns

    dut._log.info(f"PWM period: {period_ns} ns")
    dut._log.info(f"PWM freq: {freq_hz} Hz")

    assert 2970 <= freq_hz <= 3030, (
        f"Expected PWM frequncy between 2970 and 3030 Hz, got {freq_hz} Hz"
    )

    dut._log.info("PWM Frequency test completed successfully")

@cocotb.test()
async def test_pwm_duty(dut):
    # test if PWM freq is 3kHz, 3000 per sec, period = 1 / freq
    # period = second posedge - first posedge

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    ##################################
    # 0% duty cycle
    ##################################
    dut._log.info("Write transaction, address 0x00, data 0x01") # uo_out[0] output enable
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Write transaction, address 0x02, data 0x01") # uo_out[0] PWM enable
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0x01") # pwm duty cycle
    await send_spi_transaction(dut, 1, 0x04, 0x00) # 0%
    await ClockCycles(dut.clk, 100)

    await ClockCycles(dut.clk, 30000)

    uo_out_0 = int(dut.uo_out.value) & 1
    assert uo_out_0 == 0, (
        f"Expected uo_out[0] to stay low for 0% duty, got {uo_out_0}"
    )

    ##################################
    # 50% duty cycle
    ##################################
    dut._log.info("Write transaction, address 0x04, data 0x01") # pwm duty cycle
    await send_spi_transaction(dut, 1, 0x04, 0x80) # 50%
    await ClockCycles(dut.clk, 100)

    # find rising edge
    previous = int(dut.uo_out.value) & 1 # save uo_out[0] value
    rising_time = None

    for _ in range(5000):
        await RisingEdge(dut.clk)
        current = int(dut.uo_out.value) & 1

        if previous == 0 and current == 1:
            rising_time = cocotb.utils.get_sim_time(units="ns")
            break

        previous = current

    assert rising_time is not None, "DId not see 50 percent rising edge"

    # find falling edge
    previous = int(dut.uo_out.value) & 1 # save uo_out[0] value
    falling_time = None

    for _ in range(5000):
        await RisingEdge(dut.clk)
        current = int(dut.uo_out.value) & 1

        if previous == 1 and current == 0:
            falling_time = cocotb.utils.get_sim_time(units="ns")
            break

        previous = current

    assert falling_time is not None, "DId not see 50 percent falling edge"


    # find next rising edge
    previous = int(dut.uo_out.value) & 1 # save uo_out[0] value
    next_rising_time = None

    for _ in range(5000):
        await RisingEdge(dut.clk)
        current = int(dut.uo_out.value) & 1

        if previous == 0 and current == 1:
            next_rising_time = cocotb.utils.get_sim_time(units="ns")
            break

        previous = current

    assert next_rising_time is not None, "DId not see 50 percent next rising edge"

    high_time_ns = falling_time - rising_time
    period_ns = next_rising_time - rising_time
    freq_hz = 1e9 / period_ns
    measured_duty = high_time_ns / period_ns

    expected_duty = 1 / 2 # 128 /256 50%

    dut._log.info(f"high time: {high_time_ns} Hz")
    dut._log.info(f"PWM period: {period_ns} ns")
    dut._log.info(f"PWM freq: {freq_hz} Hz")

    assert abs(measured_duty - expected_duty) <= 0.01, (
        f"Expected duty around {expected_duty * 100}%, got {measured_duty * 100}%"
    )

    ##################################
    # 100% duty cycle
    ##################################
    dut._log.info("Write transaction, address 0x04, data 0x01") # pwm duty cycle
    await send_spi_transaction(dut, 1, 0x04, 0xFF) # 0%
    await ClockCycles(dut.clk, 100)

    await ClockCycles(dut.clk, 30000)

    uo_out_0 = int(dut.uo_out.value) & 1
    assert uo_out_0 == 1, (
        f"Expected uo_out[0] to stay high for 100% duty, got {uo_out_0}"
    )



    dut._log.info("PWM Duty Cycle test completed successfully")
