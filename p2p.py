"""
DecentraCloud - P2P Networking Layer  (v2 — Blockchain Integrated)
===================================================================
Implements a peer-to-peer network for blockchain synchronisation and
file-chunk distribution using raw Python sockets and threading.

New in v2
---------
* P2PNode owns a CloudBlockchain instance.
* NEW_BLOCK  → validate PoW + chain linkage before appending; gossip if valid.
* NEW_TX     → add to pending pool; trigger mining when pool is large enough.
* GET_CHAIN / CHAIN → full replace_chain consensus on connect and on demand.
* Mining runs in a dedicated background thread per node.
* broadcast_new_block sends the *complete* Block dict (nonce, previous_hash, …).

Protocol commands
-----------------
  HELLO        — handshake, exchange peer lists
  GET_CHAIN    — request full chain serialisation
  CHAIN        — carry full chain data + height
  NEW_BLOCK    — announce a freshly mined block (full dict)
  NEW_TX       — broadcast a pending transaction
  GET_CHUNK    — request a stored file chunk
  CHUNK        — carry raw chunk bytes (base64)
  CHUNK_NOT_FOUND
  GET_PEERS    — request known peer list
  PEERS        — carry peer list
"""

import socket
import threading
import json
import struct
import time
import logging
from typing import List, Dict, Optional, Callable, Set

from blockchain import CloudBlockchain, Block

logger = logging.getLogger("decentracloud.p2p")


# ─────────────────────────────────────────────
#  Wire Protocol  (length-prefixed JSON frames)
# ─────────────────────────────────────────────

def encode_message(msg: Dict) -> bytes:
    """Serialise a message dict to a 4-byte-length-prefixed UTF-8 frame."""
    raw = json.dumps(msg).encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def decode_message(sock: socket.socket) -> Optional[Dict]:
    """Read exactly one message from a socket. Returns None on EOF/error."""
    try:
        raw_len = _recv_exactly(sock, 4)
        if raw_len is None:
            return None
        length = struct.unpack(">I", raw_len)[0]
        raw_body = _recv_exactly(sock, length)
        if raw_body is None:
            return None
        return json.loads(raw_body.decode("utf-8"))
    except (ConnectionResetError, OSError, json.JSONDecodeError):
        return None


def _recv_exactly(sock: socket.socket, n: int) -> Optional[bytes]:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


# ─────────────────────────────────────────────
#  P2P Node
# ─────────────────────────────────────────────

# How many pending transactions trigger automatic mining on this node.
AUTO_MINE_THRESHOLD = 1   # set to e.g. 5 in production

# Seconds between periodic sync-chain sweeps.
SYNC_INTERVAL = 30


