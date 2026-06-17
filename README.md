# Cloudmer-cloud-storage
Cloudmer ☁️🔗
Cloudmer is a secure, decentralized peer-to-peer (P2P) cloud storage system built from scratch in Python. By combining distributed network communication, hardware-like data redundancy logic, and cryptographic verification, Cloudmer ensures that your data remains private, immutable, and highly available even if individual nodes go offline.  
🚀 Key Technical Features
1. Peer-to-Peer (P2P) ArchitectureBuilt a decentralized network topology utilizing low-level network socket programming for direct client-to-server and peer-to-peer data distribution.  Implemented robust synchronization logic backed by an SQLite relational database (cloudmer.db) to map, track, and manage node metadata across the system.
2. Low-Level Fault Tolerance (RAID-5 Engine)Designed and engineered a custom RAID-5 storage layer.  When a file is uploaded, the engine strips the data into distributed blocks and computes a parity block, guaranteeing seamless data recovery and high availability in case of node failures.
3. Tamper-Proof Audit Trail (Blockchain Ledger)Integrated a custom Blockchain architecture into the core backend.  Every major system transaction, upload, and structural block validation is written to an immutable, JSON-backed blockchain ledger (chain.json), ensuring strict data integrity and preventing unauthorized file modifications. 
4. Hybrid End-to-End EncryptionEngineered a complete cryptographic security layer using PyCryptodome.  Implemented RSA (Asymmetric Cryptography) public/private key pairs for secure node authentication and key exchanges.  Utilizes AES (Symmetric Cryptography) to encrypt the actual file streams and socket data payloads, ensuring absolute data privacy.
🛠️ Architecture & Tech StackLanguage:
Python  Database: SQLite (Relational mapping for system metadata)
Networking: TCP Socket Programming (Custom tcp_by_size chunking protocols)
Security: RSA, AES, SHA-256 (Blockchain hashing)  UI/UX: QML / QtQuick interface for an intuitive user experience (main.qml, BlockchainView.qml)
📂 Project StructurePlaintext├── client/                     # Desktop Client Application
│   ├── cloudmer_CLIENT.py      # Core client execution logic
│   ├── aes_functions.py        # Client-side symmetric encryption
│   ├── main.qml                # Main UI layout
│   └── BlockchainView.qml      # Visual ledger & transaction monitor
├── srv/                        # Server & Decentralized Node Architecture
│   ├── cloudmer_SRV.py         # Node server management
│   ├── raid5.py                # Redundancy & block-splitting engine
│   ├── blockchain.py           # Chain mechanics & transaction validation
│   ├── crypto.py & database.py # Cryptographic tools and SQLite engine
│   └── chain.json & cloudmer.db# Storage ledgers and system state
