import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.providers.rpc import HTTPProvider
from eth_account import Account

# My account info
pk = "0xb2ac935ae1f87c76d5f5704e6b247b790684d8a7d81c0c3f4a2c5d6d444cfed9"
my_addr = "0x7e85CD7990A1d46c6C45a3D852D858E3578d5A67"

# Bridge contract address
bridge_addr = "0xC847235E1b5788E78e74cEb7d7001bAb7Ed29AdB"

# Tokens to register
token1 = "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c"
token2 = "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"

# RPC endpoints
avax_url = "https://api.avax-test.network/ext/bc/C/rpc"
bsc_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"

# Minimal ABIs
src_abi_str = '[{"inputs":[{"internalType":"address","name":"_token","type":"address"}],"name":"registerToken","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
dst_abi_str = '[{"inputs":[{"internalType":"address","name":"_underlying_token","type":"address"},{"internalType":"string","name":"name","type":"string"},{"internalType":"string","name":"symbol","type":"string"}],"name":"createToken","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"nonpayable","type":"function"}]'

def run_tx(w3_instance, func, msg, manual_nonce):
    print(f"Running: {msg} (Nonce: {manual_nonce})...")
    try:
        # build transaction using the MANUALLY passed nonce
        tx = func.build_transaction({
            'from': my_addr,
            'nonce': manual_nonce,
            'gas': 300000,
            'gasPrice': w3_instance.eth.gas_price
        })
        
        # sign and send
        signed = w3_instance.eth.account.sign_transaction(tx, pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Sent. Hash: {tx_hash.hex()}")
        
        # wait for receipt
        receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            print("Success")
        else:
            print("Failed (Reverted)")
        return True # Transaction sent successfully
            
    except Exception as e:
        # check if already registered to avoid crash
        if "already" in str(e).lower():
             print("Skipping - seems already registered")
             return False # Did not send a transaction
        else:
            print(f"Error: {e}")
            return False

def main():
    print("Connecting to chains...")
    
    # Setup connection
    w3_a = Web3(HTTPProvider(avax_url))
    w3_a.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    w3_b = Web3(HTTPProvider(bsc_url))
    w3_b.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    if not w3_a.is_connected() or not w3_b.is_connected():
        print("Connection error")
        return
    
    # Init contracts
    src_contract = w3_a.eth.contract(address=bridge_addr, abi=json.loads(src_abi_str))
    dst_contract = w3_b.eth.contract(address=bridge_addr, abi=json.loads(dst_abi_str))

    # --- FIX: Get initial nonces ONCE ---
    nonce_a = w3_a.eth.get_transaction_count(my_addr)
    nonce_b = w3_b.eth.get_transaction_count(my_addr)
    print(f"Initial Nonces -> Source: {nonce_a}, Dest: {nonce_b}")

    # Process Token 1
    # Source
    if run_tx(w3_a, src_contract.functions.registerToken(token1), "Register Token 1 (Source)", nonce_a):
        nonce_a += 1 # Only increment if we actually sent a tx
    else:
        # If it failed but wasn't "already registered", we might need to be careful, 
        # but for "already registered" errors (reverts during simulation), nonce isn't used.
        # If the error happened AFTER sending (during wait), nonce IS used.
        # For simplicity in this script, if it skipped due to "already registered" simulation, nonce didn't move.
        # If it failed ON CHAIN, nonce moved.
        # Let's assume if it printed "Error" it failed pre-flight. 
        # But to be safe, you can re-run script if things get out of sync.
        pass

    # Dest
    if run_tx(w3_b, dst_contract.functions.createToken(token1, "Token A", "TKNA"), "Create Token 1 (Dest)", nonce_b):
        nonce_b += 1

    # Process Token 2
    # Source
    if run_tx(w3_a, src_contract.functions.registerToken(token2), "Register Token 2 (Source)", nonce_a):
        nonce_a += 1

    # Dest
    if run_tx(w3_b, dst_contract.functions.createToken(token2, "Token B", "TKNB"), "Create Token 2 (Dest)", nonce_b):
        nonce_b += 1

    print("Done.")

if __name__ == "__main__":
    main()