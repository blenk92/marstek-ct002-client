import socket
import binascii
import time
import paho.mqtt.client as mqtt
import os


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

class PowerMeter:
    def __init__(self, ip, meter_id, checksum=None):
        self.A = 0
        self.B = 0
        self.C = 0
        self.All = 0
        self.update_counter = 0
        self.ip = ip
        self.message = f"\x01\x0249|HMJ-3|cafecafecafe|HME-4|{meter_id}|A|0\x03"
        if not checksum:
            self._brute_checksum()
        else:
            self.message = self.message + checksum


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

    def update(self):
        A, B, C, All = self._read_power_meter(self.message)

        if A == None:
            print("Couldn't read power meter")
            # If we can not read a packet lets retransmit the next reading no matter what
            self.update_counter = 99
            return False
   
        if VERBOSE_PRINT:
            print(f"Read A: {A}, B: {B}, C: {C}, ALL: {All}")
        update_needed = (self.A, self.B, self.C, self.All) != (A, B, C, All)
        if not update_needed:
            self.update_counter += 1
        else:
            self.A = A
            self.B = B
            self.C = C
            self.All = All

        if self.update_counter >= 20:
            self.update_counter = 0
            update_needed = True

        return update_needed

if __name__ == "__main__":    
    pm = PowerMeter(MARSTEK_METER_IP, MARSTEK_METER_ID, MARSTEK_MSG_CHECKSUM)

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    mqttc.username_pw_set(MQTT_USER, MQTT_PASS)
    mqttc.connect(MQTT_HOST, int(MQTT_PORT), 60)

    mqttc.loop_start()
    while True:
        update_needed = pm.update()
        if update_needed:
            mqttc.publish(f"marstek-power-meter/acd929a73dd4/A", pm.A, qos=2)
            mqttc.publish(f"marstek-power-meter/acd929a73dd4/B", pm.B, qos=2)
            mqttc.publish(f"marstek-power-meter/acd929a73dd4/C", pm.C, qos=2)
            mqttc.publish(f"marstek-power-meter/acd929a73dd4/ALL", pm.All, qos=2)
        time.sleep(0.3)

    mqttc.loop_stop()

