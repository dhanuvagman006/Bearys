from flask import Flask, send_file, jsonify
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FILE = os.path.join(BASE_DIR, "server.py")

@app.route("/health")
def health():
    return {"status": "backup server alive"}

@app.route("/get-server")
def get_server():
    print(BACKUP_FILE)
    if not os.path.exists(BACKUP_FILE):
        return jsonify({
            "error": "Backup file missing"
        }), 404

    return send_file(
        BACKUP_FILE,
        as_attachment=True
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)