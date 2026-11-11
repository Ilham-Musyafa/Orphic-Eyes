"""Small, bounded DevTools WebSocket client for installed Chromium browsers.

Only the browser's loopback debugging socket is used. No third-party WebSocket
package, remote debugging service, page source inspection, or TLS override.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import time
from urllib.parse import urlsplit


class DevTools:
    def __init__(self, url, deadline):
        parts = urlsplit(url)
        if parts.scheme != "ws" or parts.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("Browser debugging endpoint must be loopback")
        self.deadline = deadline
        self.serial = 0
        self.events = []
        self.buffer = bytearray()
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=self.remaining())
        try:
            key = base64.b64encode(os.urandom(16)).decode()
            request = (f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\n"
                       f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                       "Sec-WebSocket-Version: 13\r\n\r\n")
            self.socket.sendall(request.encode("ascii"))
            headers = bytearray()
            while not headers.endswith(b"\r\n\r\n") and len(headers) < 16384:
                headers.extend(self._read(1))
            expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            lines = bytes(headers).split(b"\r\n")
            fields = {key.strip().lower(): value.strip() for line in lines[1:] if b":" in line
                      for key, value in [line.split(b":", 1)]}
            if (b" 101 " not in lines[0] or fields.get(b"sec-websocket-accept") != expected):
                raise RuntimeError("Browser debugging handshake failed")
        except Exception:
            self.close()
            raise

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("URL capture timed out")
        return seconds

    def _read(self, count):
        while len(self.buffer) < count:
            self.socket.settimeout(self.remaining())
            data = self.socket.recv(min(65536, count - len(self.buffer)))
            if not data:
                raise RuntimeError("Browser debugging connection closed")
            self.buffer.extend(data)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def _send(self, payload, opcode=1):
        mask = os.urandom(4)
        size = len(payload)
        header = bytes((0x80 | opcode, 0x80 | min(size, 126))) if size < 65536 else bytes((0x80 | opcode, 0xFF))
        if size >= 65536:
            header += struct.pack("!Q", size)
        elif size >= 126:
            header += struct.pack("!H", size)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.socket.settimeout(self.remaining())
        self.socket.sendall(header + mask + masked)

    def receive(self):
        message = bytearray()
        while True:
            first, second = self._read(2)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            if length + len(message) > 64 * 1024 * 1024 or second & 0x80:
                raise RuntimeError("Invalid browser debugging frame")
            payload = self._read(length)
            opcode = first & 0x0F
            if opcode == 8:
                raise RuntimeError("Browser debugging connection closed")
            if opcode == 9:
                self._send(payload, opcode=10)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1):
                raise RuntimeError("Unexpected browser debugging frame")
            message.extend(payload)
            if first & 0x80:
                return json.loads(message)

    def call(self, method, params=None):
        self.serial += 1
        serial = self.serial
        self._send(json.dumps({"id": serial, "method": method, "params": params or {}}).encode())
        while True:
            response = self.receive()
            if response.get("id") == serial:
                if "error" in response:
                    # Browser errors can embed URLs or JavaScript; do not echo.
                    raise RuntimeError("Browser command failed: " + method)
                return response.get("result", {})
            if "method" in response:
                self.events.append(response)

    def close(self):
        self.socket.close()
