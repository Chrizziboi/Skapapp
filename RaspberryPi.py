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
                print("[RFID] Funnet:", rfid_tag)
                return rfid_tag
        time.sleep(0.1)

    print("[RFID] Ingen RFID registrert")
    return None


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
        else:
            print("[RFID] Kortet har ikke tilgang til skap")
    except Exception as e:
        print(f"[API-FEIL]: {e}")


def reader_helper():
    """
    Hovedløkke som:
    1. Reagerer på manuell lukking av skap (triggerer RFID og registrering).
    2. Tillater brukere med opptatte skap å åpne igjen via ny RFID-skanning.
    """
    global siste_rfid, siste_skann_tid
    print("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort.")

    while True:
        # --- Registrer ved ny lukking ---
        for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
            Locker_closed =  GPIO.input(close_pin) == GPIO.LOW

            if Locker_closed and not skap_lukket_tidligere[locker_id]:
                print(f"[INNGANG] Skap {locker_id} lukket – klar for ny registrering.")
                skap_lukket_tidligere[locker_id] = True

                # Skann for kort umiddelbart ved lukking
                rfid_tag = scan_for_rfid(timeout=6)  # Gi brukeren tid til å skanne

                nå = time.time()
                if rfid_tag:
                    if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
                        print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (registrering).")
                        continue

                    siste_rfid = rfid_tag
                    siste_skann_tid = nå
                    Register_locker(rfid_tag, locker_id)
                    time.sleep(1.5)
                else:
                    print("[TIDSKUTT] Ingen RFID – frigjør skap.")
                    gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                    if gpio_pin:
                        magnet_release(gpio_pin)

            if not Locker_closed:
                skap_lukket_tidligere[locker_id] = False

        # --- Tillat åpning av opptatte skap via RFID ---
        rfid_tag = scan_for_rfid(timeout=1)  # Kort timeout for responsivitet
        if not rfid_tag:
            continue

        nå = time.time()
        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
            print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (gjenbruk).")
            continue

        siste_rfid = rfid_tag
        siste_skann_tid = nå
        Reuse_locker(rfid_tag)
        time.sleep(1.5)