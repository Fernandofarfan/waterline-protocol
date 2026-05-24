// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../HumanityHub.sol";
import "../HumanitySpoke.sol";

contract HumanityChainTest is Test {
    HumanityHub internal hub;
    HumanitySpoke internal spoke;

    address internal owner = address(0xABCD);
    address internal relayer = address(0xBEEF);
    address internal outsider = address(0xDEAD);

    function setUp() public {
        vm.prank(owner);
        hub = new HumanityHub(owner);
        vm.prank(owner);
        spoke = new HumanitySpoke(address(hub), owner, relayer);
    }

    function testHubUpsertAndReplayFlow() public {
        bytes32 firstHash = keccak256("message-1");
        vm.prank(owner);
        hub.upsertOperation(1, "medical", firstHash, HumanityHub.OperationStatus.queued);

        (
            uint256 operationId,
            string memory profile,
            bytes32 messageHash,
            HumanityHub.OperationStatus status,
            uint256 updatedAt
        ) = hub.operations(1);

        assertEq(operationId, 1);
        assertEq(profile, "medical");
        assertEq(messageHash, firstHash);
        assertEq(uint256(status), uint256(HumanityHub.OperationStatus.queued));
        assertGt(updatedAt, 0);

        vm.prank(owner);
        hub.upsertOperation(2, "medical", firstHash, HumanityHub.OperationStatus.sent);
        (, , , HumanityHub.OperationStatus replayStatus, ) = hub.operations(2);
        assertEq(uint256(replayStatus), uint256(HumanityHub.OperationStatus.replayed));
    }

    function testHubRejectsInvalidInputs() public {
        vm.prank(owner);
        vm.expectRevert("Invalid operationId");
        hub.upsertOperation(0, "medical", keccak256("x"), HumanityHub.OperationStatus.queued);

        vm.prank(owner);
        vm.expectRevert("Invalid messageHash");
        hub.upsertOperation(1, "medical", bytes32(0), HumanityHub.OperationStatus.queued);
    }

    function testSpokePauseAndRelayerValidation() public {
        vm.prank(owner);
        spoke.pause();

        vm.prank(relayer);
        vm.expectRevert();
        spoke.mirrorOperation(9, keccak256("paused"), HumanityHub.OperationStatus.sent);

        vm.prank(owner);
        spoke.unpause();

        vm.prank(owner);
        vm.expectRevert("Invalid relayer");
        spoke.setRelayer(address(0));
    }

    function testRelayerRotationBlocksOldRelayer() public {
        bytes32 messageHash = keccak256("rotate-relayer");

        vm.prank(owner);
        spoke.setRelayer(address(0xCAFE));

        vm.prank(relayer);
        vm.expectRevert("Unauthorized relayer");
        spoke.mirrorOperation(7, messageHash, HumanityHub.OperationStatus.sent);

        vm.prank(address(0xCAFE));
        spoke.mirrorOperation(7, messageHash, HumanityHub.OperationStatus.sent);
    }

    function testSpokeRelayerAuthorization() public {
        bytes32 messageHash = keccak256("spoke-msg");

        vm.prank(outsider);
        vm.expectRevert("Unauthorized relayer");
        spoke.mirrorOperation(1, messageHash, HumanityHub.OperationStatus.sent);

        vm.prank(relayer);
        spoke.mirrorOperation(1, messageHash, HumanityHub.OperationStatus.sent);

        (uint256 opId, bytes32 storedHash, HumanityHub.OperationStatus status, uint256 syncedAt) = spoke.mirrored(1);
        assertEq(opId, 1);
        assertEq(storedHash, messageHash);
        assertEq(uint256(status), uint256(HumanityHub.OperationStatus.sent));
        assertGt(syncedAt, 0);
    }
}
