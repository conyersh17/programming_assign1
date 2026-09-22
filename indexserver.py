"""
indexserver.py

Central indexing server for the Napster-style P2P file-sharing system.

Responsibilities
-----------------
- REGISTER: a peer registers its (host, port) and the list of files it is
  sharing. The server records this in its in-memory index. If a
  replication factor > 1 is configured, the server also picks other
  currently-registered peers as replication targets and tells the
  registering peer to push copies to them (the actual byte transfer
  happens peer-to-peer, not through this server).
- SEARCH: given a filename, return every peer currently known to hold a
  copy of it.

The server does not store file contents itself -- only metadata
(peer_id -> (host, port) and filename -> set of peer_ids).

Usage
-----
    python3 indexserver.py <listen_port> [replication_factor]

Concurrency
-----------
One thread per incoming connection. All access to the shared
`peer_table` / `file_index` dictionaries goes through `state_lock`, and
the lock is held only around the dictionary mutations -- never during
network I/O -- to keep critical sections short and avoid blocking other
peers' registrations/searches on a slow connection.
"""

import random
import socket
import sys
import threading

from common.protocol import recv_line, send_line

# ---------------------------------------------------------------------------
# Shared state. All access must go through `state_lock`.
# ---------------------------------------------------------------------------
state_lock = threading.Lock()
peer_table = {}   # peer_id -> (host, port)
file_index = {}    # filename -> set of peer_id

# Set from argv in main(); how many total copies of each file should
# exist across the system (including the original registering peer).
REPLICATION_FACTOR = 1


def handle_register(parts, conn):
    """
    parts: [peer_id, host, port, "f1,f2,f3"]

    Registers the peer and its files. Replies with:
        OK|target1_id:host:port;target2_id:host:port;...
    listing the peers (if any) that the registering peer should push
    replicas of its files to, based on REPLICATION_FACTOR.
    """
    peer_id, host, port_str, files_csv = parts
    port = int(port_str)
    files = [f for f in files_csv.split(",") if f]

    with state_lock:
        peer_table[peer_id] = (host, port)
        for fname in files:
            file_index.setdefault(fname, set()).add(peer_id)

        # Choose up to (REPLICATION_FACTOR - 1) other known peers as
        # replication targets for this peer's files.
        other_peer_ids = [pid for pid in peer_table if pid != peer_id]
        random.shuffle(other_peer_ids)
        target_ids = other_peer_ids[: max(0, REPLICATION_FACTOR - 1)]
        targets = [(pid, *peer_table[pid]) for pid in target_ids]

        # Reflect the (about-to-happen) replication in the index now, so
        # SEARCH can point to these peers as soon as the push completes.
        for pid in target_ids:
            for fname in files:
                file_index.setdefault(fname, set()).add(pid)

    reply = ";".join(f"{pid}:{h}:{p}" for pid, h, p in targets)
    send_line(conn, f"OK|{reply}")


def handle_search(parts, conn):
    """parts: [filename]. Reply: RESULTS|peer_id:host:port;peer_id:host:port..."""
    filename = parts[0]
    with state_lock:
        peer_ids = file_index.get(filename, set())
        results = [(pid, *peer_table[pid]) for pid in peer_ids if pid in peer_table]

    reply = ";".join(f"{pid}:{h}:{p}" for pid, h, p in results)
    send_line(conn, f"RESULTS|{reply}")


def handle_connection(conn, addr):
    try:
        line = recv_line(conn)
        if not line:
            return
        msg_type, _, rest = line.partition("|")
        parts = rest.split("|")

        if msg_type == "REGISTER":
            handle_register(parts, conn)
        elif msg_type == "SEARCH":
            handle_search(parts, conn)
        else:
            send_line(conn, f"ERROR|unknown command '{msg_type}'")
    except Exception as exc:  # noqa: BLE001 -- report any failure to the client
        try:
            send_line(conn, f"ERROR|{exc}")
        except OSError:
            pass
    finally:
        conn.close()


def main():
    global REPLICATION_FACTOR

    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <listen_port> [replication_factor]")
        sys.exit(1)

    listen_port = int(sys.argv[1])
    REPLICATION_FACTOR = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", listen_port))
    server_sock.listen(128)

    print(
        f"[indexserver] listening on port {listen_port}, "
        f"replication_factor={REPLICATION_FACTOR}"
    )

    try:
        while True:
            conn, addr = server_sock.accept()
            threading.Thread(
                target=handle_connection, args=(conn, addr), daemon=True
            ).start()
    except KeyboardInterrupt:
        print("\n[indexserver] shutting down")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()