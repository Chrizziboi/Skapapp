# RaspberryPi.py (kun DIREKTE bruk av pins – ALT hardkodet)

import RPi.GPIO as GPIO
import time
import requests
from mfrc522 import SimpleMFRC522

# --- KONSTANTER ---
LOCKER_ROOM_ID = 1
RFID_TIMEOUT_SEC = 8

# Skap 1: Magnetlås GPIO 21, dørsensor GPIO 20
SKAP1_MAGNET_PIN = 21
SKAP1_SENSOR_PIN = 20

# Skap 2: Magnetlås GPIO 26, dørsensor GPIO 19
SKAP2_MAGNET_PIN = 26
SKAP2_SENSOR_PIN = 19

API_URL_REG = "http://localhost:8080/assign_after_closure/"
API_URL_SCAN = "http://localhost:8080/scan_rfid/"

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Sett opp utganger og innganger direkte:
GPIO.setup(SKAP1_MAGNET_PIN, GPIO.OUT)
GPIO.output(SKAP1_MAGNET_PIN, GPIO.LOW)
GPIO.setup(SKAP2_MAGNET_PIN, GPIO.OUT)
GPIO.output(SKAP2_MAGNET_PIN, GPIO.LOW)

GPIO.setup(SKAP1_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(SKAP2_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

skap1_lukket_tidligere = False
skap2_lukket_tidligere = False

reader = SimpleMFRC522()

def magnet_release(magnet_pin):
    GPIO.output(magnet_pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(magnet_pin, GPIO.LOW)

def scan_for_rfid(timeout=RFID_TIMEOUT_SEC):
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
    global skap1_lukket_tidligere, skap2_lukket_tidligere

    # Skap 1
    if GPIO.input(SKAP1_SENSOR_PIN) == GPIO.LOW and not skap1_lukket_tidligere:
        print("[INNGANG] Skap 1 lukket – aktiverer RFID-skanning")
        skap1_lukket_tidligere = True

        rfid_tag = scan_for_rfid()
        if rfid_tag:
            try:
                response = requests.post(
                    API_URL_REG,
                    params={
                        "rfid_tag": rfid_tag,
                        "locker_room_id": LOCKER_ROOM_ID,
                        "locker_id": 1
                    },
                    timeout=2
                )
                res = response.json()
                print(f"Backend-respons: {res}")
                if res.get("success"):
                    GPIO.output(SKAP1_MAGNET_PIN, GPIO.LOW)
                    print("Skap 1 reservert til bruker.")
                else:
                    print("Ingen tilgang – åpner igjen.")
                    magnet_release(SKAP1_MAGNET_PIN)
            except Exception as e:
                print(f"API-feil: {e}")
                magnet_release(SKAP1_MAGNET_PIN)
        else:
            magnet_release(SKAP1_MAGNET_PIN)

    elif GPIO.input(SKAP1_SENSOR_PIN) == GPIO.HIGH:
        skap1_lukket_tidligere = False

    # Skap 2
    if GPIO.input(SKAP2_SENSOR_PIN) == GPIO.LOW and not skap2_lukket_tidligere:
        print("[INNGANG] Skap 2 lukket – aktiverer RFID-skanning")
        skap2_lukket_tidligere = True

        rfid_tag = scan_for_rfid()
        if rfid_tag:
            try:
                response = requests.post(
                    API_URL_REG,
                    params={
                        "rfid_tag": rfid_tag,
                        "locker_room_id": LOCKER_ROOM_ID,
                        "locker_id": 2
                    },
                    timeout=2
                )
                res = response.json()
                print(f"Backend-respons: {res}")
                if res.get("success"):
                    GPIO.output(SKAP2_MAGNET_PIN, GPIO.LOW)
                    print("Skap 2 reservert til bruker.")
                else:
                    print("Ingen tilgang – åpner igjen.")
                    magnet_release(SKAP2_MAGNET_PIN)
            except Exception as e:
                print(f"API-feil: {e}")
                magnet_release(SKAP2_MAGNET_PIN)
        else:
            magnet_release(SKAP2_MAGNET_PIN)

    elif GPIO.input(SKAP2_SENSOR_PIN) == GPIO.HIGH:
        skap2_lukket_tidligere = False

def reuse_locker():
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
            if res.get("open_locker_id") == 1:
                print("Åpner skap 1 for eksisterende bruker.")
                magnet_release(SKAP1_MAGNET_PIN)
            elif res.get("open_locker_id") == 2:
                print("Åpner skap 2 for eksisterende bruker.")
                magnet_release(SKAP2_MAGNET_PIN)
        except Exception as e:
            print(f"Gjenbruk API-feil: {e}")

def main_loop():
    print("[SYSTEM] RaspberryPi skaplås-system starter (ALT hardkodet)...")
    try:
        while True:
            register_locker()
            reuse_locker()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Avslutter og rydder opp GPIO.")
    finally:
        GPIO.cleanup()

