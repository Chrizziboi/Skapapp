import RPi.GPIO as GPIO
import time
import spidev
from fastapi import requests
from mfrc522 import SimpleMFRC522

from backend.model import LockerRoom

# --- Konfigurasjon ---

MAGNETLÅS_PIN = 2
API_URL = "http://localhost:8080/scan_rfid/"  # Endre til FastAPI-serverens adresse/IP
LOCKER_ROOM_ID = LockerRoom.id  # Tilpass etter faktisk garderoberom ID


def magnet_release():
    GPIO.setmode(GPIO.BCM)
    lock = 2
    GPIO.setup(lock, GPIO.OUT)

    GPIO.output(lock, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(lock, GPIO.LOW)
    time.sleep(1)


def reader_helper():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MAGNETLÅS_PIN, GPIO.OUT)
    GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)

    reader = SimpleMFRC522()
    try:
        print("Hold kortet inntil leseren...")
        while True:
            id, _ = reader.read()
            rfid_tag = str(id)
            print(f"Skannet tag: {rfid_tag}")

            try:
                response = requests.post(
                    API_URL,
                    params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                    timeout=5
                )
                data = response.json()
                if response.status_code == 200 and data.get("access_granted"):
                    print("Tilgang gitt!", data.get("message"))
                    magnet_release()
                else:
                    print("Tilgang nektet:", data.get("message"))
            except Exception as e:
                print(f"API-feil: {e}")

            time.sleep(1)
    finally:
        GPIO.cleanup()



