__author__ = 'Omer'

from aes_functions import recv_with_AES, send_with_AES
import threading, traceback, time, socket, pathlib, rsa, os, hashlib, zlib, json, math
from tcp_by_size import recv_by_size, send_with_size
from database import init_db, register_user, login_user
from blockchain import CloudBlockchain, make_upload_tx

PUBLIC_KEY  = None
PRIVATE_KEY = None
all_to_die  = False

UPLOADS_DIR = "uploads"
CHAIN_PATH  = "chain.json"

active_transfers = {}   # tid -> {filename, total_chunks, chunks{}, owner}

blockchain = CloudBlockchain()
chain_lock = threading.Lock()


# ── Blockchain persistence ────────────────────────────────────────────────────

def init_blockchain():
    global blockchain
    if os.path.exists(CHAIN_PATH):
        blockchain.load(CHAIN_PATH)
        print(f"[CHAIN] Loaded from {CHAIN_PATH} — height {blockchain.height}")
    else:
        print("[CHAIN] Starting new blockchain.")


def save_blockchain():
    with chain_lock:
        blockchain.save(CHAIN_PATH)
    print(f"[CHAIN] Saved to {CHAIN_PATH} (height={blockchain.height})")


# ── RSA ───────────────────────────────────────────────────────────────────────

def get_existing_rsa_keys():
    global PUBLIC_KEY, PRIVATE_KEY
    with open("public_key.pem", "rb") as f:
        PUBLIC_KEY = rsa.PublicKey.load_pkcs1(f.read())
    with open("private_key.pem", "rb") as f:
        PRIVATE_KEY = rsa.PrivateKey.load_pkcs1(f.read())


def logtcp(direction, tid, byte_data):
    label = 'Sent     >>>' if direction == 'sent' else 'Received <<<'
    print(f'{tid} S LOG:{label} {byte_data[:80]}')


def send_data(sock, tid, bdata, key):
    send_with_AES(sock, bdata, key)
    logtcp('sent', tid, bdata)


# ── AUTH ──────────────────────────────────────────────────────────────────────

def handle_login(parts):
    if len(parts) < 3:
        return b'LOGN~FAIL~Bad request format'
    success, result = login_user(parts[1], parts[2])
    if success:
        print(f'Login success: {parts[1]}')
        return f'LOGN~OK~{result["full_name"]}'.encode()
    return f'LOGN~FAIL~{result}'.encode()


def handle_signup(parts):
    if len(parts) < 4:
        return b'RGST~FAIL~Bad request format'
    success, result = register_user(parts[1], parts[2], parts[3])
    if success:
        return f'RGST~OK~{parts[1]}'.encode()
    return f'RGST~FAIL~{result}'.encode()


# ── FILE LISTS ────────────────────────────────────────────────────────────────

def _get_file_meta(filepath):
    stat = os.stat(filepath)
    sb   = stat.st_size
    if sb < 1024:        size_str = f"{sb} B"
    elif sb < 1024**2:   size_str = f"{sb/1024:.1f} KB"
    else:                size_str = f"{sb/1024**2:.2f} MB"
    import datetime
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y")
    return os.path.basename(filepath), size_str, modified


