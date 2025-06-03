import RPi.GPIO as GPIO
import time
import spidev
import requests
from mfrc522 import SimpleMFRC522
import json
import threading
from collections import defaultdict

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

# Tilstandshåndtering med debouncing
skap_lukket_tidligere = {locker_id: False for locker_id in LOCKER_CLOSE_PIN_MAP}
sensor_stable_count = defaultdict(int)  # Teller for stabile avlesninger
STABILITY_THRESHOLD = 3  # Antall like avlesninger før vi tror på endringen

siste_rfid = None
siste_skann_tid = 0

# Threading locks for å unngå race conditions
sensor_lock = threading.Lock()
rfid_lock = threading.Lock()


def magnet_release(pin):
    """Frigjør magnetlås"""
    try:
        print(f"[MAGNET] Frigjør lås på pin {pin}")
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)
        print(f"[MAGNET] Lås på pin {pin} frigjort")
    except Exception as e:
        print(f"[FEIL] Kunne ikke frigjøre lås på pin {pin}: {e}")


def debounced_sensor_read(locker_id, close_pin):
    """
    Leser sensor med debouncing for å unngå støy
    Returnerer True bare hvis sensor er stabil i flere avlesninger
    """
    current_state = GPIO.input(close_pin) == GPIO.LOW

    # Sjekk om tilstanden er endret
    if current_state != skap_lukket_tidligere[locker_id]:
        sensor_stable_count[locker_id] += 1

        # Krev flere like avlesninger før vi tror på endringen
        if sensor_stable_count[locker_id] >= STABILITY_THRESHOLD:
            sensor_stable_count[locker_id] = 0
            return current_state, True  # Stabil endring detektert
        else:
            return skap_lukket_tidligere[locker_id], False  # Ikke stabil ennå
    else:
        # Tilstanden er uendret, reset counter
        sensor_stable_count[locker_id] = 0
        return current_state, False  # Ingen endring


def scan_for_rfid(timeout=5, init_delay=0):
    """Forbedret RFID-skanning med bedre feilhåndtering"""
    with rfid_lock:  # Sikre at bare én tråd skanner om gangen
        time.sleep(init_delay)
        try:
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
                    print(f"[RFID-FEIL] Under skanning: {e}")
                    time.sleep(0.1)
                    continue

                time.sleep(0.1)

            print("[RFID] Ingen RFID registrert innen timeout")
            return None

        except Exception as e:
            print(f"[RFID-FEIL] Kritisk feil: {e}")
            return None


def Register_locker(rfid_tag, locker_id):
    """Forbedret registrering med bedre feilhåndtering"""
    try:
        print(f"[API] Registrerer RFID {rfid_tag} til skap {locker_id}")
        response = requests.post(
            API_URL_REG,
            params={
                "rfid_tag": rfid_tag,
                "locker_room_id": LOCKER_ROOM_ID,
                "locker_id": locker_id
            },
            timeout=2.0  # Økt timeout
        )

        if response.status_code != 200:
            print(f"[API-FEIL] HTTP {response.status_code}: {response.text}")
            return False

        data = response.json()
        if data.get("access_granted"):
            assigned_id = data.get("locker_id")
            print(f"[TILGANG] RFID godkjent – Skap {assigned_id} låst")
            return True
        else:
            print("[RFID] Ikke godkjent – frigjør skap")
            gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
            if gpio_pin:
                magnet_release(gpio_pin)
            return False

    except Exception as e:
        print(f"[API-FEIL] Register_locker: {e}")
        # Ved API-feil, frigjør skapet som sikkerhetstiltak
        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
        if gpio_pin:
            magnet_release(gpio_pin)
        return False


