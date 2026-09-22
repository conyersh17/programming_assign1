"""

Shared wire-protocol helpers for the P2P file-sharing system.

Design: all control messages are newline-terminated, pipe-delimited text
lines, e.g. "REGISTER|peer1|10.0.0.1|5001|a.txt,b.bin". File payloads are
sent as a text header line giving the size in bytes, followed by exactly
that many raw bytes on the same socket -- this lets us move files of any
type/size (1KB text up to 1GB binary) without needing a serialization
library.
"""

import os
import socket

# Chunk size used when streaming file bytes over the socket.
BUF_SIZE = 65536


def send_line(sock: socket.socket, line: str) -> None:
    """Send a single newline-terminated text line."""
    sock.sendall((line + "\n").encode("utf-8"))


def recv_line(sock: socket.socket) -> str:
    """
    Read a single newline-terminated text line from the socket.

    Reads one byte at a time. Control messages are short (peer ids,
    filenames, ports), so the per-byte overhead is negligible -- and
    reading byte-by-byte guarantees we stop exactly at the '\\n' and
    never accidentally consume bytes belonging to a file payload that
    follows in the same stream.
    """
    chars = []
    while True:
        b = sock.recv(1)
        if not b:
            # Peer closed the connection.
            break
        if b == b"\n":
            break
        chars.append(b)
    return b"".join(chars).decode("utf-8")


def send_file(sock: socket.socket, filepath: str) -> None:
    """Send a file's size (as a header line) followed by its raw bytes."""
    size = os.path.getsize(filepath)
    send_line(sock, str(size))
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(BUF_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)


def recv_file(sock: socket.socket, dest_path: str) -> int:
    """
    Receive a file: read the size header line, then read exactly that
    many bytes and write them to dest_path. Returns the number of bytes
    received.
    """
    size = int(recv_line(sock))
    remaining = size
    with open(dest_path, "wb") as f:
        while remaining > 0:
            chunk = sock.recv(min(BUF_SIZE, remaining))
            if not chunk:
                raise ConnectionError(
                    "connection closed before file transfer completed "
                    f"({remaining} of {size} bytes still expected)"
                )
            f.write(chunk)
            remaining -= len(chunk)
    return size