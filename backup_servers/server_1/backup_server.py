# pyrefly: ignore [missing-import]
from flask import Flask, send_file, jsonify
import os
import hashlib

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FILE = os.path.join(BASE_DIR, "server.py")
HASH_FILE = os.path.join(BASE_DIR, "stored_hash.txt")

def get_current_hash():
    if not os.path.exists(BACKUP_FILE):
        return None
    sha256 = hashlib.sha256()
    with open(BACKUP_FILE, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

@app.route("/health")
def health():
    return {"status": "backup server 1 alive"}

@app.route("/check-integrity")
def check_integrity():
    if not os.path.exists(HASH_FILE):
        return jsonify({"status": "error", "message": "Stored hash missing"}), 500
    
    with open(HASH_FILE, "r") as f:
        stored_hash = f.read().strip()
    
    current_hash = get_current_hash()
    if current_hash == stored_hash:
        return jsonify({"status": "clean", "hash": current_hash})
    else:
        return jsonify({"status": "corrupted", "expected": stored_hash, "got": current_hash})

@app.route("/get-backup")
def get_backup():
    if not os.path.exists(BACKUP_FILE):
        return jsonify({"error": "Backup file missing"}), 404
    
    # Optional: block download if corrupted
    # but usually we let the manager decide
    return send_file(BACKUP_FILE, as_attachment=True, download_name="server.py")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
