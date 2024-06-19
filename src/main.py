import sched
import time

import openems_api_client
import variables
# import municipal_utilities
from modbus_utilities import ModbusUtils

scheduler = sched.scheduler(time.time, time.sleep)

def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] {message}")

def regulate_direktvermarkter():
    polling_activation_list = read_coils(12)
    if isinstance(polling_activation_list, list) and len(polling_activation_list) > 0:
        polling_activation = bool(polling_activation_list[0])
    else:
        raise ValueError("Invalid set point specification value")

    log_message('Polling activation: ' + str(polling_activation))

    if polling_activation:
        log_message('Start regulation of inverters: ' + str(variables.inverter_ids))
        total_peak_power = retrieve_total_peak_power()
        log_message('total_peak_power: ' + str(total_peak_power))
        set_point_specification = read_holding_modbus_register(10)
        log_message('Set point specification: ' + str(set_point_specification))

        # Sicherstellen, dass set_point_specification eine Liste ist und ein Element enthält
        if isinstance(set_point_specification, list) and len(set_point_specification) > 0:
            set_point_value = set_point_specification[0]
        else:
            raise ValueError("Invalid set point specification value")

        regulate_factor = set_point_value / total_peak_power
        log_message('Using regulate factor: ' + str(regulate_factor) + ' for every inverter.')
        do_regulation(regulate_factor, True)

    scheduler.enter(3, 1, regulate_direktvermarkter)  # Schedule the next call in 5 seconds

def main():
    total_power = retrieve_active_power()
    log_message('total_power: ' + str(total_power))

    # Sent 4-20 mA Signal
 #   municipal_utilities.write_output(municipal_utilities.calculate_dac_value(total_power))
    # Write Modbus TCP Register
    write_modbus_32bit_register(total_power)
    scheduler.enter(5, 1, main)  # Schedule the next call in 5 seconds

def retrieve_active_power():
    total_power = 0

    for inverter_id in variables.inverter_ids:
        current_power = openems_api_client.get_current_power(inverter_id)
        log_message(inverter_id + ' active_power: ' + str(current_power))
        total_power += current_power

    return total_power / 1000

def retrieve_total_peak_power():
    total_power = 0

    for inverter_id in variables.inverter_ids:
        current_power = openems_api_client.get_peak_power(inverter_id)
        log_message(inverter_id + ' peak_power: ' + str(current_power))
        total_power += current_power

    return total_power

def write_modbus_32bit_register(total_power):
    modbus = ModbusUtils(variables.modbus_tcp_ip)
    try:
        response = modbus.write_32bit_register(0, total_power)
        log_message(f"Write Response: {response}")
    finally:
        modbus.close()

def read_coils(address):
    modbus = ModbusUtils(variables.modbus_tcp_ip)
    try:
        response = modbus.read_coils(int(address))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()

def read_input_modbus_register(register):
    modbus = ModbusUtils(variables.modbus_tcp_ip)
    try:
        response = modbus.read_input_registers(int(register))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()

def read_holding_modbus_register(register):
    modbus = ModbusUtils(variables.modbus_tcp_ip)
    try:
        response = modbus.read_holding_registers(int(register))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()

def do_regulation(regulation_factor, dry_run):
    for inverter_id in variables.inverter_ids:
        peak_power = openems_api_client.get_peak_power(inverter_id)
        value_to_write = regulation_factor * peak_power
        if dry_run:
            log_message('Dry RUN: Value would be: ' + str(value_to_write))
        else:
            openems_api_client.write_channel_value(inverter_id, 'SetActivePower', value_to_write)

if __name__ == '__main__':
    scheduler.enter(0, 1, main)
    scheduler.enter(0, 1, regulate_direktvermarkter)
    scheduler.run()
