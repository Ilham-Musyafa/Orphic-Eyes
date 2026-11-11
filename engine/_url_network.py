"""HTTP-only browser proxy with bounded DNS and private-address protection.

Every connection (including redirects and subresources) is checked here. Direct
connections use the validated numeric address, avoiding a second DNS lookup.
An inherited HTTP(S)_PROXY remains authoritative for routing and destination
policy. Public-only CONNECT requests also pin the numeric destination so a
second lookup at an upstream proxy cannot rebind a public name to a private IP.
"""

import base64
import ipaddress
import queue
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import getproxies, proxy_bypass


class URLPolicyError(ValueError):
    """Safe, URL-free explanation of a rejected destination."""


class URLResolutionError(OSError):
    """DNS is unavailable, without implying a private-address policy denial."""


def parse_url(url):
    try:
        if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise URLPolicyError("URL must use http or https")
        if "\\" in url or parts.username is not None or parts.password is not None:
            raise URLPolicyError("URL must not contain credentials or backslashes")
        host = parts.hostname
        if not host or "%" in host:
            raise ValueError
        host = host.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if not host or not 1 <= port <= 65535 or parts.port == 0:
            raise ValueError
        return parts, host, port
    except URLPolicyError:
        raise
    except (ValueError, TypeError, UnicodeError):
        raise URLPolicyError("Invalid URL: supply an absolute http/https URL with a valid host and port") from None


def resolve(host, port, timeout):
    """Bound system DNS without leaving non-daemon resolver threads behind."""
    result = queue.Queue(maxsize=1)

    def lookup():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except OSError:
            result.put(None)

    threading.Thread(target=lookup, daemon=True).start()
    try:
        addresses = result.get(timeout=max(0.001, timeout))
    except queue.Empty:
        raise TimeoutError("URL DNS resolution timed out") from None
    if not addresses:
        raise URLResolutionError("URL host could not be resolved")
    return addresses


# Cloud metadata and link-local services are refused even with allow_local.
ALWAYS_BLOCKED = tuple(ipaddress.ip_network(net) for net in (
    "169.254.0.0/16", "fe80::/10", "fd00:ec2::254/128"))


def always_blocked(address):
    """True for link-local/metadata addresses, including mapped and tunnelled forms."""
    address = ipaddress.ip_address(address)
    candidates = [address]
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped:
        candidates.append(mapped)
    if getattr(address, "sixtofour", None):
        candidates.append(address.sixtofour)
    candidates += list(getattr(address, "teredo", None) or [])
    if address.version == 6 and address in ipaddress.ip_network("64:ff9b::/96"):
        candidates.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
    return any(item.version == net.version and item in net
               for item in candidates for net in ALWAYS_BLOCKED)


def destination(url, allow_local, timeout):
    parts, host, port = parse_url(url)
    if not allow_local and (host == "localhost" or host.endswith((".localhost", ".local", ".internal"))):
        raise URLPolicyError("URL local/private network access requires the user's allow_local plugin config")
    addresses = resolve(host, port, timeout)
    for entry in addresses:
        if always_blocked(entry[4][0].split("%", 1)[0]):
            raise URLPolicyError("URL link-local/metadata destinations are always blocked")
    if not allow_local:
        for entry in addresses:
            address = ipaddress.ip_address(entry[4][0])
            address = getattr(address, "ipv4_mapped", None) or address
            embedded = ([address.sixtofour] if getattr(address, "sixtofour", None) else [])
            embedded += list(getattr(address, "teredo", None) or [])
            if (not address.is_global or address.is_multicast or address.is_reserved or
                    any(not item.is_global or item.is_multicast for item in embedded)):
                raise URLPolicyError("URL local/private network access requires the user's allow_local plugin config")
    return parts, host, port, addresses


