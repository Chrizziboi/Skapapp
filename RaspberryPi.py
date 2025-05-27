import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json

# --- Konfigurasjon ---

MAGNETLÅS_PIN = 17

GPIO.setmode(GPIO.BCM)

with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)  # fallback til 1 hvis ikke satt

API_URL = "http://localhost:8080/scan_rfid/"  # Endre til FastAPI-serverens adresse/IP

def magnet_release(pin):
    try:

        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)


    except Exception as e:
        print(f"Pin eksisterer ikke: {e}")


def reader_helper():
    print("[DEBUG] RFID-tråd startet", flush=True)

    reader = SimpleMFRC522()
    print("Hold kortet inntil leseren...")

    while True:
        try:
            (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
            print("READER status:", status)
            if status != reader.READER.MI_OK:
                time.sleep(0.2)
                continue

            print("Kort funnet")
            (status, uid) = reader.READER.MFRC522_Anticoll()
            if status != reader.READER.MI_OK:
                time.sleep(0.2)
                continue

            # Konverter UID til streng
            rfid_tag = "".join([str(num) for num in uid])
            print("UID:", rfid_tag)

            # Send til FastAPI
            response = requests.post(
                API_URL,
                params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                timeout=5
            )
            data = response.json()

            if response.status_code == 200 and data.get("access_granted"):
                print("Tilgang gitt!", data.get("message"))
                magnet_release(MAGNETLÅS_PIN)  # Kun når tilgang er bekreftet
            else:
                print("Tilgang nektet:", data.get("message"))

        except Exception as e:
            print(f"[API-FEIL]: {e}")

        time.sleep(1)