// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./IERC8004.sol";
import "../SLASettlement.sol";

/// @title SLAOrchestrator — ERC-8004 adapter for SLAgent-402 settlement lifecycle
/// @notice Maps SLAgent-402 operations (settle, finalize, dispute) to ERC-8004
///         registry hooks: Identity (agent registration), Validation (receipt
///         verification), and Reputation (post-settlement feedback).
///
/// Flow:
///   1. Agents register via registerAgent() → Identity Registry
///   2. After settlement, gateway calls recordValidation() → Validation Registry
///   3. Validator calls submitValidationResult() → Validation Registry response
///   4. After finalization, anyone calls recordReputation() → Reputation Registry
contract SLAOrchestrator {
    // --- ERC-8004 Registries ---
    IERC8004Identity public immutable identity;
    IERC8004Reputation public immutable reputation;
    IERC8004Validation public immutable validation;

    // --- SLAgent-402 Settlement ---
    SLASettlement public immutable settlement;

    // --- State ---
    // agentId for addresses registered through this orchestrator
    mapping(address => uint256) public agentIds;
    // validator address for this orchestrator (gateway acts as validator)
    address public immutable validator;
    // track which requestIds have had validation recorded
    mapping(bytes32 => bool) public validationRecorded;
    // track which requestIds have had reputation recorded
    mapping(bytes32 => bool) public reputationRecorded;

    // --- Events ---
    event AgentRegistered(address indexed agent, uint256 indexed agentId, string uri);
    event ValidationRecorded(bytes32 indexed requestId, uint256 indexed sellerAgentId);
    event ValidationResultSubmitted(bytes32 indexed requestId, uint8 response, string tag);
    event ReputationRecorded(
        bytes32 indexed requestId, uint256 indexed sellerAgentId, int128 score
    );

    // --- Errors ---
    error AgentAlreadyRegistered();
    error AgentNotRegistered();
    error AlreadyRecorded();
    error SettlementNotFinalized();
    error SettlementNotPending();

    constructor(
        address _identity,
        address _reputation,
        address _validation,
        address _settlement,
        address _validator
    ) {
        identity = IERC8004Identity(_identity);
        reputation = IERC8004Reputation(_reputation);
        validation = IERC8004Validation(_validation);
        settlement = SLASettlement(_settlement);
        validator = _validator;
    }

    /// @notice Register an agent (buyer, seller, or gateway) on the Identity Registry.
    /// @param agentURI Off-chain JSON describing agent capabilities, endpoints, etc.
    function registerAgent(string calldata agentURI) external returns (uint256 agentId) {
        if (agentIds[msg.sender] != 0) revert AgentAlreadyRegistered();

        agentId = identity.register(agentURI);
        agentIds[msg.sender] = agentId;

        // Link the caller's wallet
        identity.setAgentWallet(agentId, msg.sender);

        emit AgentRegistered(msg.sender, agentId, agentURI);
    }

    /// @notice Record a receipt validation request on the Validation Registry.
    ///         Called by gateway after settlement is submitted (status = PENDING).
    /// @param requestId The settlement request ID
    /// @param receiptHash The receipt hash to validate
    function recordValidation(bytes32 requestId, bytes32 receiptHash) external {
        if (validationRecorded[requestId]) revert AlreadyRecorded();

        // Look up seller from settlement
        (
            , /* mandateId */
            , /* buyer */
            address seller,
            , /* maxPrice */
            , /* payout */
            , /* receiptHash */
            , /* finalizeAfter */
            SLASettlement.Status status
        ) = settlement.settlements(requestId);

        if (
            status != SLASettlement.Status.PENDING
                && status != SLASettlement.Status.DISPUTED
                && status != SLASettlement.Status.FINALIZED
        ) {
            revert SettlementNotPending();
        }

        uint256 sellerAgentId = agentIds[seller];
        if (sellerAgentId == 0) revert AgentNotRegistered();

        validationRecorded[requestId] = true;
        // Use address(this) as validator since the orchestrator calls validationResponse
        validation.validationRequest(address(this), sellerAgentId, receiptHash);

        emit ValidationRecorded(requestId, sellerAgentId);
    }

    /// @notice Submit validation result (called by the validator/gateway).
    /// @param receiptHash The receipt hash being validated
    /// @param pass Whether the receipt passed validation (true=100, false=0)
    /// @param tag Validation tag (e.g., "sla-compliance", "schema-pass")
    function submitValidationResult(bytes32 receiptHash, bool pass, string calldata tag)
        external
    {
        require(msg.sender == validator, "not validator");

        uint8 response = pass ? 100 : 0;
        validation.validationResponse(receiptHash, response, tag);

        emit ValidationResultSubmitted(receiptHash, response, tag);
    }

    /// @notice Record reputation feedback after settlement is finalized.
    ///         Score is derived from payout ratio: (payout / maxPrice) * 100.
    /// @param requestId The settlement request ID (must be FINALIZED)
    function recordReputation(bytes32 requestId) external {
        if (reputationRecorded[requestId]) revert AlreadyRecorded();

        (
            , /* mandateId */
            , /* buyer */
            address seller,
            uint256 maxPrice,
            uint256 payout,
            bytes32 receiptHash,
            , /* finalizeAfter */
            SLASettlement.Status status
        ) = settlement.settlements(requestId);

        if (status != SLASettlement.Status.FINALIZED) revert SettlementNotFinalized();

        uint256 sellerAgentId = agentIds[seller];
        if (sellerAgentId == 0) revert AgentNotRegistered();

        reputationRecorded[requestId] = true;

        // Score: payout percentage (0-100)
        int128 score = maxPrice > 0 ? int128(int256((payout * 100) / maxPrice)) : int128(0);

        reputation.giveFeedback(
            sellerAgentId,
            score,
            0, // no decimals
            "sla",
            "settlement",
            "", // feedbackURI (off-chain)
            receiptHash
        );

        emit ReputationRecorded(requestId, sellerAgentId, score);
    }

    /// @notice Get the ERC-8004 agent ID for an address (0 if not registered).
    function getAgentId(address agent) external view returns (uint256) {
        return agentIds[agent];
    }
}
