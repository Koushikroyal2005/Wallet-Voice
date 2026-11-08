import logging
import time
from .maintenance import tick

if __name__ == "__main__":
    while True:
        try:
            tick()
        except Exception:
            logging.exception("Wallet maintenance pass failed; retrying next pass")
        time.sleep(10)
