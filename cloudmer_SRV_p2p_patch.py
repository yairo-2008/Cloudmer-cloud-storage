"""
cloudmer_SRV_p2p_patch.py
=========================
Drop-in additions/replacements for cloudmer_SRV.py to wire up the P2P node.

1.  Import + global p2p_node
2.  Updated handle_upload_done  — broadcasts TX instead of mining locally
3.  Updated main()              — starts the P2P node before accepting clients
"""

# ── 1. Add these imports at the top of cloudmer_SRV.py ───────────────────────

from p2p import P2PNode
from blockchain import make_upload_tx

# Replace the existing:
#   blockchain = CloudBlockchain()
#   chain_lock = threading.Lock()
# With a single P2PNode that owns the blockchain:

P2P_PORT   = 6000          # TCP port this server node listens on for P2P traffic
CHAIN_PATH = "chain.json"

p2p_node: P2PNode = None   # initialised in main()


# ── 2. Updated handle_upload_done ────────────────────────────────────────────

def handle_upload_done(parts, owner_email: str):
    """
    DONE~transfer_id~md5  →  DONE~OK~file_hash

    After verifying the MD5:
      a) Save the file to disk.
      b) Build an UPLOAD transaction.
      c) Submit it to the P2P network via p2p_node.submit_transaction().
         - This adds it to the local pending pool.
         - It broadcasts NEW_TX to every peer.
         - The mining loop on any node (including this one) will pick it up,
           run PoW, and then broadcast the finished block via NEW_BLOCK.
    """
    import hashlib, os, zlib

    if len(parts) < 3:
        return b'DONE~FAIL~Bad format'

    tid          = parts[1]
    expected_md5 = parts[2]

    if tid not in active_transfers:
        return b'DONE~FAIL~Unknown transfer'

    transfer   = active_transfers.pop(tid)
    chunks     = transfer["chunks"]
    filename   = transfer["filename"]
    num_chunks = transfer["total_chunks"]

    # ── Reconstruct & verify ──────────────────────────────────────────────
    file_data  = b''.join(chunks[i] for i in range(num_chunks))
    actual_md5 = hashlib.md5(file_data).hexdigest()
    if actual_md5 != expected_md5:
        return b'DONE~FAIL~MD5 mismatch - file corrupted'

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    out_path = os.path.join(UPLOADS_DIR, filename)
    with open(out_path, 'wb') as f:
        f.write(file_data)

    file_size = len(file_data)
    file_hash = hashlib.sha256(file_data).hexdigest()
    print(f'[UPLOAD] Saved: {filename} ({file_size} B)  sha256={file_hash[:12]}…')

    # ── Build transaction ─────────────────────────────────────────────────
    tx = make_upload_tx(
        owner_key    = owner_email,
        file_hash    = file_hash,
        file_name    = filename,
        file_size    = file_size,
        chunk_count  = num_chunks,
        storage_nodes= [p2p_node.node_id],   # this server is the storage node
    )

    # ── Submit to P2P network (add to pool + broadcast NEW_TX) ───────────
    p2p_node.submit_transaction(tx)
    print(f'[P2P] TX broadcast for {filename}. Pending: '
          f'{len(p2p_node.blockchain.pending_transactions)}')

    return f'DONE~OK~{file_hash}'.encode()


# ── 3. Updated main() ─────────────────────────────────────────────────────────

def main():
    global all_to_die, p2p_node

    get_existing_rsa_keys()
    init_db()

    # ── Start P2P node ───────────────────────────────────────────────────
    p2p_node = P2PNode(
        host       = "0.0.0.0",
        port       = P2P_PORT,
        node_id    = f"server:{P2P_PORT}",
        difficulty = 3,
        chain_path = CHAIN_PATH,
    )

    # Register callbacks for observability
    p2p_node.on("block_mined",    lambda b: print(f"[CHAIN] ⛏  Mined block #{b.index}"))
    p2p_node.on("block_accepted", lambda b: print(f"[CHAIN] ✓  Accepted block #{b.index} from peer"))
    p2p_node.on("chain_replaced", lambda:   print("[CHAIN] ↔  Chain replaced (longer chain found)"))

    p2p_node.start()

    # ── Optionally connect to bootstrap peers ────────────────────────────
    # p2p_node.connect_to_peer("192.168.1.10", 6000)

    # ── Start file upload TCP server ─────────────────────────────────────
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, ".trash"),   exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, ".starred"), exist_ok=True)

    srv_sock = socket.socket()
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_sock.bind(('0.0.0.0', 8888))
    srv_sock.listen(0)
    print(f'[SRV] Client server up on :8888 | P2P node on :{P2P_PORT}')

    threads = []
    i = 1
    while True:
        cli_sock, addr = srv_sock.accept()
        t = threading.Thread(target=handle_client, args=(cli_sock, i, addr))
        t.start()
        threads.append(t)
        i += 1
        if i > 1000:
            print('Going down for maintenance')
            break

    all_to_die = True
    p2p_node.stop()
    for t in threads:
        t.join()
    srv_sock.close()
    print('Bye..')


# ── Helper used in dispatcher — queries via p2p_node.blockchain ───────────────

def handle_file_metadata(parts):
    if len(parts) < 2:
        return b'FMTA~FAIL~missing file_hash'
    import json
    meta = p2p_node.blockchain.get_file_metadata(parts[1])
    if meta is None:
        return b'FMTA~FAIL~not found'
    return f'FMTA~OK~{json.dumps(meta)}'.encode()


def handle_file_history(parts):
    if len(parts) < 2:
        return b'FHST~FAIL~missing file_hash'
    import json
    history = p2p_node.blockchain.get_file_history(parts[1])
    return f'FHST~OK~{json.dumps(history)}'.encode()
