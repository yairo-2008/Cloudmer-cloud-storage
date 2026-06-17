__author__ = 'Omer'

import sys, os, threading, socket, rsa, json, time
from aes_functions import recv_with_AES, send_with_AES
from tcp_by_size import recv_by_size, send_with_size
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot, Signal

# ── Shared persistent connection ──────────────────────────────────────────────
_sock: socket.socket = None
_key:  str           = None
_sock_lock           = threading.Lock()   # one request/response at a time
_logged_in           = threading.Event()  # set after successful login/signup


def connect_to_server():
    """Open a fresh RSA-handshaked AES session. Returns (sock, session_key)."""
    s = socket.socket()
    s.connect(('127.0.0.1', 8888))
    pub_bytes  = recv_by_size(s)
    public_key = rsa.PublicKey.load_pkcs1(pub_bytes)
    session_key = os.urandom(16).hex()
    send_with_size(s, rsa.encrypt(session_key.encode(), public_key))
    return s, session_key


def _req(message: str) -> str:
    """
    Thread-safe single request/response over the shared socket.
    Holds _sock_lock for the full send+recv so no two threads interleave.
    """
    with _sock_lock:
        send_with_AES(_sock, message.encode(), _key)
        return recv_with_AES(_sock, _key).decode()


def parse_file_list(raw: str):
    """Parse 'name|size|modified|file_hash;...' into list of dicts."""
    files = []
    if not raw or not raw.strip():
        return files
    for entry in raw.split(';'):
        parts = entry.split('|')
        if len(parts) >= 3:
            files.append({
                "name":      parts[0],
                "size":      parts[1],
                "modified":  parts[2],
                "file_hash": parts[3] if len(parts) > 3 else "",
            })
    return files


