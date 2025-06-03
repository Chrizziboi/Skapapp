import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json
import logging
from locker_state import LockerState

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

# Initialiser tilstandshåndtering
locker_states = {
    locker_id: LockerState(locker_id, LOCKER_GPIO_MAP[locker_id], close_pin)
    for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items()
}

siste_rfid = None
siste_skann_tid = 0


def magnet_release(pin):
    try:
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)
        logging.info(f"Magnetlås på pin {pin} frigjort")
    except Exception as e:
        logging.error(f"Feil ved frigjøring av magnetlås på pin {pin}: {e}")


def scan_for_rfid(timeout=5, init_delay=0):
    time.sleep(init_delay)
    reader = SimpleMFRC522()
    start_time = time.time()
    logging.info("[RFID] Klar for skanning...")

    while time.time() - start_time < timeout:
        try:
            (status, TagType) = reader.READER.MFRC522_Request(reader.READER.PICC_REQIDL)
            if status == reader.READER.MI_OK:
                (status, uid) = reader.READER.MFRC522_Anticoll()
                if status == reader.READER.MI_OK:
                    rfid_tag = "".join([str(num) for num in uid])
                    if len(rfid_tag) >= 8 and rfid_tag.isdigit():
                        logging.info(f"[RFID] Funnet: {rfid_tag}")
                        return rfid_tag
                    else:
                        logging.warning("[ADVARSEL] Ugyldig RFID format – ignorerer")
        except Exception as e:
            logging.error(f"[RFID] Feil ved skanning: {e}")
        time.sleep(0.1)

    logging.info("[RFID] Ingen RFID registrert")
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
                logging.info(f"[TILGANG] RFID godkjent – Skap {assigned_id} låst")
            else:
                logging.error(f"[FEIL] Mangler GPIO for skap {assigned_id}")
        else:
            logging.info("[RFID] Ikke godkjent – frigjør skap")
            gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
            if gpio_pin:
                magnet_release(gpio_pin)
    except Exception as e:
        logging.error(f"[API-FEIL]: {e}")
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
                logging.info(f"[Frigjøring] Åpner skap {assigned_id}")
                magnet_release(gpio_pin)
            return assigned_id
        else:
            logging.info("[RFID] Kortet har ikke tilgang til skap")
    except Exception as e:
        logging.error(f"[API-FEIL]: {e}")
    return None


def reader_helper():
    global siste_rfid, siste_skann_tid
    logging.info("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort.")

    while True:
        try:
            for locker_id, state in locker_states.items():
                if state.update_state():  # Kun hvis det er en validert tilstandsendring
                    if state.get_state():  # Skap er lukket
                        logging.info(f"[INNGANG] Skap {locker_id} nettopp lukket – starter registrering")
                        rfid_tag = scan_for_rfid(timeout=6)

                        nå = time.time()
                        if rfid_tag:
                            if rfid_tag == siste_rfid and nå - siste_skann_tid < 2:
                                logging.info(f"[DUPLIKAT] RFID {rfid_tag} ignorert (for rask skanning).")
                                continue

                            siste_rfid = rfid_tag
                            siste_skann_tid = nå

                            try:
                                Register_locker(rfid_tag, locker_id)
                            except Exception as e:
                                logging.error(f"[FEIL] Register_locker feilet: {e}")
                                magnet_release(state.gpio_pin)
                        else:
                            logging.info(f"[TIDSKUTT] Ingen RFID registrert for skap {locker_id}.")
                            magnet_release(state.gpio_pin)

            # Gjenbrukslogikk med forbedret feilhåndtering
            try:
                rfid_tag = scan_for_rfid(timeout=1)
                if rfid_tag:
                    nå = time.time()
                    if not (rfid_tag == siste_rfid and nå - siste_skann_tid < 2):
                        siste_rfid = rfid_tag
                        siste_skann_tid = nå
                        logging.info(f"[GJENBRUK] RFID {rfid_tag} forsøker åpning av tidligere skap")
                        Reuse_locker(rfid_tag)
            except Exception as e:
                logging.error(f"[FEIL] Gjenbruksløkke feilet: {e}")

            time.sleep(0.1)  # Kort pause for å unngå CPU-overbelastning

        except Exception as e:
            logging.error(f"[KRITISK FEIL] i hovedløkken: {e}")
            time.sleep(1)  # Vent litt før vi fortsetter ved kritisk feil