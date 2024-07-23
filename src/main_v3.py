import os
import json
import sched
import struct
import time
import subprocess

import requests
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
from widgetlords.pi_spi import *

# Variablen
inverter_ids = [
    {
        "id": "meter2",
        "type": "OPENEMS"
    },
    {
        "id": "meter3",
        "type": "OPENEMS"
    },
    {
        "id": "meter4",
        "type": "OPENEMS"
    },
    {
        "id": "192.168.0.221",
        "type": "REFU"
    },
    {
        "id": "192.168.0.222",
        "type": "REFU"
    },
    {
        "id": "192.168.0.223",
        "type": "REFU"
    },
    {
        "id": "192.168.0.224",
        "type": "REFU"
    },
    {
        "id": "192.168.0.225",
        "type": "REFU"
    },
    {
        "id": "192.168.0.226",
        "type": "REFU"
    },
    {
        "id": "192.168.0.227",
        "type": "REFU"
    },
    {
        "id": "192.168.0.228",
        "type": "REFU"
    },
    {
        "id": "192.168.0.229",
        "type": "REFU"
    },
    {
        "id": "192.168.0.230",
        "type": "REFU"
    },
    {
        "id": "192.168.0.231",
        "type": "REFU"
    },
    {
        "id": "192.168.0.232",
        "type": "REFU"
    },
    {
        "id": "192.168.0.233",
        "type": "REFU"
    },
    {
        "id": "192.168.0.234",
        "type": "REFU"
    },
    {
        "id": "192.168.0.235",
        "type": "REFU"
    },
    {
        "id": "192.168.0.236",
        "type": "REFU"
    },
    {
        "id": "192.168.0.237",
        "type": "REFU"
    },
    {
        "id": "192.168.0.238",
        "type": "REFU"
    },
    {
        "id": "192.168.0.239",
        "type": "REFU"
    },
    {
        "id": "192.168.0.240",
        "type": "REFU"
    },
    {
        "id": "192.168.0.241",
        "type": "REFU"
    },
    {
        "id": "192.168.0.242",
        "type": "REFU"
    },
    {
        "id": "192.168.0.243",
        "type": "REFU"
    },
    {
        "id": "192.168.0.244",
        "type": "REFU"
    },
    {
        "id": "192.168.0.245",
        "type": "REFU"
    },
    {
        "id": "192.168.0.246",
        "type": "REFU"
    },
    {
        "id": "192.168.0.247",
        "type": "REFU"
    },
    {
        "id": "192.168.0.248",
        "type": "REFU"
    },
    {
        "id": "192.168.0.249",
        "type": "REFU"
    }
]

modbus_tcp_ip = '192.168.0.27'
min_power = -1200
max_power = 1200
max_dac = 3723
min_dac = 745

# ModbusUtils Klasse
class ModbusUtils:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModbusUtils, cls).__new__(cls)
            cls._instance.client = ModbusTcpClient(modbus_tcp_ip)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'client'):
            self.client = ModbusTcpClient(modbus_tcp_ip)

    def read_coils(self, address, count=1, slave=5):
        try:
            response = self.client.read_coils(address, count, slave=slave)
            if response.isError():
                raise ModbusException(f"Error reading coils at address {address}")
            return response.bits
        except ModbusException as e:
            log_message(f"Modbus exception: {e}")
            return None

    def write_input_register(self, address, value, slave=5):
        try:
            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.add_32bit_float(value)
            payload = builder.build()
            response = self.client.write_registers(address, payload, skip_encode=True, slave=slave)
            if response.isError():
                raise ModbusException(f"Error writing input register at address {address}")
            return response
        except ModbusException as e:
            log_message(f"Modbus exception: {e}")
            return None

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

