import logging
import os
from fastapi import HTTPException

# Finn riktig loggsti basert på operativsystem
if os.name == "nt":  # Windows
    log_dir = os.path.join(os.getenv("USERPROFILE"), "fastapi_logs")
else:  # Linux/macOS
    log_dir = "/var/log"

# Opprett loggmappen hvis den ikke eksisterer
os.makedirs(log_dir, exist_ok=True)

# Definer loggfilen
log_file = os.path.join(log_dir, "fastapi_errors.log")

# Sett opp logging **etter** at loggfilen er satt riktig
logging.basicConfig(
    filename=log_file,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

class ErrorHandler:
    """
    En klasse for å håndtere feilmeldinger og kontrollere programflyten under problematiske kjøretidshendelser.
    """

    def __init__(self, log_errors=True):
        """
        Initialiserer ErrorHandler.

        :param log_errors: Boolsk flagg for å indikere om feil skal logges.
        """
        self.log_errors = log_errors
        self.error_log = []

    def log_error(self, error_message):
        """
        Logger en feilmelding.

        :param error_message: Feilmeldingen for å logge.
        """
        if self.log_errors:
            self.error_log.append(error_message)
            logging.error(error_message)
            print(f"Error logged: {error_message}")

    def handle_error(self, error_message, raise_exception=False):
        """
        Håndterer en feil ved å logge den og eventuelt gjøre et unntak.

        :param error_message: Feilmeldingen som skal håndteres.
        :param raise_exception: Om et unntak skal tas opp etter logging.
        """
        self.log_error(error_message)
        if raise_exception:
            raise Exception(error_message)

    def get_error_log(self):
        """
        Returnerer listen over loggede feil.

        :return: Liste over feilmeldinger.
        """
        return self.error_log

    def clear_log(self):
        """
        Tømmer feilloggen.
        """
        self.error_log.clear()
        print("Error log cleared.")

# FastAPI error handling integrasjon
def fastapi_error_handler(error_message, status_code=400):
    handler = ErrorHandler()
    handler.log_error(error_message)
    raise HTTPException( detail=error_message, status_code=status_code)

# Test logging og feilhåndtering
if __name__ == "__main__":
    handler = ErrorHandler()
    try:
        handler.handle_error("This is a test error.", raise_exception=True)
    except Exception as e:
        print(f"Exception caught: {e}")

    print("Logged errors:", handler.get_error_log())
