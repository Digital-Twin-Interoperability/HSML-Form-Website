import base58
import argparse
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

def extract_did_from_private_key(private_key_path):
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=None)

    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Invalid key type. Expected Ed25519.")

    public_key = private_key.public_key()
    
    # Serialize the public key to raw bytes
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # Multicodec prefix for Ed25519 keys
    multicodec_prefix = b'\xed\x01'  # 0xED01 prefix for Ed25519
    multicodec_key = multicodec_prefix + public_key_bytes
    
    # Base58 encoding for DID:key format
    did_key = "did:key:" + base58.b58encode(multicodec_key).decode('utf-8')
    
    return did_key

def generate_did_key():
    # Generate Ed25519 key pair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize public key to raw bytes
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # Multicodec for Ed25519 key (0xED01 prefix)
    multicodec_prefix = b'\xed\x01'  
    multicodec_key = multicodec_prefix + public_key_bytes
    
    # Encode to Base58 for DID:key
    did_key = f"did:key:{base58.b58encode(multicodec_key).decode('utf-8')}"
    
    return did_key, private_key

def main():
    parser = argparse.ArgumentParser(description="Generate DID:key for your objects")
    parser.add_argument("--export-private", action="store_true", help="Export private key to a file")
    args = parser.parse_args()
    
    did_key, private_key = generate_did_key()
    print(f"Generated DID:key: {did_key}")
    
    if args.export_private:
        with open("private_key.pem", "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        print("Private key saved to private_key.pem")

if __name__ == "__main__":
    main()
