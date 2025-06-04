import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json
import logging
from locker_state import LockerState
from threading import Timer

# --- Konfigurasjon ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Maksimal tid en magnetlås kan være aktivert (i sekunder)
MAX_MAGNET_ACTIVATION_TIME = 1.0

class MagnetWatchdog:
    def __init__(self, pin):
        self.pin = pin
        self.timer = None

    def start(self):
        self.timer = Timer(MAX_MAGNET_ACTIVATION_TIME, self.force_deactivate)
        self.timer.start()

    def cancel(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def force_deactivate(self):
        logging.error(f"WATCHDOG: Tvungen deaktivering av pin {self.pin} - var aktiv for lenge!")
        try:
            GPIO.output(self.pin, GPIO.LOW)
        except:
            pass

# Opprett watchdogs for alle magnetlåser
magnet_watchdogs = {
    pin: MagnetWatchdog(pin) for pin in LOCKER_GPIO_MAP.values()
}

with open("config.json", "r") as config_file:
    CONFIG = json.load(config_file)

LOCKER_ROOM_ID = CONFIG.get("locker_room_id", 1)
LOCKER_GPIO_MAP = {int(k): v for k, v in CONFIG.get("locker_gpio_map", {}).items()}
LOCKER_CLOSE_PIN_MAP = {int(k): v for k, v in CONFIG.get("locker_close_pin_map", {}).items()}

# Initialiser GPIO og sikre at alle pinner starter i LOW
for gpio_pin in LOCKER_GPIO_MAP.values():
    GPIO.setup(gpio_pin, GPIO.OUT)
    GPIO.output(gpio_pin, GPIO.LOW)
    logging.info(f"Initialiserer magnetlås pin {gpio_pin} til LOW")

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

def safe_gpio_high(pin):
    """Sikker aktivering av GPIO pin med watchdog"""
    try:
        GPIO.output(pin, GPIO.HIGH)
        magnet_watchdogs[pin].start()
        return True
    except Exception as e:
        logging.error(f"Feil ved aktivering av pin {pin}: {e}")
        return False

def safe_gpio_low(pin):
    """Sikker deaktivering av GPIO pin"""
    try:
        GPIO.output(pin, GPIO.LOW)
        magnet_watchdogs[pin].cancel()
        return True
    except Exception as e:
        logging.error(f"Feil ved deaktivering av pin {pin}: {e}")
        return False

def magnet_release(pin):
    """
    Sikker frigjøring av magnetlås med maksimal sikkerhetstid.
    Garanterer at låsen ikke kan stå med strøm på over lengre tid.
    """
    try:
        # Sikkerhetskontroll - sjekk nåværende tilstand
        if GPIO.input(pin) == GPIO.HIGH:
            logging.error(f"ADVARSEL: Pin {pin} var allerede HIGH ved magnet_release!")
            safe_gpio_low(pin)
            time.sleep(0.1)  # Kort pause for å sikre at pin er LAV
            
        # Normal åpningssekvens
        if safe_gpio_high(pin):
            time.sleep(0.5)  # Redusert fra 1 sekund til 0.5 sekund
            safe_gpio_low(pin)
            
            # Dobbeltsjekk at pin er LAV
            if GPIO.input(pin) == GPIO.HIGH:
                logging.error(f"KRITISK: Pin {pin} forble HIGH etter magnet_release!")
                safe_gpio_low(pin)
                
            logging.info(f"Magnetlås på pin {pin} frigjort")
    except Exception as e:
        logging.error(f"Feil ved frigjøring av magnetlås på pin {pin}: {e}")
        # Sikkerhetstiltak - forsøk å sette pin LAV ved feil
        safe_gpio_low(pin)


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


def safety_check_pins():
    """
    Sjekker alle magnetlås-pinner og sikrer at ingen står på HIGH over tid.
    """
    for gpio_pin in LOCKER_GPIO_MAP.values():
        try:
            if GPIO.input(gpio_pin) == GPIO.HIGH:
                logging.error(f"KRITISK: Fant pin {gpio_pin} i HIGH tilstand under sikkerhetssjekk!")
                GPIO.output(gpio_pin, GPIO.LOW)
                time.sleep(0.1)
        except Exception as e:
            logging.error(f"Feil under sikkerhetssjekk av pin {gpio_pin}: {e}")


def reader_helper():
    global siste_rfid, siste_skann_tid
    logging.info("[SYSTEM] Starter RFID-løkke – overvåker lukking og kort.")
    
    last_safety_check = time.time()
    SAFETY_CHECK_INTERVAL = 5  # Kjør sikkerhetssjekk hvert 5. sekund

    while True:
        try:
            # Periodisk sikkerhetssjekk
            current_time = time.time()
            if current_time - last_safety_check >= SAFETY_CHECK_INTERVAL:
                safety_check_pins()
                last_safety_check = current_time

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
            # Ved kritisk feil, sikre at alle pinner er LAV
            for pin in LOCKER_GPIO_MAP.values():
                try:
                    GPIO.output(pin, GPIO.LOW)
                except:
                    pass
            time.sleep(1)  # Vent litt før vi fortsetter ved kritisk feil