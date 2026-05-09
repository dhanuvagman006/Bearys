import subprocess
import time
import sys
import requests
import os
import platform
import shutil
import tempfile
import threading
import queue
import concurrent.futures

from colorama import init, Fore, Style

init(autoreset=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_FILE = os.path.join(
    BASE_DIR,
    "backend",
    "server.py"
)

TEMPLATES_DIR = os.path.join(
    BASE_DIR,
    "backend",
    "templates"
)

BACKUP_URLS = [
    "http://127.0.0.1:8000/get-backup",
    "http://127.0.0.1:8001/get-backup"
]


# =========================================================
# PROCESS MANAGER
# =========================================================

class ProcessManager:

    def __init__(self):

        self.process = None
        self.restart_count = 0
        self.log_queue = queue.Queue()
        self.log_thread = None
        self.last_mtime = None

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
            f"Attempting recovery from {len(BACKUP_URLS)} backup servers..."
        )

        def fetch_backup(url):
            try:
                self.log("INFO", f"Requesting backup from {url}...")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return response
            except Exception:
                pass
            return None

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(BACKUP_URLS)) as executor:
                # Start all requests simultaneously
                futures = {executor.submit(fetch_backup, url): url for url in BACKUP_URLS}
                
                # Wait for the first one that returns a valid response
                for future in concurrent.futures.as_completed(futures):
                    response = future.result()
                    if response:
                        # Cancel other futures (though Python's executor doesn't support true cancellation once started,
                        # we just ignore subsequent results)
                        
                        self.log(
                            "SUCCESS",
                            f"Fastest response received from {futures[future]}"
                        )

                        os.makedirs(
                            os.path.dirname(SERVER_FILE),
                            exist_ok=True
                        )

                        # Save the zip temporarily
                        temp_zip_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip")
                        os.close(temp_zip_fd)
                        
                        with open(temp_zip_path, "wb") as f:
                            f.write(response.content)

                        # Unpack the archive into the backend directory
                        backend_dir = os.path.dirname(SERVER_FILE)
                        shutil.unpack_archive(temp_zip_path, backend_dir)
                        
                        # Clean up temporary zip
                        os.remove(temp_zip_path)

                        self.log(
                            "SUCCESS",
                            "Recovered server.py and templates successfully!"
                        )

                        return True

            self.log(
                "ERROR",
                "All backup servers failed or returned invalid responses."
            )

            except Exception as e:
                self.log(
                    "ERROR",
                    f"Backup recovery from {url} failed: {e}"
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

        # Start a background thread to read logs without blocking the monitor
        def reader():
            for line in iter(self.process.stdout.readline, ""):
                self.log_queue.put(line)
            self.process.stdout.close()

        self.log_thread = threading.Thread(target=reader, daemon=True)
        self.log_thread.start()

        self.log(
            "SUCCESS",
            "Server process launched successfully!"
        )

    # =====================================================
    # STREAM LOGS
    # =====================================================

    def stream_logs(self):

        try:

            while not self.log_queue.empty():

                line = self.log_queue.get_nowait()

                if line:

                    print(
                        Fore.WHITE +
                        "[SERVER] " +
                        line.strip()
                    )

        except queue.Empty:
            pass

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
            # FILE CHECK & HOT RELOAD
            # -------------------------------------------------

            if os.path.exists(SERVER_FILE):
                current_mtime = os.path.getmtime(SERVER_FILE)
                if self.last_mtime is not None and current_mtime > self.last_mtime:
                    self.log("WARNING", "server.py changed! Reloading...")
                    self.kill_process()
                    self.process = None # Force restart
                self.last_mtime = current_mtime

            if not os.path.exists(SERVER_FILE) or not os.path.exists(TEMPLATES_DIR):

                self.log(
                    "ERROR",
                    "server.py or templates missing or deleted!"
                )

                self.kill_process()

                recovered = self.download_backup()

                if not recovered:

                    self.log(
                        "ERROR",
                        "Could not recover from backup"
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

                    # If server crashed with error, pull fresh version
                    if self.process.returncode != 0:
                        self.log("WARNING", "Error detected! Pulling fresh backup...")
                        self.download_backup()

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
        
        import signal
        def handle_exit(signum, frame):
            manager.kill_process()
            sys.exit(0)
            
        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)
        
        try:
            manager.monitor()
        except KeyboardInterrupt:
            print("\nExiting monitor...")
        finally:
            manager.kill_process()

    else:

        print(
            "Launching monitoring terminal..."
        )

        open_monitor_terminal()