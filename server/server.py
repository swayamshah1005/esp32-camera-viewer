from flask import Flask, request, send_file
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

LATEST_IMAGE = "latest.jpg"

@app.route("/")
def home():
    return "Server is running"

@app.route("/upload", methods=["POST"])
def upload():
    with open(LATEST_IMAGE, "wb") as f:
        f.write(request.data)
    return {"status": "ok"}

@app.route("/latest")
def latest():
    if not os.path.exists(LATEST_IMAGE):
        return {"error": "No image uploaded yet"}, 404
    return send_file(LATEST_IMAGE, mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)