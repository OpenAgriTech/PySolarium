from machine import UART
import machine
from network import WLAN
import os
import time
from config import SSID, PSK

uart = UART(0, 115200)
os.dupterm(uart)

rtc = machine.RTC()

wlan = WLAN() # get current object, without changing the mode
#wlan.deinit()

if machine.reset_cause() != machine.SOFT_RESET:
    wlan.init(mode=WLAN.STA)
    # configuration below MUST match your home router settings!!
    #wlan.ifconfig(config=('192.168.1.101', '255.255.255.0', '192.168.1.1', '8.8.8.8'))

if not wlan.isconnected():
    # change the line below to match your network ssid, security and password
    wlan.connect(SSID, auth=(WLAN.WPA2, PSK), timeout=5000)
    while not wlan.isconnected():
        machine.idle() # save power while waiting
    print('WLAN connection succeeded!')
    print(wlan.ifconfig())
    rtc.ntp_sync("pool.ntp.org")
