// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @title SLASettlement — Settlement + Dispute contract for SLAgent-402
/// @notice Escrowed settlement with delayed finalization and bonded disputes.
///         Buyer deposits funds via deposit(), gateway calls settle() to set terms,
///         funds are held until dispute window passes or dispute is resolved.
contract SLASettlement {
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;

    // --- Enums ---
    enum Status { NONE, DEPOSITED, PENDING, DISPUTED, FINALIZED }

    // --- Structs ---
    struct Settlement {
        bytes32 mandateId;
        address buyer;
        address seller;
        uint256 maxPrice;
        uint256 payout;
        bytes32 receiptHash;
        uint256 finalizeAfter; // timestamp after which seller can withdraw
        Status status;
    }

    struct Dispute {
        address disputer;
        uint256 bond;
    }

    // --- Events ---
    event Deposited(
        bytes32 indexed requestId,
        address indexed buyer,
        address depositor,
        uint256 amount
    );

    event Settled(
        bytes32 indexed mandateId,
        bytes32 indexed requestId,
        address buyer,
        address seller,
        uint256 payout,
        uint256 refund,
        bytes32 receiptHash
    );

    event DisputeOpened(
        bytes32 indexed requestId,
        address disputer,
        uint256 bond
    );

    event DisputeResolved(
        bytes32 indexed requestId,
        uint256 originalPayout,
        uint256 finalPayout,
        bool disputerWon
    );

    event Finalized(
        bytes32 indexed requestId,
        uint256 payout,
        uint256 refund
    );

    // --- State ---
    IERC20 public immutable token;
    address public immutable gateway;
    address public immutable resolver;
    uint256 public immutable disputeWindow; // seconds
    uint256 public immutable bondAmount;

    mapping(bytes32 => Settlement) public settlements;
    mapping(bytes32 => Dispute) public disputes;

    // --- Errors ---
    error AlreadySettled();
    error AlreadyDeposited();
    error PayoutExceedsMax();
    error ZeroAddress();
    error ZeroAmount();
    error InvalidSignature();
    error NotDeposited();
    error InsufficientDeposit();
    error BuyerMismatch();
    error NotPending();
    error NotDisputed();
    error DisputeWindowActive();
    error DisputeWindowExpired();
    error OnlyResolver();
    error FinalPayoutExceedsMax();

    constructor(
        address _token,
        address _gateway,
        address _resolver,
        uint256 _disputeWindow,
        uint256 _bondAmount
    ) {
        require(_token != address(0), "token=0");
        require(_gateway != address(0), "gateway=0");
        require(_resolver != address(0), "resolver=0");
        token = IERC20(_token);
        gateway = _gateway;
        resolver = _resolver;
        disputeWindow = _disputeWindow;
        bondAmount = _bondAmount;
    }

    /// @dev Minimal ERC-191 "eth_sign" prefix for bytes32 hashes.
    ///      Keeps the dependency surface small for testnet demos and reproducible builds.
    function _toEthSignedMessageHash(bytes32 messageHash) internal pure returns (bytes32 digest) {
        assembly ("memory-safe") {
            mstore(0x00, "\x19Ethereum Signed Message:\n32")
            mstore(0x1c, messageHash)
            digest := keccak256(0x00, 0x3c)
        }
    }

    /// @notice Deposit funds for a request (buyer pays, not gateway).
    ///         Can be called by the buyer directly, or by gateway/facilitator on behalf.
    ///         msg.sender pays the tokens; `buyer` is recorded for accounting.
    /// @param requestId Unique request identifier
    /// @param buyer The buyer address (who the deposit is for)
    /// @param amount Amount of tokens to deposit (must be >= maxPrice at settle time)
    function deposit(
        bytes32 requestId,
        address buyer,
        uint256 amount
    ) external {
        if (settlements[requestId].status != Status.NONE) revert AlreadyDeposited();
        if (buyer == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        // Record the deposit
        settlements[requestId] = Settlement({
            mandateId: bytes32(0),
            buyer: buyer,
            seller: address(0),
            maxPrice: amount,
            payout: 0,
            receiptHash: bytes32(0),
            finalizeAfter: 0,
            status: Status.DEPOSITED
        });

        // Pull tokens from msg.sender (buyer or facilitator) into escrow
        token.safeTransferFrom(msg.sender, address(this), amount);

        emit Deposited(requestId, buyer, msg.sender, amount);
    }

    /// @notice Submit a settlement — uses already-deposited funds.
    ///         Only the gateway can call this (verified by signature).
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
        Settlement storage s = settlements[requestId];

        // Must have a prior deposit
        if (s.status == Status.NONE) revert NotDeposited();
        if (s.status != Status.DEPOSITED) revert AlreadySettled();
        if (payout > maxPrice) revert PayoutExceedsMax();
        if (buyer == address(0) || seller == address(0)) revert ZeroAddress();
        if (s.buyer != buyer) revert BuyerMismatch();
        if (s.maxPrice < maxPrice) revert InsufficientDeposit();

        // Verify gateway signature
        bytes32 digest = _toEthSignedMessageHash(keccak256(
            abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash)
        ));

        address recovered = digest.recover(gatewaySig);
        if (recovered != gateway) revert InvalidSignature();

        // Update settlement with full terms
        s.mandateId = mandateId;
        s.seller = seller;
        s.maxPrice = maxPrice;
        s.payout = payout;
        s.receiptHash = receiptHash;
        s.finalizeAfter = block.timestamp + disputeWindow;
        s.status = Status.PENDING;

        // If deposit was larger than maxPrice, refund the excess immediately
        uint256 deposited = s.maxPrice;
        if (deposited > maxPrice) {
            uint256 excess = deposited - maxPrice;
            token.safeTransfer(buyer, excess);
        }

        emit Settled(mandateId, requestId, buyer, seller, payout, maxPrice - payout, receiptHash);
    }

    /// @notice Open a dispute (requires bond). Must be within dispute window.
    function openDispute(bytes32 requestId) external {
        Settlement storage s = settlements[requestId];
        if (s.status != Status.PENDING) revert NotPending();
        if (block.timestamp >= s.finalizeAfter) revert DisputeWindowExpired();

        // Pull bond from disputer
        token.safeTransferFrom(msg.sender, address(this), bondAmount);

        s.status = Status.DISPUTED;
        disputes[requestId] = Dispute({
            disputer: msg.sender,
            bond: bondAmount
        });

        emit DisputeOpened(requestId, msg.sender, bondAmount);
    }

    /// @notice Resolver decides final payout. Handles bond slashing.
    function resolveDispute(bytes32 requestId, uint256 finalPayout) external {
        if (msg.sender != resolver) revert OnlyResolver();
        Settlement storage s = settlements[requestId];
        if (s.status != Status.DISPUTED) revert NotDisputed();
        if (finalPayout > s.maxPrice) revert FinalPayoutExceedsMax();

        Dispute memory d = disputes[requestId];
        uint256 originalPayout = s.payout;
        bool disputerWon = (finalPayout != originalPayout);

        // Update payout and finalize
        s.payout = finalPayout;
        s.status = Status.FINALIZED;

        // Distribute escrowed funds
        _distribute(s);

        // Handle bond
        if (disputerWon) {
            // Return bond to disputer
            token.safeTransfer(d.disputer, d.bond);
        } else {
            // Slash bond — send to resolver (protocol revenue)
            token.safeTransfer(resolver, d.bond);
        }

        emit DisputeResolved(requestId, originalPayout, finalPayout, disputerWon);
    }

    /// @notice Finalize after dispute window passes without dispute.
    function finalize(bytes32 requestId) external {
        Settlement storage s = settlements[requestId];
        if (s.status != Status.PENDING) revert NotPending();
        if (block.timestamp < s.finalizeAfter) revert DisputeWindowActive();

        s.status = Status.FINALIZED;
        _distribute(s);

        emit Finalized(requestId, s.payout, s.maxPrice - s.payout);
    }

    /// @dev Internal: send payout to seller, refund to buyer
    function _distribute(Settlement storage s) internal {
        if (s.payout > 0) {
            token.safeTransfer(s.seller, s.payout);
        }
        uint256 refund = s.maxPrice - s.payout;
        if (refund > 0) {
            token.safeTransfer(s.buyer, refund);
        }
    }
}
