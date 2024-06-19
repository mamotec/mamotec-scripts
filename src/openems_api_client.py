import json

import requests

import variables


def get_current_power(inverter_id):
    try:
        url = f'http://x:admin@{variables.modbus_tcp_ip}:8084/rest/channel/{inverter_id}/ActivePower'
        response = requests.get(url)
        response_dict = response.json()
        return response_dict['value']
    except Exception as e:
        print(f"Error getting current power: {e}")
        return None


def get_peak_power(inverter_id):
    try:
        url = f'http://x:admin@{variables.modbus_tcp_ip}:8084/rest/channel/{inverter_id}/MaxApparentPower'
        response = requests.get(url)
        response_dict = response.json()
        return response_dict['value']
    except Exception as e:
        print(f"Error getting peak power: {e}")
        return None


def write_channel_value(inverter_id, channel, value):
    try:
        url = f'http://x:admin@{variables.modbus_tcp_ip}:8084/rest/channel/{inverter_id}/{channel}'
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({'value': value})
        response = requests.post(url, headers=headers, data=payload, auth=('admin', 'x'))

        if response.status_code == 200:
            response_dict = response.json()
            return response_dict['value']
        else:
            print(f"Error updating channel value: {response.text}")
            return None

    except Exception as e:
        print(f"Error updating channel value: {e}")
    return None
