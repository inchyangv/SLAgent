// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title SLAToken — Mock ERC20 for hackathon demo
/// @notice 6-decimal test token matching USDC convention
contract SLAToken is ERC20 {
    uint8 private constant _DECIMALS = 6;

    constructor() ERC20("SLA Test Token", "SLAT") {}

    function decimals() public pure override returns (uint8) {
        return _DECIMALS;
    }

    /// @notice Anyone can mint for testing
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
