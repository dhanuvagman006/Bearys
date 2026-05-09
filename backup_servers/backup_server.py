from flask import Flask, send_file, jsonify
import os

app = Flask(__name__)

BACKUP_FOLDER = "backup"

@app.route("/health")
def health():
    return {"status": "backup server alive"}

@app.route("/get-server")
def get_server():

    file_path = os.path.join(BACKUP_FOLDER, "server.py")

    if not os.path.exists(file_path):
        return jsonify({
            "error": "Backup file missing"
        }), 404

    return send_file(
        file_path,
        as_attachment=True
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)