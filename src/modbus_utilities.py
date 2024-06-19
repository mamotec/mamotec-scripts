# modbus_utils.py

import struct

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.exceptions import ModbusException


class ModbusUtils:
    def __init__(self, modbus_tcp_ip):
        # Initialisiere deine Modbus-Verbindung hier
        self.client = ModbusTcpClient(modbus_tcp_ip)

    def read_coils(self, address, count=1, unit=5):
        try:
            response = self.client.read_coils(address, count, unit=unit)
            if response.isError():
                raise ModbusException(f"Error reading coils at address {address}")
            return response.bits
        except ModbusException as e:
            print(f"Modbus exception: {e}")
            return None

    def write_register(self, address, value, unit=5):
        try:
            response = self.client.write_register(address, value, unit=unit)
            if response.isError():
                raise ModbusException(f"Error writing register at address {address}")
            return response
        except ModbusException as e:
            print(f"Modbus exception: {e}")
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
            print(f"Modbus exception: {e}")
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