def Reuse_locker(rfid_tag):
    """Forbedret gjenbruk med bedre logging"""
    try:
        print(f"[GJENBRUK] Prøver RFID {rfid_tag}")
        response = requests.post(
            API_URL_SCAN,
            params={
                "rfid_tag": rfid_tag,
                "locker_room_id": LOCKER_ROOM_ID
            },
            timeout=2.0
        )

        if response.status_code != 200:
            print(f"[API-FEIL] Gjenbruk HTTP {response.status_code}")
            return False

        data = response.json()
        if data.get("access_granted"):
            assigned_id = data.get("locker_id")
            gpio_pin = LOCKER_GPIO_MAP.get(assigned_id)
            if gpio_pin:
                print(f"[FRIGJØRING] Åpner skap {assigned_id}")
                magnet_release(gpio_pin)
                return True
        else:
            print("[RFID] Kortet har ikke tilgang til skap")
            return False

    except Exception as e:
        print(f"[API-FEIL] Reuse_locker: {e}")
        return False


def handle_locker_closure(locker_id):
    """Håndterer skaplukking i egen funksjon"""
    print(f"[LUKKING] Skap {locker_id} lukket – starter RFID-registrering")

    # Skann for RFID
    rfid_tag = scan_for_rfid(timeout=6)

    if rfid_tag:
        # Sjekk for duplikater
        global siste_rfid, siste_skann_tid
        nå = time.time()

        if rfid_tag == siste_rfid and nå - siste_skann_tid < 3:
            print(f"[DUPLIKAT] RFID {rfid_tag} ignorert (for rask skanning).")
            return

        siste_rfid = rfid_tag
        siste_skann_tid = nå

        # Registrer skap
        success = Register_locker(rfid_tag, locker_id)
        if success:
            print(f"[SUKSESS] Skap {locker_id} registrert til RFID {rfid_tag}")
        else:
            print(f"[FEIL] Kunne ikke registrere skap {locker_id}")
    else:
        print(f"[TIMEOUT] Ingen RFID for skap {locker_id} – frigjør automatisk")
        gpio_pin = LOCKER_GPIO_MAP.get(locker_id)
        if gpio_pin:
            magnet_release(gpio_pin)


def reader_helper():
    """Hovedløkke med forbedret stabilitet"""
    print("[SYSTEM] Starter forbedret RFID-løkke")

    last_gjenbruk_check = 0
    GJENBRUK_INTERVAL = 2.0  # Sjekk gjenbruk hvert 2. sekund

    while True:
        try:
            with sensor_lock:
                # Sjekk alle sensorer med debouncing
                for locker_id, close_pin in LOCKER_CLOSE_PIN_MAP.items():
                    current_state, state_changed = debounced_sensor_read(locker_id, close_pin)

                    if state_changed:
                        if current_state:  # Skap lukket
                            if not skap_lukket_tidligere[locker_id]:
                                skap_lukket_tidligere[locker_id] = True
                                # Håndter lukking i egen funksjon
                                handle_locker_closure(locker_id)
                        else:  # Skap åpnet
                            if skap_lukket_tidligere[locker_id]:
                                print(f"[ÅPNING] Skap {locker_id} åpnet – nullstiller status")
                                skap_lukket_tidligere[locker_id] = False

            # Sjekk gjenbruk med intervall (ikke hver gang)
            nå = time.time()
            if nå - last_gjenbruk_check >= GJENBRUK_INTERVAL:
                last_gjenbruk_check = nå

                # Kort timeout på gjenbruk-skanning
                rfid_tag = scan_for_rfid(timeout=0.5)
                if rfid_tag:
                    # Sjekk for duplikater
                    if rfid_tag != siste_rfid or nå - siste_skann_tid >= 3:
                        siste_rfid = rfid_tag
                        siste_skann_tid = nå
                        print(f"[GJENBRUK] RFID {rfid_tag} prøver åpning")
                        Reuse_locker(rfid_tag)

            # Viktig: Gi systemet tid til å puste
            time.sleep(0.2)  # 200ms delay mellom hver hovedløkke-iterasjon

        except Exception as e:
            print(f"[KRITISK FEIL] reader_helper: {e}")
            time.sleep(1)  # Lengre pause ved feil


# Separat funksjon for graceful shutdown
def cleanup():
    """Rydder opp GPIO ved avslutning"""
    print("[CLEANUP] Rydder opp GPIO...")
    GPIO.cleanup()


if __name__ == "__main__":
    try:
        reader_helper()
    except KeyboardInterrupt:
        print("[AVSLUTNING] Avbryter...")
    finally:
        cleanup()