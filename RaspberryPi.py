import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

#SKAPLUKK_PIN = 20  # Inputsignal når skapet fysisk lukkes
#SKAPLUKK_PIN = 19

# Last inn konfigurasjon
with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)
LOCKER_GPIO_MAP = {int(k): v for k, v in CONFIG.get("locker_gpio_map", {}).items()}
LOCKER_CLOSE_PIN_MAP = {int(k): v for k, v in CONFIG.get("locker_close_pin_map", {}).items()}

# Sett opp alle skaplåspins og sørg for at de er åpne ved oppstart
for gpio_pin in LOCKER_GPIO_MAP.values():
    GPIO.setup(gpio_pin, GPIO.OUT)
    GPIO.output(gpio_pin, GPIO.LOW)

for close_pin in LOCKER_CLOSE_PIN_MAP.values():
    GPIO.setup(close_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

API_URL_REG = "http://localhost:8080/assign_after_closure/"
API_URL_SCAN = "http://localhost:8080/scan_rfid/"

def magnet_release(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)


def scan_for_rfid(timeout=5, init_delay=0):
    time.sleep(init_delay)
    if init_delay > 0:
        print(f"[RFID] Initieringsforsinkelse: {init_delay}s")
        time.sleep(init_delay)

    reader = SimpleMFRC522()

    start_time = time.time()
    print("[RFID] Klar for skanning...")

    while time.time() - start_time < timeout:
        (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
        if status == reader.READER.MI_OK:
            (status, uid) = reader.READER.MFRC522_Anticoll()
            if status == reader.READER.MI_OK:
                rfid_tag = "".join([str(num) for num in uid])
                print("[RFID] Funnet:", rfid_tag)
                return rfid_tag
        time.sleep(0.1)

    print("[RFID] Ingen RFID registrert")
    return None



skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
siste_rfid = None
siste_skann_tid = 0

def reader_helper():
    print("[SYSTEM] RFID-løkke startet. Skapene er passivt åpne.")
    global siste_rfid, siste_skann_tid

    while True:
        rfid_tag = scan_for_rfid()
        if not rfid_tag:
            continue

        nå = time.time()
        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
            print(f"[RFID] Ignorerer duplikatskann av {rfid_tag}")
            continue

        siste_rfid = rfid_tag
        siste_skann_tid = nå

        # Sjekk om RFID allerede er koblet til skap
        try:
            response = requests.post(
                API_URL_SCAN,
                params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                timeout=0.5
            )
            data = response.json()
        except Exception as e:
            print(f"[API-FEIL]: {e}")
            continue

        if response.status_code == 200 and data.get("access_granted"):
            Reuse_locker(rfid_tag)
        else:
            Register_locker(rfid_tag)

def Register_locker(rfid_tag):
    for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
        if GPIO.input(close_pin) == GPIO.LOW and not skap_lukket_tidligere[locker_id]:
            print(f"[INNGANG] Skap {locker_id} lukket – forsøker å registrere RFID: {rfid_tag}")
            skap_lukket_tidligere[locker_id] = True

            try:
                response = requests.post(
                    API_URL_REG,
                    params={
                        "rfid_tag": rfid_tag,
                        "locker_room_id": LOCKER_ROOM_ID,
                        "locker_id": locker_id
                    },
                    timeout=0.5
                )
                data = response.json()

                if response.status_code == 200 and data.get("access_granted"):
                    assigned_id = data.get("locker_id")
                    gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
                    if gpio_pin is not None:
                        print(f"[TILGANG] RFID godkjent. Aktiverer skap {assigned_id} på pin {gpio_pin}")
                else:
                    print("[RFID] RFID ikke godkjent – frigjør skap igjen")
                    gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                    if gpio_pin is not None:
                        magnet_release(gpio_pin)

            except Exception as e:
                print(f"[API-FEIL]: {e}")
                gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                if gpio_pin is not None:
                    magnet_release(gpio_pin)

def Reuse_locker(rfid_tag):
    for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
        if GPIO.input(close_pin) == GPIO.HIGH:
            skap_lukket_tidligere[locker_id] = False
            try:
                response = requests.post(
                    API_URL_SCAN,
                    params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                    timeout=0.5
                )
                data = response.json()

                if response.status_code == 200 and data.get("access_granted"):
                    assigned_id = data.get("locker_id")
                    gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
                    print(f"[DEBUG] locker_id={assigned_id}, gpio_pin={gpio_pin}")
                    if gpio_pin is not None:
                        print(f"[GJENBRUK] Åpner skap {assigned_id} på pin {gpio_pin}")
                        magnet_release(gpio_pin)
                else:
                    print("[RFID] Ingen tilgang – kortet er ikke koblet til noe skap")

            except Exception as e:
                print(f"[API-FEIL]: {e}")
