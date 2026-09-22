"""
peer.py

A peer in the P2P file-sharing system. Each peer is simultaneously:

  - a *server*: a background thread that listens for and serves OBTAIN
    (download) requests from other peers, and REPLICATE (replica push)
    requests coming from the peer that owns the original copy.
  - a *client*: registers its shared directory with the indexing server
    on startup, and gives the user a CLI to look up and download files.

Usage
-----
    python3 peer.py <peer_id> <shared_dir> <peer_listen_port> \\
        <indexserver_host> <indexserver_port>

CLI commands once running
--------------------------
    lookup <filename>          -- ask the index server who holds this file
    get <filename> <index>     -- download from the peer shown at <index>
                                   in the most recent lookup's results
    quit
"""

import os
import socket
import sys
import threading

from common.protocol import recv_file, recv_line, send_file, send_line

# Directory this peer shares and stores downloaded/replicated files in.
# Set once in main().
shared_dir = None


def list_shared_files(directory):
    return [
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
    ]


# ---------------------------------------------------------------------------
# Peer server: answers OBTAIN (download) and REPLICATE (push) requests.
# ---------------------------------------------------------------------------
def handle_peer_connection(conn, addr):
    try:
        line = recv_line(conn)
        if not line:
            return
        msg_type, _, rest = line.partition("|")
        parts = rest.split("|")

        if msg_type == "OBTAIN":
            filename = parts[0]
            filepath = os.path.join(shared_dir, filename)
            if not os.path.isfile(filepath):
                send_line(conn, "ERROR|file not found")
                return
            send_line(conn, "OK|")
            send_file(conn, filepath)

        elif msg_type == "REPLICATE":
            # Another peer is pushing us a replica of one of its files.
            filename = parts[0]
            send_line(conn, "OK|")
            dest_path = os.path.join(shared_dir, filename)
            size = recv_file(conn, dest_path)
            print(f"[peer-server] received replica '{filename}' ({size} bytes)")

        else:
            send_line(conn, f"ERROR|unknown command '{msg_type}'")
    except Exception as exc:  # noqa: BLE001
        print(f"[peer-server] error handling {addr}: {exc}")
    finally:
        conn.close()


def run_peer_server(listen_port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", listen_port))
    server_sock.listen(128)
    print(f"[peer-server] listening on port {listen_port}")

    while True:
        conn, addr = server_sock.accept()
        threading.Thread(
            target=handle_peer_connection, args=(conn, addr), daemon=True
        ).start()


# ---------------------------------------------------------------------------
# Peer client: talks to the indexing server and to other peers.
# ---------------------------------------------------------------------------
def register_with_index_server(index_host, index_port, peer_id, self_host, self_port):
    files = list_shared_files(shared_dir)
    with socket.create_connection((index_host, index_port)) as sock:
        send_line(
            sock, f"REGISTER|{peer_id}|{self_host}|{self_port}|{','.join(files)}"
        )
        reply = recv_line(sock)

    msg_type, _, rest = reply.partition("|")
    if msg_type != "OK":
        print(f"[peer] registration failed: {reply}")
        return

    print(f"[peer] registered {len(files)} file(s) with index server")
    if rest:
        push_replicas(rest, files)


def push_replicas(targets_str, files):
    """
    targets_str: "peer_id:host:port;peer_id:host:port;...", as returned
    by the index server's REGISTER reply. Push every locally shared file
    to each target peer.
    """
    for target in targets_str.split(";"):
        if not target:
            continue
        pid, host, port_str = target.split(":")
        port = int(port_str)
        for fname in files:
            try:
                with socket.create_connection((host, port)) as sock:
                    send_line(sock, f"REPLICATE|{fname}")
                    ack = recv_line(sock)
                    if ack.startswith("OK"):
                        send_file(sock, os.path.join(shared_dir, fname))
                print(f"[peer] replicated '{fname}' to {pid} ({host}:{port})")
            except OSError as exc:
                print(f"[peer] failed to replicate '{fname}' to {pid}: {exc}")


def do_lookup(index_host, index_port, filename):
    with socket.create_connection((index_host, index_port)) as sock:
        send_line(sock, f"SEARCH|{filename}")
        reply = recv_line(sock)

    msg_type, _, rest = reply.partition("|")
    if msg_type != "RESULTS" or not rest:
        print(f"No peers found holding '{filename}'")
        return []

    results = []
    for entry in rest.split(";"):
        pid, host, port_str = entry.split(":")
        results.append((pid, host, int(port_str)))

    for i, (pid, host, port) in enumerate(results):
        print(f"  [{i}] peer {pid} at {host}:{port}")
    return results


def do_get(filename, peer_host, peer_port):
    with socket.create_connection((peer_host, peer_port)) as sock:
        send_line(sock, f"OBTAIN|{filename}")
        reply = recv_line(sock)
        if not reply.startswith("OK"):
            print(f"download failed: {reply}")
            return
        dest_path = os.path.join(shared_dir, filename)
        recv_file(sock, dest_path)

    # Required by the assignment: never print actual file contents.
    print(f"display file '{filename}'")


def cli_loop(index_host, index_port):
    print("Commands: lookup <filename> | get <filename> <peer_index> | quit")
    last_results = []
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        cmd, *args = line.split()

        if cmd == "lookup" and len(args) == 1:
            last_results = do_lookup(index_host, index_port, args[0])
        elif cmd == "get" and len(args) == 2:
            filename, idx_str = args
            idx = int(idx_str)
            if 0 <= idx < len(last_results):
                _, host, port = last_results[idx]
                do_get(filename, host, port)
            else:
                print("invalid peer index -- run 'lookup <filename>' first")
        elif cmd == "quit":
            break
        else:
            print("unknown command")


def main():
    global shared_dir

    if len(sys.argv) != 6:
        print(
            f"usage: {sys.argv[0]} <peer_id> <shared_dir> <peer_listen_port> "
            f"<indexserver_host> <indexserver_port>"
        )
        sys.exit(1)

    peer_id = sys.argv[1]
    shared_dir = sys.argv[2]
    peer_listen_port = int(sys.argv[3])
    index_host = sys.argv[4]
    index_port = int(sys.argv[5])

    os.makedirs(shared_dir, exist_ok=True)

    # Start the peer server before registering, so it's ready to accept
    # connections (including replica pushes) as soon as registration
    # completes.
    threading.Thread(
        target=run_peer_server, args=(peer_listen_port,), daemon=True
    ).start()

    self_host = socket.gethostbyname(socket.gethostname())
    register_with_index_server(index_host, index_port, peer_id, self_host, peer_listen_port)

    cli_loop(index_host, index_port)


if __name__ == "__main__":
    main()