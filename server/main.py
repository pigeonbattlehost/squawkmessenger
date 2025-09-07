import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import uuid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}

def generate_room_code():
    return str(uuid.uuid4())[:6].upper()

@app.route("/create_room", methods=["POST"])
def create_room():
    room_code = generate_room_code()
    rooms[room_code] = {"players": {}}
    return jsonify({"room_code": room_code}), 200

@socketio.on("join_room")
def on_join(data):
    nickname = data.get("nickname", "Anon")
    room_code = data.get("room_code")
    if not room_code or room_code not in rooms:
        emit("system_message", {"text": "Room not found"})
        return
    player_id = str(uuid.uuid4())
    rooms[room_code]["players"][player_id] = nickname
    join_room(room_code)
    emit("joined_room", {"player_id": player_id})
    emit("system_message", {"text": f"{nickname} joined the room"}, room=room_code)

@socketio.on("send_message")
def handle_message(data):
    text = data.get("text")
    room_code = data.get("room_code")
    player_id = data.get("player_id")
    if not room_code or room_code not in rooms:
        emit("system_message", {"text": "Room not found"})
        return
    nickname = rooms[room_code]["players"].get(player_id, "Anon")
    emit("receive_message", {"nickname": nickname, "text": text, "player_id": player_id}, room=room_code)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
