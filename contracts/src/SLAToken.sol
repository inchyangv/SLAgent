// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title SLAToken — Mock ERC20 for hackathon demo
/// @notice 6-decimal mock "Tether USD" token for Sepolia demos
contract SLAToken is ERC20 {
    uint8 private constant _DECIMALS = 6;

    constructor() ERC20("Tether USD", "USDT") {}

    function decimals() public pure override returns (uint8) {
        return _DECIMALS;
    }

    /// @notice Anyone can mint for testing
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
