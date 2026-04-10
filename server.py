from __future__ import annotations

from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

# Register extracted route blueprints
from routes import register_blueprints
register_blueprints(app)


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


import os
import sys
import atexit
import logging
import subprocess

if __name__ == "__main__":
    # Flask with debug=True spawns 2 processes. 
    # We only want to start the watcher in the main worker process.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logging.info("Starting Drive Watcher background process...")
        
        # Start the watcher as a background subprocess
        watcher_process = subprocess.Popen([sys.executable, "-m", "sync.drive_watcher"])
        logging.info("Drive Watcher started (PID: %d)", watcher_process.pid)
        
        def cleanup_watcher():
            """Ensure background watcher is killed when server dies."""
            logging.info("Shutting down Drive Watcher...")
            watcher_process.terminate()
            try:
                watcher_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watcher_process.kill()
                
        atexit.register(cleanup_watcher)

    app.run(host="127.0.0.1", port=8000, debug=True)