# ─────────────────────────────────────────────────────────────────────────────
class Backend(QObject):

    # Auth
    loginSuccess  = Signal(str)
    loginFailed   = Signal(str)
    signupSuccess = Signal(str)
    signupFailed  = Signal(str)

    # File ops
    uploadProgress   = Signal(int)
    uploadSuccess    = Signal(str)        # "filename|file_hash"
    uploadFailed     = Signal(str)
    fileListReady    = Signal('QVariantList')
    starredListReady = Signal('QVariantList')
    trashListReady   = Signal('QVariantList')
    starToggled      = Signal(str, bool)
    fileDeleted      = Signal(str)
    fileRestored     = Signal(str)
    filePurged       = Signal(str)

    # ── Download signals ──────────────────────────────────────────────────────
    downloadProgress = Signal(int)        # 0-100
    downloadSuccess  = Signal(str)        # local save path
    downloadFailed   = Signal(str)        # error message

    # Blockchain
    blockchainUpdated = Signal('QVariantList')
    fileMetaReady     = Signal('QVariant')
    fileHistoryReady  = Signal('QVariantList')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chain_height = -1
        threading.Thread(target=self._chain_poller, daemon=True).start()

    # ── Chain poller ──────────────────────────────────────────────────────────

    def _chain_poller(self):
        """
        Poll BLCH every 10 s to keep BlockchainView fresh.
        Waits for _logged_in so it never touches the socket before login.
        """
        _logged_in.wait()
        while True:
            time.sleep(10)
            try:
                resp  = _req("BLCH")
                parts = resp.split('~', 2)
                if len(parts) >= 2 and parts[1] == 'OK':
                    chain = json.loads(parts[2])
                    if len(chain) != self._chain_height:
                        self._chain_height = len(chain)
                        self.blockchainUpdated.emit(chain)
            except Exception:
                pass  # server not up yet — retry next tick

    # ── AUTH ──────────────────────────────────────────────────────────────────

    @Slot(str, str)
    def login(self, email: str, password: str):
        email = email.strip(); password = password.strip()
        if not email or not password:
            self.loginFailed.emit("Please fill in all fields.")
            return

        def do():
            global _sock, _key
            try:
                s, k = connect_to_server()
                # Login without the lock — socket is not shared yet
                send_with_AES(s, f"LOGN~{email}~{password}".encode(), k)
                resp  = recv_with_AES(s, k).decode()
                parts = resp.split('~')
                if parts[1] == 'OK':
                    with _sock_lock:
                        _sock = s
                        _key  = k
                    _logged_in.set()
                    self.loginSuccess.emit(parts[2])
                else:
                    s.close()
                    self.loginFailed.emit(parts[2])
            except Exception as e:
                self.loginFailed.emit(f"Connection error: {e}")

        threading.Thread(target=do, daemon=True).start()

    @Slot(str, str, str)
    def signup(self, name: str, email: str, password: str):
        name = name.strip(); email = email.strip(); password = password.strip()
        if not name or not email or not password:
            self.signupFailed.emit("Please fill in all fields.")
            return
        if len(password) < 6:
            self.signupFailed.emit("Password must be at least 6 characters.")
            return

        def do():
            global _sock, _key
            try:
                s, k = connect_to_server()
                send_with_AES(s, f"RGST~{name}~{email}~{password}".encode(), k)
                resp  = recv_with_AES(s, k).decode()
                parts = resp.split('~')
                if parts[1] == 'OK':
                    with _sock_lock:
                        _sock = s
                        _key  = k
                    _logged_in.set()
                    self.signupSuccess.emit(f"Welcome, {parts[2]}! Account created.")
                else:
                    s.close()
                    self.signupFailed.emit(parts[2])
            except Exception as e:
                self.signupFailed.emit(f"Connection error: {e}")

        threading.Thread(target=do, daemon=True).start()

    # ── FILE LISTS ────────────────────────────────────────────────────────────

    @Slot()
    def getFileList(self):
        def do():
            try:
                resp  = _req("FLST~all")
                parts = resp.split('~', 2)
                if parts[1] == 'OK':
                    self.fileListReady.emit(parse_file_list(parts[2] if len(parts) > 2 else ""))
            except Exception as e:
                print(f"getFileList error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot()
    def getStarredFiles(self):
        def do():
            try:
                resp  = _req("FLST~starred")
                parts = resp.split('~', 2)
                if parts[1] == 'OK':
                    self.starredListReady.emit(parse_file_list(parts[2] if len(parts) > 2 else ""))
            except Exception as e:
                print(f"getStarredFiles error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot()
    def getTrashFiles(self):
        def do():
            try:
                resp  = _req("FLST~trash")
                parts = resp.split('~', 2)
                if parts[1] == 'OK':
                    self.trashListReady.emit(parse_file_list(parts[2] if len(parts) > 2 else ""))
            except Exception as e:
                print(f"getTrashFiles error: {e}")
        threading.Thread(target=do, daemon=True).start()

    # ── FILE ACTIONS ──────────────────────────────────────────────────────────

    @Slot(str)
    def starFile(self, filename: str):
        def do():
            try:
                resp  = _req(f"STAR~{filename}")
                parts = resp.split('~')
                if parts[1] == 'OK':
                    self.starToggled.emit(filename, parts[2] == '1')
            except Exception as e:
                print(f"starFile error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def deleteFile(self, filename: str):
        def do():
            try:
                resp  = _req(f"DELT~{filename}")
                parts = resp.split('~')
                if parts[1] == 'OK':
                    self.fileDeleted.emit(filename)
            except Exception as e:
                print(f"deleteFile error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def restoreFile(self, filename: str):
        def do():
            try:
                resp  = _req(f"RDLT~{filename}")
                parts = resp.split('~')
                if parts[1] == 'OK':
                    self.fileRestored.emit(filename)
            except Exception as e:
                print(f"restoreFile error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def purgeFile(self, filename: str):
        def do():
            try:
                resp  = _req(f"PRGE~{filename}")
                parts = resp.split('~')
                if parts[1] == 'OK':
                    self.filePurged.emit(filename)
            except Exception as e:
                print(f"purgeFile error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def uploadFile(self, file_path: str):
        """
        Chunked upload.  The ENTIRE sequence (UPLD → CHNK loop → DONE) runs
        inside a single _sock_lock acquisition so the poller cannot inject a
        BLCH request between sends and receives.
        """
        def do():
            try:
                import hashlib, zlib, math
                CHUNK_SIZE = 1024 * 1024  # 1 MB

                with open(file_path, 'rb') as f:
                    data = f.read()

                filename   = os.path.basename(file_path)
                total_size = len(data)
                num_chunks = max(1, math.ceil(total_size / CHUNK_SIZE))
                md5        = hashlib.md5(data).hexdigest()

                with _sock_lock:
                    # ── 1. Initiate ───────────────────────────────────────────
                    send_with_AES(_sock, f"UPLD~{filename}~{total_size}~{num_chunks}".encode(), _key)
                    resp  = recv_with_AES(_sock, _key).decode()
                    parts = resp.split('~')
                    if parts[1] != 'OK':
                        self.uploadFailed.emit(parts[2] if len(parts) > 2 else "UPLD rejected")
                        return
                    transfer_id = parts[2]

                    # ── 2. Chunks ─────────────────────────────────────────────
                    for i in range(num_chunks):
                        chunk      = data[i * CHUNK_SIZE: (i + 1) * CHUNK_SIZE]
                        compressed = zlib.compress(chunk, level=6)
                        use_comp   = len(compressed) < len(chunk) * 0.9
                        payload    = compressed if use_comp else chunk
                        is_comp    = 1 if use_comp else 0

                        # Header first, then raw payload — server reads both
                        send_with_AES(_sock,
                            f"CHNK~{transfer_id}~{i}~{len(payload)}~{is_comp}".encode(),
                            _key)
                        send_with_AES(_sock, payload, _key)
                        recv_with_AES(_sock, _key)          # get CHNK~OK~{i}

                        self.uploadProgress.emit(int((i + 1) / num_chunks * 100))

                    # ── 3. Finalise ───────────────────────────────────────────
                    send_with_AES(_sock, f"DONE~{transfer_id}~{md5}".encode(), _key)
                    resp = recv_with_AES(_sock, _key).decode()

                # Lock released — safe to call other methods now
                parts = resp.split('~')
                if parts[1] == 'OK':
                    file_hash = parts[2] if len(parts) > 2 else ""
                    self.uploadSuccess.emit(f"{filename}|{file_hash}")
                    self.getBlockchain()
                else:
                    self.uploadFailed.emit(parts[2] if len(parts) > 2 else "Unknown error")

            except Exception as e:
                self.uploadFailed.emit(str(e))

        threading.Thread(target=do, daemon=True).start()


    @Slot(str, str)
    def downloadFile(self, filename: str, save_dir:str):
        def do():
            import hashlib, zlib
            try:
                save_path = os.path.join(save_dir, filename)
                with _sock_lock:
                    send_with_AES(_sock, f"DWNL~{filename}".encode(), _key)
                    resp = recv_with_AES(_sock, _key).decode()
                    parts = resp.split('~')

                    if parts[1] != 'OK':
                        self.downloadFailed.emit(parts[2] if len(parts) > 2 else "Download rejected")
                        return

                    total_size = int(parts[2])
                    num_chunks = int(parts[3])
                    server_md5 = parts[4]

                    chunks = {}
                    for i in range(num_chunks):
                        header = recv_with_AES(_sock, _key).decode()
                        h = header.split('~')  # DCNK~idx~is_comp~size

                        raw_payload = recv_with_AES(_sock, _key)

                        send_with_AES(_sock, f"DACK~{i}".encode(), _key)

                        is_comp = h[2] == '1'
                        chunk_data = zlib.decompress(raw_payload) if is_comp else raw_payload
                        chunks[int(h[1])] = chunk_data

                        self.downloadProgress.emit(int((i + 1) / num_chunks * 100))

                file_data = b''.join(chunks[i] for i in range(num_chunks))
                if hashlib.md5(file_data).hexdigest() != server_md5:
                    self.downloadFailed.emit("MD5 mismatch - file corrupted")
                    return

                os.makedirs(save_dir, exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(file_data)

                self.downloadSuccess.emit(save_path)
            except Exception as e:
                self.downloadFailed.emit(f"Download error: {e}")

        threading.Thread(target=do, daemon=True).start()

    # ── BLOCKCHAIN ────────────────────────────────────────────────────────────

    @Slot()
    def getBlockchain(self):
        def do():
            try:
                resp  = _req("BLCH")
                parts = resp.split('~', 2)
                if len(parts) >= 2 and parts[1] == 'OK':
                    chain = json.loads(parts[2])
                    self._chain_height = len(chain)
                    self.blockchainUpdated.emit(chain)
            except Exception as e:
                print(f"getBlockchain error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def getFileDetails(self, file_hash: str):
        def do():
            try:
                resp  = _req(f"FMTA~{file_hash}")
                parts = resp.split('~', 2)
                if parts[1] == 'OK':
                    self.fileMetaReady.emit(json.loads(parts[2]))
            except Exception as e:
                print(f"getFileDetails error: {e}")
        threading.Thread(target=do, daemon=True).start()

    @Slot(str)
    def getFileHistory(self, file_hash: str):
        def do():
            try:
                resp  = _req(f"FHST~{file_hash}")
                parts = resp.split('~', 2)
                if parts[1] == 'OK':
                    self.fileHistoryReady.emit(json.loads(parts[2]))
                else:
                    self.fileHistoryReady.emit([])
            except Exception as e:
                print(f"getFileHistory error: {e}")
        threading.Thread(target=do, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Force Basic style — fixes "does not support customization" QML warnings
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    from PySide6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(lambda mode, ctx, msg: print(f"QML: {msg}"))

    app     = QGuiApplication(sys.argv)
    backend = Backend()
    engine  = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(os.path.join(os.path.dirname(__file__), "main.qml"))
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
