import subprocess
import time
import sys
import logging
import requests
import os

SERVER_FILE = "backend/server.py"

BACKUP_URL = "http://127.0.0.1:8000/get-server"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("manager.log")
    ]
)


class ProcessManager:

    def __init__(self):
        self.process = None

    def download_backup(self):

        logging.warning("Attempting recovery from backup server...")

        try:

            response = requests.get(BACKUP_URL, timeout=5)

            if response.status_code == 200:

                os.makedirs("backend", exist_ok=True)

                with open(SERVER_FILE, "wb") as f:
                    f.write(response.content)

                logging.info("Recovered server.py successfully!")

                return True

            logging.error(
                f"Backup server returned status "
                f"{response.status_code}"
            )

            return False

        except Exception as e:

            logging.error(f"Backup recovery failed: {e}")

            return False

    def kill_process(self):

        if self.process and self.process.poll() is None:

            logging.warning("Killing running server process...")

            self.process.kill()

            self.process.wait()

    def start_process(self):

        logging.info(f"Starting {SERVER_FILE}")

        self.process = subprocess.Popen(
            [sys.executable, "-u", SERVER_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

    def monitor(self):

        while True:

            # ==========================================
            # FILE INTEGRITY CHECK
            # ==========================================

            if not os.path.exists(SERVER_FILE):

                logging.error("server.py missing or deleted!")

                self.kill_process()

                recovered = self.download_backup()

                if not recovered:

                    logging.error(
                        "Could not recover server.py"
                    )

                    time.sleep(2)

                    continue

            # ==========================================
            # PROCESS CHECK
            # ==========================================

            if (
                self.process is None or
                self.process.poll() is not None
            ):

                if self.process is not None:

                    logging.error(
                        f"Server crashed with exit code "
                        f"{self.process.returncode}"
                    )

                try:

                    self.start_process()

                except Exception as e:

                    logging.error(
                        f"Failed to start server: {e}"
                    )

                    recovered = self.download_backup()

                    if recovered:

                        logging.info(
                            "Retrying startup after recovery..."
                        )

                    time.sleep(2)

                    continue

            # ==========================================
            # LIVE LOG STREAMING
            # ==========================================

            try:

                if self.process.stdout.readable():

                    line = self.process.stdout.readline()

                    if line:

                        logging.info(
                            f"[SERVER] {line.strip()}"
                        )

            except Exception as e:

                logging.error(
                    f"Error reading logs: {e}"
                )

            time.sleep(0.1)


if __name__ == "__main__":

    manager = ProcessManager()

    manager.monitor()