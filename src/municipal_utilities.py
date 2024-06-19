from time import sleep

from widgetlords.pi_spi import *

import variables

max_dac = 3723
min_dac = 745


def calculate_dac_value(power):
    if power is None:
        print("Error: Power is None")
        return None
    dac = min_dac + ((max_dac - min_dac) / (variables.max_power - variables.min_power)) * (power - variables.min_power)
    return round(dac, 1)


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
