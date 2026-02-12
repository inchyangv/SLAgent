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
    address internal resolverAddr = address(0xDE5);

    address internal buyer = address(0xB0B);
    address internal seller = address(0x5E11);
    address internal disputer = address(0xD15);

    bytes32 internal mandateId = keccak256("mandate-1");
    bytes32 internal requestId = keccak256("req-001");
    bytes32 internal receiptHash = keccak256("receipt-001");

    uint256 internal maxPrice = 100_000;
    uint256 internal payout_ = 100_000;
    uint256 internal disputeWindowSec = 600;
    uint256 internal bondAmount = 50_000;

    function setUp() public {
        gatewayAddr = vm.addr(gatewayPk);
        token = new SLAToken();
        settlement = new SLASettlement(
            address(token), gatewayAddr, resolverAddr, disputeWindowSec, bondAmount
        );

        // Fund buyer and disputer
        token.mint(buyer, 10_000_000);
        token.mint(disputer, 10_000_000);

        vm.prank(buyer);
        token.approve(address(settlement), type(uint256).max);
        vm.prank(disputer);
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

    function _doDeposit(bytes32 _requestId, uint256 _amount) internal {
        vm.prank(buyer);
        settlement.deposit(_requestId, buyer, _amount);
    }

    function _doSettle(bytes32 _requestId, uint256 _payout) internal {
        _doDeposit(_requestId, maxPrice);
        bytes memory sig = _sign(mandateId, _requestId, buyer, seller, maxPrice, _payout, receiptHash);
        vm.prank(gatewayAddr);
        settlement.settle(mandateId, _requestId, buyer, seller, maxPrice, _payout, receiptHash, sig);
    }

    // ===================== DEPOSIT TESTS =====================

    function test_deposit_success() public {
        vm.prank(buyer);
        settlement.deposit(requestId, buyer, maxPrice);

        assertEq(token.balanceOf(address(settlement)), maxPrice);
        assertEq(token.balanceOf(buyer), 10_000_000 - maxPrice);

        (,,,,,,, SLASettlement.Status status) = settlement.settlements(requestId);
        assertEq(uint256(status), uint256(SLASettlement.Status.DEPOSITED));
    }

    function test_deposit_emitsEvent() public {
        vm.prank(buyer);
        vm.expectEmit(true, true, false, true);
        emit SLASettlement.Deposited(requestId, buyer, buyer, maxPrice);
        settlement.deposit(requestId, buyer, maxPrice);
    }

    function test_deposit_zeroAddressReverts() public {
        vm.prank(buyer);
        vm.expectRevert(SLASettlement.ZeroAddress.selector);
        settlement.deposit(requestId, address(0), maxPrice);
    }

    function test_deposit_zeroAmountReverts() public {
        vm.prank(buyer);
        vm.expectRevert(SLASettlement.ZeroAmount.selector);
        settlement.deposit(requestId, buyer, 0);
    }

    function test_deposit_doubleReverts() public {
        _doDeposit(requestId, maxPrice);
        vm.prank(buyer);
        vm.expectRevert(SLASettlement.AlreadyDeposited.selector);
        settlement.deposit(requestId, buyer, maxPrice);
    }

    // ===================== SETTLEMENT TESTS =====================

    function test_settle_fullPayout() public {
        _doSettle(requestId, maxPrice);

        // Funds escrowed in contract, not yet distributed
        assertEq(token.balanceOf(address(settlement)), maxPrice);
        assertEq(token.balanceOf(seller), 0);

        (,,,,,,, SLASettlement.Status status) = settlement.settlements(requestId);
        assertEq(uint256(status), uint256(SLASettlement.Status.PENDING));
    }

    function test_settle_withoutDepositReverts() public {
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, maxPrice, receiptHash);
        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.NotDeposited.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, maxPrice, receiptHash, sig);
    }

    function test_settle_replayReverts() public {
        _doSettle(requestId, maxPrice);

        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, maxPrice, receiptHash);
        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.AlreadySettled.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, maxPrice, receiptHash, sig);
    }

    function test_settle_payoutExceedsMax() public {
        _doDeposit(requestId, maxPrice);
        uint256 badPayout = maxPrice + 1;
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, badPayout, receiptHash);

        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.PayoutExceedsMax.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, badPayout, receiptHash, sig);
    }

    function test_settle_zeroAddress() public {
        _doDeposit(requestId, maxPrice);
        bytes memory sig = _sign(mandateId, requestId, buyer, address(0), maxPrice, payout_, receiptHash);
        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.ZeroAddress.selector);
        settlement.settle(mandateId, requestId, buyer, address(0), maxPrice, payout_, receiptHash, sig);
    }

    function test_settle_buyerMismatch() public {
        _doDeposit(requestId, maxPrice);
        address wrongBuyer = address(0xBAD);
        bytes memory sig = _sign(mandateId, requestId, wrongBuyer, seller, maxPrice, payout_, receiptHash);
        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.BuyerMismatch.selector);
        settlement.settle(mandateId, requestId, wrongBuyer, seller, maxPrice, payout_, receiptHash, sig);
    }

    function test_settle_invalidSignature() public {
        _doDeposit(requestId, maxPrice);
        uint256 wrongPk = 0xDEAD;
        bytes32 digest = keccak256(
            abi.encodePacked(mandateId, requestId, buyer, seller, maxPrice, payout_, receiptHash)
        );
        bytes32 ethSignedHash = MessageHashUtils.toEthSignedMessageHash(digest);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(wrongPk, ethSignedHash);
        bytes memory badSig = abi.encodePacked(r, s, v);

        vm.prank(gatewayAddr);
        vm.expectRevert(SLASettlement.InvalidSignature.selector);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout_, receiptHash, badSig);
    }

    function test_settle_emitsEvent() public {
        _doDeposit(requestId, maxPrice);
        bytes memory sig = _sign(mandateId, requestId, buyer, seller, maxPrice, payout_, receiptHash);

        vm.prank(gatewayAddr);
        vm.expectEmit(true, true, false, true);
        emit SLASettlement.Settled(mandateId, requestId, buyer, seller, payout_, 0, receiptHash);
        settlement.settle(mandateId, requestId, buyer, seller, maxPrice, payout_, receiptHash, sig);
    }

    // ===================== FINALIZE TESTS =====================

    function test_finalize_afterWindow() public {
        _doSettle(requestId, 80_000);

        // Warp past dispute window
        vm.warp(block.timestamp + disputeWindowSec + 1);

        settlement.finalize(requestId);

        assertEq(token.balanceOf(seller), 80_000);
        assertEq(token.balanceOf(buyer), 10_000_000 - maxPrice + 20_000); // original - deposit + refund
        assertEq(token.balanceOf(address(settlement)), 0);

        (,,,,,,, SLASettlement.Status status) = settlement.settlements(requestId);
        assertEq(uint256(status), uint256(SLASettlement.Status.FINALIZED));
    }

    function test_finalize_zeroPayout_fullRefund() public {
        _doSettle(requestId, 0);
        vm.warp(block.timestamp + disputeWindowSec + 1);
        settlement.finalize(requestId);

        assertEq(token.balanceOf(seller), 0);
        assertEq(token.balanceOf(buyer), 10_000_000); // full deposit returned
    }

    function test_finalize_beforeWindowReverts() public {
        _doSettle(requestId, maxPrice);

        vm.expectRevert(SLASettlement.DisputeWindowActive.selector);
        settlement.finalize(requestId);
    }

    function test_finalize_emitsEvent() public {
        _doSettle(requestId, 60_000);
        vm.warp(block.timestamp + disputeWindowSec + 1);

        vm.expectEmit(true, false, false, true);
        emit SLASettlement.Finalized(requestId, 60_000, 40_000);
        settlement.finalize(requestId);
    }

    // ===================== DISPUTE TESTS =====================

    function test_openDispute() public {
        _doSettle(requestId, maxPrice);

        vm.prank(disputer);
        settlement.openDispute(requestId);

        (,,,,,,, SLASettlement.Status status) = settlement.settlements(requestId);
        assertEq(uint256(status), uint256(SLASettlement.Status.DISPUTED));

        // Bond held in contract
        assertEq(token.balanceOf(address(settlement)), maxPrice + bondAmount);
    }

    function test_openDispute_afterWindowReverts() public {
        _doSettle(requestId, maxPrice);
        vm.warp(block.timestamp + disputeWindowSec);

        vm.prank(disputer);
        vm.expectRevert(SLASettlement.DisputeWindowExpired.selector);
        settlement.openDispute(requestId);
    }

    function test_openDispute_notPendingReverts() public {
        vm.prank(disputer);
        vm.expectRevert(SLASettlement.NotPending.selector);
        settlement.openDispute(requestId);
    }

    // ===================== RESOLVE DISPUTE TESTS =====================

    function test_resolveDispute_disputerWins() public {
        _doSettle(requestId, 100_000); // original: full payout to seller
        vm.prank(disputer);
        settlement.openDispute(requestId);

        // Resolver reduces payout to 60_000 (disputer was right)
        vm.prank(resolverAddr);
        settlement.resolveDispute(requestId, 60_000);

        assertEq(token.balanceOf(seller), 60_000);
        assertEq(token.balanceOf(buyer), 10_000_000 - maxPrice + 40_000); // refund
        assertEq(token.balanceOf(disputer), 10_000_000 - bondAmount + bondAmount); // bond returned
        assertEq(token.balanceOf(resolverAddr), 0); // bond NOT slashed

        (,,,,,,, SLASettlement.Status status) = settlement.settlements(requestId);
        assertEq(uint256(status), uint256(SLASettlement.Status.FINALIZED));
    }

    function test_resolveDispute_disputerLoses() public {
        _doSettle(requestId, 80_000);
        vm.prank(disputer);
        settlement.openDispute(requestId);

        // Resolver confirms original payout (disputer was wrong)
        vm.prank(resolverAddr);
        settlement.resolveDispute(requestId, 80_000);

        assertEq(token.balanceOf(seller), 80_000);
        assertEq(token.balanceOf(buyer), 10_000_000 - maxPrice + 20_000);
        assertEq(token.balanceOf(disputer), 10_000_000 - bondAmount); // bond slashed
        assertEq(token.balanceOf(resolverAddr), bondAmount); // resolver gets bond
    }

    function test_resolveDispute_onlyResolver() public {
        _doSettle(requestId, maxPrice);
        vm.prank(disputer);
        settlement.openDispute(requestId);

        vm.prank(address(0x999));
        vm.expectRevert(SLASettlement.OnlyResolver.selector);
        settlement.resolveDispute(requestId, 0);
    }

    function test_resolveDispute_finalPayoutExceedsMax() public {
        _doSettle(requestId, maxPrice);
        vm.prank(disputer);
        settlement.openDispute(requestId);

        vm.prank(resolverAddr);
        vm.expectRevert(SLASettlement.FinalPayoutExceedsMax.selector);
        settlement.resolveDispute(requestId, maxPrice + 1);
    }

    function test_resolveDispute_notDisputedReverts() public {
        _doSettle(requestId, maxPrice);

        vm.prank(resolverAddr);
        vm.expectRevert(SLASettlement.NotDisputed.selector);
        settlement.resolveDispute(requestId, 0);
    }
}
