import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

MAGNETLÅS_PIN = 21
SKAPLUKK_PIN = 20

GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)

GPIO.setup(SKAPLUKK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)  # fallback til 1 hvis ikke satt

API_URL = "http://localhost:8080/assign_after_closure/"  # NYTT endpoint

#API_URL = "http://localhost:8080/scan_rfid/"  # Endre til FastAPI-serverens adresse/IP

def magnet_release(pin):
    try:

        #GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)


    except Exception as e:
        print(f"Pin eksisterer ikke: {e}")

def scan_for_rfid(timeout=2):
    reader = SimpleMFRC522()
    start_time = time.time()
    print("[RFID] Klar for skanning...")

    while time.time() - start_time < timeout:
        (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
        print(f"[DEBUG]{status}")
        if status == reader.READER.MI_OK:
            (status, uid) = reader.READER.MFRC522_Anticoll()
            if status == reader.READER.MI_OK:
                rfid_tag = "".join([str(num) for num in uid])
                print("[RFID] Funnet:", rfid_tag)
                return rfid_tag
        time.sleep(0.1)

    print("[RFID] Ingen RFID registrert")
    return None

def reader_helper():
    print("[DEBUG] RFID-tråd startet", flush=True)
    GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)  # Sikrer at skap er åpent ved oppstart

    while True:
        # Sjekk om skaplukk-knappen/sensoren har blitt aktivert
        if GPIO.input(SKAPLUKK_PIN) == GPIO.HIGH:
            print("[INNGANG] Skap lukket – venter på RFID")

            rfid_tag = scan_for_rfid(timeout=2)

            if rfid_tag:
                try:
                    response = requests.post(
                        API_URL,
                        params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                        timeout=5
                    )
                    data = response.json()

                    if response.status_code == 200 and data.get("access_granted"):
                        print("RFID registrert, tilgang gitt:", data.get("message"))
                        GPIO.output(MAGNETLÅS_PIN, GPIO.HIGH)  # Lås skapet
                    else:
                        print("Ukjent RFID – skap forblir åpent")
                        GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)
                except Exception as e:
                    print(f"[API-FEIL]: {e}")
                    GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)
            else:
                print("Ingen RFID skannet – deaktiverer lås")
                GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)

            # Vent til signalet faller (skap åpnet igjen) før neste deteksjon
            while GPIO.input(SKAPLUKK_PIN) == GPIO.HIGH:
                time.sleep(0.1)

        time.sleep(0.1)


"""
def reader_helper():
    print("[DEBUG] RFID-tråd startet", flush=True)
    GPIO.output(MAGNETLÅS_PIN, GPIO.LOW)

    reader = SimpleMFRC522()
    print("Hold kortet inntil leseren...")

    while True:
        try:
            (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
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
"""
#time.sleep(1)