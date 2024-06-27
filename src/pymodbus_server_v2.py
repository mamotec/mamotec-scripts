import logging
import struct
from pymodbus.server.sync import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock

# Logging-Konfiguration
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Initialisiere die Datenblöcke und den Kontext
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0]*20)  # 20 Register für Holding-Registers
)
context = ModbusServerContext(slaves=store, single=True)

# Funktion zum Setzen von 32-Bit Float-Werten
def set_float(context, address, value):
    packed_value = struct.unpack('>HH', struct.pack('>f', value))
    context[0].setValues(3, address, packed_value)

set_float(context, 0, 0.0)  # Wirkleistung
set_float(context, 2, 100.0)  # Leistungsvorgabe des EVU
set_float(context, 4, 0.0)  # Windgeschwindigkeit
context[0].setValues(3, 6, [0])  # Abrufmeldung (Bool)
context[0].setValues(3, 8, [0])  # Betriebsmeldung (Bool)
set_float(context, 10, 0.0)  # Sollwertvorgabe
context[0].setValues(3, 12, [0])  # Bereitschaftsmeldung (Bool)

# Mapping der Adressen zu den Datentypen
address_map = {
    0: 'float',
    2: 'float',
    4: 'float',
    6: 'bool',
    8: 'bool',
    10: 'float',  # Sollwertvorgabe als float
    12: 'bool'  # Bereitschaftsmeldung als bool
}

# Callback-Funktion zum Protokollieren der geschriebenen Werte
def on_write_data(address, values):
    i = 0
    while i < len(values):
        actual_address = address + i
        if address_map.get(actual_address) == 'float':
            if i + 1 < len(values):
                float_value = struct.unpack('>f', struct.pack('>HH', values[i], values[i+1]))[0]
                logger.info(f"Register {actual_address} geschrieben mit Wert: {float_value} (Float)")
                i += 2  # Float nimmt 2 Register ein
            else:
                logger.warning(f"Unvollständige Float-Daten bei Adresse {actual_address}")
                i += 1
        elif address_map.get(actual_address) == 'bool':
            bool_value = bool(values[i])
            logger.info(f"Register {actual_address} geschrieben mit Wert: {bool_value} (Boolean)")
            i += 1
        else:
            logger.warning(f"Unbekannter Datentyp bei Adresse {actual_address}")
            i += 1

# Override der setValues-Methode, um Änderungen zu protokollieren
original_set_values = store.setValues

def logging_set_values(framer, address, values):
    on_write_data(address, values)
    return original_set_values(framer, address, values)

store.setValues = logging_set_values

# Modbus-Server-Identifikation
identity = ModbusDeviceIdentification()
identity.VendorName = 'Pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl = 'http://github.com/riptideio/pymodbus/'
identity.ProductName = 'Pymodbus Server'
identity.ModelName = 'Pymodbus Server'
identity.MajorMinorRevision = '1.0'

# Starte den Modbus-TCP-Server auf Port 502
try:
    logger.info("Starte Modbus-TCP-Server auf Port 502...")
    StartTcpServer(context, identity=identity, address=("0.0.0.0", 502))
except Exception as e:
    logger.error(str(e))
