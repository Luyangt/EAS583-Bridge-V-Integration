from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware 
from datetime import datetime
import json
import pandas as pd
from eth_account import Account
import os

def connect_to(chain):
    if chain == 'source': 
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" 

    if chain == 'destination': 
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" 

    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    try:
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]

def get_sk():
    try:
        with open('secret_key.txt', 'r') as f:
            return f.readline().strip()
    except:
        return os.environ.get('PRIVATE_KEY')

def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0
    
    sk = get_sk()
    if not sk:
        print("Secret key not found")
        return

    acct = Account.from_key(sk)
    
    source_info = get_contract_info('source', contract_info)
    dest_info = get_contract_info('destination', contract_info)

    w3_source = connect_to('source')
    w3_dest = connect_to('destination')

    source_contract = w3_source.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = w3_dest.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    if chain == 'source':
        current_block = w3_source.eth.block_number
        start_block = current_block - 5
        
        event_filter = source_contract.events.Deposit.create_filter(from_block=start_block, to_block='latest')
        events = event_filter.get_all_entries()

        for evt in events:
            token = evt.args['token']
            recipient = evt.args['recipient']
            amount = evt.args['amount']
            
            nonce = w3_dest.eth.get_transaction_count(acct.address)
            tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gasPrice': w3_dest.eth.gas_price
            })
            
            # Use Account.sign_transaction (v6+ style)
            signed_tx = w