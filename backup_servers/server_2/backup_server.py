# pyrefly: ignore [missing-import]
from flask import Flask, send_file, jsonify
import os
import shutil
import tempfile

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FILE = os.path.join(BASE_DIR, "server.py")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

@app.route("/health")
def health():
    return {"status": "backup server 2 alive"}

@app.route("/get-backup")
def get_backup():
    print("Serving backup zip from server 2...")
    if not os.path.exists(BACKUP_FILE) or not os.path.exists(TEMPLATES_DIR):
        return jsonify({
            "error": "Backup files missing"
        }), 404

    temp_dir = tempfile.mkdtemp()
    
    # Copy files to temp dir
    shutil.copy(BACKUP_FILE, temp_dir)
    shutil.copytree(TEMPLATES_DIR, os.path.join(temp_dir, "templates"))
    
    # Create zip
    zip_base_name = tempfile.mktemp()
    zip_path = shutil.make_archive(zip_base_name, 'zip', temp_dir)
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name="backup.zip"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
