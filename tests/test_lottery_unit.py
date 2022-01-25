import time

import pytest
from brownie import Lottery, config, exceptions, network
from scripts.utils import LOCAL_DEV_CHAINS, get_account, fund_contract_with_link
from scripts.deploy_lottery import deploy_lottery, contract_to_mock, get_contract
from web3 import Web3

# Note: skip these test if we're not testing locally with mocks


def test_get_entrance_fee():
    """
    Test: does the getEntranceFee() function work?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    mocked_eth_rate = contract_to_mock['eth_usd_address']['params']['1_initial_value'] * (
            10 ** (18 - contract_to_mock['eth_usd_address']['params']['0_decimals'])
    )
    usd_entry_fee = Web3.toWei(config['lottery'].get('entrance_fee'), "ether")
    # Act
    entrance_fee = lottery.getEntranceFee()
    expected_entry_fee = Web3.toWei(usd_entry_fee / mocked_eth_rate, "ether")
    # Asset
    assert (entrance_fee == expected_entry_fee)


def test_cannot_enter_not_started():
    """
    Test: are users restricted from entering the lottery when it hasn't started yet?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    # Act, assert
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.enter({"from": get_account(),
                       "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})


def test_can_start_and_enter():
    """
    Test: can users validly enter the lottery once it has started?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    # Act
    account = get_account()
    lottery.startLottery({"from": account})
    lottery.enter({"from": account,
                   "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})
    # Assert
    assert lottery.players(0) == account.address
    assert lottery.lotteryState() == 0


def test_cannot_enter_small_fee():
    """
    Test: are the users restricted from entering the lottery with not enought wei?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    # Act, assert
    account = get_account()
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.enter({"from": account,
                       "value": lottery.getEntranceFee() - Web3.toWei(0.001, "ether")})
    assert lottery.getPlayersCount() == 0 or lottery.players(lottery.getPlayersCount() - 1) != account.address


def test_cannot_start_not_owner():
    """
    Test: can only the owner start the lottery?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    account = get_account()
    evil = get_account(account_ix=1)
    lottery = deploy_lottery(account)
    # Act, assert
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.startLottery({"from": evil}).wait(1)


def test_lottery_end_conditions():
    """
    Test: does lottery knows when it should end?
    """
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    max_duration = 5  # seconds
    max_participants = 3
    account = get_account()
    lottery = deploy_lottery(account=account, test_duration=max_duration, test_participants=max_participants)
    # Act
    lottery.startLottery({"from": account})
    fund_contract_with_link(lottery.address, get_contract('link_token').address)
    # Assert
    upkeepNeeded, performData = lottery.checkUpkeep.call("", {"from": account},)
    assert not upkeepNeeded
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.performUpkeep("", {"from": account}).wait(1)
    for players in range(max_participants):
        lottery.enter({"from": get_account(account_ix=players+1),
                       "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})
    time.sleep(max_duration + 1)
    upkeepNeeded, performData = lottery.checkUpkeep.call("", {"from": account}, )
    assert upkeepNeeded
    lottery.performUpkeep("", {"from": account}).wait(1)


def test_can_pick_winner():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    owner = get_account(9)
    owner_starting_balance = owner.balance()
    static_rng = 777
    max_duration = 5  # seconds
    max_participants = 5
    management_fee = 2  # percentage points
    lottery = deploy_lottery(account=owner, test_duration=max_duration, test_participants=max_participants,
                             test_management_fee=management_fee)
    # Act
    lottery.startLottery({"from": owner})
    assert lottery.lotteryState() == 0
    fund_contract_with_link(lottery.address, get_contract('link_token').address,
                            account=owner)
    for account_ix in range(max_participants):
        lottery.enter({"from": get_account(account_ix=account_ix),
                       "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})
    predicted_winner = get_account(account_ix=static_rng % max_participants)
    predicted_winner_starting_balance = predicted_winner.balance()
    lottery_balance = lottery.balance()
    time.sleep(max_duration + 1)
    tx = lottery.performUpkeep("", {"from": owner})
    tx.wait(1)
    assert lottery.lotteryState() == 2
    request_id = tx.events['RequestedRandomness']['requestId']
    get_contract("vrf_coordinator").callBackWithRandomness(
        request_id, static_rng, lottery.address,
        {"from": owner}
    )
    # Assert
    owner_fee = lottery_balance * management_fee / 100
    winner_prize = lottery_balance - owner_fee
    assert lottery.lotteryState() == 1
    assert lottery.latestWinner() == predicted_winner.address
    assert lottery.balance() == 0
    assert owner.balance() == owner_starting_balance + owner_fee
    assert predicted_winner.balance() == predicted_winner_starting_balance + winner_prize
