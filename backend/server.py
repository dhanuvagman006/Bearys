from flask import Flask
import os
import random

app = Flask(__name__)

@app.route("/")
def home():
    return {"status": "alive"}

@app.route("/crash")
def crash():
    os._exit(1)

@app.route("/random")
def random_crash():
    if random.randint(1, 5) == 1:
        os._exit(1)
    return {"status": "survived"}

if __name__ == "__main__":
    print("Server booting...")
    app.run(host="0.0.0.0", port=5000)