import sched
import time

import openems_api_client
import variables
from common import municipal_utilities
from modbus_utilities import ModbusUtils

scheduler = sched.scheduler(time.time, time.sleep)


def regulate_direktvermarkter():
    polling_activation = read_input_modbus_register(12.0)
    print('Polling activation: ' + str(polling_activation))
    if polling_activation:
        print('Start regulation of inverters: ' + str(variables.inverter_ids))
        total_peak_power = retrieve_total_peak_power()
        print('total_peak_power: ' + str(total_peak_power))
        set_point_specification = read_holding_modbus_register(10)
        print('Set point specification: ' + str(set_point_specification))
        regulate_factor = set_point_specification / total_peak_power
        print('Using regulate factor: ' + str(regulate_factor) + ' for every inverter.')
        do_regulation(regulate_factor, True)


scheduler.enter(3, 1, regulate_direktvermarkter)  # Schedule the next call in 5 seconds


def main():
    total_power = retrieve_active_power()
    print('total_power: ' + str(total_power))

    # Sent 4-20 mA Signal
    municipal_utilities.write_output(municipal_utilities.calculate_dac_value(total_power))
    # Write Modbus TCP Register
    write_modbus_register(total_power)
    scheduler.enter(5, 1, main)  # Schedule the next call in 5 seconds


def retrieve_active_power():
    total_power = 0

    for inverter_id in variables.inverter_ids:
        current_power = openems_api_client.get_current_power(inverter_id)
        print(inverter_id + ' active_power: ' + str(current_power))
        total_power += current_power

    return total_power


def retrieve_total_peak_power():
    total_power = 0

    for inverter_id in variables.inverter_ids:
        current_power = openems_api_client.get_peak_power(inverter_id)
        print(inverter_id + ' active_power: ' + str(current_power))
        total_power += current_power

    return total_power


def write_modbus_register(total_power):
    modbus = ModbusUtils(variables.modbus_tcp_ip)

    try:
        response = modbus.write_register(0, total_power)
        print(f"Write Response: {response}")
    finally:
        modbus.close()


def read_input_modbus_register(register):
    modbus = ModbusUtils(variables.modbus_tcp_ip)

    try:
        response = modbus.read_input_registers(register)
        return response
    finally:
        modbus.close()


def read_holding_modbus_register(register):
    modbus = ModbusUtils(variables.modbus_tcp_ip)

    try:
        response = modbus.read_holding_registers(register)
        return response
    finally:
        modbus.close()


def do_regulation(regulation_factor, dry_run):
    for inverter_id in variables.inverter_ids:
        peak_power = openems_api_client.get_peak_power(inverter_id)
        value_to_write = regulation_factor * peak_power
        if dry_run:
            print('Dry RUN: Value would be: ' + value_to_write)
        else:
            openems_api_client.write_channel_value(inverter_id, 'SetActivePower', value_to_write)


if __name__ == '__main__':
    scheduler.enter(0, 1, main)
    scheduler.enter(0, 1, regulate_direktvermarkter)
    scheduler.run()
