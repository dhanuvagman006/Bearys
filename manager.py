import subprocess
import time
import sys
import requests
import os
import platform

from colorama import init, Fore, Style

# =========================================================
# INIT
# =========================================================

init(autoreset=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_FILE = os.path.join(
    BASE_DIR,
    "backend",
    "server.py"
)

BACKUP_URL = "http://127.0.0.1:8000/get-server"


# =========================================================
# PROCESS MANAGER
# =========================================================

class ProcessManager:

    def __init__(self):

        self.process = None
        self.restart_count = 0

    # =====================================================
    # LOGGER
    # =====================================================

    def log(self, level, message):

        colors = {
            "INFO": Fore.CYAN,
            "SUCCESS": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
        }

        color = colors.get(level, Fore.WHITE)

        print(
            color +
            f"[{level}] {message}" +
            Style.RESET_ALL
        )

    # =====================================================
    # DOWNLOAD BACKUP
    # =====================================================

    def download_backup(self):

        self.log(
            "WARNING",
            "Attempting recovery from backup server..."
        )

        try:

            response = requests.get(
                BACKUP_URL,
                timeout=5
            )

            if response.status_code == 200:

                os.makedirs(
                    os.path.dirname(SERVER_FILE),
                    exist_ok=True
                )

                with open(SERVER_FILE, "wb") as f:
                    f.write(response.content)

                self.log(
                    "SUCCESS",
                    "Recovered server.py successfully!"
                )

                return True

            self.log(
                "ERROR",
                f"Backup server returned "
                f"status {response.status_code}"
            )

            return False

        except Exception as e:

            self.log(
                "ERROR",
                f"Backup recovery failed: {e}"
            )

            return False

    # =====================================================
    # KILL PROCESS
    # =====================================================

    def kill_process(self):

        if self.process and self.process.poll() is None:

            self.log(
                "WARNING",
                "Killing running server process..."
            )

            self.process.kill()
            self.process.wait()

    # =====================================================
    # START SERVER
    # =====================================================

    def start_process(self):

        self.restart_count += 1

        self.log(
            "INFO",
            f"Starting server "
            f"(restart #{self.restart_count})"
        )

        self.process = subprocess.Popen(
            [sys.executable, "-u", SERVER_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        self.log(
            "SUCCESS",
            "Server process launched successfully!"
        )

    # =====================================================
    # STREAM LOGS
    # =====================================================

    def stream_logs(self):

        try:

            if (
                self.process and
                self.process.stdout and
                self.process.stdout.readable()
            ):

                line = self.process.stdout.readline()

                if line:

                    print(
                        Fore.WHITE +
                        "[SERVER] " +
                        line.strip()
                    )

        except Exception as e:

            self.log(
                "ERROR",
                f"Log streaming failed: {e}"
            )

    # =====================================================
    # MONITOR LOOP
    # =====================================================

    def monitor(self):

        self.log(
            "INFO",
            "Process manager started"
        )

        while True:

            # -------------------------------------------------
            # FILE CHECK
            # -------------------------------------------------

            if not os.path.exists(SERVER_FILE):

                self.log(
                    "ERROR",
                    "server.py missing or deleted!"
                )

                self.kill_process()

                recovered = self.download_backup()

                if not recovered:

                    self.log(
                        "ERROR",
                        "Could not recover server.py"
                    )

                    time.sleep(2)
                    continue

            # -------------------------------------------------
            # PROCESS CHECK
            # -------------------------------------------------

            if (
                self.process is None or
                self.process.poll() is not None
            ):

                if self.process is not None:

                    self.log(
                        "ERROR",
                        f"Server crashed "
                        f"(exit code "
                        f"{self.process.returncode})"
                    )

                try:

                    self.start_process()

                except Exception as e:

                    self.log(
                        "ERROR",
                        f"Failed to start server: {e}"
                    )

                    recovered = self.download_backup()

                    if recovered:

                        self.log(
                            "SUCCESS",
                            "Recovery successful"
                        )

                    time.sleep(2)
                    continue

            # -------------------------------------------------
            # LIVE LOGS
            # -------------------------------------------------

            self.stream_logs()

            time.sleep(0.1)


# =========================================================
# OPEN MONITOR TERMINAL
# =========================================================

def open_monitor_terminal():

    system = platform.system()

    python_exec = sys.executable
    current_file = os.path.abspath(__file__)

    try:

        # =================================================
        # WINDOWS
        # =================================================

        if system == "Windows":

            subprocess.Popen(
                [
                    "cmd",
                    "/k",
                    python_exec,
                    current_file,
                    "--monitor"
                ]
            )

        # =================================================
        # LINUX
        # =================================================

        elif system == "Linux":

            terminals = [
                "gnome-terminal",
                "x-terminal-emulator",
                "konsole",
                "xfce4-terminal",
                "xterm"
            ]

            launched = False

            for terminal in terminals:

                exists = (
                    subprocess.call(
                        ["which", terminal],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    ) == 0
                )

                if exists:

                    try:

                        # GNOME TERMINAL
                        if terminal in [
                            "gnome-terminal",
                            "xfce4-terminal",
                            "x-terminal-emulator"
                        ]:

                            subprocess.Popen(
                                [
                                    terminal,
                                    "--",
                                    python_exec,
                                    current_file,
                                    "--monitor"
                                ]
                            )

                        # KONSOLE
                        elif terminal == "konsole":

                            subprocess.Popen(
                                [
                                    terminal,
                                    "-e",
                                    python_exec,
                                    current_file,
                                    "--monitor"
                                ]
                            )

                        # XTERM
                        elif terminal == "xterm":

                            subprocess.Popen(
                                [
                                    terminal,
                                    "-e",
                                    python_exec,
                                    current_file,
                                    "--monitor"
                                ]
                            )

                        launched = True

                        break

                    except Exception as e:

                        print(
                            f"Failed using "
                            f"{terminal}: {e}"
                        )

            if not launched:

                print(
                    "No supported Linux terminal "
                    "emulator found."
                )

        # =================================================
        # MACOS
        # =================================================

        elif system == "Darwin":

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    (
                        'tell app "Terminal" '
                        f'to do script '
                        f'"{python_exec} '
                        f'{current_file} --monitor"'
                    )
                ]
            )

        else:

            print(
                f"Unsupported operating system: "
                f"{system}"
            )

    except Exception as e:

        print(
            f"Failed to open monitor terminal: {e}"
        )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    if "--monitor" in sys.argv:

        manager = ProcessManager()
        manager.monitor()

    else:

        print(
            "Launching monitoring terminal..."
        )

        open_monitor_terminal()