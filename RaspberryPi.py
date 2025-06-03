import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)
LOCKER_GPIO_MAP = {int(k): v for k, v in CONFIG.get("locker_gpio_map", {}).items()}
LOCKER_CLOSE_PIN_MAP = {int(k): v for k, v in CONFIG.get("locker_close_pin_map", {}).items()}

# Initialiser GPIO
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
                if len(rfid_tag) >= 8 and rfid_tag.isdigit():
                    print("[RFID] Funnet:", rfid_tag)
                    return rfid_tag
                else:
                    print("[ADVARSEL] Ugyldig RFID format – ignorerer")
        time.sleep(0.1)

    print("[RFID] Ingen RFID registrert")


def Register_locker(rfid_tag, locker_id):
    """
    Forsøker å koble RFID til skapet etter manuell lukking.
    """
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
                print(f"[TILGANG] RFID godkjent – Skap {assigned_id} låst")
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
    """
    Gjenåpner et skap tilknyttet samme RFID hvis det er lukket igjen.
    """
    try:
        response = requests.post(
            API_URL_SCAN,
            params={
                "rfid_tag": rfid_tag,
                "locker_room_id": LOCKER_ROOM_ID
            },
            timeout=0.5
        )
        data = response.json()
        if response.status_code == 200 and data.get("access_granted"):
            assigned_id = data.get("locker_id")
            gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
            if gpio_pin:
                print(f"[Frigjøring] Åpner skap {assigned_id}")
                magnet_release(gpio_pin)
            return assigned_id
        else:
            print("[RFID] Kortet har ikke tilgang til skap")
    except Exception as e:
        print(f"[API-FEIL]: {e}")


def reader_helper():
    global siste_rfid, siste_skann_tid
    print("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort.")

    while True:
        for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
            is_closed = GPIO.input(close_pin) == GPIO.LOW

            print(f"[DEBUG] Skap {locker_id} (pin {close_pin}) status: {'LUKKET' if is_closed else 'ÅPEN'} | Tidligere lukket: {skap_lukket_tidligere[locker_id]}")

            if is_closed:
                if skap_lukket_tidligere[locker_id]:
                    continue

                print(f"[INNGANG] Skap {locker_id} lukket – initierer RFID-registrering")
                rfid_tag = scan_for_rfid(timeout=6)

                nå = time.time()
                if rfid_tag:
                    if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
                        print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (for rask skanning).")
                        continue

                    siste_rfid = rfid_tag
                    siste_skann_tid = nå

                    skap_lukket_tidligere[locker_id] = True
                    print(f"[STATUS] Registrerer skap {locker_id} med RFID {rfid_tag}")

                    try:
                        Register_locker(rfid_tag, locker_id)
                    except Exception as e:
                        print(f"[FEIL] Register_locker feilet: {e}")
                    time.sleep(1.5)

                else:
                    print(f"[TIDSKUTT] Ingen RFID registrert for skap {locker_id}.")
                    skap_lukket_tidligere[locker_id] = True  # Hindre ny registrering uten RFID
                    magnet_release(gpio_pin)

            else:
                if skap_lukket_tidligere[locker_id]:
                    print(f"[STATUS] Skap {locker_id} åpnet igjen – nullstiller status")
                    skap_lukket_tidligere[locker_id] = False

        # --- Gjenbruk: RFID gir tilgang til tidligere reservert skap ---
        rfid_tag = scan_for_rfid(timeout=1)
        if not rfid_tag:
            continue

        nå = time.time()
        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
            print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (gjenbruk).")
            continue

        siste_rfid = rfid_tag
        siste_skann_tid = nå
        print(f"[GJENBRUK] RFID {rfid_tag} forsøker åpning av tidligere skap")
        Reuse_locker_id = Reuse_locker(rfid_tag)
        skap_lukket_tidligere[Reuse_locker_id] = True
        time.sleep(1.5)
