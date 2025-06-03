import RPi.GPIO as GPIO
import time
import logging

logging.basicConfig(
    filename='locker_system.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class LockerState:
    def __init__(self, locker_id, gpio_pin, close_pin):
        self.locker_id = locker_id
        self.gpio_pin = gpio_pin
        self.close_pin = close_pin
        self.is_closed = False
        self.last_state_change = time.time()
        self.state_buffer = []
        self.buffer_size = 5  # Antall målinger vi vil ha før vi godtar en endring
        self.debounce_time = 0.1  # Minimum tid mellom tilstandsendringer
        
        # Logging av initialisering
        logging.info(f"Initialiserer LockerState for skap {locker_id}")
        logging.info(f"GPIO pin: {gpio_pin}, Close pin: {close_pin}")

    def update_state(self):
        """
        Oppdaterer og validerer skapets tilstand.
        Returnerer True hvis det er en validert tilstandsendring.
        """
        current_reading = GPIO.input(self.close_pin) == GPIO.LOW
        self.state_buffer.append(current_reading)
        
        if len(self.state_buffer) > self.buffer_size:
            self.state_buffer.pop(0)
            
        # Sjekk om vi har stabil tilstand
        if len(self.state_buffer) == self.buffer_size:
            stable_state = all(x == self.state_buffer[0] for x in self.state_buffer)
            if stable_state and time.time() - self.last_state_change > self.debounce_time:
                new_state = self.state_buffer[0]
                if new_state != self.is_closed:
                    old_state = self.is_closed
                    self.is_closed = new_state
                    self.last_state_change = time.time()
                    
                    # Logg tilstandsendring
                    logging.info(f"Skap {self.locker_id}: Tilstandsendring fra {old_state} til {new_state}")
                    logging.debug(f"Skap {self.locker_id}: Tilstandsbuffer ved endring: {self.state_buffer}")
                    return True
        return False

    def get_state(self):
        """Returnerer nåværende tilstand"""
        return self.is_closed

    def get_last_change_time(self):
        """Returnerer tidspunkt for siste tilstandsendring"""
        return self.last_state_change 