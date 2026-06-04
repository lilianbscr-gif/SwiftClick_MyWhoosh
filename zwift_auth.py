"""
zwift_auth.py — Handshake ECDH + keepalive chiffré pour Zwift Click V2.

Deux générations de firmware coexistent :
  • Post-Jan 2025 (ex. PLUS) : bare RideOn suffit — pas de chiffrement.
  • Pré-Jan 2025  (ex. MINUS): handshake ECDH obligatoire + keepalive AES-CCM.

Handshake (les deux générations acceptent cette séquence) :
  Client → Device (UUID 00000003) :
    "RideOn" [01 02] [64 bytes clé publique SECP256R1 sans prefix 0x04]
  Device → Client (UUID 00000004, indicate) :
    "RideOn" [01 03] [64 bytes clé publique device]
  → ECDH → HKDF-SHA256 → clé AES-CCM + IV

Keepalive (firmware ancien seulement) :
  Message chiffré : [4 bytes counter LE] [AES-CCM(payload)] [4 bytes MAC]
  Nonce AES-CCM   : IV (4 bytes) + counter (4 bytes)
  Payload         : b"RideOn"
"""
from cryptography.hazmat.primitives.asymmetric.ec import (
    generate_private_key, SECP256R1, ECDH
)
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

RIDE_ON        = b"RideOn"
REQUEST_START  = bytes([0x01, 0x02])
RESPONSE_START = bytes([0x01, 0x03])

# UUID 00000004 — indication de la réponse de clé publique du device
SYNC_TX_UUID   = "00000004-19ca-4651-86e5-fa29dcdd09d1"
SYNC_RX_UUID   = "00000003-19ca-4651-86e5-fa29dcdd09d1"  # = WRITE_UUID

KEY_BYTES      = 64   # SECP256R1 uncompressed point sans prefix 0x04
HKDF_LENGTH    = 36   # 32 bytes clé + 4 bytes IV
KEY_LENGTH     = 32


class ZwiftAuth:
    """Gère le handshake ECDH d'un Zwift Click V2."""

    def __init__(self):
        self._private_key = generate_private_key(SECP256R1())
        self._public_key  = self._private_key.public_key()
        self._shared_key: bytes | None = None
        self._iv:         bytes | None = None
        self._counter     = 0
        self.completed    = False

    def build_handshake(self) -> bytes:
        """Construit le message d'initiation (72 bytes) à écrire sur UUID 00000003."""
        pub_bytes = self._public_key.public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )[1:]   # strip 0x04 prefix → 64 bytes
        return RIDE_ON + REQUEST_START + pub_bytes

    def process_response(self, data: bytes | bytearray) -> bool:
        """
        Traite la réponse indication du device (UUID 00000004).
        Retourne True si le handshake est complété avec succès.
        """
        data = bytes(data)
        header = RIDE_ON + RESPONSE_START
        if not data.startswith(header):
            return False
        if len(data) < len(header) + KEY_BYTES:
            return False

        device_pub_raw = data[len(header): len(header) + KEY_BYTES]

        # Reconstruire la clé publique SECP256R1 (ajoute prefix 0x04)
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePublicKey
        )
        from cryptography.hazmat.backends import default_backend
        full_key = bytes([0x04]) + device_pub_raw
        device_pub = EllipticCurvePublicKey.from_encoded_point(SECP256R1(), full_key)

        # ECDH shared secret
        shared_secret = self._private_key.exchange(ECDH(), device_pub)

        # HKDF-SHA256 : salt = device_pub_bytes + local_pub_bytes
        local_pub_raw = self._public_key.public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )[1:]
        salt = device_pub_raw + local_pub_raw

        hkdf_out = HKDF(
            algorithm=hashes.SHA256(),
            length=HKDF_LENGTH,
            salt=salt,
            info=None,
        ).derive(shared_secret)

        self._shared_key = hkdf_out[:KEY_LENGTH]
        self._iv         = hkdf_out[KEY_LENGTH:KEY_LENGTH + 4]
        self.completed   = True
        return True

    def make_keepalive(self) -> bytes:
        """
        Génère un keepalive chiffré AES-CCM pour firmware ancien (pré-Jan 2025).
        Format : [4 bytes counter LE] [AES-CCM(RideOn)] [4 bytes MAC]
        Appeler après process_response() ; retourne bare RideOn si non complété.
        """
        if not self.completed:
            return RIDE_ON  # firmware nouveau : bare RideOn suffit

        counter_bytes = self._counter.to_bytes(4, "little")
        nonce = self._iv + counter_bytes       # 8 bytes : IV4 + counter4
        self._counter += 1

        aesccm = AESCCM(self._shared_key, tag_length=4)
        # encrypt() retourne ciphertext + 4 bytes MAC concaténés
        ciphertext_and_tag = aesccm.encrypt(nonce, RIDE_ON, None)
        return counter_bytes + ciphertext_and_tag

    def is_device_response(self, data: bytes | bytearray) -> bool:
        """Vrai si ce paquet est la réponse de clé publique du device."""
        return bytes(data).startswith(RIDE_ON + RESPONSE_START)
