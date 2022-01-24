from brownie import (
    accounts, network, config, interface
)

LOCAL_DEV_CHAINS = ["development", "ganache-local"]
FORKED_CHAINS = ["mainnet-fork", "mainnet-fork-dev"]


def get_account(account_ix=None, account_id=None):
    if account_id:
        return accounts.load(account_id)
    if account_ix:
        return accounts[account_ix]  # ganache
    if network.show_active() in LOCAL_DEV_CHAINS or network.show_active() in FORKED_CHAINS:
        return accounts[0]  # ganache
    return accounts.load('dev-1')


def fund_contract_with_link(contract_address, link_token_address, account=None, amount=100000000000000000):
    account = account if account else get_account()
    link_token = interface.LinkTokenInterface(link_token_address)
    tx = link_token.transfer(contract_address, amount, {"from": account})
    tx.wait(1)
    print(f"Funded {contract_address} with {amount / (10 ** 18)} LINK tokens")
    return tx
