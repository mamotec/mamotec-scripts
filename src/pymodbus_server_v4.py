import logging
import struct
import asyncio
import socket
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder

# Logging-Konfiguration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Initialisiere die Datenblöcke und den Kontext
store = ModbusSlaveContext(
    ir=ModbusSequentialDataBlock(0, [0]*14),  # Input Register (0-13)
    hr=ModbusSequentialDataBlock(0, [0]*14)   # Holding Register (0-13)
)
context = ModbusServerContext(slaves=store, single=True)

# Funktion zum Setzen von 32-Bit Float-Werten
def set_float(context, address, value, fc=3):
    builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
    builder.add_32bit_float(value)
    payload = builder.to_registers()
    context[0].setValues(fc, address, payload)
    logger.info(f"Float-Wert gesetzt: Adresse={address}, Wert={value}, Funktion Code={fc}")

# Funktion zum Setzen von Bool-Werten
def set_bool(context, address, bit, value, fc=3):
    register = context[0].getValues(fc, address, 1)[0]
    old_value = bool(register & (1 << bit))
    if value:
        register |= (1 << bit)
    else:
        register &= ~(1 << bit)
    context[0].setValues(fc, address, [register])
    logger.info(f"Bool-Wert gesetzt: Adresse={address}, Bit={bit}, Alter Wert={old_value}, Neuer Wert={value}, Funktion Code={fc}")

# Initialisierung der Datenpunkte
set_float(context, 0, 0.0, fc=4)  # Wirkleistung (Input Register)
set_float(context, 2, 100.0, fc=4)  # Leistungsvorgabe des EVU (Input Register)
set_float(context, 4, 0.0, fc=4)  # Windgeschwindigkeit (Input Register)
set_bool(context, 6, 0, False, fc=4)  # Abrufmeldung (Input Register)
set_bool(context, 6, 8, False, fc=4)  # Betriebsmeldung (Input Register)
set_bool(context, 6, 12, False, fc=4)  # Bereitschaftsmeldung (Input Register)
set_float(context, 8, 0.0, fc=4)  # Verfügbare Leistung (Input Register)
set_float(context, 10, 0.0)  # Sollwertvorgabe (Holding Register)
set_bool(context, 12, 0, False)  # Abrufaktivierung (Holding Register)

# Mapping der Adressen zu den Datentypen
address_map = {
    0: ('float', 4),
    2: ('float', 4),
    4: ('float', 4),
    6: ('bool', 4),
    8: ('float', 4),
    10: ('float', 3),
    12: ('bool', 3)
}

# Callback-Funktion zum Protokollieren der geschriebenen Werte
def on_write_data(address, values):
    i = 0
    while i < len(values):
        actual_address = address + i
        data_type, fc = address_map.get(actual_address, (None, None))
        if data_type == 'float':
            if i + 1 < len(values):
                decoder = BinaryPayloadDecoder.fromRegisters(values[i:i+2], byteorder=Endian.Big, wordorder=Endian.Big)
                float_value = decoder.decode_32bit_float()
                logger.info(f"Register {actual_address} geschrieben mit Wert: {float_value} (Float)")
                i += 2  # Float nimmt 2 Register ein
            else:
                logger.warning(f"Unvollständige Float-Daten bei Adresse {actual_address}")
                i += 1
        elif data_type == 'bool':
            for bit in [0, 8, 12]:
                bool_value = bool(values[i] & (1 << bit))
                logger.info(f"Register {actual_address}.{bit} geschrieben mit Wert: {bool_value} (Boolean)")
            i += 1
        else:
            logger.warning(f"Unbekannter Datentyp bei Adresse {actual_address}")
            i += 1

# Override der setValues-Methode, um Änderungen zu protokollieren und Schreibzugriffe auf Input Register zu verhindern
original_set_values = store.setValues

def logging_set_values(fc_as_hex, address, values):
    fc = fc_as_hex
    if fc == 4:  # Input Register
        logger.warning(f"Schreibversuch auf Input Register bei Adresse {address} abgelehnt")
        return False
    if address > 13:  # Anpassen, wenn Sie mehr als 14 Register haben
        logger.warning(f"Schreibversuch auf ungültige Adresse {address} abgelehnt")
        return False
    logger.info(f"Schreibvorgang gestartet: Funktion Code={fc}, Adresse={address}, Werte={values}")
    on_write_data(address, values)
    result = original_set_values(fc_as_hex, address, values)
    logger.info(f"Schreibvorgang abgeschlossen: Ergebnis={result}")
    return result

store.setValues = logging_set_values

# Custom Read Handler
def custom_read_handler(register_type, address, count):
    values = context[0].getValues(register_type, address, count)
    logger.info(f"Lesevorgang: Typ={register_type}, Adresse={address}, Anzahl={count}, Werte={values}")
    return values

store.read = custom_read_handler

# Modbus-Server-Identifikation
identity = ModbusDeviceIdentification()
identity.VendorName = 'Pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl = 'http://github.com/pymodbus-dev/pymodbus/'
identity.ProductName = 'Pymodbus Server'
identity.ModelName = 'Pymodbus Server'
identity.MajorMinorRevision = '3.6.9'

# Heartbeat-Funktion
async def heartbeat():
    while True:
        logger.info("Server läuft und wartet auf Verbindungen...")
        await asyncio.sleep(60)  # Alle 60 Sekunden

# Statusreporter-Funktion
async def status_reporter():
    while True:
        ir_values = context[0].getValues(4, 0, 14)
        hr_values = context[0].getValues(3, 0, 14)
        logger.info(f"Server-Status: Aktiv. Aktuelle Input Register Werte: {ir_values}")
        logger.info(f"Server-Status: Aktiv. Aktuelle Holding Register Werte: {hr_values}")
        await asyncio.sleep(300)  # Alle 5 Minuten

async def run_server():
    try:
        server = await StartAsyncTcpServer(
            context=context,
            identity=identity,
            address=("0.0.0.0", 502)
        )
        logger.info("Modbus-TCP-Server erfolgreich gestartet auf Port 502")
        
        # Überprüfe, ob der Server tatsächlich auf Port 502 hört
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('127.0.0.1', 502))
            if result == 0:
                logger.info("Server hört erfolgreich auf Port 502")
            else:
                logger.error(f"Server konnte nicht auf Port 502 hören. Fehlercode: {result}")
        
        # Starte Heartbeat-Task und Status-Reporter
        asyncio.create_task(heartbeat())
        asyncio.create_task(status_reporter())
        
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Fehler beim Starten oder Ausführen des Servers: {e}")
        raise

async def main():
    logger.info("Starte Modbus-TCP-Server...")
    try:
        await run_server()
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Starten des Servers: {e}")
    finally:
        logger.info("Server wird beendet.")

if __name__ == "__main__":
    asyncio.run(main())
