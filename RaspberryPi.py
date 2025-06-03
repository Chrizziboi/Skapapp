# RaspberryPi.py

import RPi.GPIO as GPIO
import time
import requests
import json
from mfrc522 import SimpleMFRC522

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)
LOCKER_GPIO_MAP = {int(k): v for k, v in CONFIG.get("locker_gpio_map", {}).items()}
LOCKER_CLOSE_PIN_MAP = {int(k): v for k, v in CONFIG.get("locker_close_pin_map", {}).items()}
RFID_TIMEOUT_SEC = CONFIG.get("rfid_timeout_sec", 8)

API_URL_REG = "http://localhost:8080/assign_after_closure/"
API_URL_SCAN = "http://localhost:8080/scan_rfid/"

# --- Init GPIO ---
for gpio_pin in LOCKER_GPIO_MAP.values():
    GPIO.setup(gpio_pin, GPIO.OUT)
    GPIO.output(gpio_pin, GPIO.LOW)

for close_pin in LOCKER_CLOSE_PIN_MAP.values():
    GPIO.setup(close_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# --- Hjelpevariabler ---
skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
siste_rfid = None
siste_skann_tid = 0

reader = SimpleMFRC522()

def magnet_release(locker_id):
    """Fjerner strøm til magnetlåsen for å åpne skapet"""
    pin = LOCKER_GPIO_MAP[locker_id]
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)

def scan_for_rfid(timeout=RFID_TIMEOUT_SEC):
    """Skanner etter RFID-brikke innen gitt tid"""
    print("Hold kortet inntil leseren...")
    start = time.time()
    while time.time() - start < timeout:
        id, text = reader.read_no_block()
        if id:
            print(f"RFID funnet: {id}")
            return str(id)
        time.sleep(0.1)
    print("Ingen RFID funnet, timeout.")
    return None

def register_locker():
    """Lytter på skaplukking, triggere RFID-scan og API-kall"""
    global skap_lukket_tidligere

    for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
        if GPIO.input(close_pin) == GPIO.LOW and not skap_lukket_tidligere[locker_id]:
            print(f"[INNGANG] Skap {locker_id} lukket – aktiverer RFID-skanning")
            skap_lukket_tidligere[locker_id] = True

            rfid_tag = scan_for_rfid()
            if rfid_tag:
                try:
                    response = requests.post(
                        API_URL_REG,
                        params={
                            "rfid_tag": rfid_tag,
                            "locker_room_id": LOCKER_ROOM_ID,
                            "locker_id": locker_id
                        },
                        timeout=2
                    )
                    res = response.json()
                    print(f"Backend-respons: {res}")
                    if res.get("success"):
                        # Lås skapet (hold lås aktivert)
                        GPIO.output(LOCKER_GPIO_MAP[locker_id], GPIO.LOW)
                        print(f"Skap {locker_id} reservert til bruker.")
                    else:
                        print("Ingen tilgang – åpner igjen.")
                        magnet_release(locker_id)
                except Exception as e:
                    print(f"API-feil: {e}")
                    magnet_release(locker_id)
            else:
                # Timeout, åpne igjen
                magnet_release(locker_id)

        # Reset ved åpning
        elif GPIO.input(close_pin) == GPIO.HIGH:
            skap_lukket_tidligere[locker_id] = False

def reuse_locker():
    """Lytter etter RFID-gjenbruk – åpne skap hvis tilgang"""
    id, text = reader.read_no_block()
    if id:
        try:
            response = requests.post(
                API_URL_SCAN,
                params={
                    "rfid_tag": str(id),
                    "locker_room_id": LOCKER_ROOM_ID
                },
                timeout=2
            )
            res = response.json()
            if res.get("open_locker_id") is not None:
                locker_id = res["open_locker_id"]
                print(f"Åpner skap {locker_id} for eksisterende bruker.")
                magnet_release(locker_id)
        except Exception as e:
            print(f"Gjenbruk API-feil: {e}")