def is_reachable(ip_address):
    try:
        process = subprocess.Popen(['ping', '-c', '1', ip_address], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            return True
        else:
            log_message(f"Erreichbarkeitstest fehlgeschlagen: {stderr.decode('utf-8').strip()}")
    except Exception as e:
        log_message(f"Fehler beim Erreichbarkeitstest: {str(e)}")
    return False

def get_current_power_refu(inverter_id):
    if not is_reachable(inverter_id):
        log_message(f"Inverter {inverter_id} is not reachable.")
        return 0

    try:
        for _ in range(10):  # 10 Retries
            try:
                process = subprocess.Popen(f'socat - TCP4:{inverter_id}:21063', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=b'REFU.GetParameter 1106\n')
                stderr_output = stderr.decode('utf-8').strip()
                stdout_output = stdout.decode('utf-8').strip()
                
                if process.returncode == 0 and not stderr_output and stdout_output:
                    try:
                        power_value = int(float(stdout_output))
                        return power_value
                    except ValueError:
                        log_message("Error converting power value to integer.")
                        return 0
            except Exception as inner_exception:
                log_message(f"Attempt failed with error: {inner_exception}")
    except Exception as e:
        log_message(f"Error getting current power from refu inverter: {e}")
        return 0
    
    log_message(f"Failed to get current power from refu inverter after 10 retries.")
    return 0

def set_current_power_refu(inverter_id, regulation_factor):
    if not is_reachable(inverter_id):
        log_message(f"Inverter {inverter_id} is not reachable.")
        return 0

    try:
        for _ in range(10):  # 10 Retries
            try:
                process = subprocess.Popen(f'socat - TCP4:{inverter_id}:21063', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                multiplied_factor = regulation_factor * 1000
                command = f'REFU.SetParameter 1162,0,{multiplied_factor}\n'
                stdout, stderr = process.communicate(input=command.encode())
                stderr_output = stderr.decode('utf-8').strip()
                stdout_output = stdout.decode('utf-8').strip()

            except Exception as inner_exception:
                log_message(f"Attempt failed with error: {inner_exception}")
    except Exception as e:
        log_message(f"Error setting current power from refu inverter: {e}")
        return 0
    
    log_message(f"Failed to set current power from refu inverter after 10 retries.")
    return 0

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

# Kommunale Dienstleistungsfunktionen
def calculate_dac_value(power):
    if power is None:
        log_message("Error: Power is None")
        return None
    dac = min_dac + ((max_dac - min_dac) / (max_power - min_power)) * (power - min_power)
    return round(dac)

def write_output(dac_value):
    try:
        if dac_value is not None:
            log_message("Calculated DAC value: " + str(dac_value))
            outputs.write_single(0, dac_value)
            time.sleep(0.1)
        else:
            log_message("Error: DAC value is None")
    except Exception as e:
        log_message(f"Error writing output: {e}")

# Hauptfunktionen
def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] {message}")

def regulate_direktvermarkter():
    modbus = ModbusUtils()
    try:
        polling_activation_list = modbus.read_coils(12)
        if isinstance(polling_activation_list, list) and len(polling_activation_list) > 0:
            polling_activation = bool(polling_activation_list[0])
        else:
            log_message("ERROR: Invalid set point specification value")
            return

        log_message('Polling activation: ' + str(polling_activation))

        if polling_activation:
            log_message('Start regulation of inverters: ' + str(inverter_ids))
            total_peak_power = retrieve_total_peak_power()
            log_message('total_peak_power: ' + str(total_peak_power))
            set_point_specification = modbus.client.read_holding_registers(10, 1).registers
            log_message('Set point specification: ' + str(set_point_specification))

            if isinstance(set_point_specification, list) and len(set_point_specification) > 0:
                set_point_value = set_point_specification[0]
            else:
                log_message("ERROR: Invalid set point specification value")
                return

            regulate_factor = set_point_value / total_peak_power
            log_message('Using regulate factor: ' + str(regulate_factor) + ' for every inverter.')
            do_regulation(regulate_factor, True)

    finally:
        modbus.close()

    scheduler.enter(3, 1, regulate_direktvermarkter)  # Schedule the next call in 3 seconds

def main():
    total_power = retrieve_active_power()
    log_message('total_power: ' + str(total_power))

    # 4-20 mA Signal senden
    write_output(calculate_dac_value(total_power))

    # Modbus TCP Input Register schreiben
    write_modbus_input_register(total_power)
    scheduler.enter(5, 1, main)  # Schedule the next call in 5 seconds

def retrieve_active_power():
    total_power = 0

    for inverter in inverter_ids:
        if inverter["type"] == "OPENEMS":
            current_power = get_current_power(inverter["id"])
            log_message(inverter["id"] + ' active_power: ' + str(current_power))
            total_power += current_power
        else:
            current_power = get_current_power_refu(inverter["id"])
            log_message(inverter["id"] + ' active_power: ' + str(current_power))
            total_power += current_power

    return total_power / 1000

def retrieve_total_peak_power():
    total_power = 0
    # TODO - Max Total Peak power der Refu Wechselrichter in Watt
    refu_total_power = 579000

    for inverter in inverter_ids:
        if inverter["type"] == "OPENEMS":
            current_power = get_peak_power(inverter["id"])
            log_message(inverter["id"] + ' peak_power: ' + str(current_power))
            total_power += current_power

    return total_power + refu_total_power

def write_modbus_input_register(total_power):
    modbus = ModbusUtils()
    try:
        response = modbus.write_input_register(0, total_power)
        log_message(f"Write Response: {response}")
    finally:
        modbus.close()

def do_regulation(regulation_factor, dry_run):
    for inverter in inverter_ids:
        if inverter["type"] == "OPENEMS":
            peak_power = get_peak_power(inverter["id"])
            value_to_write = regulation_factor * peak_power
            if dry_run:
                log_message('Dry RUN: Value would be: ' + str(value_to_write))
            else:
                write_channel_value(inverter["id"], 'SetActivePower', value_to_write)
        elif inverter["type"] == "REFU":
            if dry_run:
                log_message('Dry RUN: Would call set_current_power_refu with: ' + str(inverter["id"]) + ', ' + str(regulation_factor))
            else:
                set_current_power_refu(inverter["id"], regulation_factor)

# Hauptausführung
if __name__ == '__main__':
    outputs = Mod2AO()
    scheduler = sched.scheduler(time.time, time.sleep)
    scheduler.enter(0, 1, main)
    scheduler.enter(0, 1, regulate_direktvermarkter)
    scheduler.run()
