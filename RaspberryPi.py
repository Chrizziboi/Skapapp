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
API_URL_ADM = "http://localhost:8080/lockers/manual_release/"

skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
siste_rfid = None
siste_skann_tid = 0

# Debounce-tilstand for hvert skap
locker_state = {locker_id: {"last_state": None, "last_change": time.time()} for locker_id in LOCKER_CLOSE_PIN_MAP}
DEBOUNCE_TIME = 1.0  # sekunder

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

def manual_release_locker(locker_id):
    """
    Frigjør (åpner) skapet med gitt locker_id etter å ha fått bekreftelse fra backend.
    """
    response = requests.put(
        API_URL_ADM,
        params={
            "locker_id": locker_id,
            "locker_room_id": LOCKER_ROOM_ID
        },
        timeout=0.5
    )
    print(f"manual_release_locker: status={response.status_code}, body={response.text}")
    data = response.json()
    if response.status_code == 200 and data.get("access_granted"):
        print(f"[Manuell frigjøring] Åpner skap {locker_id}")
        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
        if gpio_pin:
            magnet_release(gpio_pin)
        return locker_id
    else:
        print("[Manuell frigjøring] Fikk ikke tilgang til å åpne skapet")
        return None

def reader_helper():
    global siste_rfid, siste_skann_tid
    print("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort.")

    while True:
        for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
            is_closed = GPIO.input(close_pin) == GPIO.LOW
            now = time.time()
            state_info = locker_state[locker_id]

            # Hvis tilstanden har endret seg
            if is_closed != state_info["last_state"]:
                state_info["last_change"] = now
                state_info["last_state"] = is_closed

            if is_closed and not skap_lukket_tidligere[locker_id]:
                if now - state_info["last_change"] >= DEBOUNCE_TIME:
                    print(f"[INNGANG] Skap {locker_id} nettopp lukket – starter registrering")
                    rfid_tag = scan_for_rfid(timeout=6)
                    nå = time.time()
                    if rfid_tag:
                        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
                            print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (for rask skanning).")
                            continue
                        siste_rfid = rfid_tag
                        siste_skann_tid = nå
                        print(f"[STATUS] Registrerer skap {locker_id} med RFID {rfid_tag}")
                        try:
                            Register_locker(rfid_tag, locker_id)
                        except Exception as e:
                            print(f"[FEIL] Register_locker feilet: {e}")
                        time.sleep(1.5)
                    else:
                        print(f"[TIDSKUTT] Ingen RFID registrert for skap {locker_id}.")
                        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
                        if gpio_pin is not None:
                            magnet_release(gpio_pin)
                        else:
                            print(f"[FEIL] Fant ikke gpio_pin for skap {locker_id}")
                    skap_lukket_tidligere[locker_id] = True

            elif not is_closed and skap_lukket_tidligere[locker_id]:
                if now - state_info["last_change"] >= DEBOUNCE_TIME:
                    print(f"[STATUS] Skap {locker_id} nettopp åpnet – klar for ny syklus")
                    skap_lukket_tidligere[locker_id] = False

                    # --- Failsafe sjekk ---
                    try:
                        response = requests.get("http://localhost:8080/lockers/RBPI/occupied", timeout=0.5)
                        occupied_ids = response.json()
                        if locker_id in occupied_ids:
                            print(
                                f"[FAILSAFE] Skap {locker_id} ble fysisk åpnet mens det fortsatt er registrert som opptatt!")
                            try:
                                release_response = requests.put(
                                    "http://localhost:8080/lockers/manual_release/",
                                    params={"locker_id": locker_id, "locker_room_id": LOCKER_ROOM_ID},
                                    timeout=0.5
                                )
                                if release_response.status_code == 200 and release_response.json().get(
                                        "access_granted"):
                                    print(f"[FAILSAFE] Skap {locker_id} er manuelt frigjort via backend.")
                                else:
                                    print(f"[FAILSAFE] Backend avslo manuell frigjøring: {release_response.text}")
                            except Exception as e:
                                print(f"[FAILSAFE] Klarte ikke kontakte backend for manuell frigjøring: {e}")
                    except Exception as e:
                        print(f"[FAILSAFE] Feil ved sjekk av opptatt status: {e}")

        # --- Gjenbruk ---
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
        reuse_locker_id = Reuse_locker(rfid_tag)
        if reuse_locker_id is not None and reuse_locker_id in skap_lukket_tidligere:
            skap_lukket_tidligere[reuse_locker_id] = False
        time.sleep(1.5)
