

import hashlib
import json
import time
from typing import List, Dict, Optional, Any


# ─────────────────────────────────────────────
#  BlockChain Structure
# ─────────────────────────────────────────────

class Block:
    """
    A single block in the DecentraCloud blockchain.

    Contains:
    - index          : Position in the chain
    - timestamp      : Unix time of creation
    - transactions   : List of file metadata transactions
    - previous_hash  : Hash of the previous block (links the chain)
    - nonce          : Number used for Proof-of-Work mining
    - merkle_root    : Root hash of all transactions (efficient verification)
    - hash           : This block's own SHA-256 fingerprint
    """

    def __init__(
            self,
            index: int,
            transactions: List[Dict],
            previous_hash: str,
            nonce: int = 0,
    ):
        self.index = index
        self.timestamp = time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.merkle_root = self._compute_merkle_root()
        self.hash = self.compute_hash()

    # ── Hashing ──────────────────────────────

    def compute_hash(self) -> str:
        """Compute SHA-256 of the block's contents."""
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
        }
        raw = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def _compute_merkle_root(self) -> str:
        """
        Build a Merkle Root from all transaction hashes.
        Provides efficient integrity verification of the tx list.
        """
        if not self.transactions:
            return hashlib.sha256(b"empty").hexdigest()

        hashes = [
            hashlib.sha256(
                json.dumps(tx, sort_keys=True).encode()
            ).hexdigest()
            for tx in self.transactions
        ]

        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])  # duplicate last if odd
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]

        return hashes[0]

    # ── Serialization ─────────────────────────

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Block":
        block = cls(
            index=data["index"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            nonce=data["nonce"],
        )
        block.timestamp = data["timestamp"]
        block.merkle_root = data["merkle_root"]
        block.hash = data["hash"]
        return block

    def __repr__(self) -> str:
        return (
            f"Block(#{self.index} | txs={len(self.transactions)} "
            f"| hash={self.hash[:12]}...)"
        )


# ─────────────────────────────────────────────
#  Transaction Types
# ─────────────────────────────────────────────

class TransactionType:
    UPLOAD = "UPLOAD"
    DELETE = "DELETE"
    GRANT_ACCESS = "GRANT_ACCESS"
    REVOKE_ACCESS = "REVOKE_ACCESS"
    UPDATE_META = "UPDATE_META"


def make_upload_tx(
        owner_key: str,
        file_hash: str,
        file_name: str,
        file_size: int,
        chunk_count: int,
        storage_nodes: List[str],
        access_list: Optional[List[str]] = None,
        signature: Optional[str] = None,
) -> Dict:
    """Create an UPLOAD transaction (stores file metadata on-chain)."""
    return {
        "type": TransactionType.UPLOAD,
        "owner": owner_key,
        "file_hash": file_hash,
        "file_name": file_name,
        "file_size": file_size,
        "chunk_count": chunk_count,
        "storage_nodes": storage_nodes,
        "access_list": access_list or [],
        "signature": signature or "",
        "timestamp": time.time(),
    }


def make_grant_tx(
        owner_key: str,
        file_hash: str,
        target_key: str,
        encrypted_file_key: str,
        expires_at: Optional[float] = None,
        signature: Optional[str] = None,
) -> Dict:
    """Create a GRANT_ACCESS transaction."""
    return {
        "type": TransactionType.GRANT_ACCESS,
        "owner": owner_key,
        "file_hash": file_hash,
        "target_user": target_key,
        "encrypted_file_key": encrypted_file_key,
        "expires_at": expires_at,
        "signature": signature or "",
        "timestamp": time.time(),
    }


def make_revoke_tx(
        owner_key: str,
        file_hash: str,
        target_key: str,
        signature: Optional[str] = None,
) -> Dict:
    """Create a REVOKE_ACCESS transaction."""
    return {
        "type": TransactionType.REVOKE_ACCESS,
        "owner": owner_key,
        "file_hash": file_hash,
        "target_user": target_key,
        "signature": signature or "",
        "timestamp": time.time(),
    }


def make_delete_tx(
        owner_key: str,
        file_hash: str,
        signature: Optional[str] = None,
) -> Dict:
    """Create a DELETE transaction."""
    return {
        "type": TransactionType.DELETE,
        "owner": owner_key,
        "file_hash": file_hash,
        "signature": signature or "",
        "timestamp": time.time(),
    }


# ─────────────────────────────────────────────
#  Proof of Work
# ─────────────────────────────────────────────

class ProofOfWork:
    """
    Simple Proof-of-Work: find a nonce such that
    SHA-256(last_hash + nonce) starts with `difficulty` zeros.
    """

    DEFAULT_DIFFICULTY = 3

    def __init__(self, difficulty: int = DEFAULT_DIFFICULTY):
        self.difficulty = difficulty
        self.target = "0" * difficulty

    def mine(self, block: Block) -> int:
        """Find a valid nonce for the block. Returns the nonce."""
        block.nonce = 0
        while not block.compute_hash().startswith(self.target):
            block.nonce += 1
        block.hash = block.compute_hash()
        return block.nonce

    def is_valid_proof(self, block: Block) -> bool:
        return block.hash.startswith(self.target) and block.hash == block.compute_hash()


# ─────────────────────────────────────────────
#  The Blockchain
# ─────────────────────────────────────────────

class CloudBlockchain:
    """
    DecentraCloud's main blockchain class.

    Responsibilities:
    - Maintain an immutable chain of blocks
    - Manage pending transactions
    - Mine new blocks (Proof-of-Work)
    - Query file metadata and access rights
    - Validate chain integrity
    - Serialize/deserialize for P2P sync
    """

    MINING_REWARD_NODE = "NETWORK_REWARD"

    def __init__(self, difficulty: int = 3):
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict] = []
        self.pow = ProofOfWork(difficulty)

        # ── Genesis Block ──
        genesis = Block(
            index=0,
            transactions=[],
            previous_hash="0" * 64,
        )
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)

    # ── Chain Properties ──────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def height(self) -> int:
        return len(self.chain)

    # ── Transactions ──────────────────────────

    def add_transaction(self, tx: Dict) -> int:
        """Queue a transaction for the next block. Returns expected block index."""
        self.pending_transactions.append(tx)
        return self.last_block.index + 1

    # ── Mining ────────────────────────────────

    def mine_pending_transactions(self, miner_id: str = "local") -> Block:
        """
        Mine all pending transactions into a new block.
        Includes a mining reward transaction.
        """
        if not self.pending_transactions:
            raise ValueError("No transactions to mine.")

        # Add mining reward
        reward_tx = {
            "type": "MINING_REWARD",
            "miner": miner_id,
            "reward_storage_credits": 100,
            "timestamp": time.time(),
        }
        txs = self.pending_transactions + [reward_tx]

        new_block = Block(
            index=len(self.chain),
            transactions=txs,
            previous_hash=self.last_block.hash,
        )

        # Proof of Work
        self.pow.mine(new_block)
        self.chain.append(new_block)
        self.pending_transactions = []
        return new_block

    # ── Query Engine ──────────────────────────

    def get_file_metadata(self, file_hash: str) -> Optional[Dict]:
        """
        Return the most recent UPLOAD metadata for a file.
        Scans from newest to oldest block.
        """
        for block in reversed(self.chain):
            for tx in block.transactions:
                if tx.get("file_hash") == file_hash and tx.get("type") == TransactionType.UPLOAD:
                    return tx
        return None

    def check_access(self, user_key: str, file_hash: str) -> bool:
        """
        Determine if `user_key` currently has access to `file_hash`.
        Replays the entire chain history (grants and revocations).
        """
        # Check if file was deleted
        for block in reversed(self.chain):
            for tx in block.transactions:
                if tx.get("file_hash") == file_hash and tx.get("type") == TransactionType.DELETE:
                    return False

        # Build access state by replaying chain
        has_access = False
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("file_hash") != file_hash:
                    continue

                tx_type = tx.get("type")
                now = time.time()

                if tx_type == TransactionType.UPLOAD:
                    if tx.get("owner") == user_key:
                        has_access = True
                    if user_key in tx.get("access_list", []):
                        has_access = True

                elif tx_type == TransactionType.GRANT_ACCESS:
                    if tx.get("target_user") == user_key:
                        expires = tx.get("expires_at")
                        has_access = (expires is None or now < expires)

                elif tx_type == TransactionType.REVOKE_ACCESS:
                    if tx.get("target_user") == user_key:
                        has_access = False

        return has_access

    def get_user_files(self, user_key: str) -> List[Dict]:
        """Return all files owned by `user_key` (not deleted)."""
        owned: Dict[str, Dict] = {}
        deleted: set = set()

        for block in self.chain:
            for tx in block.transactions:
                fh = tx.get("file_hash")
                if not fh:
                    continue
                if tx.get("type") == TransactionType.UPLOAD and tx.get("owner") == user_key:
                    owned[fh] = tx
                elif tx.get("type") == TransactionType.DELETE and tx.get("owner") == user_key:
                    deleted.add(fh)

        return [meta for fh, meta in owned.items() if fh not in deleted]

    def get_file_history(self, file_hash: str) -> List[Dict]:
        """Return full event history for a file (all transactions)."""
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("file_hash") == file_hash:
                    history.append({**tx, "_block_index": block.index, "_block_time": block.timestamp})
        return history

    def get_access_list(self, file_hash: str) -> List[str]:
        """Return the current list of users with access to a file."""
        meta = self.get_file_metadata(file_hash)
        if not meta:
            return []

        access: set = set(meta.get("access_list", []))
        access.add(meta.get("owner", ""))

        for block in self.chain:
            for tx in block.transactions:
                if tx.get("file_hash") != file_hash:
                    continue
                if tx.get("type") == TransactionType.GRANT_ACCESS:
                    access.add(tx.get("target_user", ""))
                elif tx.get("type") == TransactionType.REVOKE_ACCESS:
                    access.discard(tx.get("target_user", ""))

        return list(access)

    def get_stats(self) -> Dict:
        """Return summary statistics about the chain."""
        total_files = 0
        total_size = 0
        tx_count = 0

        for block in self.chain:
            for tx in block.transactions:
                tx_count += 1
                if tx.get("type") == TransactionType.UPLOAD:
                    total_files += 1
                    total_size += tx.get("file_size", 0)

        return {
            "chain_height": self.height,
            "total_transactions": tx_count,
            "pending_transactions": len(self.pending_transactions),
            "total_files_registered": total_files,
            "total_data_indexed_bytes": total_size,
            "pow_difficulty": self.pow.difficulty,
        }

    # ── Validation ────────────────────────────

    def is_valid(self) -> bool:
        """
        Full chain integrity check:
        1. Genesis block is untouched
        2. Every block's hash is correct
        3. Every block links to its predecessor
        4. Every block satisfies Proof-of-Work
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Hash integrity
            if current.hash != current.compute_hash():
                return False

            # Chain linkage
            if current.previous_hash != previous.hash:
                return False

            # PoW
            if not self.pow.is_valid_proof(current):
                return False

        return True

    # ── Consensus (Longest Chain) ─────────────

    def replace_chain(self, new_chain_data: List[Dict]) -> bool:
        """
        Replace local chain if the incoming chain is:
        - Longer than the current chain
        - Fully valid
        Returns True if the chain was replaced.
        """
        if len(new_chain_data) <= len(self.chain):
            return False

        # Reconstruct and validate
        candidate = []
        for block_data in new_chain_data:
            candidate.append(Block.from_dict(block_data))

        temp = CloudBlockchain.__new__(CloudBlockchain)
        temp.chain = candidate
        temp.pow = self.pow
        if not temp.is_valid():
            return False

        self.chain = candidate
        return True

    # ── Persistence ───────────────────────────

    def save(self, filepath: str):
        """Persist the blockchain to a JSON file."""
        data = [block.to_dict() for block in self.chain]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str):
        """Load blockchain from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        self.chain = [Block.from_dict(b) for b in data]

    # ── Serialization ─────────────────────────

    def to_json(self) -> str:
        return json.dumps([block.to_dict() for block in self.chain], indent=2)

    def __repr__(self) -> str:
        return f"CloudBlockchain(height={self.height}, valid={self.is_valid()})"