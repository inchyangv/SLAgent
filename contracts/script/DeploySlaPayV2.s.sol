// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "forge-std/console2.sol";

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import "../src/SLAToken.sol";
import "../src/SLASettlement.sol";

/// @notice Deploy SLAToken + SLASettlement for demo networks (ex: SKALE Base Sepolia (BITE v2 Sandbox 2)).
/// Recommended: use one EOA as deployer+gateway+resolver for the demo.
contract DeploySlaPayV2 is Script {
    function run() external {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");

        // For demo simplicity we default gateway/resolver to the broadcaster address.
        address broadcaster = vm.addr(privateKey);
        address gateway = _envAddressOr("GATEWAY_ADDRESS", broadcaster);
        address resolver = _envAddressOr("RESOLVER_ADDRESS", broadcaster);

        uint256 disputeWindow = vm.envOr("DISPUTE_WINDOW_SECONDS", uint256(60));
        uint256 bondAmount = vm.envOr("BOND_AMOUNT", uint256(10_000)); // 0.01 SLAT if 6 decimals

        // Optional bootstrap (mint + approve) for the gateway EOA.
        uint256 mintToGateway = vm.envOr("MINT_TO_GATEWAY", uint256(1_000_000_000)); // 1000 SLAT (6 decimals)
        bool approveMax = vm.envOr("APPROVE_MAX", true);

        // Optional: use an existing token (ex: USDC on SKALE Base Sepolia (BITE v2 Sandbox 2))
        // instead of deploying SLAToken.
        address existingToken = _envAddressOr("TOKEN_ADDRESS", address(0));

        vm.startBroadcast(privateKey);

        address tokenAddr;
        bool deployedToken;

        if (existingToken != address(0)) {
            tokenAddr = existingToken;
            deployedToken = false;
        } else {
            SLAToken token = new SLAToken();
            tokenAddr = address(token);
            deployedToken = true;

            if (mintToGateway > 0) {
                token.mint(gateway, mintToGateway);
            }
        }

        SLASettlement settlement = new SLASettlement(
            tokenAddr,
            gateway,
            resolver,
            disputeWindow,
            bondAmount
        );

        // Approve from broadcaster only if broadcaster == gateway
        if (approveMax && broadcaster == gateway) {
            IERC20(tokenAddr).approve(address(settlement), type(uint256).max);
        }

        vm.stopBroadcast();

        console2.log("Deployer:", broadcaster);
        console2.log("Gateway:", gateway);
        console2.log("Resolver:", resolver);
        console2.log("Token:", tokenAddr);
        console2.log("SLASettlement:", address(settlement));
        console2.log("DisputeWindowSeconds:", disputeWindow);
        console2.log("BondAmount:", bondAmount);
        console2.log("DeployedToken:", deployedToken);
        console2.log("MintedToGateway:", deployedToken ? mintToGateway : uint256(0));
        console2.log("ApprovedMaxFromBroadcaster:", approveMax && broadcaster == gateway);
    }

    function _envAddressOr(string memory key, address fallbackAddr) internal returns (address) {
        // Foundry exposes envOr for some primitive types; addresses are easiest to parse from string.
        string memory raw = vm.envOr(key, string(""));
        if (bytes(raw).length == 0) return fallbackAddr;
        return vm.parseAddress(raw);
    }
}
