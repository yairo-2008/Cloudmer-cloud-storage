"""
DecentraCloud - Cryptography Layer
====================================
Handles:
- RSA key pair generation (user identity)
- Digital signatures (transaction authenticity)
- AES file encryption / decryption
- File chunking with content-addressed hashing
- Key sharing (encrypt AES key with recipient's public RSA key)
"""

import os
import hashlib
import hmac
import json
import base64
import struct
from typing import Tuple, List, Dict

# ── Optional: use 'cryptography' library if available ──────────────────────────
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# ── Fallback pure-stdlib helpers ───────────────────────────────────────────────


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """Minimal XOR cipher (demo only — not production-safe)."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# ─────────────────────────────────────────────
#  Key Management
# ─────────────────────────────────────────────

class KeyPair:
    """
    RSA-2048 identity key pair for a DecentraCloud user.
    The public key acts as the user's address on the blockchain.
    """

    def __init__(self):
        if not _CRYPTO_AVAILABLE:
            # Simulated keys for demo environments without 'cryptography' installed
            self._private_bytes = os.urandom(32)
            self._public_bytes = hashlib.sha256(self._private_bytes).digest()
            self._mode = "simulated"
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            self._public_key = self._private_key.public_key()
            self._mode = "rsa"

    @property
    def public_key_hex(self) -> str:
        """Hex-encoded public key — used as blockchain identity."""
        if self._mode == "simulated":
            return self._public_bytes.hex()
        pub = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pub.hex()

    def sign(self, data: bytes) -> str:
        """Sign arbitrary bytes. Returns base64-encoded signature."""
        if self._mode == "simulated":
            sig = hmac.new(self._private_bytes, data, hashlib.sha256).digest()
            return base64.b64encode(sig).decode()
        sig = self._private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode()

    def verify(self, data: bytes, signature_b64: str) -> bool:
        """Verify a signature against this key pair's public key."""
        sig = base64.b64decode(signature_b64)
        if self._mode == "simulated":
            expected = hmac.new(self._private_bytes, data, hashlib.sha256).digest()
            return hmac.compare_digest(sig, expected)
        try:
            self._public_key.verify(
                sig,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def encrypt_for_recipient(self, data: bytes) -> bytes:
        """Encrypt `data` with this key pair's public key (key sharing)."""
        if self._mode == "simulated":
            return _xor_bytes(data, self._public_bytes)
        return self._public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext encrypted with this key pair's public key."""
        if self._mode == "simulated":
            return _xor_bytes(ciphertext, self._public_bytes)
        return self._private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

    def export_public_pem(self) -> str:
        if self._mode == "simulated":
            return f"SIMULATED_KEY:{self.public_key_hex}"
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()


# ─────────────────────────────────────────────
#  AES File Encryption
# ─────────────────────────────────────────────

def generate_file_key() -> bytes:
    """Generate a random 256-bit AES key for a file."""
    return os.urandom(32)


def encrypt_data(data: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt `data` using AES-256-GCM.
    Returns (ciphertext_with_tag, nonce).
    Falls back to XOR if 'cryptography' is not installed.
    """
    if not _CRYPTO_AVAILABLE:
        nonce = os.urandom(16)
        ct = _xor_bytes(data, key + nonce)
        return ct, nonce

    nonce = os.urandom(12)
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce),
        backend=default_backend(),
    )
    enc = cipher.encryptor()
    ct = enc.update(data) + enc.finalize()
    return ct + enc.tag, nonce


def decrypt_data(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt AES-256-GCM ciphertext."""
    if not _CRYPTO_AVAILABLE:
        return _xor_bytes(ciphertext, key + nonce)

    tag = ciphertext[-16:]
    ct = ciphertext[:-16]
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce, tag),
        backend=default_backend(),
    )
    dec = cipher.decryptor()
    return dec.update(ct) + dec.finalize()


# ─────────────────────────────────────────────
#  File Chunking (Content-Addressed Storage)
# ─────────────────────────────────────────────

