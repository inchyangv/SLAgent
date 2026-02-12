// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IERC8004Identity — Minimal Identity Registry interface (ERC-8004)
/// @notice Each agent gets an on-chain ID (NFT-based in the full spec).
///         We define the subset needed for SLA-Pay orchestration.
interface IERC8004Identity {
    event Registered(uint256 indexed agentId, string agentURI, address indexed owner);

    /// @notice Register an agent, returns a unique agentId.
    function register(string calldata agentURI) external returns (uint256 agentId);

    /// @notice Get the wallet address linked to an agent.
    function getAgentWallet(uint256 agentId) external view returns (address);

    /// @notice Link a wallet address to an agent (owner only).
    function setAgentWallet(uint256 agentId, address wallet) external;

    /// @notice Get the URI for an agent.
    function getAgentURI(uint256 agentId) external view returns (string memory);

    /// @notice Get the owner of an agent.
    function ownerOf(uint256 agentId) external view returns (address);
}

/// @title IERC8004Reputation — Minimal Reputation Registry interface (ERC-8004)
/// @notice Structured on-chain feedback about agent performance.
interface IERC8004Reputation {
    event NewFeedback(
        uint256 indexed agentId,
        address indexed clientAddress,
        uint64 feedbackIndex,
        int128 value,
        uint8 valueDecimals,
        string tag1,
        string tag2,
        bytes32 feedbackHash
    );

    /// @notice Post feedback about an agent.
    function giveFeedback(
        uint256 agentId,
        int128 value,
        uint8 valueDecimals,
        string calldata tag1,
        string calldata tag2,
        string calldata feedbackURI,
        bytes32 feedbackHash
    ) external;

    /// @notice Get summary feedback for an agent filtered by tags.
    function getSummary(
        uint256 agentId,
        string calldata tag1,
        string calldata tag2
    ) external view returns (uint64 count, int128 totalValue, uint8 valueDecimals);
}

/// @title IERC8004Validation — Minimal Validation Registry interface (ERC-8004)
/// @notice Third-party validators post verification results for agent work.
interface IERC8004Validation {
    event ValidationRequest(
        address indexed validatorAddress,
        uint256 indexed agentId,
        bytes32 indexed requestHash
    );

    event ValidationResponse(
        address indexed validatorAddress,
        uint256 indexed agentId,
        bytes32 indexed requestHash,
        uint8 response,
        string tag
    );

    /// @notice Request validation for agent work.
    function validationRequest(
        address validatorAddress,
        uint256 agentId,
        bytes32 requestHash
    ) external;

    /// @notice Submit validation result.
    function validationResponse(
        bytes32 requestHash,
        uint8 response,
        string calldata tag
    ) external;

    /// @notice Get validation status.
    function getValidationStatus(bytes32 requestHash)
        external
        view
        returns (address validatorAddress, uint256 agentId, uint8 response, string memory tag);
}