def handle_file_list(parts):
    filter_type = parts[1] if len(parts) > 1 else "all"

    if filter_type == "trash":
        folder = os.path.join(UPLOADS_DIR, ".trash")
    elif filter_type == "starred":
        folder = os.path.join(UPLOADS_DIR, ".starred")
    else:
        folder = UPLOADS_DIR

    os.makedirs(folder, exist_ok=True)   # ensure exists before listdir + getmtime

    try:
        entries = []
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath) or fname.startswith('.'):
                continue
            name, size, modified = _get_file_meta(fpath)
            with open(fpath, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            entries.append((fname, f"{name}|{size}|{modified}|{file_hash}"))

        if filter_type in ("all", "recent"):
            entries.sort(
                key=lambda x: os.path.getmtime(os.path.join(folder, x[0])),
                reverse=True,
            )

        payload = ';'.join(e[1] for e in entries)
        return f'FLST~OK~{payload}'.encode()
    except Exception as e:
        return f'FLST~FAIL~{e}'.encode()


# ── FILE ACTIONS ──────────────────────────────────────────────────────────────

def handle_star(parts):
    if len(parts) < 2:
        return b'STAR~FAIL~missing filename'
    filename= parts[1]
    src = os.path.join(UPLOADS_DIR, filename)
    starred_dir = os.path.join(UPLOADS_DIR, ".starred")
    os.makedirs(starred_dir, exist_ok=True)
    dest = os.path.join(starred_dir, filename)

    if os.path.exists(dest):
        os.remove(dest)
        return b'STAR~OK~0'
    elif os.path.exists(src):
        import shutil; shutil.copy2(src, dest)
        return b'STAR~OK~1'
    return b'STAR~FAIL~file not found'


def handle_delete(parts):
    if len(parts) < 2:
        return b'DELT~FAIL~missing filename'
    filename = parts[1]
    src = os.path.join(UPLOADS_DIR, filename)
    trash = os.path.join(UPLOADS_DIR, ".trash")
    os.makedirs(trash, exist_ok=True)
    dest = os.path.join(trash, filename)
    if not os.path.exists(src):
        return b'DELT~FAIL~file not found'
    import shutil; shutil.move(src, dest)
    starred = os.path.join(UPLOADS_DIR, ".starred", filename)
    if os.path.exists(starred):
        os.remove(starred)
    return f'DELT~OK~{filename}'.encode()


def handle_restore(parts):
    if len(parts) < 2:
        return b'RDLT~FAIL~missing filename'
    filename = parts[1]
    src  = os.path.join(UPLOADS_DIR, ".trash", filename)
    dest = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(src):
        return b'RDLT~FAIL~file not in trash'
    import shutil; shutil.move(src, dest)
    return f'RDLT~OK~{filename}'.encode()


def handle_purge(parts):
    if len(parts) < 2:
        return b'PRGE~FAIL~missing filename'
    filename = parts[1]
    path     = os.path.join(UPLOADS_DIR, ".trash", filename)
    if not os.path.exists(path):
        return b'PRGE~FAIL~file not in trash'
    os.remove(path)
    return f'PRGE~OK~{filename}'.encode()


# ── UPLOAD ────────────────────────────────────────────────────────────────────

def handle_upload_init(parts, owner_email: str):
    """UPLD~filename~size~chunks  →  UPLD~OK~transfer_id"""
    if len(parts) < 4:
        return b'UPLD~FAIL~Bad format'
    filename   = parts[1]
    num_chunks = int(parts[3])
    tid        = os.urandom(8).hex()
    active_transfers[tid] = {
        "filename":     filename,
        "total_chunks": num_chunks,
        "chunks":       {},
        "owner":        owner_email,
    }
    return f'UPLD~OK~{tid}'.encode()


def handle_chunk(sock, session_key, parts):
    """
    CHNK~tid~idx~size~compressed
    The client sends the CHNK header as one AES message, then immediately
    sends the raw payload as a second AES message — no intermediate ACK.
    We read the payload here, store it, then return CHNK~OK~{idx}.
    """
    if len(parts) < 5:
        return b'CHNK~FAIL~Bad format'
    tid     = parts[1]
    idx     = int(parts[2])
    is_comp = parts[4] == '1'

    if tid not in active_transfers:
        return b'CHNK~FAIL~Unknown transfer id'

    # Read the payload (second AES message from client)
    raw  = recv_with_AES(sock, session_key)
    if not raw:
        return b'CHNK~FAIL~Empty payload'

    data = zlib.decompress(raw) if is_comp else raw
    active_transfers[tid]["chunks"][idx] = data
    return f'CHNK~OK~{idx}'.encode()


def handle_upload_done(parts, owner_email: str):
    """DONE~transfer_id~md5  →  DONE~OK~file_hash"""
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

    # Guard: all chunks must have arrived
    for i in range(num_chunks):
        if i not in chunks:
            return f'DONE~FAIL~Missing chunk {i}'.encode()

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
    print(f'[UPLOAD] Saved: {filename} ({file_size} bytes) hash={file_hash[:12]}...')

    tx = make_upload_tx(
        owner_key    = owner_email,
        file_hash    = file_hash,
        file_name    = filename,
        file_size    = file_size,
        chunk_count  = num_chunks,
        storage_nodes= ["local"],
    )
    with chain_lock:
        blockchain.add_transaction(tx)
        new_block = blockchain.mine_pending_transactions(miner_id="server")
    save_blockchain()
    print(f'[CHAIN] Block #{new_block.index} mined for {filename} hash={file_hash[:12]}…')

    return f'DONE~OK~{file_hash}'.encode()


# ── DOWNLOAD (NEW) ────────────────────────────────────────────────────────────

DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB per chunk, matches upload side


def handle_download(sock, session_key, parts):
    if len(parts) < 2:
        send_with_AES(sock, b'DWNL~FAIL~missing filename', session_key)
        return None

    filename = parts[1]
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or '..' in filename:
        send_with_AES(sock, b'DWNL~FAIL~invalid filename', session_key)
        return None

    file_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.isfile(file_path):
        send_with_AES(sock, f'DWNL~FAIL~file not found: {filename}'.encode(), session_key)
        return None

    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        total_size = len(file_data)
        num_chunks = max(1, math.ceil(total_size / DOWNLOAD_CHUNK_SIZE))
        file_md5 = hashlib.md5(file_data).hexdigest()

        send_with_AES(sock, f'DWNL~OK~{total_size}~{num_chunks}~{file_md5}'.encode(), session_key)


        for i in range(num_chunks):
            chunk = file_data[i * DOWNLOAD_CHUNK_SIZE: (i + 1) * DOWNLOAD_CHUNK_SIZE]
            compressed = zlib.compress(chunk, level=6)
            use_comp = len(compressed) < len(chunk) * 0.9
            if use_comp:
                payload = compressed
            else:
                payload=chunk
            is_comp = 1 if use_comp else 0

            send_with_AES(sock, f'DCNK~{i}~{is_comp}~{len(payload)}'.encode(), session_key)
            send_with_AES(sock, payload, session_key)

            ack_raw = recv_with_AES(sock, session_key)
            if not ack_raw:
                break
            ack = ack_raw.decode()
            if not ack.startswith('DACK'):
                print(f'Unexpected ACK: {ack}')
                break

        print(f'Sent {filename} ({total_size} bytes)')

    except Exception as e:
        print(f' Error sending {filename}: {e}')

    return None


# ── BLOCKCHAIN QUERIES ────────────────────────────────────────────────────────

def handle_file_metadata(parts):
    if len(parts) < 2:
        return b'FMTA~FAIL~missing file_hash'
    meta = blockchain.get_file_metadata(parts[1])
    if meta is None:
        return b'FMTA~FAIL~not found'
    return f'FMTA~OK~{json.dumps(meta)}'.encode()


def handle_file_history(parts):
    if len(parts) < 2:
        return b'FHST~FAIL~missing file_hash'
    history = blockchain.get_file_history(parts[1])
    return f'FHST~OK~{json.dumps(history)}'.encode()


def handle_get_chain():
    """BLCH  →  BLCH~OK~[{block summary dicts}]"""
    with chain_lock:
        chain_snapshot = list(blockchain.chain)

    summaries = []
    for block in chain_snapshot:
        primary_tx = next(
            (tx for tx in block.transactions if tx.get("type") == "UPLOAD"),
            None,
        )
        summaries.append({
            "index":         block.index,
            "hash":          block.hash,
            "timestamp":     block.timestamp,
            "previous_hash": block.previous_hash,
            "nonce":         block.nonce,
            "tx_count":      len(block.transactions),
            "file_hash":     primary_tx.get("file_hash", "") if primary_tx else "",
            "file_name":     primary_tx.get("file_name", "") if primary_tx else "",
            "sender_id":     primary_tx.get("owner",     "") if primary_tx else "",
            "is_verified":   blockchain.pow.is_valid_proof(block),
        })

    return f'BLCH~OK~{json.dumps(summaries)}'.encode()



def protocol_build_reply(request: bytes, sock, session_key, session_owner: str):
    try:
        decoded = request.decode("utf-8")
    except UnicodeDecodeError:
        return b'ERRR~004~Invalid encoding', False

    code  = decoded[:4]
    parts = decoded.split('~') if '~' in decoded else [decoded]

    if   code == 'EXIT':
        return b'EXTR', True
    elif code == 'LOGN':
        return handle_login(parts), False
    elif code == 'RGST':
        return handle_signup(parts), False
    elif code == 'FLST':
        return handle_file_list(parts), False
    elif code == 'STAR':
        return handle_star(parts), False
    elif code == 'DELT':
        return handle_delete(parts), False
    elif code == 'RDLT':
        return handle_restore(parts), False
    elif code == 'PRGE':
        return handle_purge(parts), False
    elif code == 'UPLD':
        return handle_upload_init(parts, session_owner), False
    elif code == 'CHNK':
        return handle_chunk(sock, session_key, parts), False
    elif code == 'DONE':
        tid   = parts[1] if len(parts) > 1 else ""
        owner = active_transfers.get(tid, {}).get("owner", session_owner)
        return handle_upload_done(parts, owner), False
    elif code == 'DWNL':
        handle_download(sock, session_key, parts)
        return None, False   # המנגנון של handle_download מטפל ב-IO בעצמו
    elif code == 'FMTA':
        return handle_file_metadata(parts), False
    elif code == 'FHST':
        return handle_file_history(parts), False
    elif code == 'BLCH':
        return handle_get_chain(), False
    else:
        return b'ERRR~002~code not supported', False


def handle_request(request: bytes, sock, session_key, session_owner: str):
    try:
        return protocol_build_reply(request, sock, session_key, session_owner)
    except Exception as err:
        print(traceback.format_exc())
        return b'ERRR~001~General error', True


def handle_client(sock, tid, addr):
    finish        = False
    session_owner = ""
    print(f'New Client #{tid} from {addr}')

    pub_bytes = pathlib.Path("public_key.pem").read_bytes()
    send_with_size(sock, pub_bytes)
    encrypted_session_key = recv_by_size(sock)
    session_key = rsa.decrypt(encrypted_session_key, PRIVATE_KEY).decode()
    print(f'[{tid}] Session key established.')

    sock.settimeout(0.1)
    while not finish:
        if all_to_die:
            break
        try:
            byte_data = recv_with_AES(sock, session_key)
            if not byte_data:
                print(f'Client #{tid} disconnected')
                break
            logtcp('recv', tid, byte_data)

            # Update session_owner BEFORE dispatching so upload handlers see it
            try:
                decoded = byte_data.decode("utf-8")
                if decoded.startswith("LOGN~"):
                    p = decoded.split('~')
                    if len(p) >= 2:
                        session_owner = p[1]   # email
            except Exception:
                pass

            to_send, finish = handle_request(byte_data, sock, session_key, session_owner)
            if to_send is not None:
                send_data(sock, tid, to_send, session_key)
            if finish:
                time.sleep(1)
                break

        except (socket.timeout, TimeoutError):
            pass
        except socket.error as e:
            print(f'Socket Error: {e}')
            break
        except Exception as e:
            print(f'General Error: {e}\n{traceback.format_exc()}')
            break

    print(f'Client #{tid} Exit')
    sock.close()


def main():
    global all_to_die
    get_existing_rsa_keys()
    init_db()
    init_blockchain()
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, ".trash"),   exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, ".starred"), exist_ok=True)

    srv_sock = socket.socket()
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_sock.bind(('0.0.0.0', 8888))
    srv_sock.listen(10)
    print('Server is up!\nWaiting for connections...')

    threads = []
    i = 1
    while True:
        try:
            cli_sock, addr = srv_sock.accept()
        except KeyboardInterrupt:
            break
        t = threading.Thread(target=handle_client, args=(cli_sock, i, addr), daemon=True)
        t.start()
        threads.append(t)
        i += 1
        if i > 1000:
            print('Going down for maintenance')
            break

    all_to_die = True
    srv_sock.close()
    print('Bye..')


if __name__ == '__main__':
    main()
