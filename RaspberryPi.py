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

def magnet_release(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)

def scan_for_rfid(timeout=5, init_delay=0):
    if init_delay > 0:
        print(f"[RFID] Venter {init_delay}s før skanning...")
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

def reader_helper():
    print("[SYSTEM] RFID-løkke startet. Skapene er passivt åpne.")

    skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
    last_rfid = None
    last_scan_time = 0

    while True:
        for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
            # === REGISTRERING AV NY RFID ETTER LUKKING ===
            if GPIO.input(close_pin) == GPIO.LOW and not skap_lukket_tidligere[locker_id]:
                print(f"[INNGANG] Skap {locker_id} lukket – aktiverer RFID-skanning")
                skap_lukket_tidligere[locker_id] = True

                rfid_tag = scan_for_rfid(timeout=5)

                if rfid_tag:
                    try:
                        response = requests.post(
                            API_URL_REG,
                            params={
                                "rfid_tag": rfid_tag,
                                "locker_room_id": LOCKER_ROOM_ID,
                                "locker_id": locker_id
                            },
                            timeout=1
                        )
                        data = response.json()
                        if response.status_code == 200 and data.get("access_granted"):
                            assigned_id = data.get("locker_id")
                            gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
                            if gpio_pin is not None:
                                print(f"[TILGANG] RFID godkjent. Aktiverer skap {assigned_id} på pin {gpio_pin}")
                            else:
                                print(f"[FEIL] Ingen GPIO definert for locker_id {assigned_id}")
                        else:
                            print("[RFID] RFID ikke godkjent – frigjør skap igjen")
                            gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                            if gpio_pin is not None:
                                magnet_release(gpio_pin)
                    except Exception as e:
                        print(f"[API-FEIL]: {e}")
                else:
                    print("[TIDSKUTT] Ingen RFID registrert – frigjør skap igjen")
                    gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                    if gpio_pin is not None:
                        magnet_release(gpio_pin)

            # === GJENBRUK AV SKAP ===
            elif GPIO.input(close_pin) == GPIO.HIGH:
                skap_lukket_tidligere[locker_id] = False

                rfid_tag = scan_for_rfid(timeout=5, init_delay=2)

                if rfid_tag:
                    if rfid_tag == last_rfid and time.time() - last_scan_time < 3:
                        print("[IGNORERT] Duplikat skanning – hopper over.")
                        continue

                    last_rfid = rfid_tag
                    last_scan_time = time.time()

                    try:
                        response = requests.post(
                            API_URL_SCAN,
                            params={"rfid_tag": rfid_tag, "locker_room_id": LOCKER_ROOM_ID},
                            timeout=1
                        )
                        data = response.json()
                        if response.status_code == 200 and data.get("access_granted"):
                            assigned_id = data.get("locker_id")
                            gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
                            if gpio_pin is not None:
                                print(f"[GJENBRUK] Åpner skap {assigned_id} på pin {gpio_pin}")
                                magnet_release(gpio_pin)
                            else:
                                print(f"[FEIL] Ingen GPIO definert for locker_id {assigned_id}")
                        else:
                            print("[RFID] Ingen tilgang – kortet er ikke koblet til noe skap")
                    except Exception as e:
                        print(f"[API-FEIL]: {e}")

        time.sleep(0.1)
