import socket
import time
import paho.mqtt.client as mqtt
import os
import copy
import json

MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT") or 1883)
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID") or "marstek-powermeter-reader"
MARSTEK_METER_ID = os.getenv("MARSTEK_METER_ID")
MARSTEK_METER_IP = os.getenv("MARSTEK_METER_IP")
MARSTEK_FAKE_CLIENT_ID = os.getenv("MARSTEK_FAKE_CLIENT_ID") or "cafecafecafe"
CONNECTION_READ_TIMEOUT = float(os.getenv("CONNECTION_READ_TIMEOUT") or 0.5)
MARSTEK_MSG_CHECKSUM = os.getenv("MARSTEK_MSG_CHECKSUM") 
VERBOSE_PRINT = bool(os.getenv("VERBOSE_PRINT"))

class HA_CONFIG:
    HA_CONFIG_TEMPLATE = {
        "name": "Phase {PHASE}",
        "device_class": "power",
        "state_topic": "marstek-power-meter/{ID}/{PHASE}",
        "unit_of_measurement": "W",
        "state_class": "measurement",
        "availability": [
            {
                "topic": "marstek-power-meter/{ID}/availability",
                "payload_available": "online",
                "payload_not_available": "offline"
            }
        ],
        "unique_id": "{ID}_power_{PHASE}",
        "device": {
            "ids": [
                "hame_energy_{ID}"
            ],
            "name": "Marstek HME-4 {ID}",
            "model_id": "HME-4",
            "manufacturer": "HAME Energy"
        },
        "origin": {
            "name": "marstek-ct002-client",
            "url": "https://github.com/blenk92/marstek-ct002-client"
        }
    }

    def __init__(self, PHASE, ID):
        self.PHASE = PHASE
        self.ID = ID
        self.config = copy.deepcopy(self.HA_CONFIG_TEMPLATE)

        self.config["name"] = self.config["name"].format(PHASE=PHASE)
        self.config["state_topic"] = self.config["state_topic"].format(PHASE=PHASE, ID=ID)
        self.config["availability"][0]["topic"] = self.config["availability"][0]["topic"].format(PHASE=PHASE, ID=ID)
        self.config["unique_id"] = self.config["unique_id"].format(PHASE=PHASE, ID=ID)
        self.config["device"]["ids"][0] = self.config["device"]["ids"][0].format(PHASE=PHASE, ID=ID)
        self.config["device"]["name"] = self.config["device"]["name"].format(PHASE=PHASE, ID=ID)

    def get_str(self):
        return json.dumps(self.config)



HA_CONFIG_A = HA_CONFIG("A", MARSTEK_METER_ID)
HA_CONFIG_B = HA_CONFIG("B", MARSTEK_METER_ID)
HA_CONFIG_C = HA_CONFIG("C", MARSTEK_METER_ID)
HA_CONFIG_ALL = HA_CONFIG("ALL", MARSTEK_METER_ID)


