"""Read one message of a ROS topic from the AGV base's rosbridge (WebSocket, ws://192.168.10.10:9090; its own web
pages use it). Only what the Lumi app's position correction needs: the lidar scan. A small WebSocket client of our
own (no extra package): one connection per read, subscribe, the first message, unsubscribe, close."""
import base64
import json
import os
import socket
import struct

HOST, PORT = "192.168.10.10", 9090


def client_frame(data):
    """A masked text frame (a client must mask what it sends)."""
    mask = os.urandom(4)
    n = len(data)
    head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n)
                            if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n))
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data))


def read_message(sock, buf):
    """One JSON message (its frames joined) from the server, and the bytes read past it."""
    def need(k):
        nonlocal buf
        while len(buf) < k:
            chunk = sock.recv(65536)
            if not chunk:
                raise ConnectionError("rosbridge closed the connection")
            buf += chunk
    data = b""
    while True:
        need(2)
        fin, n, i = buf[0] & 0x80, buf[1] & 0x7F, 2
        if n == 126:
            need(4)
            n, i = struct.unpack(">H", buf[2:4])[0], 4
        elif n == 127:
            need(10)
            n, i = struct.unpack(">Q", buf[2:10])[0], 10
        need(i + n)
        data, buf = data + buf[i:i + n], buf[i + n:]
        if fin:
            return json.loads(data), buf


def read_once(topic, timeout=3.0):
    """The next message of `topic` (rosbridge's {"op": "publish", "msg": ...}); raises OSError when there is none."""
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: {HOST}:{PORT}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("rosbridge did not answer the handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"rosbridge refused: {head.split(b'\\r\\n', 1)[0]!r}")
        buf = head.split(b"\r\n\r\n", 1)[1]
        s.sendall(client_frame(json.dumps({"op": "subscribe", "topic": topic, "queue_length": 1}).encode()))
        while True:
            msg, buf = read_message(s, buf)
            if msg.get("op") == "publish" and msg.get("topic", topic) == topic:
                s.sendall(client_frame(json.dumps({"op": "unsubscribe", "topic": topic}).encode()))
                return msg
