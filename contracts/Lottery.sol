// SPDX-License-Identifier: MIT

pragma solidity ^0.8.0;

import "@chainlink/contracts/src/v0.8/interfaces/AggregatorV3Interface.sol";
import "@chainlink/contracts/src/v0.8/VRFConsumerBase.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@chainlink/contracts/src/v0.8/KeeperCompatible.sol";
import "contracts/Utils.sol";


contract Lottery is VRFConsumerBase, KeeperCompatibleInterface, Ownable {

    enum LotteryState {OPEN, CLOSED, CALCULATING_WINNER}
    event RequestedRandomness(bytes32 requestId);

    // internals / configuration
    uint256 internal immutable maxDuration; // how long should the lottery last (in seconds)
    uint256 internal immutable maxParticipants; // maximum number of participants
    uint256 internal immutable managementFee; // the fee that the owner takes as the lottery ends (proportion, base 100)
    uint256 internal immutable usdEntryFee; // entry fee (in USD, 18 decimals)
    bytes32 internal immutable vrfKeyHash; // key hash to provide to the VRF provider
    uint256 internal immutable vrfFee; // fee to pay to the VRF provider, for randomness
    AggregatorV3Interface internal priceFeed; // Price feed provider
    uint256 internal lastTimestamp; // when the last lottery started
    // public

    LotteryState public lotteryState; // state of the lottery (open, closed, calculating)
    address payable[] public players; // all the players who bought a ticket
    address payable[] public winners; // all the winners, so far
    address payable public latestWinner; // the last winner (corresponds to winners[-1])
    uint256 public _latestRandomness; // last randomness (to vet the validity of the winner picking)


    constructor(uint256 _usdEntryFee, uint256 _maxDuration, uint256 _maxParticipants, uint256 _managementFee,
        address _priceFeedAddress,
        address _vrfCoordinator, address _link, uint256 _vrfFee,
        bytes32 _keyHash) public
    VRFConsumerBase(
        _vrfCoordinator, _link
    ) {
        usdEntryFee = _usdEntryFee;
        maxDuration = _maxDuration;
        maxParticipants = _maxParticipants;
        managementFee = _managementFee;
        latestWinner = payable(address(0x0000000000000000000000000000000000000000000000000000000000000000));
        priceFeed = AggregatorV3Interface(_priceFeedAddress);
        lotteryState = LotteryState.CLOSED;
        vrfFee = _vrfFee;
        vrfKeyHash = _keyHash;
        lastTimestamp = block.timestamp;
    }

    function enter() public payable {
        // based on a pre-defined fee,
        // anyone can enter the lottery,
        // provided that it's open
        uint256 entrance_fee = getEntranceFee();
        string memory debug_message = string(abi.encodePacked(
            "Not enough ETH to enter the lottery -> ",
            toString(msg.value), " < ", toString(entrance_fee))
        );
        require(msg.value >= entrance_fee, debug_message);
        require(lotteryState == LotteryState.OPEN, "Lottery not yet open");
        players.push(payable(msg.sender));
    }

    function getConversionRate() internal view returns (uint256) {
        (,int price,,,) = priceFeed.latestRoundData();
        // returns 8 decimals
        uint256 adjustedPrice = uint256(price) * (10 ** 10);
        // 18 decimals, to be uniform
        return adjustedPrice;
    }

    function getEntranceFee() public view returns (uint256) {
        // returns the entrance fee, in ETH
        // fee: 50(18 dec) / adjustedPrice(18 dec)
        // * 10*18 → to bring it back to 18 decimals (otherwise it's 0 dec)
        uint256 adjustedPrice = getConversionRate();
        return (usdEntryFee * (10 ** 18)) / adjustedPrice;
    }

    function startLottery() public onlyOwner {
        // only the owner can start the lottery
        require(lotteryState == LotteryState.CLOSED, "Can't start a new lottery yet.");
        lotteryState = LotteryState.OPEN;
    }

    function canLotteryEnd() internal view returns(bool) {
        bool isLotteryOpen = lotteryState == LotteryState.OPEN;
        bool isOvertime = (block.timestamp - lastTimestamp) > maxDuration;
        bool maxParticipantsReached = players.length >= maxParticipants;

        return (isOvertime || maxParticipantsReached) && (players.length >= 2) && isLotteryOpen;
    }

    function endLottery() internal {
        require(canLotteryEnd(), "Conditions to end the lottery are not met.");
        lotteryState = LotteryState.CALCULATING_WINNER;

        // random number request
        bytes32 requestId = requestRandomness(vrfKeyHash, vrfFee);  // this method is coming from its super class
        emit RequestedRandomness(requestId);
    }

    function distributePool(uint256 _randomness) internal {
        uint256 winnerIx = _randomness % players.length;
        // assign winner variable
        latestWinner = players[winnerIx];
        winners.push(latestWinner);
        // determine the final prize
        uint totalPool = address(this).balance;
        uint managementFeeAmount = totalPool * managementFee / 100;
        uint prizeAmount = totalPool - managementFeeAmount;
        // distribute
        latestWinner.transfer(prizeAmount);
        payable(owner()).transfer(managementFeeAmount);
        // reset lottery
        players = new address payable[](0);
        lotteryState = LotteryState.CLOSED;
        _latestRandomness = _randomness;
    }

    function getPlayersCount() public view returns(uint count) {
        return players.length;
    }

    // VRF callback

    function fulfillRandomness(bytes32 requestId, uint256 _randomness) internal override {
        // we're overriding the super class → this function will be called by the VRF coordinator
        require(lotteryState == LotteryState.CALCULATING_WINNER, "Lottery still open / closed");
        require(_randomness > 0, "Random number not found");
        distributePool(_randomness);
    }

    // Keeper callbacks

    function checkUpkeep(bytes calldata /* checkData */) external override returns (bool upkeepNeeded, bytes memory /* performData */) {
        upkeepNeeded = canLotteryEnd();
    }

    function performUpkeep(bytes calldata /* performData */) external override {
        require(canLotteryEnd(), "Conditions to end the lottery are not met.");
        endLottery();
    }

}