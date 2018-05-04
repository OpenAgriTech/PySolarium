""" ETWatch code compatible with the LoPy Nano Gateway """

from network import LoRa
from machine import I2C, RTC
from MCP342x import MCP342x
from AS726X import AS726X
import socket
import binascii
import struct
import time
import pycom
import config
import json

rtc = RTC()
sensor_type = "None"


MAX_JOIN_RETRY = 100  # Max number of LoRa join before going to deep sleep

print("Hi there!")
# Save battery by disabling the LED
pycom.heartbeat(False)

# Define sleep time in seconds. Default is 1min, modify by downlink message.
# This needs to be read from file since data is lost between reboots
my_config_dict = {'sleep_time': 60}

try:
    with open("/flash/my_config.json", 'r') as conf_file:
        my_config_dict =  json.loads(conf_file.read())
except Exception as ex:
    print("Config file not found")
    with open("/flash/my_config.json", 'w') as conf_file:
        conf_file.write(json.dumps(my_config_dict))


# Give some time for degubbing
time.sleep(2.5)

# Initialize LoRa in LORAWAN mode.
lora = LoRa(mode=LoRa.LORAWAN)
# create an OTA authentication params for this node
dev_eui = binascii.unhexlify(config.DEV_EUI.replace(' ',''))
app_eui = binascii.unhexlify(config.APP_EUI.replace(' ',''))
app_key = binascii.unhexlify(config.APP_KEY.replace(' ',''))

print("Setting up LoRa channels...")
# Channels configures for TTN-EU863-870
lora.add_channel(0, frequency=868100000, dr_min=0, dr_max=5)
lora.add_channel(1, frequency=868300000, dr_min=0, dr_max=5)
lora.add_channel(2, frequency=868500000, dr_min=0, dr_max=5)
lora.add_channel(3, frequency=867100000, dr_min=0, dr_max=5)
lora.add_channel(4, frequency=867300000, dr_min=0, dr_max=5)
lora.add_channel(5, frequency=867500000, dr_min=0, dr_max=5)
lora.add_channel(6, frequency=867700000, dr_min=0, dr_max=5)
lora.add_channel(7, frequency=867900000, dr_min=0, dr_max=5)




print("Joining LoRa...")
# join a network using OTAA
lora.join(activation=LoRa.OTAA, auth=(dev_eui, app_eui, app_key), timeout=0)

#time.sleep(2.5)
join_retry = 0
# wait until the module has joined the network
while not lora.has_joined():
    pycom.rgbled(0x101000) # now make the LED light up yellow in colour
    time.sleep(5.0)
    print('Not joined yet... ', rtc.now())
    join_retry+=1
    if join_retry > MAX_JOIN_RETRY:
        raise Exception("Couldn join LoRa!")


print("Connected to LoRa")
pycom.rgbled(0x000000) # now turn the LED off

print("Waking up I2C sensors...")
try:
    i2c = I2C(1, I2C.MASTER, pins=('P9', 'P10'), baudrate=100000)
    addr68_ch0 = MCP342x(i2c, 0x68, channel=0, resolution=18, gain=8,
                         scale_factor=1000.0)
    addr68_ch1 = MCP342x(i2c, 0x68, channel=1, resolution=18, gain=8,
                         scale_factor=1000.0)
    addr68_ch2 = MCP342x(i2c, 0x68, channel=2, resolution=18, gain=8,
                         scale_factor=1000.0)
    addr68_ch3 = MCP342x(i2c, 0x68, channel=3, resolution=18, gain=8,
                         scale_factor=1000.0)
    time.sleep(1)
    print('Ready to read ADC')

    i2c_2 = I2C(0, I2C.MASTER, pins=('P22', 'P21'))
    sensor = AS726X(i2c=i2c_2)
    sensor_type = sensor.get_sensor_type()
    time.sleep(1)
    print('Ready to read on wavelengths:')
    print(sensor.get_wavelengths())

except Exception as error:
    print(error)
    pycom.rgbled(0xff0000) # now make the LED light up red in colour
    print(error)
    time.sleep(5.0)  # Wait 5 senconds with the red LED
    pycom.rgbled(0x000000) # now make the LED light up red in colour
    print("Couldn find sensor")
    pass

print("Setting up battery sensing...")
# Battery sensing
adc = machine.ADC(0)
batt = adc.channel(pin='P16', attn=3)

# create a LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# set the LoRaWAN data rate
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

# make the socket blocking
s.setblocking(False)

print("Joined to LoRa and socket created")
pycom.rgbled(0x001000) # now make the LED light up green in colour

#time.sleep(5.0)

# Payload is sent as byte array with 7*float32 (4 bytes each) and 2*uint16
# Total payload size is 32 bytes
# Data structure is: ADC, {ch0},{ch1},{ch2},{ch3},{ch4},{ch5}, Tsensor,Volt
# All data is sent as ADC
msg = bytearray(32)

while True:
    float_values = [-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, 0, 0]
    try:
        float_values[0] = addr68_ch0.convert_and_read()

    except Exception as error:
        print(error)

    try:
        sensor.take_measurements()
        float_values[1:7] = sensor.get_calibrated_values()
        float_values[7] = sensor.get_temperature()

    except Exception as error:
        print(error)

    float_values[8] = int((batt.value()/4096)*354.8/0.316)

    print("{sensor_type}:{ch0},{ch1},{ch2},{ch3},{ch4},{ch5},{ch6},{ch7},{ch8}".format(
        sensor_type=sensor_type, ch0=float_values[0],
        ch1=float_values[1], ch2=float_values[2],
        ch3=float_values[3], ch4=float_values[4],
        ch5=float_values[5], ch6=float_values[6],
        ch7=float_values[7], ch8=float_values[8]))

    msg = bytearray(struct.pack('7f2h', *float_values))

    s.send(msg)

    time.sleep(4)
    rx = s.recv(256)
    if rx:
        print("Got a packet from the cloud")
        print(rx)
        in_msg = bytearray(rx)
        if len(in_msg) > 2:
            if in_msg[0] == 1:
                # Sleep time command
                my_config_dict["sleep_time"] = int.from_bytes(in_msg[1:3], 'little')
                print("New sleep time {}s".format(my_config_dict["sleep_time"]))
        with open("/flash/my_config.json", 'w') as conf_file:
            conf_file.write(json.dumps(my_config_dict))


    pycom.rgbled(0x000000) # now make the LED light up green in colour
    time.sleep(my_config_dict["sleep_time"])  # go to sleep
