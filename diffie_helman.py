from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import base64
import traceback

# Fixed DH parameters - Both sides must use the same parameters
# These are 2048-bit RFC 3526 MODP Group 14 parameters
P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16
)
G = 2


class DiffieHellman:
    def __init__(self):
        # Use fixed parameters instead of generating new ones
        self.parameters = dh.DHParameterNumbers(p=P, g=G, q=None).parameters(default_backend())
        # Generate private key with these parameters
        self.private_key = self.parameters.generate_private_key()
        # Get public key
        self.public_key = self.private_key.public_key()

    def get_public_key_bytes(self):
        try:
            return self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        except Exception as e:
            raise Exception(f"Error serializing public key: {str(e)}")

    def get_shared_key(self, peer_public_key_bytes):
        try:
            peer_public_key = serialization.load_pem_public_key(
                peer_public_key_bytes,
                backend=default_backend()
            )

            # Get the shared key
            shared_secret = self.private_key.exchange(peer_public_key)

            # Derive a suitable encryption key using HKDF
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 32 bytes for AES-256
                salt=None,
                info=b'handshake data',
                backend=default_backend()
            ).derive(shared_secret)

            return derived_key

        except Exception as e:
            traceback.print_exc()
            raise Exception(f"Error computing shared key: {str(e)}")

