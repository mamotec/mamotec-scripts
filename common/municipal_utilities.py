# Hier die 4-20 mA Signale empfangen und errechnen
import json
import requests
from time import sleep
from widgetlords.pi_spi import *

min_power, max_power = -1200, 1200
min_mA, max_mA = 4, 20
max_dac = 3723
min_dac = 745
active_power_channel = 'meter3'


def get_current_power():
    try:
        url = f'http://x:admin@localhost:8084/rest/channel/{active_power_channel}/ActivePower'
        response = requests.get(url)
        response_dict = response.json()
        return response_dict['value']
    except Exception as e:
        print(f"Error getting current power: {e}")
        return None


def calculate_dac_value(power):
    if power is None:
        print("Error: Power is None")
        return None
    DAC = min_dac + ((max_dac - min_dac) / (max_power - min_power)) * (power - min_power)
    return round(DAC, 1)  # Runden des Ergebnisses auf eine Dezimalstelle

def write_output(dac_value):
    try:
        if dac_value is not None:
            outputs.write_single(0, dac_value)
            sleep(0.1)
        else:
            print("Error: DAC value is None")
    except Exception as e:
        print(f"Error writing output: {e}")


init()
outputs = Mod2AO()

while True:

    current_power = get_current_power()
    dac_value = calculate_dac_value(current_power)
    write_output(dac_value)

    if dac_value is not None:
        print(f'The DAC value for a power input of {current_power} kW is {dac_value}.')
    else:
        print("Error: DAC value could not be calculated")
    sleep(1)