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

# Tilstandssporing med debouncing
skap_tilstand = {}
for locker_id in LOCKER_CLOSE_PIN_MAP:
    skap_tilstand[locker_id] = {
        'siste_status': None,  # None, True (lukket), False (åpen)
        'status_endret_tid': 0,
        'behandlet_lukking': False,
        'behandlet_åpning': False
    }

siste_rfid = None
siste_skann_tid = 0

# Debounce tid i sekunder
DEBOUNCE_TID = 0.5


def magnet_release(pin):
    print(f"[MAGNET] Åpner lås på GPIO pin {pin}")
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)
    print(f"[MAGNET] Lås på GPIO pin {pin} deaktivert")


def les_skap_status(close_pin):
    """
    Les skap status med debouncing
    """
    return GPIO.input(close_pin) == GPIO.LOW  # LOW = lukket


def scan_for_rfid(timeout=5, init_delay=0):
    time.sleep(init_delay)
    reader = SimpleMFRC522()
    start_time = time.time()
    print("[RFID] Klar for skanning...")

    while time.time() - start_time < timeout:
        try:
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
        except Exception as e:
            print(f"[RFID-FEIL] {e}")
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
            print(f"[TILGANG] RFID godkjent – Skap {assigned_id} låst og registrert")
        else:
            print("[RFID] Ikke godkjent – frigjør skap")
            gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
            if gpio_pin:
                magnet_release(gpio_pin)
    except Exception as e:
        print(f"[API-FEIL]: {e}")
        # Ved API-feil, frigjør skapet
        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
        if gpio_pin:
            magnet_release(gpio_pin)


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
                print(f"[FRIGJØRING] Åpner skap {assigned_id}")
                magnet_release(gpio_pin)
        else:
            print("[RFID] Kortet har ikke tilgang til skap")
    except Exception as e:
        print(f"[API-FEIL]: {e}")


def behandle_skap_lukking(locker_id):
    """
    Behandler når et skap blir lukket
    """
    print(f"[LUKKING] Skap {locker_id} lukket – starter RFID-registrering")

    # Vent litt for å la systemet stabilisere seg
    time.sleep(0.2)

    rfid_tag = scan_for_rfid(timeout=6)

    nå = time.time()
    global siste_rfid, siste_skann_tid

    if rfid_tag:
        if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
            print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (for rask skanning)")
            return

        siste_rfid = rfid_tag
        siste_skann_tid = nå

        print(f"[REGISTRERING] Registrerer skap {locker_id} med RFID {rfid_tag}")

        try:
            Register_locker(rfid_tag, locker_id)
        except Exception as e:
            print(f"[FEIL] Register_locker feilet: {e}")
    else:
        print(f"[AUTO-ÅPNING] Ingen RFID registrert for skap {locker_id} – åpner automatisk")
        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
        if gpio_pin:
            magnet_release(gpio_pin)
        else:
            print(f"[FEIL] Ingen GPIO pin funnet for skap {locker_id}")


def behandle_gjenbruk_rfid():
    """
    Behandler RFID-skanning for gjenbruk av eksisterende skap
    """
    rfid_tag = scan_for_rfid(timeout=1)
    if not rfid_tag:
        return

    nå = time.time()
    global siste_rfid, siste_skann_tid

    if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
        print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (gjenbruk)")
        return

    siste_rfid = rfid_tag
    siste_skann_tid = nå
    print(f"[GJENBRUK] RFID {rfid_tag} forsøker åpning av tidligere skap")
    Reuse_locker(rfid_tag)


def reader_helper():
    print("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort")

    while True:
        try:
            # Sjekk alle skap for statusendringer
            for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
                nåværende_status = les_skap_status(close_pin)
                tilstand = skap_tilstand[locker_id]
                nå = time.time()

                # Hvis status har endret seg
                if tilstand['siste_status'] != nåværende_status:
                    print(f"[DEBUG] Skap {locker_id} statusendring: {tilstand['siste_status']} -> {nåværende_status}")
                    tilstand['siste_status'] = nåværende_status
                    tilstand['status_endret_tid'] = nå
                    tilstand['behandlet_lukking'] = False
                    tilstand['behandlet_åpning'] = False

                # Hvis statusen har vært stabil i debounce-perioden
                elif nå - tilstand['status_endret_tid'] > DEBOUNCE_TID:

                    # Skap er lukket og vi har ikke behandlet denne lukkingen ennå
                    if nåværende_status and not tilstand['behandlet_lukking']:
                        tilstand['behandlet_lukking'] = True
                        behandle_skap_lukking(locker_id)

                    # Skap er åpnet og vi har ikke behandlet denne åpningen ennå
                    elif not nåværende_status and not tilstand['behandlet_åpning']:
                        tilstand['behandlet_åpning'] = True
                        print(f"[ÅPNING] Skap {locker_id} åpnet")

            # Behandle RFID for gjenbruk (bare hvis ingen skap-hendelser pågår)
            alle_stabile = all(
                time.time() - tilstand['status_endret_tid'] > DEBOUNCE_TID
                for tilstand in skap_tilstand.values()
            )

            if alle_stabile:
                behandle_gjenbruk_rfid()

            time.sleep(0.1)  # Kort pause for å unngå CPU-overbelastning

        except Exception as e:
            print(f"[HOVEDLØKKE-FEIL] {e}")
            time.sleep(1)  # Lengre pause ved feil