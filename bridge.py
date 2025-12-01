from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware 
import json
from eth_account import Account
import os

def connect_to(chain):
    if chain == 'source': 
        api_url = "https://api.avax-test.network/ext/bc/C/rpc" 
    elif chain == 'destination': 
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/" 
    else:
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3

def get_contract_info(chain, contract_info_file):
    try:
        with open(contract_info_file, 'r') as f:
            contracts = json.load(f)
        return contracts[chain]
    except Exception as e:
        print(f"Failed to read contract info: {e}")
        return None

def get_sk():
    try:
        with open('secret_key.txt', 'r') as f:
            return f.readline().strip()
    except:
        return os.environ.get('PRIVATE_KEY')

def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return

    sk = get_sk()
    if not sk:
        print("Secret key not found")
        return

    acct = Account.from_key(sk)
    
    source_info = get_contract_info('source', contract_info)
    dest_info = get_contract_info('destination', contract_info)

    if not source_info or not dest_info:
        print("Could not load contract info")
        return

    w3_source = connect_to('source')
    w3_dest = connect_to('destination')

    source_contract = w3_source.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = w3_dest.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    if chain == 'source':
        # 监听 Source (Avalanche) 上的 Deposit，去 Destination (BSC) 执行 wrap
        current_block = w3_source.eth.block_number
        start_block = current_block - 5
        
        event_filter = source_contract.events.Deposit.create_filter(from_block=start_block, to_block='latest')
        events = event_filter.get_all_entries()

        for evt in events:
            print(f"Found Deposit: {evt.transactionHash.hex()}")
            token = evt.args['token']
            recipient = evt.args['recipient']
            amount = evt.args['amount']
            
            tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                'from': acct.address,
                'nonce': w3_dest.eth.get_transaction_count(acct.address),
                'gas': 300000,
                'gasPrice': w3_dest.eth.gas_price
            })
            
            signed_tx = w3_dest.eth.account.sign_transaction(tx, private_key=sk)
            # FIX: 使用 .raw_transaction (对应 web3.py v7.5.0)
            w3_dest.eth.send_raw_transaction(signed_tx.raw_transaction)
            print("Sent wrap transaction")

    elif chain == 'destination':
        # 监听 Destination (BSC) 上的 Unwrap，去 Source (Avalanche) 执行 withdraw
        current_block = w3_dest.eth.block_number
        start_block = current_block - 5
        
        event_filter = dest_contract.events.Unwrap.create_filter(from_block=start_block, to_block='latest')
        events = event_filter.get_all_entries()

        for evt in events:
            print(f"Found Unwrap: {evt.transactionHash.hex()}")
            # 根据 Destination.t.sol: event Unwrap(..., address indexed to, uint256 amount );
            underlying_token = evt.args['underlying_token']
            to = evt.args['to']
            amount = evt.args['amount']
            
            tx = source_contract.functions.withdraw(underlying_token, to, amount).build_transaction({
                'from': acct.address,
                'nonce': w3_source.eth.get_transaction_count(acct.address),
                'gas': 300000,
                'gasPrice': w3_source.eth.gas_price
            })
            
            signed_tx = w3_source.eth.account.sign_transaction(tx, private_key=sk)
            # FIX: 使用 .raw_transaction (对应 web3.py v7.5.0)
            w3_source.eth.send_raw_transaction(signed_tx.raw_transaction)
            print("Sent withdraw transaction")