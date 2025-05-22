import RPi.GPIO as GPIO
import time
import spidev
from fastapi import requests
from mfrc522 import SimpleMFRC522

from backend.model import LockerRoom

# --- Konfigurasjon ---

MAGNETLÅS_PIN = 17
API_URL = "http://localhost:8080/scan_rfid/"  # Endre til FastAPI-serverens adresse/IP
LOCKER_ROOM_ID = 1  # Tilpass etter faktisk garderoberom ID
GPIO.setmode(GPIO.BCM)
GPIO.setup(MAGNETLÅS_PIN, GPIO.OUT)

def magnet_release():
    GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)
    


def reader_helper():

    reader = SimpleMFRC522()
    #try:
    print("Hold kortet inntil leseren...")
    while True:
        (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
        if status == reader.READER.MI_OK:
            print("Kort funnet")
            (status, uid) = reader.READER.MFRC522_Anticoll()
            if status == reader.READER.MI_OK:
                print("UID: ", uid)
                GPIO.output(MAGNETLÅS_PIN, GPIO.HIGH)
                time.sleep(1)
                GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)
                time.sleep(1)
                #magnet_release()

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
    #finally:
        #GPIO.cleanup()

reader_helper()

