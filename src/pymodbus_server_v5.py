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
    ir=ModbusSequentialDataBlock(0, [0]*20),  # Input Register (0-19)
    hr=ModbusSequentialDataBlock(0, [0]*20)   # Holding Register (0-19)
)
context = ModbusServerContext(slaves=store, single=True)

def update_input_register(address, values):
    """Interne Funktion zum Aktualisieren von Input Registern."""
    try:
        # Erhöhe die Adresse um 1 für das Input Register
        input_address = address + 1
        
        # Schreibe die Werte in der ursprünglichen Reihenfolge
        store.store['i'].setValues(input_address, values)
        
        logger.info(f"Input Register {input_address} intern aktualisiert mit Werten: {values}")
        
        # Verifiziere den geschriebenen Wert
        written_values = store.store['i'].getValues(input_address, len(values))
        logger.info(f"Verifizierung - Gelesene Werte aus Input Register {input_address}: {written_values}")
        
        # Dekodiere den Float-Wert für besseres Logging
        if len(values) >= 2:
            decoder = BinaryPayloadDecoder.fromRegisters(written_values, byteorder=Endian.BIG, wordorder=Endian.BIG)
            float_value = decoder.decode_32bit_float()
            logger.info(f"Dekodierter Float-Wert im Input Register: {float_value}")
    except Exception as e:
        logger.error(f"Fehler beim Aktualisieren des Input Registers {input_address}: {e}")

def logging_set_values(fc_as_hex, address, values):
    fc = fc_as_hex
    if fc == 4:  # Input Register
        logger.warning(f"Schreibversuch auf Input Register bei Adresse {address} abgelehnt")
        return False
    if address >= 14:  # Erweitere den zulässigen Bereich auf 14 Adressen
        logger.warning(f"Schreibversuch auf ungültige Adresse {address} abgelehnt")
        return False
    logger.info(f"Schreibvorgang gestartet: Funktion Code={fc}, Adresse={address}, Werte={values}")
    on_write_data(address, values)
    result = original_set_values(fc_as_hex, address, values)
    
    # Wenn in Holding Register 0 geschrieben wird (FC 16 oder FC 6), aktualisiere Input Register 0
    if (fc == 16 or fc == 6) and address == 0:  # Preset Multiple Registers oder Preset Single Register
        # Stelle sicher, dass wir beide Werte kopieren
        update_input_register(0, values[:2])  # Kopiere die ersten zwei Register (für Float)
        
        # Verifiziere den Kopiervorgang
        hr_values = context[0].getValues(fc, address, 2)
        ir_values = store.store['i'].getValues(0, 2)
        logger.info(f"Verifizierung - Holding Register Werte: {hr_values}, Input Register Werte: {ir_values}")

    logger.info(f"Schreibvorgang abgeschlossen: Ergebnis={result}")
    return result

# Funktion zum Setzen von 32-Bit Float-Werten
def set_float(context, address, value, fc=4):
    builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
    builder.add_32bit_float(value)
    payload = builder.to_registers()
    if fc == 4:  # Input Register
        update_input_register(address, payload)
    else:  # Holding Register (fc sollte 16 sein)
        context[0].setValues(fc, address, payload)
    logger.info(f"Float-Wert gesetzt: Adresse={address}, Wert={value}, Funktion Code={fc}")

# Funktion zum Setzen von Bool-Werten
def set_bool(context, address, bit, value, fc=4):
    if fc == 4:  # Input Register
        register = store.store['i'].getValues(address, 1)[0]
    else:  # Holding Register (fc sollte 16 sein)
        register = context[0].getValues(fc, address, 1)[0]
    
    old_value = bool(register & (1 << bit))
    if value:
        register |= (1 << bit)
    else:
        register &= ~(1 << bit)
    
    if fc == 4:  # Input Register
        update_input_register(address, [register])
    else:  # Holding Register
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
set_float(context, 10, 0.0, fc=16)  # Sollwertvorgabe (Holding Register)
set_bool(context, 12, 0, False, fc=16)  # Abrufaktivierung (Holding Register)

# Mapping der Adressen zu den Datentypen
address_map = {
    0: ('float', 4),
    2: ('float', 4),
    4: ('float', 4),
    6: ('bool', 4),
    8: ('float', 4),
    10: ('float', 16),
    12: ('bool', 16)
}

# Callback-Funktion zum Protokollieren der geschriebenen Werte
def on_write_data(address, values):
    i = 0
    while i < len(values):
        actual_address = address + i
        data_type, fc = address_map.get(actual_address, (None, None))
        if data_type == 'float':
            if i + 1 < len(values):
                decoder = BinaryPayloadDecoder.fromRegisters(values[i:i+2], byteorder=Endian.BIG, wordorder=Endian.BIG)
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
    if address >= 14:  # Erweitere den zulässigen Bereich auf 14 Adressen
        logger.warning(f"Schreibversuch auf ungültige Adresse {address} abgelehnt")
        return False
    logger.info(f"Schreibvorgang gestartet: Funktion Code={fc}, Adresse={address}, Werte={values}")
    on_write_data(address, values)
    result = original_set_values(fc_as_hex, address, values)
    
    # Wenn in Holding Register 0 geschrieben wird (FC 16 oder FC 6), aktualisiere Input Register 0
    if (fc == 16 or fc == 6) and address == 0:  # Preset Multiple Registers oder Preset Single Register
        # Stelle sicher, dass wir beide Werte kopieren
        update_input_register(0, values[:2])  # Kopiere die ersten zwei Register (für Float)
        
    logger.info(f"Schreibvorgang abgeschlossen: Ergebnis={result}")
    return result

store.setValues = logging_set_values

# Custom Read Handler
def custom_read_handler(register_type, address, count):
    try:
        if register_type == 4:  # Input Register
            # Erhöhe die Adresse um 1 für das Input Register
            input_address = address + 1
            values = store.store['i'].getValues(input_address, count)
        else:
            values = context[0].getValues(register_type, address, count)
        
        # Dekodiere den Float-Wert für besseres Logging, wenn möglich
        if count == 2:
            decoder = BinaryPayloadDecoder.fromRegisters(values, byteorder=Endian.BIG, wordorder=Endian.BIG)
            float_value = decoder.decode_32bit_float()
            logger.info(f"Lesevorgang: Typ={register_type}, Adresse={address}, Anzahl={count}, Werte={values}, Float-Wert={float_value}")
        else:
            logger.info(f"Lesevorgang: Typ={register_type}, Adresse={address}, Anzahl={count}, Werte={values}")
        
        return values
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Register: Typ={register_type}, Adresse={address}, Anzahl={count}, Fehler: {e}")
        return [0] * count  # Rückgabe von Nullen im Fehlerfall

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
        ir_values = custom_read_handler(4, 0, 14)
        hr_values = custom_read_handler(3, 0, 14)
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
