import time

from brownie import (
    network,
    config,
    Lottery,
    MockV3Aggregator,
    Contract,
    VRFCoordinatorMock,
    LinkToken
)
from scripts.utils import get_account, LOCAL_DEV_CHAINS, fund_contract_with_link
from web3 import Web3

CHAINLINK_TIMEOUT = 120
CHAINLINK_REFERSH_RATE = 3

contract_to_mock = {
    'eth_usd_address': {
        'contract': MockV3Aggregator,
        'params': {
            '0_decimals': 8,
            '1_initial_value': 2000_00_000_000
        }
    },
    'vrf_coordinator': {
        'contract': VRFCoordinatorMock,
        'params': {}
    },
    'link_token': {'contract': LinkToken, 'params': {}},
}


def get_contract(contract_name, params=None, account=None):
    # we don't check if network in FORKED chain because in a forked
    # chain we we already have the contract ready and deployed
    mock = contract_to_mock.get(contract_name)
    if network.show_active() in LOCAL_DEV_CHAINS:
        if len(mock['contract']) == 0:
            # no mock has been deployed → move on deploying it
            if account is None:
                account = get_account()
            if params is None:
                params = [v for k, v in sorted(mock['params'].items())]
            mock['contract'].deploy(*params, {'from': account})
            print(f"Deployed {contract_name}")
        contract = mock['contract'][-1]
    else:
        # we're NOT in our dev network here: we're on testnets
        # to interact with a contract on chain we need 1. its address, 2. its interface (ABI)
        # the ABI comes from the mocks, while the address from the config (dependent on the type of chain)
        contract_address = config["networks"][network.show_active()][contract_name]
        contract_abi = mock['contract'].abi
        contract = Contract.from_abi(mock['contract']._name, contract_address, contract_abi)
    return contract


def deploy_lottery(account=None):
    account = account if account else get_account()
    price_feed = get_contract('eth_usd_address', account=account)
    link_token = get_contract('link_token', account=account)
    vrf_coordinator = get_contract('vrf_coordinator', params=[link_token.address], account=account)
    vrf_fee = config["networks"][network.show_active()].get('vrf_fee')
    vrf_keyhash = config["networks"][network.show_active()].get('vrf_keyhash')
    usd_entry_fee = Web3.toWei(config['lottery'].get('entrance_fee'), "ether")
    max_duration = config['lottery'].get('max_duration')
    max_participants = config['lottery'].get('max_participants')
    management_fee = config['lottery'].get('management_fee')
    print("Loaded all external dependencies")
    lottery = Lottery.deploy(usd_entry_fee,
                             max_duration,
                             max_participants,
                             management_fee,
                             price_feed.address,
                             vrf_coordinator.address,
                             link_token.address,
                             vrf_fee,
                             vrf_keyhash,
                             {"from": account},
                             publish_source=config["networks"][network.show_active()].get('verify', False))
    print(f"Successfully deployed lottery contract: {lottery.address}.")
    return lottery


def start_lottery():
    account = get_account()
    lottery = Lottery[-1]
    lottery.startLottery({"from": account}).wait(1)
    print("Lottery has started.")


def enter_lottery():
    account = get_account()
    lottery = Lottery[-1]
    entrance_fee_wei = lottery.getEntranceFee()
    lottery.enter({"from": account, "value": entrance_fee_wei + Web3.toWei(0.0001, "ether")}).wait(1)
    print("Entered the lottery!")


def end_lottery():
    account = get_account()
    lottery = Lottery[-1]
    # fund the lottery contract with some LINK tokens, in order to pay the oracles
    tx = fund_contract_with_link(lottery.address, get_contract("link_token").address, account, 10 ** 17)
    # now that the contract is sufficiently funded, we can end the lottery
    lottery.endLottery({"from": account}).wait(1)
    time_passed = 0
    while (lottery.lotteryState() == 2) and (time_passed < CHAINLINK_TIMEOUT):
        time.sleep(CHAINLINK_REFERSH_RATE)
        time_passed += CHAINLINK_REFERSH_RATE
    print(f"Ended the lottery! The winner is {lottery.latestWinner()}")


def main():
    deploy_lottery()
    start_lottery()
    enter_lottery()
    end_lottery()
