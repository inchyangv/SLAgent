// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/SLASettlement.sol";
import "../src/SLAToken.sol";
import "../src/erc8004/IERC8004.sol";
import "../src/erc8004/ERC8004Mocks.sol";
import "../src/erc8004/SLAOrchestrator.sol";

contract SLAOrchestratorTest is Test {
    SLAToken public token;
    SLASettlement public settlement;

    MockIdentityRegistry public identityReg;
    MockReputationRegistry public reputationReg;
    MockValidationRegistry public validationReg;
    SLAOrchestrator public orchestrator;

    uint256 internal gatewayPk = 0xA11CE;
    address internal gatewayAddr;
    address internal resolverAddr = address(0xDE5);

    address internal buyer = address(0xB0B);
    address internal seller = address(0x5E11);

    bytes32 internal mandateId = keccak256("mandate-1");
    bytes32 internal requestId = keccak256("req-001");
    bytes32 internal receiptHash = keccak256("receipt-001");

    uint256 internal maxPrice = 100_000;
    uint256 internal disputeWindowSec = 600;
    uint256 internal bondAmount = 50_000;

    function setUp() public {
        gatewayAddr = vm.addr(gatewayPk);

        // Deploy token + settlement
        token = new SLAToken();
        settlement = new SLASettlement(
            address(token), gatewayAddr, resolverAddr, disputeWindowSec, bondAmount
        );

        // Deploy ERC-8004 mock registries
        identityReg = new MockIdentityRegistry();
        reputationReg = new MockReputationRegistry();
        validationReg = new MockValidationRegistry();

        // Deploy orchestrator
        orchestrator = new SLAOrchestrator(
            address(identityReg),
            address(reputationReg),
            address(validationReg),
            address(settlement),
            gatewayAddr // gateway is the validator
        );

        // Fund buyer
        token.mint(buyer, 10_000_000);
        vm.prank(buyer);
        token.approve(address(settlement), type(uint256).max);
    }

    function _sign(
        bytes32 _mandateId,
        bytes32 _requestId,
        address _buyer,
        address _seller,
        uint256 _maxPrice,
        uint256 _payout,
        bytes32 _receiptHash
    ) internal view returns (bytes memory) {
        bytes32 digest = keccak256(
            abi.encodePacked(_mandateId, _requestId, _buyer, _seller, _maxPrice, _payout, _receiptHash)
        );
        bytes32 ethSignedHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(gatewayPk, ethSignedHash);
        return abi.encodePacked(r, s, v);
    }

    function _doSettlement(bytes32 _requestId, uint256 _payout) internal {
        vm.prank(buyer);
        settlement.deposit(_requestId, buyer, maxPrice);

        bytes memory sig = _sign(mandateId, _requestId, buyer, seller, maxPrice, _payout, receiptHash);
        vm.prank(gatewayAddr);
        settlement.settle(mandateId, _requestId, buyer, seller, maxPrice, _payout, receiptHash, sig);
    }

    function _doFinalize(bytes32 _requestId) internal {
        vm.warp(block.timestamp + disputeWindowSec + 1);
        settlement.finalize(_requestId);
    }

    // ===================== AGENT REGISTRATION =====================

    function test_registerAgent() public {
        vm.prank(seller);
        uint256 agentId = orchestrator.registerAgent("https://seller.example.com/agent.json");

        assertEq(agentId, 1);
        assertEq(orchestrator.agentIds(seller), 1);
        assertEq(identityReg.getAgentWallet(agentId), seller);
        assertEq(identityReg.ownerOf(agentId), address(orchestrator));
    }

    function test_registerAgent_buyer() public {
        vm.prank(buyer);
        uint256 agentId = orchestrator.registerAgent("https://buyer.example.com/agent.json");

        assertEq(agentId, 1);
        assertEq(orchestrator.agentIds(buyer), 1);
    }

    function test_registerAgent_doubleReverts() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");

        vm.prank(seller);
        vm.expectRevert(SLAOrchestrator.AgentAlreadyRegistered.selector);
        orchestrator.registerAgent("https://seller2.example.com/agent.json");
    }

    function test_registerAgent_emitsEvent() public {
        vm.prank(seller);
        vm.expectEmit(true, true, false, true);
        emit SLAOrchestrator.AgentRegistered(seller, 1, "https://seller.example.com/agent.json");
        orchestrator.registerAgent("https://seller.example.com/agent.json");
    }

    // ===================== VALIDATION RECORDING =====================

    function test_recordValidation() public {
        // Register seller
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");

        // Create and settle
        _doSettlement(requestId, 80_000);

        // Record validation
        vm.prank(gatewayAddr);
        orchestrator.recordValidation(requestId, receiptHash);

        assertTrue(orchestrator.validationRecorded(requestId));

        // Check validation registry — validator is the orchestrator (calls validationResponse)
        (address valAddr, uint256 agentId, uint8 response,) =
            validationReg.getValidationStatus(receiptHash);
        assertEq(valAddr, address(orchestrator));
        assertEq(agentId, 1); // seller's agent ID
        assertEq(response, 0); // not yet responded
    }

    function test_recordValidation_doubleReverts() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);

        vm.prank(gatewayAddr);
        orchestrator.recordValidation(requestId, receiptHash);

        vm.prank(gatewayAddr);
        vm.expectRevert(SLAOrchestrator.AlreadyRecorded.selector);
        orchestrator.recordValidation(requestId, receiptHash);
    }

    function test_recordValidation_agentNotRegistered() public {
        _doSettlement(requestId, 80_000);

        vm.prank(gatewayAddr);
        vm.expectRevert(SLAOrchestrator.AgentNotRegistered.selector);
        orchestrator.recordValidation(requestId, receiptHash);
    }

    function test_recordValidation_emitsEvent() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);

        vm.prank(gatewayAddr);
        vm.expectEmit(true, true, false, true);
        emit SLAOrchestrator.ValidationRecorded(requestId, 1);
        orchestrator.recordValidation(requestId, receiptHash);
    }

    // ===================== VALIDATION RESULT =====================

    function test_submitValidationResult() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);

        vm.prank(gatewayAddr);
        orchestrator.recordValidation(requestId, receiptHash);

        // Submit validation result
        vm.prank(gatewayAddr);
        orchestrator.submitValidationResult(receiptHash, true, "sla-compliance");

        // Check
        (, , uint8 response, string memory tag) = validationReg.getValidationStatus(receiptHash);
        assertEq(response, 100);
        assertEq(tag, "sla-compliance");
    }

    function test_submitValidationResult_fail() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 0);

        vm.prank(gatewayAddr);
        orchestrator.recordValidation(requestId, receiptHash);

        vm.prank(gatewayAddr);
        orchestrator.submitValidationResult(receiptHash, false, "schema-fail");

        (, , uint8 response, string memory tag) = validationReg.getValidationStatus(receiptHash);
        assertEq(response, 0);
        assertEq(tag, "schema-fail");
    }

    function test_submitValidationResult_notValidator() public {
        vm.prank(address(0x999));
        vm.expectRevert("not validator");
        orchestrator.submitValidationResult(receiptHash, true, "sla-compliance");
    }

    // ===================== REPUTATION RECORDING =====================

    function test_recordReputation_fullPayout() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 100_000);
        _doFinalize(requestId);

        orchestrator.recordReputation(requestId);

        assertTrue(orchestrator.reputationRecorded(requestId));

        // Check reputation: 100_000 / 100_000 * 100 = 100
        (uint64 count, int128 totalValue, ) = reputationReg.getSummary(1, "sla", "settlement");
        assertEq(count, 1);
        assertEq(totalValue, 100);
    }

    function test_recordReputation_partialPayout() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 60_000);
        _doFinalize(requestId);

        orchestrator.recordReputation(requestId);

        (uint64 count, int128 totalValue, ) = reputationReg.getSummary(1, "sla", "settlement");
        assertEq(count, 1);
        assertEq(totalValue, 60); // 60_000 / 100_000 * 100 = 60
    }

    function test_recordReputation_zeroPayout() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 0);
        _doFinalize(requestId);

        orchestrator.recordReputation(requestId);

        (uint64 count, int128 totalValue, ) = reputationReg.getSummary(1, "sla", "settlement");
        assertEq(count, 1);
        assertEq(totalValue, 0);
    }

    function test_recordReputation_notFinalized() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);

        vm.expectRevert(SLAOrchestrator.SettlementNotFinalized.selector);
        orchestrator.recordReputation(requestId);
    }

    function test_recordReputation_doubleReverts() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);
        _doFinalize(requestId);

        orchestrator.recordReputation(requestId);

        vm.expectRevert(SLAOrchestrator.AlreadyRecorded.selector);
        orchestrator.recordReputation(requestId);
    }

    function test_recordReputation_emitsEvent() public {
        vm.prank(seller);
        orchestrator.registerAgent("https://seller.example.com/agent.json");
        _doSettlement(requestId, 80_000);
        _doFinalize(requestId);

        vm.expectEmit(true, true, false, true);
        emit SLAOrchestrator.ReputationRecorded(requestId, 1, 80);
        orchestrator.recordReputation(requestId);
    }

    // ===================== FULL LIFECYCLE =====================

    function test_fullLifecycle() public {
        // 1. Register agents
        vm.prank(buyer);
        uint256 buyerAgentId = orchestrator.registerAgent("https://buyer.example.com/agent.json");
        vm.prank(seller);
        uint256 sellerAgentId = orchestrator.registerAgent("https://seller.example.com/agent.json");
        assertEq(buyerAgentId, 1);
        assertEq(sellerAgentId, 2);

        // 2. Settlement
        _doSettlement(requestId, 80_000);

        // 3. Record validation
        vm.prank(gatewayAddr);
        orchestrator.recordValidation(requestId, receiptHash);

        // 4. Submit validation result (pass)
        vm.prank(gatewayAddr);
        orchestrator.submitValidationResult(receiptHash, true, "sla-compliance");

        // 5. Finalize
        _doFinalize(requestId);

        // 6. Record reputation
        orchestrator.recordReputation(requestId);

        // Verify final state
        (, , uint8 valResponse, string memory tag) =
            validationReg.getValidationStatus(receiptHash);
        assertEq(valResponse, 100);
        assertEq(tag, "sla-compliance");

        (uint64 count, int128 totalValue, ) =
            reputationReg.getSummary(sellerAgentId, "sla", "settlement");
        assertEq(count, 1);
        assertEq(totalValue, 80); // 80_000 / 100_000 * 100
    }
}
