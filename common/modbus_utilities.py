# modbus_utils.py

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.exceptions import ModbusException

class ModbusUtils:
    def __init__(self, ip, port=502):
        self.client = ModbusTcpClient(ip, port)
        if not self.client.connect():
            raise ConnectionError(f"Unable to connect to {ip}:{port}")

    def read_holding_registers(self, address, count=1, unit=1):
        try:
            response = self.client.read_holding_registers(address, count, unit=unit)
            if response.isError():
                raise ModbusException(f"Error reading holding registers at address {address}")
            return response.registers
        except ModbusException as e:
            print(f"Modbus exception: {e}")
            return None

    def read_input_registers(self, address, count=1, unit=1):
        try:
            response = self.client.read_input_registers(address, count, unit=unit)
            if response.isError():
                raise ModbusException(f"Error reading input registers at address {address}")
            return response.registers
        except ModbusException as e:
            print(f"Modbus exception: {e}")
            return None

    def write_register(self, address, value, unit=1):
        try:
            response = self.client.write_register(address, value, unit=unit)
            if response.isError():
                raise ModbusException(f"Error writing register at address {address}")
            return response
        except ModbusException as e:
            print(f"Modbus exception: {e}")
            return None

    def close(self):
        self.client.close()
