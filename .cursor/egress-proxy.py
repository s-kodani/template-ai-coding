#!/usr/bin/env python3
"""Host-side CONNECT proxy so Docker containers can reach allowlisted HTTPS hosts.

Cloud Agent nested Docker disables bridge-nf-call-iptables so intra-compose
traffic works. That also skips MASQUERADE, so containers cannot open sockets to
the public internet. Containers should set HTTPS_PROXY to this process
(bridge gateway, typically 172.18.0.1:8888).
"""

from __future__ import annotations

import select
import socket
import threading

HOST = "0.0.0.0"
PORT = 8888
TIMEOUT = 30


def _relay(left: socket.socket, right: socket.socket) -> None:
    sockets = [left, right]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], TIMEOUT)
            if not readable:
                return
            for sock in readable:
                other = right if sock is left else left
                data = sock.recv(65536)
                if not data:
                    return
                other.sendall(data)
    except OSError:
        return
    finally:
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()


def _handle(client: socket.socket) -> None:
    client.settimeout(TIMEOUT)
    try:
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = client.recv(4096)
            if not chunk:
                return
            request += chunk
        first = request.split(b"\r\n", 1)[0].decode("latin1")
        parts = first.split(" ")
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
            return
        host_port = parts[1]
        host, _, port_s = host_port.partition(":")
        port = int(port_s or "443")
        upstream = socket.create_connection((host, port), timeout=TIMEOUT)
        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        client.settimeout(None)
        upstream.settimeout(None)
        _relay(client, upstream)
    except Exception:
        try:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
        except OSError:
            pass
        client.close()


def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(64)
    while True:
        client, _addr = server.accept()
        threading.Thread(target=_handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
