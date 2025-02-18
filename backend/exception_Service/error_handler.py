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
    A class to handle error messages and control program flow during problematic runtime events.
    """

    def __init__(self, log_errors=True):
        """
        Initializes the ErrorHandler.

        :param log_errors: Boolean flag to indicate whether errors should be logged.
        """
        self.log_errors = log_errors
        self.error_log = []

    def log_error(self, error_message):
        """
        Logs an error message.

        :param error_message: The error message to log.
        """
        if self.log_errors:
            self.error_log.append(error_message)
            logging.error(error_message)  # **Nå logger vi også til fil**
            print(f"Error logged: {error_message}")

    def handle_error(self, error_message, raise_exception=False):
        """
        Handles an error by logging it and optionally raising an exception.

        :param error_message: The error message to handle.
        :param raise_exception: Whether to raise an exception after logging.
        """
        self.log_error(error_message)
        if raise_exception:
            raise Exception(error_message)

    def get_error_log(self):
        """
        Returns the list of logged errors.

        :return: List of error messages.
        """
        return self.error_log

    def clear_log(self):
        """
        Clears the error log.
        """
        self.error_log.clear()
        print("Error log cleared.")

# FastAPI error handling integrasjon
def fastapi_error_handler(error_message, status_code=400):
    handler = ErrorHandler()
    handler.log_error(error_message)
    raise HTTPException(status_code=status_code, detail=error_message)

# Test logging og feilhåndtering
if __name__ == "__main__":
    handler = ErrorHandler()
    try:
        handler.handle_error("This is a test error.", raise_exception=True)
    except Exception as e:
        print(f"Exception caught: {e}")

    print("Logged errors:", handler.get_error_log())
