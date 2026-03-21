from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, send_from_directory


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")

# Register extracted route blueprints
from routes import register_blueprints
register_blueprints(app)


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
