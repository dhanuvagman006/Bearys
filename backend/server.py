from flask import Flask, render_template
import os
import random

app = Flask(__name__)

SERVER_STATUS = "Loaded from Main Server"


# =====================================================
# HOME PAGE
# =====================================================

@app.route("/")
def home():

    return render_template(
        "index.html",
        status=SERVER_STATUS
    )


# =====================================================
# API STATUS
# =====================================================

@app.route("/api/status")
def status():

    return {
        "status": SERVER_STATUS
    }


# =====================================================
# FORCE CRASH
# =====================================================

@app.route("/crash")
def crash():

    os._exit(1)


# =====================================================
# RANDOM CRASH
# =====================================================

@app.route("/random")
def random_crash():

    if random.randint(1, 5) == 1:

        os._exit(1)

    return {
        "status": "survived"
    }


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("Server booting...")

    app.run(
        host="0.0.0.0",
        port=5000
    )