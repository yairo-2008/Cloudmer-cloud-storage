
import math


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _xor_bytes(*arrays: bytes) -> bytes:
    """XOR two or more equal-length byte strings together."""
    result = bytearray(arrays[0])
    for arr in arrays[1:]:
        for i in range(len(result)):
            result[i] ^= arr[i]
    return bytes(result)


# ─────────────────────────────────────────────────────────────────────────────
# RAID-5 Storage
# ─────────────────────────────────────────────────────────────────────────────

class Raid5Storage:
    """
    Simulates a RAID-5 array with `num_data_disks` data disks + 1 parity disk
    (total disks = num_data_disks + 1).

    Parameters
    ----------
    num_data_disks : int
        Number of disks that store actual file data (minimum 2).
    stripe_size : int
        Size of each stripe block in bytes.
    """

    def __init__(self, num_data_disks: int = 3, stripe_size: int = 64):
        if num_data_disks < 2:
            raise ValueError("RAID-5 requires at least 2 data disks.")

        self.num_data_disks = num_data_disks
        self.total_disks    = num_data_disks + 1   # +1 for parity
        self.stripe_size    = stripe_size

        # Each "disk" is a list of stripe blocks (bytes objects)
        self.disks: list[list[bytes]] = [[] for _ in range(self.total_disks)]

        # Track which disk (if any) has "failed" (None = all healthy)
        self.failed_disk: int | None = None

        # How many stripe rows have been written
        self.num_stripe_rows: int = 0

        # Padding we added to the last stripe (needed for clean read)
        self._padding: int = 0

    # ── Write ─────────────────────────────────────────────────────────────────

    def write(self, data: bytes) -> None:
        """
        Split `data` into stripes and distribute across disks with XOR parity.

        Layout for num_data_disks=3, stripe_size=4, total_disks=4:

          Row 0:  [D0_blk0] [D1_blk1] [D2_blk2] [P_blk←parity on disk 3]
          Row 1:  [D0_blk3] [D1_blk4] [P_blk←parity on disk 2] [D3_blk5]
          Row 2:  [D0_blk6] [P_blk←parity on disk 1] [D2_blk7] [D3_blk8]
          Row 3:  [P_blk←parity on disk 0] [D1_blk9] [D2_blk10][D3_blk11]

        Parity position rotates: row i → parity on disk (total_disks - 1 - i % total_disks)
        """
        # Clear previous content
        self.disks = [[] for _ in range(self.total_disks)]
        self.num_stripe_rows = 0
        self._padding = 0

        # Pad data so it fills complete stripe rows
        total_data_bytes = self.num_data_disks * self.stripe_size
        remainder = len(data) % total_data_bytes
        if remainder:
            self._padding = total_data_bytes - remainder
            data = data + b'\x00' * self._padding

        num_rows = len(data) // total_data_bytes
        self.num_stripe_rows = num_rows

        for row in range(num_rows):
            # Slice out the data blocks for this row
            row_offset   = row * total_data_bytes
            data_blocks  = [
                data[row_offset + d * self.stripe_size :
                     row_offset + (d + 1) * self.stripe_size]
                for d in range(self.num_data_disks)
            ]

            # Compute parity = XOR of all data blocks in this row
            parity_block = _xor_bytes(*data_blocks)

            # Rotating parity position: last disk of row 0, second-to-last of row 1…
            parity_disk = (self.total_disks - 1 - (row % self.total_disks))

            # Place blocks onto disks (skip parity_disk for data, insert parity there)
            data_iter = iter(data_blocks)
            for disk_idx in range(self.total_disks):
                if disk_idx == parity_disk:
                    self.disks[disk_idx].append(parity_block)
                else:
                    self.disks[disk_idx].append(next(data_iter))

        print(f"[RAID-5] Write complete: {num_rows} stripe rows across "
              f"{self.total_disks} disks (stripe_size={self.stripe_size}B).")

    # ── Read ──────────────────────────────────────────────────────────────────

    def read(self) -> bytes:
        """
        Reassemble the original file from the stripe array.
        If one disk has failed, rebuilds its blocks via XOR reconstruction
        before reassembling.
        """
        result = bytearray()

        for row in range(self.num_stripe_rows):
            parity_disk = (self.total_disks - 1 - (row % self.total_disks))

            # Collect all blocks for this row (possibly with a missing/failed one)
            row_blocks = [self.disks[d][row] for d in range(self.total_disks)]

            # ── Rebuild failed disk ───────────────────────────────────────────
            if self.failed_disk is not None:
                surviving = [row_blocks[d]
                             for d in range(self.total_disks)
                             if d != self.failed_disk]
                rebuilt = _xor_bytes(*surviving)
                row_blocks[self.failed_disk] = rebuilt
                # (In production we'd write `rebuilt` back to the replacement disk)

            # ── Extract data blocks in order (skip parity disk) ───────────────
            for disk_idx in range(self.total_disks):
                if disk_idx != parity_disk:
                    result.extend(row_blocks[disk_idx])

        # Remove padding added during write
        if self._padding:
            result = result[:-self._padding]

        return bytes(result)

    # ── Fault simulation ──────────────────────────────────────────────────────

    def simulate_disk_failure(self, disk_index: int) -> None:
        """
        Mark disk `disk_index` as failed and zero-out its blocks to simulate
        data loss.  Subsequent read() calls will reconstruct its content.
        """
        if disk_index < 0 or disk_index >= self.total_disks:
            raise IndexError(f"Disk index {disk_index} out of range "
                             f"(0–{self.total_disks - 1}).")
        self.failed_disk = disk_index
        # Overwrite blocks to simulate physical data loss
        for row in range(self.num_stripe_rows):
            self.disks[disk_index][row] = b'\x00' * self.stripe_size
        print(f"[RAID-5] ⚠  Disk {disk_index} FAILED — "
              f"data will be reconstructed on next read().")

    def recover_disk(self) -> None:
        """
        Simulate replacing a failed disk: rebuild all its blocks from parity
        and mark the array healthy again.
        """
        if self.failed_disk is None:
            print("[RAID-5] No failed disk to recover.")
            return

        fd = self.failed_disk
        for row in range(self.num_stripe_rows):
            surviving = [self.disks[d][row]
                         for d in range(self.total_disks) if d != fd]
            self.disks[fd][row] = _xor_bytes(*surviving)

        print(f"[RAID-5] Disk {fd} rebuilt successfully.")
        self.failed_disk = None

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def print_layout(self) -> None:
        """Pretty-print the stripe layout for debugging / educational display."""
        print(f"\n{'─'*60}")
        print(f"  RAID-5 Layout  "
              f"({self.num_data_disks} data disks + 1 parity, "
              f"stripe={self.stripe_size}B)")
        print(f"{'─'*60}")
        header = "  Row | " + " | ".join(f"  Disk {d}  " for d in range(self.total_disks))
        print(header)
        print(f"{'─'*60}")

        for row in range(self.num_stripe_rows):
            parity_disk = (self.total_disks - 1 - (row % self.total_disks))
            cells = []
            for d in range(self.total_disks):
                label = "PARITY" if d == parity_disk else "DATA  "
                blk   = self.disks[d][row]
                cells.append(f"[{label} {blk.hex()[:8]}]")
            print(f"  {row:3d}  | " + " | ".join(cells))

        print(f"{'─'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Demo / self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Cloudmer — RAID-5 Logic Demo")
    print("=" * 60)

    MESSAGE = b"This is a secret file stored with RAID-5 redundancy!"
    STRIPE  = 8   # small stripe so the layout table is readable

    storage = Raid5Storage(num_data_disks=3, stripe_size=STRIPE)

    # 1. Write
    storage.write(MESSAGE)
    storage.print_layout()

    # 2. Normal read
    recovered = storage.read()
    assert recovered == MESSAGE, "Read mismatch (no failure)!"
    print(f"[OK] Normal read: '{recovered.decode()}'")

    # 3. Simulate disk failure and rebuild
    for failed in range(storage.total_disks):
        storage.write(MESSAGE)            # re-stripe fresh
        storage.simulate_disk_failure(failed)
        rebuilt = storage.read()
        assert rebuilt == MESSAGE, f"Rebuild failed for disk {failed}!"
        print(f"[OK] Rebuilt after disk {failed} failure: '{rebuilt.decode()}'")

    print("\nAll RAID-5 tests passed ✓")
