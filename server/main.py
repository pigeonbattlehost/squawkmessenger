import os
import uuid
import base64
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename

MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 6 MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}

def generate_room_code():
    return str(uuid.uuid4())[:6].upper()

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS

def build_data_url(file_storage):

    mimetype = file_storage.mimetype or 'application/octet-stream'
    data = file_storage.read()
    if not data:
        return None
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mimetype};base64,{b64}"

@app.route("/create_room", methods=["POST"])
def create_room():
    room_code = generate_room_code()
    rooms[room_code] = {"players": {}}
    app.logger.info(f"Created private room {room_code}")
    return jsonify({"room_code": room_code}), 200

@app.route("/upload_image", methods=["POST"])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    try:
        data_url = build_data_url(file)
        if not data_url:
            return jsonify({'error': 'Empty file'}), 400
    except Exception as e:
        app.logger.exception("Failed to process uploaded file")
        return jsonify({'error': 'Failed to process file'}), 500

    return jsonify({'data_url': data_url}), 200

@socketio.on("join_room")
def on_join(data):

    nickname = data.get("nickname", "Anon")
    room_code = data.get("room_code")
    if not room_code:
        emit("system_message", {"text": "Missing room_code"})
        return

    if room_code not in rooms:
        emit("system_message", {"text": "Room not found"})
        return

    player_id = str(uuid.uuid4())
    rooms[room_code]["players"][player_id] = nickname
    join_room(room_code)
    emit("joined_room", {"player_id": player_id})
    emit("system_message", {"text": f"{nickname} joined the room"}, room=room_code)
    app.logger.info(f"Player {player_id} ({nickname}) joined private room {room_code}")

@socketio.on("send_message")
def handle_message(data):
    msg_type = data.get("type", "text")
    room_code = data.get("room_code")
    player_id = data.get("player_id")

    if not room_code or room_code not in rooms:
        emit("system_message", {"text": "Room not found"})
        return

    nickname = rooms[room_code]["players"].get(player_id, "Anon")

    if msg_type == "image":
        data_url = data.get("data_url") or data.get("url")
        if not data_url:
            emit("system_message", {"text": "No image data provided"})
            return
        payload = {"type": "image", "nickname": nickname, "url": data_url, "player_id": player_id}
        emit("receive_message", payload, room=room_code)
        app.logger.info(f"[{room_code}] image from {nickname} (len={len(data_url)} chars)")
    else:
        text = data.get("text", "")
        payload = {"type": "text", "nickname": nickname, "text": text, "player_id": player_id}
        emit("receive_message", payload, room=room_code)
        app.logger.info(f"[{room_code}] text from {nickname}: {text}")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logging.basicConfig(level=logging.INFO)
    print(f"Starting private Squawk server on 0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port)
