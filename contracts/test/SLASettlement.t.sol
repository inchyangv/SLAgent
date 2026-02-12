// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/SLASettlement.sol";
import "../src/SLAToken.sol";

contract SLASettlementTest is Test {
    SLASettlement public settlement;
    SLAToken public token;

    uint256 internal gatewayPk = 0xA11CE;
    address internal gatewayAddr;

    address internal buyer = address(0xB0B);
    address internal seller = address(0x5E11);
    address internal caller = address(0xCA11);

    bytes32 internal mandateId = keccak256("mandate-1");
    bytes32 internal requestId = keccak256("req-001");
    bytes32 internal receiptHash = keccak256("receipt-001");

    uint256 internal maxPrice = 100_000; // $0.10 in 6-decimal token
    uint256 internal payout = 100_000;   // full payout

    function setUp() public {
        gatewayAddr = vm.addr(gatewayPk);
        token = new SLAToken();
        settlement = new SLASettlement(address(token), gatewayAddr);

        // Mint tokens to caller and approve settlement
        token.mint(caller, 1_000_000);
        vm.prank(caller);
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
        bytes32 ethSignedHash = MessageHashUtils.toEthSignedMessageHash(digest);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(gatewayPk, ethSignedHash);
        return abi.encodePacked(r, s, v);
    }

    // --- Happy path: full payout ---
    function test_settle_fullPayout() public {
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash);

        vm.prank(caller);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, sig);

        assertEq(token.balanceOf(seller), payout);
        assertEq(token.balanceOf(buyer), 0); // no refund
        assertTrue(settlement.settled(requestId));
    }

    // --- Partial payout with refund ---
    function test_settle_partialPayout() public {
        uint256 partialPayout = 60_000; // base_pay only
        uint256 expectedRefund = maxPrice - partialPayout; // 40_000

        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, partialPayout, receiptHash);

        vm.prank(caller);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, partialPayout, receiptHash, sig);

        assertEq(token.balanceOf(seller), partialPayout);
        assertEq(token.balanceOf(buyer), expectedRefund);
        assertTrue(settlement.settled(requestId));
    }

    // --- Zero payout: full refund ---
    function test_settle_zeroPayout() public {
        uint256 zeroPayout = 0;

        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, zeroPayout, receiptHash);

        vm.prank(caller);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, zeroPayout, receiptHash, sig);

        assertEq(token.balanceOf(seller), 0);
        assertEq(token.balanceOf(buyer), maxPrice);
        assertTrue(settlement.settled(requestId));
    }

    // --- Replay protection ---
    function test_settle_replayReverts() public {
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash);

        vm.prank(caller);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, sig);

        vm.prank(caller);
        vm.expectRevert(SLASettlement.AlreadySettled.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, sig);
    }

    // --- Payout > maxPrice reverts ---
    function test_settle_payoutExceedsMax() public {
        uint256 badPayout = maxPrice + 1;
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, badPayout, receiptHash);

        vm.prank(caller);
        vm.expectRevert(SLASettlement.PayoutExceedsMax.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, badPayout, receiptHash, sig);
    }

    // --- Zero address reverts ---
    function test_settle_zeroAddressBuyer() public {
        bytes memory sig = _sign(mandateId, requestId, address(0), seller, maxPrice, payout, receiptHash);

        vm.prank(caller);
        vm.expectRevert(SLASettlement.ZeroAddress.selector);
        settlement.settle(mandateId, requestId, address(0), seller, maxPrice, payout, receiptHash, sig);
    }

    function test_settle_zeroAddressSeller() public {
        bytes memory sig = _sign(mandateId, requestId, buyer, address(0), maxPrice, payout, receiptHash);

        vm.prank(caller);
        vm.expectRevert(SLASettlement.ZeroAddress.selector);
        settlement.settle(mandateId, requestId, buyer, address(0), maxPrice, payout, receiptHash, sig);
    }

    // --- Invalid signature ---
    function test_settle_invalidSignature() public {
        // Sign with wrong key
        uint256 wrongPk = 0xDEAD;
        bytes32 digest = keccak256(
            abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash)
        );
        bytes32 ethSignedHash = MessageHashUtils.toEthSignedMessageHash(digest);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(wrongPk, ethSignedHash);
        bytes memory badSig = abi.encodePacked(r, s, v);

        vm.prank(caller);
        vm.expectRevert(SLASettlement.InvalidSignature.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, badSig);
    }

    // --- Event emission ---
    function test_settle_emitsEvent() public {
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash);

        vm.prank(caller);
        vm.expectEmit(true, true, false, true);
        emit SLASettlement.Settled(mandateId, requestId, buyer, seller, payout, 0, receiptHash);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout, receiptHash, sig);
    }
}
