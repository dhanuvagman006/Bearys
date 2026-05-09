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

IMMUTABLE_DIR = os.path.join(BASE_DIR, "backup_server_immutable")
BACKUP_DIRS = {
    "server_1": os.path.join(BASE_DIR, "backup_servers", "server_1"),
    "server_2": os.path.join(BASE_DIR, "backup_servers", "server_2")
}


# =========================================================
# FETCH BACKUP TASK
# =========================================================

def fetch_backup_task(url):
    try:
        # 1. Check integrity first
        status_url = url.replace("/get-backup", "/check-integrity")
        status_res = requests.get(status_url, timeout=3)
        
        if status_res.status_code == 200:
            status_data = status_res.json()
            if status_data.get("status") == "clean":
                # 2. Download the backup
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return response.content, url
    except Exception:
        pass
    return None, url

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
        self.backup_mtimes = {}
        
        # Ensure immutable directory exists
        os.makedirs(IMMUTABLE_DIR, exist_ok=True)

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


        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=len(BACKUP_URLS)) as executor:
                # Start all requests simultaneously
                futures = {executor.submit(fetch_backup_task, url): url for url in BACKUP_URLS}
                
                # Wait for the first one that returns a valid response
                for future in concurrent.futures.as_completed(futures):
                    content, url = future.result()
                    if content:
                        self.log(
                            "SUCCESS",
                            f"Valid backup received from {url}"
                        )

                        os.makedirs(
                            os.path.dirname(SERVER_FILE),
                            exist_ok=True
                        )

                        with open(SERVER_FILE, "wb") as f:
                            f.write(content)

                        self.log(
                            "SUCCESS",
                            "Recovered server.py successfully!"
                        )

                        return True

            self.log(
                "ERROR",
                "All backup servers failed or returned invalid responses."
            )

            # FALLBACK: Try to recover from the latest immutable snapshot
            self.log("WARNING", "Attempting fallback to local immutable snapshots...")
            try:
                snapshots = [d for d in os.listdir(IMMUTABLE_DIR) if d.startswith("snapshot_")]
                if snapshots:
                    # Sort by name (which includes timestamp) and get the latest
                    latest_snapshot = sorted(snapshots)[-1]
                    snapshot_path = os.path.join(IMMUTABLE_DIR, latest_snapshot)
                    
                    self.log("INFO", f"Recovering from latest binary snapshot: {latest_snapshot}")
                    
                    # Unpack the binary snapshot archive into the backend directory
                    backend_dir = os.path.dirname(SERVER_FILE)
                    shutil.unpack_archive(snapshot_path, backend_dir)
                    
                    self.log("SUCCESS", "Recovered successfully from binary immutable snapshot!")
                    return True
                else:
                    self.log("ERROR", "No local snapshots found to recover from.")
            except Exception as e:
                self.log("ERROR", f"Local snapshot recovery failed: {e}")

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

    def create_clean_snapshot(self, source_dir, snapshot_base):
        # Create a temporary directory to build the clean snapshot
        temp_dir = tempfile.mkdtemp()
        
        # Only copy server.py and templates
        shutil.copy(os.path.join(source_dir, "server.py"), temp_dir)
        
        templates_src = os.path.join(source_dir, "templates")
        if os.path.exists(templates_src):
            shutil.copytree(templates_src, os.path.join(temp_dir, "templates"))
            
        # Create the zip archive
        shutil.make_archive(snapshot_base, 'zip', temp_dir)
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)

    # =====================================================
    # MONITOR LOOP
    # =====================================================

    def monitor(self):

        self.log(
            "INFO",
            "Process manager started"
        )

        # Initial check: if immutable folder is empty, populate it
        try:
            if not any(f for f in os.listdir(IMMUTABLE_DIR) if f.startswith("snapshot_")):
                self.log("INFO", "Immutable directory is empty. Creating initial snapshots...")
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                for name, path in BACKUP_DIRS.items():
                    if os.path.exists(path):
                        snapshot_base = os.path.join(IMMUTABLE_DIR, f"snapshot_{name}_{timestamp}")
                        self.create_clean_snapshot(path, snapshot_base)
                        self.log("INFO", f"Initial binary snapshot for {name} saved to {snapshot_base}.zip")
        except Exception as e:
            self.log("ERROR", f"Failed to initialize immutable directory: {e}")

        while True:

            # -------------------------------------------------
            # BACKUP SERVER SNAPSHOT CHECK
            # -------------------------------------------------

            for name, path in BACKUP_DIRS.items():
                target_file = os.path.join(path, "server.py")
                if os.path.exists(target_file):
                    mtime = os.path.getmtime(target_file)
                    if name in self.backup_mtimes and mtime > self.backup_mtimes[name]:
                        self.log("SUCCESS", f"Update detected in {name}! Creating snapshot...")
                        
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        snapshot_base = os.path.join(IMMUTABLE_DIR, f"snapshot_{name}_{timestamp}")
                        
                        try:
                            # Create a zip archive containing only server.py and templates
                            self.create_clean_snapshot(path, snapshot_base)
                            self.log("INFO", f"Clean binary snapshot saved to {snapshot_base}.zip")
                        except Exception as e:
                            self.log("ERROR", f"Failed to create binary snapshot: {e}")
                            
                    self.backup_mtimes[name] = mtime

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