CHUNK_SIZE = 1024 * 1024  # 1 MB default


def hash_data(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def chunk_and_encrypt_file(
        filepath: str,
        file_key: bytes,
        chunk_size: int = CHUNK_SIZE,
) -> Dict:
    """
    Read a file, split into chunks, encrypt each chunk, and return metadata.

    Returns:
    {
        "file_hash"   : SHA-256 of the entire plaintext file,
        "file_name"   : original filename,
        "file_size"   : size in bytes,
        "chunk_count" : number of chunks,
        "chunks"      : [{"chunk_hash": ..., "ciphertext": b64, "nonce": b64}, ...]
    }
    """
    with open(filepath, "rb") as f:
        raw = f.read()

    file_hash = hash_data(raw)
    file_name = os.path.basename(filepath)
    file_size = len(raw)

    chunks = []
    for i in range(0, file_size, chunk_size):
        chunk_data = raw[i: i + chunk_size]
        ct, nonce = encrypt_data(chunk_data, file_key)
        chunk_hash = hash_data(chunk_data)  # hash of PLAINTEXT for deduplication
        chunks.append({
            "chunk_index": len(chunks),
            "chunk_hash": chunk_hash,
            "ciphertext": base64.b64encode(ct).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "size": len(chunk_data),
        })

    return {
        "file_hash": file_hash,
        "file_name": file_name,
        "file_size": file_size,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def reconstruct_file(
        chunks: List[Dict],
        file_key: bytes,
        output_path: str,
) -> str:
    """
    Decrypt and reassemble chunks into the original file.
    Returns the output path.
    """
    chunks_sorted = sorted(chunks, key=lambda c: c["chunk_index"])
    raw_parts = []

    for chunk in chunks_sorted:
        ct = base64.b64decode(chunk["ciphertext"])
        nonce = base64.b64decode(chunk["nonce"])
        plaintext = decrypt_data(ct, file_key, nonce)

        # Integrity check
        assert hash_data(plaintext) == chunk["chunk_hash"], (
            f"Chunk {chunk['chunk_index']} hash mismatch — data corrupted!"
        )
        raw_parts.append(plaintext)

    with open(output_path, "wb") as f:
        f.write(b"".join(raw_parts))

    return output_path


# ─────────────────────────────────────────────
#  Transaction Signing
# ─────────────────────────────────────────────

def sign_transaction(tx: Dict, keypair: "KeyPair") -> Dict:
    """
    Add a digital signature to a transaction dict.
    The signature covers all fields except 'signature' itself.
    """
    tx_copy = {k: v for k, v in tx.items() if k != "signature"}
    payload = json.dumps(tx_copy, sort_keys=True).encode()
    tx["signature"] = keypair.sign(payload)
    tx["signer"] = keypair.public_key_hex
    return tx


def verify_transaction_signature(tx: Dict, keypair: "KeyPair") -> bool:
    """Verify the digital signature of a transaction."""
    sig = tx.get("signature", "")
    if not sig:
        return False
    tx_copy = {k: v for k, v in tx.items() if k not in ("signature", "signer")}
    payload = json.dumps(tx_copy, sort_keys=True).encode()
    return keypair.verify(payload, sig)


# ─────────────────────────────────────────────
#  Key Sharing
# ─────────────────────────────────────────────

def share_file_key(
        file_key: bytes,
        recipient_keypair: "KeyPair",
) -> str:
    """
    Encrypt a file's AES key using the recipient's public RSA key.
    Returns base64-encoded encrypted key (stored on-chain).
    """
    encrypted = recipient_keypair.encrypt_for_recipient(file_key)
    return base64.b64encode(encrypted).decode()


def retrieve_file_key(
        encrypted_key_b64: str,
        recipient_keypair: "KeyPair",
) -> bytes:
    """
    Decrypt the file's AES key using the recipient's private key.
    """
    encrypted = base64.b64decode(encrypted_key_b64)
    return recipient_keypair.decrypt(encrypted)



def get_file_hash(filepath):
    """מחזירה SHA-256 של קובץ"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()