class P2PNode:
    """
    A single DecentraCloud network node.

    Owns a CloudBlockchain and participates in consensus:

    Validation & Propagation
    ------------------------
    When a NEW_BLOCK message arrives the node:
      1. Reconstructs the Block from the dict.
      2. Checks PoW validity  (hash starts with difficulty zeros AND matches
         computed hash).
      3. Checks chain linkage (previous_hash == our last block's hash).
      4. If both pass → appends to local chain and gossips to every *other*
         peer (excluding the sender so the message doesn't loop).
      5. If rejected → triggers a full sync (maybe we are behind).

    Conflict Resolution  (Longest-Chain Rule)
    ------------------------------------------
    On HELLO-ACK and on a periodic sweep the node calls sync_chain():
      • Sends GET_CHAIN to every peer.
      • Calls blockchain.replace_chain() with each response.
      • replace_chain only replaces if the candidate is LONGER and VALID.
    This is Nakamoto consensus: honest nodes always extend the longest chain,
    so an attacker would need >50 % of the network's hash-power to out-pace
    the honest majority.

    PoW as Spam-Prevention ("Approval by Work")
    --------------------------------------------
    difficulty=3 means a valid hash must start with "000".  On average a node
    must try ~16^3 = 4 096 nonces before finding one.  An attacker who wants
    to plant a fake block must do the same work as every honest miner — and
    then beat the rest of the network to build a longer chain on top of it.
    Raising difficulty to 5 requires ~1 M iterations, making spam
    computationally expensive.

    What "confirmed" means
    ----------------------
    A block at height H is considered confirmed once K blocks have been built
    on top of it (K = confirmation depth, typically 6 in Bitcoin-style chains).
    In Cloudmer, because uploads are the only write operation and the network
    is semi-trusted, K=1 (immediate acceptance after PoW) is reasonable for
    development.  Production deployments should wait for ≥ 2 additional blocks.
    """

    def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 5000,
            node_id: Optional[str] = None,
            difficulty: int = 3,
            chain_path: Optional[str] = None,   # persist chain to this file
    ):
        self.host = host
        self.port = port
        self.node_id = node_id or f"{host}:{port}"

        self.peers: Set[str] = set()        # "host:port" strings
        self.chunk_store: Dict[str, bytes] = {}  # chunk_hash → raw bytes

        # ── Blockchain (owned by this node) ──────────────────────────────────
        self.blockchain = CloudBlockchain(difficulty=difficulty)
        self._chain_path = chain_path
        if chain_path:
            import os
            if os.path.exists(chain_path):
                self.blockchain.load(chain_path)
                logger.info(
                    f"[{self.node_id}] Loaded chain from {chain_path} "
                    f"(height={self.blockchain.height})"
                )

        # ── Thread safety ────────────────────────────────────────────────────
        # Protects blockchain.chain and blockchain.pending_transactions
        self._chain_lock = threading.Lock()
        # Tracks hashes of blocks we have already gossiped so we don't loop
        self._seen_block_hashes: Set[str] = set()

        self._running = False
        self._server_sock: Optional[socket.socket] = None
        self._callbacks: Dict[str, List[Callable]] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        """Start listener + mining loop + periodic sync in background threads."""
        self._running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(20)
        self._server_sock.settimeout(1.0)

        threading.Thread(target=self._accept_loop,  daemon=True, name=f"p2p-accept-{self.port}").start()
        threading.Thread(target=self._mining_loop,  daemon=True, name=f"p2p-mine-{self.port}").start()
        threading.Thread(target=self._sync_loop,    daemon=True, name=f"p2p-sync-{self.port}").start()

        logger.info(f"[P2P] Node {self.node_id} listening on {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._server_sock:
            self._server_sock.close()

    # ── Accept Loop ────────────────────────────────────────────────────────

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_peer,
                    args=(conn, addr),
                    daemon=True,
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    # ── Per-connection handler ─────────────────────────────────────────────

    def _handle_peer(self, conn: socket.socket, addr):
        peer_str = f"{addr[0]}:{addr[1]}"
        logger.debug(f"[P2P] New connection from {peer_str}")
        try:
            while self._running:
                msg = decode_message(conn)
                if msg is None:
                    break
                response = self._dispatch(msg, peer_str)
                if response:
                    conn.sendall(encode_message(response))
        except Exception as e:
            logger.debug(f"[P2P] Peer {peer_str} error: {e}")
        finally:
            conn.close()

    # ── Message Dispatch ───────────────────────────────────────────────────

    def _dispatch(self, msg: Dict, sender: str) -> Optional[Dict]:
        """Route an incoming message to the correct handler."""
        cmd = msg.get("cmd")

        # ── HELLO ──────────────────────────────────────────────────────────
        if cmd == "HELLO":
            peer_addr = msg.get("addr", sender)
            self.peers.add(peer_addr)
            return {
                "cmd":     "HELLO_ACK",
                "node_id": self.node_id,
                "peers":   list(self.peers),
                "height":  self.blockchain.height,
            }

        # ── GET_CHAIN ──────────────────────────────────────────────────────
        elif cmd == "GET_CHAIN":
            with self._chain_lock:
                chain_data = [b.to_dict() for b in self.blockchain.chain]
                height     = self.blockchain.height
            return {
                "cmd":    "CHAIN",
                "chain":  chain_data,
                "height": height,
            }

        # ── CHAIN  (incoming — try to replace our local chain) ─────────────
        elif cmd == "CHAIN":
            incoming = msg.get("chain", [])
            with self._chain_lock:
                replaced = self.blockchain.replace_chain(incoming)
            if replaced:
                logger.info(
                    f"[{self.node_id}] Chain replaced from {sender} "
                    f"(new height={self.blockchain.height})"
                )
                self._persist_chain()
                self._fire("chain_replaced")

        # ── NEW_BLOCK ──────────────────────────────────────────────────────
        elif cmd == "NEW_BLOCK":
            block_dict = msg.get("block")
            if block_dict:
                self._receive_block(block_dict, sender)

        # ── NEW_TX  (incoming pending transaction) ─────────────────────────
        elif cmd == "NEW_TX":
            tx = msg.get("tx")
            if tx:
                with self._chain_lock:
                    # Deduplicate by tx timestamp + file_hash
                    already = any(
                        p.get("file_hash") == tx.get("file_hash") and
                        p.get("timestamp") == tx.get("timestamp")
                        for p in self.blockchain.pending_transactions
                    )
                    if not already:
                        self.blockchain.add_transaction(tx)
                        logger.debug(
                            f"[{self.node_id}] Added incoming TX "
                            f"({tx.get('type')}) from {sender}"
                        )
                        self._fire("new_tx", tx)

        # ── GET_CHUNK ──────────────────────────────────────────────────────
        elif cmd == "GET_CHUNK":
            chunk_hash = msg.get("chunk_hash")
            if chunk_hash in self.chunk_store:
                import base64
                return {
                    "cmd":        "CHUNK",
                    "chunk_hash": chunk_hash,
                    "data":       base64.b64encode(self.chunk_store[chunk_hash]).decode(),
                }
            return {"cmd": "CHUNK_NOT_FOUND", "chunk_hash": chunk_hash}

        # ── GET_PEERS ──────────────────────────────────────────────────────
        elif cmd == "GET_PEERS":
            return {"cmd": "PEERS", "peers": list(self.peers)}

        return None

    # ── Block Reception & Validation ───────────────────────────────────────

    def _receive_block(self, block_dict: Dict, sender: str):
        """
        Validate an incoming block and, if accepted, append and gossip it.

        Validation steps:
          1. Skip if we have already seen this block hash (loop prevention).
          2. Reconstruct the Block object from the wire dict.
          3. PoW check  : block.hash starts with difficulty zeros AND equals
             the freshly computed hash of its contents.
          4. Linkage    : block.previous_hash must equal our current tip's hash.
             If the incoming index <= our height we simply ignore (already have it).
          5. Accept     : append, mark as seen, persist, fire callbacks, gossip.
          6. Reject     : trigger a full sync (we may be on a shorter fork).
        """
        block_hash = block_dict.get("hash", "")

        # ── 1. Deduplication ───────────────────────────────────────────────
        if block_hash in self._seen_block_hashes:
            return
        self._seen_block_hashes.add(block_hash)

        # ── 2. Reconstruct ─────────────────────────────────────────────────
        try:
            candidate = Block.from_dict(block_dict)
        except Exception as e:
            logger.warning(f"[{self.node_id}] Malformed block from {sender}: {e}")
            return

        with self._chain_lock:
            last = self.blockchain.last_block

            # ── 3. PoW validity ────────────────────────────────────────────
            if not self.blockchain.pow.is_valid_proof(candidate):
                logger.warning(
                    f"[{self.node_id}] Block #{candidate.index} from {sender} "
                    f"FAILED PoW check — rejected."
                )
                return

            # ── 4. Chain linkage ───────────────────────────────────────────
            if candidate.index <= last.index:
                # Already have this block or an even newer one — ignore.
                return

            if candidate.previous_hash != last.hash:
                logger.info(
                    f"[{self.node_id}] Block #{candidate.index} does not link to "
                    f"our tip (height={last.index}) — triggering sync."
                )
                # Release lock before sync (sync acquires it internally)
                self.blockchain.chain  # just access to prevent lint warning

            # ── 5. Accept ──────────────────────────────────────────────────
            else:
                self.blockchain.chain.append(candidate)
                # Remove any pending txs that are now confirmed in this block
                confirmed_hashes = {
                    tx.get("file_hash")
                    for tx in candidate.transactions
                    if tx.get("file_hash")
                }
                self.blockchain.pending_transactions = [
                    tx for tx in self.blockchain.pending_transactions
                    if tx.get("file_hash") not in confirmed_hashes
                ]
                logger.info(
                    f"[{self.node_id}] ✓ Accepted block #{candidate.index} "
                    f"from {sender} (hash={candidate.hash[:12]}…)"
                )
                self._fire("block_accepted", candidate)
                self._persist_chain()

                # ── 6. Gossip to other peers ───────────────────────────────
                threading.Thread(
                    target=self._gossip_block,
                    args=(block_dict, sender),
                    daemon=True,
                ).start()
                return  # done inside lock

        # Linkage failed — sync outside the lock
        threading.Thread(target=self.sync_chain, daemon=True).start()

    def _gossip_block(self, block_dict: Dict, origin_peer: str):
        """Forward a validated block to all peers *except* the one who sent it."""
        msg = {"cmd": "NEW_BLOCK", "block": block_dict}
        dead = set()
        for peer in list(self.peers):
            if peer == origin_peer:
                continue
            result = self.send_to_peer(peer, msg)
            if result is None:
                dead.add(peer)
        self.peers -= dead

    # ── Mining Loop ────────────────────────────────────────────────────────

    def _mining_loop(self):
        """
        Background thread: whenever the pending pool reaches AUTO_MINE_THRESHOLD
        transactions, mine them into a block and broadcast the result.

        This implements the 'any node can mine' property of the network.
        The miner_id is this node's node_id so it earns the mining reward.
        """
        while self._running:
            time.sleep(1)   # poll every second
            with self._chain_lock:
                pending_count = len(self.blockchain.pending_transactions)

            if pending_count >= AUTO_MINE_THRESHOLD:
                logger.info(
                    f"[{self.node_id}] Mining — {pending_count} pending txs…"
                )
                try:
                    with self._chain_lock:
                        new_block = self.blockchain.mine_pending_transactions(
                            miner_id=self.node_id
                        )
                    logger.info(
                        f"[{self.node_id}] ⛏  Block #{new_block.index} mined! "
                        f"nonce={new_block.nonce}  hash={new_block.hash[:12]}…"
                    )
                    self._persist_chain()
                    self._seen_block_hashes.add(new_block.hash)  # don't re-process our own
                    self._fire("block_mined", new_block)

                    # Broadcast to network
                    self.broadcast_new_block(new_block.to_dict())

                except ValueError:
                    pass   # pending_transactions became empty between check and mine

    # ── Periodic Sync ──────────────────────────────────────────────────────

    def _sync_loop(self):
        """Periodically pull the longest chain from the network."""
        while self._running:
            time.sleep(SYNC_INTERVAL)
            if self.peers:
                self.sync_chain()

    # ── Sending Helpers ────────────────────────────────────────────────────

    def send_to_peer(self, peer: str, msg: Dict) -> Optional[Dict]:
        """Open a short-lived connection, send one message, read one reply."""
        try:
            host, port = peer.rsplit(":", 1)
            with socket.create_connection((host, int(port)), timeout=5) as s:
                s.sendall(encode_message(msg))
                return decode_message(s)
        except Exception as e:
            logger.debug(f"[P2P] Failed to reach {peer}: {e}")
            self.peers.discard(peer)
            return None

    def connect_to_peer(self, host: str, port: int):
        """
        HELLO handshake with a new peer.
        After connecting, sync the chain so we adopt the longest valid version.
        """
        peer = f"{host}:{port}"
        if peer == self.node_id:
            return
        response = self.send_to_peer(peer, {
            "cmd":     "HELLO",
            "addr":    self.node_id,
            "node_id": self.node_id,
        })
        if response:
            self.peers.add(peer)
            for p in response.get("peers", []):
                if p != self.node_id:
                    self.peers.add(p)
            logger.info(
                f"[P2P] Connected to {peer}. "
                f"Known peers: {len(self.peers)}  "
                f"Their height: {response.get('height', '?')}"
            )
            # ── Immediately sync chain after joining ──────────────────
            self.sync_chain()

    def broadcast(self, msg: Dict):
        """Send a message to all known peers (fire-and-forget, removes dead peers)."""
        dead = set()
        for peer in list(self.peers):
            if self.send_to_peer(peer, msg) is None:
                dead.add(peer)
        self.peers -= dead

    def broadcast_new_block(self, block_dict: Dict):
        """
        Announce a newly mined block to the entire network.

        The block_dict must be the full output of Block.to_dict(), which includes:
          index, timestamp, transactions, previous_hash, nonce, merkle_root, hash
        All fields are required for peers to validate PoW and chain linkage.
        """
        self.broadcast({"cmd": "NEW_BLOCK", "block": block_dict})

    def broadcast_transaction(self, tx: Dict):
        """
        Propagate a new pending transaction to all peers.
        Called by the upload server after a successful file upload.
        """
        self.broadcast({"cmd": "NEW_TX", "tx": tx})

    def sync_chain(self):
        """
        Ask every peer for its chain and adopt the longest valid one.
        Uses CloudBlockchain.replace_chain() which enforces:
          - Length  : candidate must be strictly longer than ours.
          - Validity: every block hash, linkage, and PoW must pass.
        This is the core of Nakamoto consensus.
        """
        for peer in list(self.peers):
            response = self.send_to_peer(peer, {"cmd": "GET_CHAIN"})
            if response and response.get("cmd") == "CHAIN":
                with self._chain_lock:
                    replaced = self.blockchain.replace_chain(response.get("chain", []))
                if replaced:
                    logger.info(
                        f"[{self.node_id}] Chain synced from {peer} "
                        f"(height={self.blockchain.height})"
                    )
                    self._persist_chain()
                    self._fire("chain_replaced")

    # ── Transaction Submission (called by upload server) ───────────────────

    def submit_transaction(self, tx: Dict):
        """
        Add a transaction to this node's pending pool AND broadcast it.
        Called by cloudmer_SRV.handle_upload_done() after a verified upload.
        """
        with self._chain_lock:
            self.blockchain.add_transaction(tx)
        logger.info(
            f"[{self.node_id}] TX submitted: {tx.get('type')} / "
            f"{tx.get('file_name', tx.get('file_hash', '')[:12])}"
        )
        self.broadcast_transaction(tx)

    # ── Chunk Distribution ─────────────────────────────────────────────────

    def store_chunk(self, chunk_hash: str, data: bytes):
        self.chunk_store[chunk_hash] = data

    def request_chunk(self, chunk_hash: str) -> Optional[bytes]:
        import base64
        for peer in list(self.peers):
            response = self.send_to_peer(peer, {"cmd": "GET_CHUNK", "chunk_hash": chunk_hash})
            if response and response.get("cmd") == "CHUNK":
                data = base64.b64decode(response["data"])
                self.chunk_store[chunk_hash] = data
                return data
        return None

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist_chain(self):
        if self._chain_path:
            try:
                self.blockchain.save(self._chain_path)
            except Exception as e:
                logger.warning(f"[{self.node_id}] Could not save chain: {e}")

    # ── Event System ───────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable):
        """Register a callback for a named event.

        Events fired by this node:
          block_accepted  (block: Block)        — a peer's block was validated & added
          block_mined     (block: Block)        — this node mined a new block
          chain_replaced  ()                    — longest-chain rule kicked in
          new_tx          (tx: Dict)            — incoming pending transaction
        """
        self._callbacks.setdefault(event, []).append(callback)

    def _fire(self, event: str, *args):
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                logger.debug(f"[P2P] Callback error for {event}: {e}")

    # ── Status ─────────────────────────────────────────────────────────────

    def status(self) -> Dict:
        return {
            "node_id":           self.node_id,
            "host":              self.host,
            "port":              self.port,
            "connected_peers":   len(self.peers),
            "peers":             list(self.peers),
            "chain_height":      self.blockchain.height,
            "chain_valid":       self.blockchain.is_valid(),
            "pending_txs":       len(self.blockchain.pending_transactions),
            "local_chunks":      len(self.chunk_store),
            "running":           self._running,
            "difficulty":        self.blockchain.pow.difficulty,
        }
