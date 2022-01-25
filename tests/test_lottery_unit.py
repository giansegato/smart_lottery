import pytest
from brownie import Lottery, config, exceptions, network
from scripts.utils import LOCAL_DEV_CHAINS, get_account, fund_contract_with_link
from scripts.deploy_lottery import deploy_lottery, contract_to_mock, get_contract
from web3 import Web3

# Note: skip these test if we're not testing locally with mocks


def test_get_entrance_fee():
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


def test_cant_enter_not_started():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    # Act, assert
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.enter({"from": get_account(),
                       "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})


def test_can_start_and_enter():
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


def test_can_end():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    lottery = deploy_lottery()
    # Act
    account = get_account()
    lottery.startLottery({"from": account})
    lottery.enter({"from": account,
                   "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})
    fund_contract_with_link(lottery.address, get_contract('link_token').address)
    lottery.endLottery({"from": account})
    # Assert
    assert lottery.lotteryState() == 2


def test_cant_enter_small_fee():
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


def test_cant_start_not_owner():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    account = get_account()
    evil = get_account(account_ix=1)
    lottery = deploy_lottery(account)
    # Act, assert
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.startLottery({"from": evil}).wait(1)


def test_cant_end_not_owner():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    account = get_account()
    evil = get_account(account_ix=1)
    lottery = deploy_lottery(account)
    # Act, assert
    lottery.startLottery({"from": account}).wait(1)
    fund_contract_with_link(lottery.address, get_contract('link_token').address)
    with pytest.raises(exceptions.VirtualMachineError):
        lottery.endLottery({"from": evil}).wait(1)


def test_can_pick_winner():
    if network.show_active() not in LOCAL_DEV_CHAINS:
        pytest.skip("Not running locally")
    # Arrange
    account = get_account()
    lottery = deploy_lottery(account)
    STATIC_RNG = 777
    TOTAL_PLAYERS = 5
    # Act
    lottery.startLottery({"from": account})
    for account_ix in range(TOTAL_PLAYERS):
        lottery.enter({"from": get_account(account_ix=account_ix),
                       "value": lottery.getEntranceFee() + Web3.toWei(0.001, "ether")})
    predicted_winner = get_account(account_ix=STATIC_RNG % TOTAL_PLAYERS)
    predicted_winner_starting_balance = predicted_winner.balance()
    lottery_balance = lottery.balance()
    fund_contract_with_link(lottery.address, get_contract('link_token').address,
                            account=account)
    tx = lottery.endLottery({"from": account})
    request_id = tx.events['RequestedRandomness']['requestId']
    get_contract("vrf_coordinator").callBackWithRandomness(
        request_id, STATIC_RNG, lottery.address,
        {"from": get_account(7)})
    # Assert
    assert lottery.latestWinner() == predicted_winner.address
    assert lottery.balance() == 0
    assert predicted_winner.balance() == predicted_winner_starting_balance + lottery_balance
