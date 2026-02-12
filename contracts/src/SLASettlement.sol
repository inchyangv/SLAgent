// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/// @title SLASettlement — Core settlement contract for SLA-Pay v2
/// @notice Receives max_price, splits payout to seller + refund to buyer.
///         Emits receipt hash on-chain. Prevents replay via requestId uniqueness.
contract SLASettlement {
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // --- Events ---
    event Settled(
        bytes32 indexed mandateId,
        bytes32 indexed requestId,
        address buyer,
        address seller,
        uint256 payout,
        uint256 refund,
        bytes32 receiptHash
    );

    // --- State ---
    IERC20 public immutable token;
    address public immutable gateway;

    /// @notice Tracks settled requestIds to prevent replay
    mapping(bytes32 => bool) public settled;

    // --- Errors ---
    error AlreadySettled();
    error PayoutExceedsMax();
    error ZeroAddress();
    error InvalidSignature();

    constructor(address _token, address _gateway) {
        require(_token != address(0), "token=0");
        require(_gateway != address(0), "gateway=0");
        token = IERC20(_token);
        gateway = _gateway;
    }

    /// @notice Settle a request: pay seller, refund buyer, emit receipt hash.
    /// @dev The caller must have approved this contract to spend maxPrice tokens.
    ///      Gateway signs: keccak256(abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash))
    /// @param mandateId   Hash identifying the SLA mandate
    /// @param requestId   Unique request identifier (replay key)
    /// @param buyer       Address to receive refund
    /// @param seller      Address to receive payout
    /// @param maxPrice    Total amount locked for this request
    /// @param payout      Amount to pay seller (must be <= maxPrice)
    /// @param receiptHash Hash of the full performance receipt
    /// @param gatewaySig  Gateway's ECDSA signature over settlement params
    function settle(
        bytes32 mandateId,
        bytes32 requestId,
        address buyer,
        address seller,
        uint256 maxPrice,
        uint256 payout,
        bytes32 receiptHash,
        bytes calldata gatewaySig
    ) external {
        if (settled[requestId]) revert AlreadySettled();
        if (payout > maxPrice) revert PayoutExceedsMax();
        if (buyer == address(0) || seller == address(0)) revert ZeroAddress();

        // Verify gateway signature
        bytes32 digest = keccak256(
            abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash)
        ).toEthSignedMessageHash();

        address recovered = digest.recover(gatewaySig);
        if (recovered != gateway) revert InvalidSignature();

        // Mark as settled (replay protection)
        settled[requestId] = true;

        // Transfer: caller sends maxPrice to this contract, then we split
        token.safeTransferFrom(msg.sender, seller, payout);
        uint256 refund = maxPrice - payout;
        if (refund > 0) {
            token.safeTransferFrom(msg.sender, buyer, refund);
        }

        emit Settled(mandateId, requestId, buyer, seller, payout, refund, receiptHash);
    }
}
