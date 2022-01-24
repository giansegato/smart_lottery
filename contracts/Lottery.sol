// SPDX-License-Identifier: MIT

pragma solidity ^0.8.0;

import "@chainlink/contracts/src/v0.8/interfaces/AggregatorV3Interface.sol";
import "@chainlink/contracts/src/v0.8/VRFConsumerBase.sol";
import "@openzeppelin/contracts/access/Ownable.sol";


contract Lottery is VRFConsumerBase, Ownable {

    enum LotteryState {OPEN, CLOSED, CALCULATING_WINNER}

    uint256 internal usdEntryFee;
    AggregatorV3Interface internal priceFeed;
    address payable[] public players;
    LotteryState public lotteryState;
    uint256 public vrfFee;
    bytes32 public vrfKeyHash;
    address payable[] public winners;
    address payable public latestWinner;
    uint256 public _latestRandomness;
    event RequestedRandomness(bytes32 requestId);

    constructor(uint256 _usdEntryFee, address _priceFeedAddress,
        address _vrfCoordinator, address _link, uint256 _vrfFee,
        bytes32 _keyHash) public
    VRFConsumerBase(
        _vrfCoordinator, _link
    ) {
        usdEntryFee = _usdEntryFee; // must have 18 decimals
        latestWinner = payable(address(0x0000000000000000000000000000000000000000000000000000000000000000));
        priceFeed = AggregatorV3Interface(_priceFeedAddress);
        lotteryState = LotteryState.CLOSED;
        vrfFee = _vrfFee;
        vrfKeyHash = _keyHash;
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

    function endLottery() public onlyOwner {
        // only the owner can stop the lottery
        require(lotteryState == LotteryState.OPEN, "Can't stop the lottery: none open yet.");
        lotteryState = LotteryState.CALCULATING_WINNER;

        // random number request
        bytes32 requestId = requestRandomness(vrfKeyHash, vrfFee);  // this method is coming from its super class
        emit RequestedRandomness(requestId);
    }

    function getPlayersCount() public view returns(uint count) {
        return players.length;
    }

    function fulfillRandomness(bytes32 requestId, uint256 _randomness) internal override {
        // we're overriding the super class → this function will be called by the VRF coordinator
        require(lotteryState == LotteryState.CALCULATING_WINNER, "Lottery still open / closed");
        require(_randomness > 0, "Random number not found");
        uint256 winnerIx = _randomness % players.length;
        latestWinner = players[winnerIx];
        winners.push(latestWinner);
        latestWinner.transfer(address(this).balance);
        // reset lottery
        players = new address payable[](0);
        lotteryState = LotteryState.CLOSED;
        _latestRandomness = _randomness;
    }

    // useful stuff
    function toString(uint256 value) internal pure returns (string memory) {
        // from https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Strings.sol#L15-L35
        if (value == 0) {
            return "0";
        }
        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }
        return string(buffer);
    }

}