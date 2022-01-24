import time

import pytest
from brownie import Lottery, network
from scripts.utils import LOCAL_DEV_CHAINS, get_account, fund_contract_with_link, FORKED_CHAINS
from scripts.deploy_lottery import deploy_lottery, get_contract, CHAINLINK_TIMEOUT, \
    CHAINLINK_REFERSH_RATE

# Note: skip these test if we're on local test, with mocks


def test_can_pick_winner():
    if network.show_active() in LOCAL_DEV_CHAINS:
        pytest.skip("Running locally")
    # Arrange
    account = get_account(account_id='dev-1')
    print(f"Using account {account}")
    lottery = deploy_lottery(account)
    # Act
    lottery.startLottery({"from": account}).wait(1)
    print("Started the lottery")
    entrance_fee = lottery.getEntranceFee() + 10_000
    lottery.enter({"from": account, "value": entrance_fee}).wait(1)
    print(f"Entered the lottery with a ticket price of {entrance_fee}")
    prev_account_balance = account.balance()
    fund_contract_with_link(lottery.address, get_contract('link_token').address,
                            account=account)
    tx = lottery.endLottery({"from": account})
    tx.wait(1)
    print("Requested winner")
    time_passed = 0
    while (lottery.lotteryState() == 2) and (time_passed < CHAINLINK_TIMEOUT):
        time.sleep(CHAINLINK_REFERSH_RATE)
        time_passed += CHAINLINK_REFERSH_RATE
    print(f"Ended the lottery after {time_passed}\". Winner: {lottery.latestWinner()}")
    # Assert
    assert time_passed < CHAINLINK_TIMEOUT
    assert lottery.latestWinner() == account.address
    assert lottery.balance() == 0
    assert account.balance() > prev_account_balance
