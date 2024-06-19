import json
import sched
import struct
import time

import requests
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

#from widgetlords.pi_spi import *

# Variables
inverter_ids = ['meter2', 'meter3', 'meter4']
modbus_tcp_ip = '192.168.0.27'
min_power = -1200
max_power = 1200
max_dac = 3723
min_dac = 745


# ModbusUtils class
class ModbusUtils:
    _instance = None

    def __new__(cls, modbus_tcp_ip):
        if cls._instance is None:
            cls._instance = super(ModbusUtils, cls).__new__(cls)
            cls._instance.client = ModbusTcpClient(modbus_tcp_ip)
        return cls._instance

    def _init_(self, modbus_tcp_ip):
        # Initialisiere deine Modbus-Verbindung hier
        self.client = ModbusTcpClient(modbus_tcp_ip)

    def read_coils(self, address, count=1, unit=5):
        try:
            response = self.client.read_coils(address, count, unit=unit)
            if response.isError():
                raise ModbusException(f"Error reading coils at address {address}")
            return response.bits
        except ModbusException as e:
            log_message(f"Modbus exception: {e}")
            return None

    def write_register(self, address, value, unit=5):
        try:
            response = self.client.write_register(address, value, unit=unit)
            if response.isError():
                raise ModbusException(f"Error writing register at address {address}")
            return response
        except ModbusException as e:
            log_message(f"Modbus exception: {e}")
            return None

    def write_32bit_register(self, address, value, unit=5):
        try:
            # Konvertiere den Float-Wert zu UInt16-Array
            uint16_array = self.convert_float_to_uint16_array(value)

            # Schreibe die beiden UInt16-Werte in die entsprechenden Register
            response_high = self.client.write_register(address, uint16_array[0], unit=unit)
            response_low = self.client.write_register(address + 1, uint16_array[1], unit=unit)

            if response_high.isError() or response_low.isError():
                raise ModbusException(f"Error writing 32-bit value at address {address}")

            return (response_high, response_low)

        except ModbusException as e:
            log_message(f"Modbus exception: {e}")
            return None

    def convert_float_to_uint16_array(self, float_value):
        # Konvertiere den Float-Wert in eine 4-Byte-Darstellung (Big-Endian)
        buffer = struct.pack('>f', float_value)

        # Extrahiere die ersten zwei UInt16-Werte aus dem Puffer (Big-Endian)
        uint16_value1 = struct.unpack('>H', buffer[0:2])[0]
        uint16_value2 = struct.unpack('>H', buffer[2:4])[0]

        return [uint16_value1, uint16_value2]

    def close(self):
        self.client.close()


def get_current_power(inverter_id):
    try:
        url = f'http://x:admin@{modbus_tcp_ip}:8084/rest/channel/{inverter_id}/ActivePower'
        response = requests.get(url)
        response_dict = response.json()
        return response_dict['value']
    except Exception as e:
        log_message(f"Error getting current power: {e}")
        return None


def get_peak_power(inverter_id):
    try:
        url = f'http://x:admin@{modbus_tcp_ip}:8084/rest/channel/{inverter_id}/MaxApparentPower'
        response = requests.get(url)
        response_dict = response.json()
        return response_dict['value']
    except Exception as e:
        log_message(f"Error getting peak power: {e}")
        return None


def write_channel_value(inverter_id, channel, value):
    try:
        url = f'http://x:admin@{modbus_tcp_ip}:8084/rest/channel/{inverter_id}/{channel}'
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({'value': value})
        response = requests.post(url, headers=headers, data=payload, auth=('admin', 'x'))

        if response.status_code == 200:
            response_dict = response.json()
            return response_dict['value']
        else:
            log_message(f"Error updating channel value: {response.text}")
            return None

    except Exception as e:
        log_message(f"Error updating channel value: {e}")
    return None


# Municipal utilities functions
def calculate_dac_value(power):
    if power is None:
        log_message("Error: Power is None")
        return None
    dac = min_dac + ((max_dac - min_dac) / (max_power - min_power)) * (power - min_power)
    return round(dac, 1)


def write_output(dac_value):
    try:
        if dac_value is not None:
            #outputs.write_single(0, dac_value)
            time.sleep(0.1)
        else:
            log_message("Error: DAC value is None")
    except Exception as e:
        log_message(f"Error writing output: {e}")


# Main functions
def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_message(f"[{timestamp}] {message}")


def regulate_direktvermarkter():
    polling_activation_list = read_coils(12)
    if isinstance(polling_activation_list, list) and len(polling_activation_list) > 0:
        polling_activation = bool(polling_activation_list[0])
    else:
        raise ValueError("Invalid set point specification value")

    log_message('Polling activation: ' + str(polling_activation))

    if polling_activation:
        log_message('Start regulation of inverters: ' + str(inverter_ids))
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

    for inverter_id in inverter_ids:
        current_power = get_current_power(inverter_id)
        log_message(inverter_id + ' active_power: ' + str(current_power))
        total_power += current_power

    return total_power / 1000


def retrieve_total_peak_power():
    total_power = 0

    for inverter_id in inverter_ids:
        current_power = get_peak_power(inverter_id)
        log_message(inverter_id + ' peak_power: ' + str(current_power))
        total_power += current_power

    return total_power


def write_modbus_32bit_register(total_power):
    modbus = ModbusUtils()
    try:
        response = modbus.write_32bit_register(0, total_power)
        log_message(f"Write Response: {response}")
    finally:
        modbus.close()


def read_coils(address):
    modbus = ModbusUtils()
    try:
        response = modbus.read_coils(int(address))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()


def read_input_modbus_register(register):
    modbus = ModbusUtils()
    try:
        response = modbus.read_input_registers(int(register))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()


def read_holding_modbus_register(register):
    modbus = ModbusUtils()
    try:
        response = modbus.read_holding_registers(int(register))  # Sicherstellen, dass die Adresse eine ganze Zahl ist
        return response
    finally:
        modbus.close()


def do_regulation(regulation_factor, dry_run):
    for inverter_id in inverter_ids:
        peak_power = get_peak_power(inverter_id)
        value_to_write = regulation_factor * peak_power
        if dry_run:
            log_message('Dry RUN: Value would be: ' + str(value_to_write))
        else:
            write_channel_value(inverter_id, 'SetActivePower', value_to_write)


# Main execution
if __name__ == '__main__':
    #init()
    #outputs = Mod2AO()
    scheduler = sched.scheduler(time.time, time.sleep)
    scheduler.enter(0, 1, main)
    scheduler.enter(0, 1, regulate_direktvermarkter)
    scheduler.run()