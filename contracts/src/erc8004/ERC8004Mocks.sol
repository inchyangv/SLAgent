// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./IERC8004.sol";

/// @title MockIdentityRegistry — Test/demo implementation of IERC8004Identity
contract MockIdentityRegistry is IERC8004Identity {
    uint256 private _nextId = 1;

    struct Agent {
        address owner;
        address wallet;
        string uri;
    }

    mapping(uint256 => Agent) private _agents;
    mapping(address => uint256) public agentIdByOwner;

    function register(string calldata agentURI) external returns (uint256 agentId) {
        agentId = _nextId++;
        _agents[agentId] = Agent({owner: msg.sender, wallet: msg.sender, uri: agentURI});
        agentIdByOwner[msg.sender] = agentId;
        emit Registered(agentId, agentURI, msg.sender);
    }

    function getAgentWallet(uint256 agentId) external view returns (address) {
        return _agents[agentId].wallet;
    }

    function setAgentWallet(uint256 agentId, address wallet) external {
        require(_agents[agentId].owner == msg.sender, "not owner");
        _agents[agentId].wallet = wallet;
    }

    function getAgentURI(uint256 agentId) external view returns (string memory) {
        return _agents[agentId].uri;
    }

    function ownerOf(uint256 agentId) external view returns (address) {
        return _agents[agentId].owner;
    }
}

/// @title MockReputationRegistry — Test/demo implementation of IERC8004Reputation
contract MockReputationRegistry is IERC8004Reputation {
    struct FeedbackEntry {
        address client;
        int128 value;
        uint8 valueDecimals;
        string tag1;
        string tag2;
        bytes32 feedbackHash;
    }

    // agentId => feedbacks
    mapping(uint256 => FeedbackEntry[]) private _feedbacks;

    function giveFeedback(
        uint256 agentId,
        int128 value,
        uint8 valueDecimals,
        string calldata tag1,
        string calldata tag2,
        string calldata, /* feedbackURI */
        bytes32 feedbackHash
    ) external {
        uint64 idx = uint64(_feedbacks[agentId].length);
        _feedbacks[agentId].push(
            FeedbackEntry({
                client: msg.sender,
                value: value,
                valueDecimals: valueDecimals,
                tag1: tag1,
                tag2: tag2,
                feedbackHash: feedbackHash
            })
        );
        emit NewFeedback(agentId, msg.sender, idx, value, valueDecimals, tag1, tag2, feedbackHash);
    }

    function getSummary(uint256 agentId, string calldata tag1, string calldata tag2)
        external
        view
        returns (uint64 count, int128 totalValue, uint8 valueDecimals)
    {
        FeedbackEntry[] storage entries = _feedbacks[agentId];
        bytes32 t1Hash = keccak256(bytes(tag1));
        bytes32 t2Hash = keccak256(bytes(tag2));

        for (uint256 i = 0; i < entries.length; i++) {
            bool match1 = bytes(tag1).length == 0
                || keccak256(bytes(entries[i].tag1)) == t1Hash;
            bool match2 = bytes(tag2).length == 0
                || keccak256(bytes(entries[i].tag2)) == t2Hash;
            if (match1 && match2) {
                totalValue += entries[i].value;
                valueDecimals = entries[i].valueDecimals;
                count++;
            }
        }
    }

    function getFeedbackCount(uint256 agentId) external view returns (uint256) {
        return _feedbacks[agentId].length;
    }
}

/// @title MockValidationRegistry — Test/demo implementation of IERC8004Validation
contract MockValidationRegistry is IERC8004Validation {
    struct Validation {
        address validatorAddress;
        uint256 agentId;
        uint8 response; // 0=fail, 100=pass
        string tag;
        bool exists;
    }

    mapping(bytes32 => Validation) private _validations;

    function validationRequest(
        address validatorAddress,
        uint256 agentId,
        bytes32 requestHash
    ) external {
        _validations[requestHash] = Validation({
            validatorAddress: validatorAddress,
            agentId: agentId,
            response: 0,
            tag: "",
            exists: true
        });
        emit ValidationRequest(validatorAddress, agentId, requestHash);
    }

    function validationResponse(
        bytes32 requestHash,
        uint8 response,
        string calldata tag
    ) external {
        require(_validations[requestHash].exists, "no request");
        require(msg.sender == _validations[requestHash].validatorAddress, "not validator");
        _validations[requestHash].response = response;
        _validations[requestHash].tag = tag;
        emit ValidationResponse(
            msg.sender,
            _validations[requestHash].agentId,
            requestHash,
            response,
            tag
        );
    }

    function getValidationStatus(bytes32 requestHash)
        external
        view
        returns (address validatorAddress, uint256 agentId, uint8 response, string memory tag)
    {
        Validation storage v = _validations[requestHash];
        return (v.validatorAddress, v.agentId, v.response, v.tag);
    }
}
