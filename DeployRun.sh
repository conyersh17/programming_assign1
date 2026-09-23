```bash
#!/bin/bash

# ============================================================
# CS550 Programming Assignment 1
# P2P Index Server - 1 Node vs 2 Node Scaling Study
#
# VM1 = Index Server
# VM2 = Peer 1
# VM3 = Peer 2
# ============================================================

set -e

# ============================================================
# CONFIGURATION
# ============================================================

# CHANGE THESE TO YOUR ACTUAL VM IP ADDRESSES

INDEX_HOST="192.168.56.101"
PEER1="192.168.56.102"
PEER2="192.168.56.103"

INDEX_PORT="5000"
PEER1_PORT="5001"
PEER2_PORT="5002"

REMOTE_DIR="$HOME/programming_assignment1"
DATA_DIR="$REMOTE_DIR/data"

RESULTS_DIR="./results"

NUM_REQUESTS=100

# ============================================================
# FILES
# ============================================================

APP_FILES=(
    "GenDataset.py"
    "weakScaling.py"
    "strongScaling.py"
    "plotResults.py"
    "peer.py"
    "indexserver.py"
)

# ============================================================
# HELPER
# ============================================================

header() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
    echo
}

# ============================================================
# CHECK LOCAL FILES
# ============================================================

header "CHECKING LOCAL FILES"

for FILE in "${APP_FILES[@]}"
do
    if [ ! -f "$FILE" ]; then
        echo "ERROR: Missing $FILE"
        exit 1
    fi
done

if [ ! -f "common/protocol.py" ]; then
    echo "ERROR: common/protocol.py not found."
    echo
    echo "Expected:"
    echo "    common/protocol.py"
    exit 1
fi

echo "All application files found."

# ============================================================
# CHECK PSSH
# ============================================================

if ! command -v pssh >/dev/null 2>&1; then
    echo "ERROR: pssh is not installed."
    echo
    echo "Install with:"
    echo "    brew install pssh"
    exit 1
fi

if ! command -v pscp.pssh >/dev/null 2>&1; then
    echo "ERROR: pscp.pssh is not installed."
    exit 1
fi

echo "pssh and pscp.pssh found."

# ============================================================
# CREATE HOST FILES
# ============================================================

echo "$PEER1" > peer1.txt
echo "$PEER2" > peer2.txt

echo "$PEER1" > peers.txt
echo "$PEER2" >> peers.txt

# ============================================================
# CREATE RESULT DIRECTORIES
# ============================================================

mkdir -p "$RESULTS_DIR/1-node"
mkdir -p "$RESULTS_DIR/2-node"

# ============================================================
# TEST PEER CONNECTIONS
# ============================================================

header "TESTING PEER SSH CONNECTIONS"

echo "Testing Peer 1..."
ssh -o ConnectTimeout=10 "$PEER1" "hostname"

echo
echo "Testing Peer 2..."
ssh -o ConnectTimeout=10 "$PEER2" "hostname"

echo
echo "SSH connections successful."

# ============================================================
# PREPARE PEERS
# ============================================================

header "PREPARING PEER VMS"

pssh -h peers.txt -i \
    "mkdir -p $REMOTE_DIR/common $DATA_DIR"

# ============================================================
# COPY APPLICATION TO PEERS
# ============================================================

header "COPYING APPLICATION TO PEERS"

for FILE in "${APP_FILES[@]}"
do
    echo "Copying $FILE..."

    pscp.pssh \
        -h peers.txt \
        "$FILE" \
        "$REMOTE_DIR/$FILE"
done

echo "Copying common/protocol.py..."

pscp.pssh \
    -h peers.txt \
    "common/protocol.py" \
    "$REMOTE_DIR/common/protocol.py"

pssh -h peers.txt -i \
    "touch $REMOTE_DIR/common/__init__.py"

echo
echo "Application copied successfully."

# ============================================================
# VERIFY REMOTE FILES
# ============================================================

header "VERIFYING REMOTE FILES"

pssh -h peers.txt -i \
    "cd $REMOTE_DIR && \
     ls -l GenDataset.py weakScaling.py strongScaling.py \
     plotResults.py peer.py common/protocol.py"

# ============================================================
# CHECK DISK SPACE
# ============================================================

header "CHECKING DISK SPACE"

pssh -h peers.txt -i \
    "df -h \$HOME"

echo
echo "The complete dataset is approximately 9 GB per peer."
echo "Make sure sufficient free disk space is available."

read -p "Generate the full dataset now? [y/N] " ANSWER

if [[ ! "$ANSWER" =~ ^[Yy]$ ]]; then
    echo
    echo "Stopped before dataset generation."
    exit 0
fi

# ============================================================
# GENERATE PEER 1 DATASET
# ============================================================

header "GENERATING PEER 1 DATASET"

ssh "$PEER1" \
    "cd $REMOTE_DIR && \
     python3 GenDataset.py \
     $DATA_DIR \
     peer1"

echo "Peer 1 dataset complete."

# ============================================================
# GENERATE PEER 2 DATASET
# ============================================================

header "GENERATING PEER 2 DATASET"

ssh "$PEER2" \
    "cd $REMOTE_DIR && \
     python3 GenDataset.py \
     $DATA_DIR \
     peer2"

echo "Peer 2 dataset complete."

# ============================================================
# CREATE FILE LISTS
# ============================================================

header "CREATING FILE LISTS"

ssh "$PEER1" \
    "find $DATA_DIR -type f -name 'peer1_*' | sort \
     > $REMOTE_DIR/peer1_files.txt"

ssh "$PEER2" \
    "find $DATA_DIR -type f -name 'peer2_*' | sort \
     > $REMOTE_DIR/peer2_files.txt"

echo "File lists created."

# ============================================================
# COPY INDEX SERVER TO VM1
# ============================================================

header "PREPARING INDEX SERVER"

ssh "$INDEX_HOST" \
    "mkdir -p $REMOTE_DIR/common"

scp indexserver.py \
    "$INDEX_HOST:$REMOTE_DIR/indexserver.py"

scp common/protocol.py \
    "$INDEX_HOST:$REMOTE_DIR/common/protocol.py"

ssh "$INDEX_HOST" \
    "touch $REMOTE_DIR/common/__init__.py"

echo "Index server files copied."

# ============================================================
# START INDEX SERVER
# ============================================================

header "STARTING INDEX SERVER"

ssh "$INDEX_HOST" \
    "pkill -f 'python3.*indexserver.py $INDEX_PORT' 2>/dev/null || true"

ssh "$INDEX_HOST" \
    "nohup python3 $REMOTE_DIR/indexserver.py $INDEX_PORT \
     > $REMOTE_DIR/indexserver.log 2>&1 < /dev/null &"

sleep 2
```
