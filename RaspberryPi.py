import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Last inn konfigurasjon
with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)
LOCKER_GPIO_MAP = {int(k): v for k, v in CONFIG.get("locker_gpio_map", {}).items()}
LOCKER_CLOSE_PIN_MAP = {int(k): v for k, v in CONFIG.get("locker_close_pin_map", {}).items()}

# Sett opp GPIO
for gpio_pin in LOCKER_GPIO_MAP.values():
    GPIO.setup(gpio_pin, GPIO.OUT)
    GPIO.output(gpio_pin, GPIO.LOW)

for close_pin in LOCKER_CLOSE_PIN_MAP.values():
    GPIO.setup(close_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

API_URL_REG = "http://localhost:8080/assign_after_closure/"
API_URL_SCAN = "http://localhost:8080/scan_rfid/"

skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
siste_rfid = None
siste_skann_tid = 0


def magnet_release(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)


def scan_for_rfid(timeout=5, init_delay=0):
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


def handle_rfid_scan(rfid_tag):
    try:
        response = requests.post(
            API_URL_SCAN,
            params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
            timeout=0.5
        )
        data = response.json()
    except Exception as e:
        print(f"[API-FEIL]: {e}")
        return

    if response.status_code == 200 and data.get("access_granted"):
        Reuse_locker(rfid_tag)
    else:
        Register_locker(rfid_tag)


def Register_locker(rfid_tag):
    for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
        if GPIO.input(close_pin) == GPIO.LOW and not skap_lukket_tidligere[locker_id]:
            print(f"[INNGANG] Skap {locker_id} lukket – aktiverer RFID-kobling")
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
                    if gpio_pin:
                        print(f"[TILGANG] Skap {assigned_id} låst")
                    else:
                        print(f"[FEIL] Mangler GPIO for skap {assigned_id}")
                else:
                    print("[RFID] Ikke godkjent – frigjør skap")
                    gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                    if gpio_pin:
                        magnet_release(gpio_pin)
            except Exception as e:
                print(f"[API-FEIL]: {e}")


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
                    if gpio_pin:
                        print(f"[GJENBRUK] Åpner skap {assigned_id}")
                        magnet_release(gpio_pin)
                else:
                    print("[RFID] Kortet har ikke tilgang")
            except Exception as e:
                print(f"[API-FEIL]: {e}")


def reader_helper():
    print("[SYSTEM] RFID-løkke startet. Skapene er passivt åpne.")
    global siste_rfid, siste_skann_tid

    while True:
        rfid_tag = scan_for_rfid()
        if not rfid_tag:
            continue

        siste_rfid = rfid_tag

        nå = time.time()
        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
            print(f"[RFID] Ignorerer duplikatskann av {rfid_tag}")
            continue

        siste_skann_tid = nå

        handle_rfid_scan(rfid_tag)