from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
from tcp_by_size import recv_by_size, send_with_size
import socket
import hashlib


AES_DEBUG = True
LEN_TO_PRINT = 100

def hash_key(key: str | bytes) -> bytes:
    if isinstance (key, str):
        return hashlib.sha256(key.encode()).digest()
    elif isinstance (key,bytes):
        return hashlib.sha256(key).digest()


def send_with_AES(sock: socket.socket, data: str | bytes, key: str | bytes, iv: bytes = None) -> None:

    if isinstance(data, str):
        data = data.encode()


    key = hash_key(key)

    if iv is None:
        iv = get_random_bytes(16)

    cipher = AES.new(key, AES.MODE_CBC, iv)

    padded_data = pad(data, AES.block_size)

    encrypted_data = cipher.encrypt(padded_data)

    if AES_DEBUG:
        print ("\nSent AES (%s)>>>" % (len(data)), end='')
        print ("%s"%(data[:min(len(data),LEN_TO_PRINT)],))

    send_with_size(sock, iv + encrypted_data)


def recv_with_AES(sock: socket.socket, key: str | bytes) -> bytes:

    key = hash_key(key)

    encrypted_data = recv_by_size(sock)
    if len(encrypted_data) > 0:
        iv = encrypted_data[:16]
        encrypted_data = encrypted_data[16:]

        cipher = AES.new(key, AES.MODE_CBC, iv)

        decrypted_data = cipher.decrypt(encrypted_data)
        if  AES_DEBUG:
            print ("\nRecv AES (%s)>>>" % (len(decrypted_data),), end='')
            print ("%s"%(decrypted_data[:min(len(decrypted_data),LEN_TO_PRINT)],))

        return unpad(decrypted_data, AES.block_size)