import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import uuid
import time
import random
import string

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# room_code -> set(ws)
rooms = {}

# ws -> {"nickname": str, "room": str, "player_id": str}
clients = {}

def generate_code(length=7):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route("/create_room", methods=["POST"])
def create_room():
    code = generate_code()
    rooms[code] = set()
    return jsonify({"room_code": code}), 200

@socketio.on("join_room")
def join_room(data):
    room = data.get("room_code")
    nickname = data.get("nickname", "Anon")
    player_id = data.get("player_id", str(uuid.uuid4()))

    if room not in rooms:
        emit("error", {"text": "Room does not exist"}, room=request.sid)
        return

    clients[request.sid] = {"nickname": nickname, "room": room, "player_id": player_id}
    rooms[room].add(request.sid)

    emit("joined_room", {"player_id": player_id, "room_code": room}, room=request.sid)
    emit("system_message", {"text": f"{nickname} joined the room"}, room=room)

@socketio.on("send_message")
def handle_message(data):
    text = data.get("text", "")
    info = clients.get(request.sid)
    if not info:
        emit("error", {"text": "Not in a room"}, room=request.sid)
        return

    room = info["room"]
    nickname = info["nickname"]

    emit("receive_message", {"nickname": nickname, "text": text}, room=room)

@socketio.on("disconnect")
def disconnect():
    info = clients.get(request.sid)
    if info:
        room = info["room"]
        nickname = info["nickname"]
        rooms[room].discard(request.sid)
        emit("system_message", {"text": f"{nickname} left the room"}, room=room)
        del clients[request.sid]

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
