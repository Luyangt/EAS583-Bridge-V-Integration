import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.providers.rpc import HTTPProvider
from eth_account import Account

# --- 账户信息 ---
pk = "0xb2ac935ae1f87c76d5f5704e6b247b790684d8a7d81c0c3f4a2c5d6d444cfed9"
my_addr = "0x7e85CD7990A1d46c6C45a3D852D858E3578d5A67"

# --- 合约地址 ---
# Source (Avalanche): 0xC847235E1b5788E78e74cEb7d7001bAb7Ed29AdB
# Dest (BSC): 0x7706fF394525Bf7f0c98282f488dD2399B672bcE
source_bridge_addr = "0xC847235E1b5788E78e74cEb7d7001bAb7Ed29AdB"
dest_bridge_addr = "0x7706fF394525Bf7f0c98282f488dD2399B672bcE"

# --- 代币 ---
my_token = "0xB6A529030973c8BeFe9Cb3ac9E8e608bE9a8a58C"
token_a = "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c"
token_b = "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"

# RPC
avax_url = "https://api.avax-test.network/ext/bc/C/rpc"
bsc_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"

# ABI
src_abi_str = '[{"inputs":[{"internalType":"address","name":"_token","type":"address"}],"name":"registerToken","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
dst_abi_str = '[{"inputs":[{"internalType":"address","name":"_underlying_token","type":"address"},{"internalType":"string","name":"name","type":"string"},{"internalType":"string","name":"symbol","type":"string"}],"name":"createToken","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"nonpayable","type":"function"}]'

def run_tx(w3_instance, func, msg, manual_nonce):
    print(f"Running: {msg} (Nonce: {manual_nonce})...")
    try:
        tx = func.build_transaction({
            'from': my_addr,
            'nonce': manual_nonce,
            'gas': 5000000,  # <--- 修改点：增加到了 500万 Gas
            'gasPrice': w3_instance.eth.gas_price
        })
        signed = w3_instance.eth.account.sign_transaction(tx, pk)
        tx_hash = w3_instance.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Sent. Hash: {tx_hash.hex()}")
        
        receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            print("Success")
        else:
            print("Failed (Reverted)")
            # 如果失败，通常意味着已经注册过了，或者是合约逻辑拒绝了
        return True
    except Exception as e:
        if "already" in str(e).lower():
             print("Skipping - seems already registered")
             return False
        else:
            print(f"Error: {e}")
            return False

def main():
    print("Connecting...")
    w3_a = Web3(HTTPProvider(avax_url))
    w3_a.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    w3_b = Web3(HTTPProvider(bsc_url))
    w3_b.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    src_contract = w3_a.eth.contract(address=source_bridge_addr, abi=json.loads(src_abi_str))
    dst_contract = w3_b.eth.contract(address=dest_bridge_addr, abi=json.loads(dst_abi_str))

    nonce_a = w3_a.eth.get_transaction_count(my_addr)
    nonce_b = w3_b.eth.get_transaction_count(my_addr)
    print(f"Start Nonces -> Source: {nonce_a}, Dest: {nonce_b}")

    # 1. Register My Token
    if run_tx(w3_a, src_contract.functions.registerToken(my_token), "Register My Token (Source)", nonce_a): nonce_a += 1
    if run_tx(w3_b, dst_contract.functions.createToken(my_token, "Test Token", "TEST"), "Create My Token (Dest)", nonce_b): nonce_b += 1

    # 2. Register Token A
    if run_tx(w3_a, src_contract.functions.registerToken(token_a), "Register Token A (Source)", nonce_a): nonce_a += 1
    if run_tx(w3_b, dst_contract.functions.createToken(token_a, "Token A", "TKNA"), "Create Token A (Dest)", nonce_b): nonce_b += 1

    # 3. Register Token B
    if run_tx(w3_a, src_contract.functions.registerToken(token_b), "Register Token B (Source)", nonce_a): nonce_a += 1
    if run_tx(w3_b, dst_contract.functions.createToken(token_b, "Token B", "TKNB"), "Create Token B (Dest)", nonce_b): nonce_b += 1

    print("Done.")

if __name__ == "__main__":
    main()