class PowerMeter:
    def __init__(self, ip, meter_id, checksum=None):
        self.A = 0
        self.B = 0
        self.C = 0
        self.All = 0
        self.update_counter = 0
        self.ip = ip
        self.message = f"\x01\x0249|HMJ-3|{MARSTEK_FAKE_CLIENT_ID}|HME-4|{meter_id}|A|0\x03"
        if not checksum:
            self._brute_checksum()
        else:
            self.message = self.message + checksum

        self.error_read_count = 0
        self.availability = "offline"


    def _brute_checksum(self):
        # Not sure how the last byte is calcualted, but we can simply brute force it
        print("Brute forcing checksum parameter")
        while True:
            for i in range(0, 256):
                end = '{0:0{1}X}'.format(i,2).lower()
                print(f"Testing {end}")
                reading = self._read_power_meter(self.message + end)
                if reading[0]:
                    print(f"Got answer on checksum {end}")
                    self.message = self.message + end
                    break
                time.sleep(0.5)
            else:
                # If we don't break the loop lets retry
                continue
            break
        
    def _read_power_meter(self, msg):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM )
        sock.sendto(msg.encode(), (self.ip, 12345))
        sock.settimeout(CONNECTION_READ_TIMEOUT)
        try:
            answer = sock.recv(1024)
        except:
            sock.close()
            return None, None, None, None

        answer_split = answer.decode().split('|')
        A = answer_split[5]
        B = answer_split[6]
        C = answer_split[7]
        ALL = answer_split[8]

        sock.close() 
        return A, B, C, ALL

    def __power_value_debounce(self, new_A, new_B, new_C, new_ALL):
        if new_A -2 <= self.A and self.A <= new_A + 2:
            return True
        if new_B -2 <= self.B and self.B <= new_B + 2:
            return True
        if new_C -2 <= self.C and self.C <= new_C + 2:
            return True
        if new_ALL -2 <= self.ALL and self.ALL <= new_ALL + 2:
            return True

        return False


    def update(self):
        A, B, C, All = self._read_power_meter(self.message)

        if A == None:
            print("Couldn't read power meter")
            # If we can not read a packet lets retransmit the next reading no matter what
            self.update_counter = 99
            self.error_read_count += 1

            if self.error_read_count >= 3:
                self.availability = "offline"
            return False, True
   
        self.error_read_count = 0
        if self.availability == "offline":
            self.availability = "online"
            availability_update_needed = True
        else:
            availability_update_needed = False

        if VERBOSE_PRINT:
            print(f"Read A: {A}, B: {B}, C: {C}, ALL: {All}")
        update_needed = (self.A, self.B, self.C, self.All) != (A, B, C, All)
        if not update_needed:
            self.update_counter += 1
        else:
            if self.__power_value_debounce(A, B, C, All):
                update_needed = False
            else:
                self.A = A
                self.B = B
                self.C = C
                self.All = All

        if self.update_counter >= 20:
            self.update_counter = 0
            update_needed = True

        return update_needed, availability_update_needed

if __name__ == "__main__":    
    pm = PowerMeter(MARSTEK_METER_IP, MARSTEK_METER_ID, MARSTEK_MSG_CHECKSUM)

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    mqttc.username_pw_set(MQTT_USER, MQTT_PASS)

    mqttc.will_set(f"marstek-power-meter/{MARSTEK_METER_ID}/availability", payload="offline", qos=2, retain=True)

    mqttc.connect(MQTT_HOST, int(MQTT_PORT), 60)

    mqttc.loop_start()
    
    # Availability
    mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/availability", "online", qos=2, retain=True)
    
    # HA config
    mqttc.publish(f"homeassistant/sensor/HME-4_{MARSTEK_METER_ID}/{MARSTEK_METER_ID}_power_A/config", HA_CONFIG_A.get_str() , qos=2, retain=True)
    mqttc.publish(f"homeassistant/sensor/HME-4_{MARSTEK_METER_ID}/{MARSTEK_METER_ID}_power_B/config", HA_CONFIG_B.get_str() , qos=2, retain=True)
    mqttc.publish(f"homeassistant/sensor/HME-4_{MARSTEK_METER_ID}/{MARSTEK_METER_ID}_power_C/config", HA_CONFIG_C.get_str() , qos=2, retain=True)
    mqttc.publish(f"homeassistant/sensor/HME-4_{MARSTEK_METER_ID}/{MARSTEK_METER_ID}_power_ALL/config", HA_CONFIG_ALL.get_str() , qos=2, retain=True)
    
    # Power Values
    while True:
        update_needed, availability_update_needed = pm.update()
        if update_needed:
            mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/A", pm.A, qos=1)
            mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/B", pm.B, qos=1)
            mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/C", pm.C, qos=1)
            mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/ALL", pm.All, qos=1)
        if availability_update_needed:
            mqttc.publish(f"marstek-power-meter/{MARSTEK_METER_ID}/availability", pm.availability, qos=2, retain=True)

        time.sleep(0.3)

    mqttc.loop_stop()