class GuardedProxy(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, allow_local, deadline):
        self.allow_local = allow_local
        self.deadline = deadline
        self.violation = None
        self.connections = set()
        self.lock = threading.Lock()
        self.proxies = getproxies()
        super().__init__(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("URL capture timed out")
        return remaining

    def connect(self, url):
        parts, host, port, addresses = destination(url, self.allow_local, min(5, self.remaining()))
        upstream = None if proxy_bypass(host) else self.proxies.get(parts.scheme)
        if upstream:
            proxy = urlsplit(upstream if "://" in upstream else "http://" + upstream)
            if proxy.scheme != "http" or not proxy.hostname:
                raise URLPolicyError("URL capture requires an HTTP CONNECT proxy")
            # Preserve the configured proxy, while pinning the public address.
            # Hostname-only proxy allowlists may reject numeric CONNECT targets;
            # fail closed rather than allowing a second, unvalidated lookup.
            sock = socket.create_connection((proxy.hostname, proxy.port or 80), timeout=min(5, self.remaining()))
            try:
                # Always pin the validated numeric address, also with allow_local,
                # so the upstream proxy cannot re-resolve to a metadata address.
                target = addresses[0][4][0].split("%", 1)[0]
                authority = ("[" + target + "]" if ":" in target else target) + ":" + str(port)
                headers = f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n"
                if proxy.username is not None:
                    from urllib.parse import unquote
                    token = base64.b64encode((unquote(proxy.username) + ":" + unquote(proxy.password or "")).encode()).decode()
                    headers += "Proxy-Authorization: Basic " + token + "\r\n"
                sock.sendall((headers + "\r\n").encode("ascii"))
                response = bytearray()
                while not response.endswith(b"\r\n\r\n") and len(response) < 16384:
                    chunk = sock.recv(1)
                    if not chunk:
                        break
                    response.extend(chunk)
                if response.split(b" ", 2)[1:2] != [b"200"]:
                    raise OSError("upstream proxy rejected connection")
                return sock
            except Exception:
                sock.close()
                raise
        last_error = None
        for family, kind, protocol, _, address in addresses:
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(min(5, self.remaining()))
                sock.connect(address)  # Validated numeric address, no DNS rebinding.
                return sock
            except OSError as exc:
                last_error = exc
                sock.close()
        raise OSError("destination connection failed") from last_error

    def close(self):
        self.shutdown()
        with self.lock:
            for connection in self.connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.server_close()
        self.thread.join(timeout=1)

    def handle_error(self, request, client_address):
        pass  # Never log request paths, credentials, or exception details.


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    rbufsize = 0  # Do not buffer body bytes before switching to the relay.

    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(min(5, self.server.remaining()))

    def _forward(self, tunnel=False):
        remote = None
        try:
            url = "https://" + self.path if tunnel else self.path
            parts, host, port = parse_url(url)
            remote = self.server.connect(url)
            if tunnel:
                self.send_response(200)
                self.end_headers()
            else:
                path = parts.path or "/"
                if parts.query:
                    path += "?" + parts.query
                authority = ("[" + host + "]" if ":" in host else host) + ":" + str(port)
                headers = [f"{self.command} {path} HTTP/1.1", "Host: " + authority, "Connection: close"]
                for key, value in self.headers.items():
                    if key.lower() not in {"host", "connection", "proxy-connection", "proxy-authorization", "upgrade"}:
                        headers.append(key + ": " + value)
                remote.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("latin-1"))
            with self.server.lock:
                self.server.connections.update((self.connection, remote))
            peers = (self.connection, remote)
            while self.server.remaining() > 0:
                readable, _, _ = select.select(peers, [], [], min(0.1, self.server.remaining()))
                for source in readable:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    target = remote if source is self.connection else self.connection
                    target.sendall(chunk)
        except URLPolicyError as exc:
            self.server.violation = str(exc)
            self.send_error(403, "URL destination blocked")
        except (OSError, TimeoutError, ValueError):
            try:
                self.send_error(502, "URL destination unavailable")
            except OSError:
                pass
        finally:
            self.close_connection = True
            if remote is not None:
                with self.server.lock:
                    self.server.connections.discard(self.connection)
                    self.server.connections.discard(remote)
                remote.close()

    def do_CONNECT(self):
        self._forward(tunnel=True)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _forward
