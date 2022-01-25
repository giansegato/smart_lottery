# Smart Lottery

Simple lottery where a pool of players enter paying an entrance fee, and when it ends the whole pool (minus a management fee) goes to the winner.

Only the owner of the contract (defined as the one deploying the contract) can start the lottery. Once it starts, it's no longer in control of the owner.

If the lottery has started, anyone can buy a 50$ ticket in. The sum of all the tickets make the overall winning poll.

After a pre-defined amount of time has passed, or a pre-defined number of maximum participants have joined, the lottery ends. At that moment, the winning poll is fully allocated to a random participant, minus a management fee that is transferred to the owner.

All the off-chain data are provided by Chainlink:
- Chainlink VRF provides the source of randomness needed for selecting the winner
- Chainlink price feed determines the price to pay (in wei) to get in
- Chainlink Keeper automates and decentralizes the lottery ending
