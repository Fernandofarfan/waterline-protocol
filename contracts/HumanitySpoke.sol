// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./HumanityHub.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract HumanitySpoke is Ownable, Pausable {
    HumanityHub public immutable hub;
    address public relayer;

    struct MirrorOperation {
        uint256 operationId;
        bytes32 messageHash;
        HumanityHub.OperationStatus status;
        uint256 syncedAt;
    }

    mapping(uint256 => MirrorOperation) public mirrored;
    mapping(bytes32 => bool) public syncedHashes;

    event Mirrored(uint256 indexed operationId, bytes32 indexed messageHash, HumanityHub.OperationStatus status);

    constructor(address hubAddress, address initialOwner, address relayerAddress) Ownable(initialOwner) {
        hub = HumanityHub(hubAddress);
        relayer = relayerAddress;
    }

    function mirrorOperation(
        uint256 operationId,
        bytes32 messageHash,
        HumanityHub.OperationStatus status
    ) external whenNotPaused {
        require(msg.sender == relayer || msg.sender == owner(), "Unauthorized relayer");
        require(operationId != 0, "Invalid operationId");
        require(messageHash != bytes32(0), "Invalid messageHash");
        if (syncedHashes[messageHash]) {
            status = HumanityHub.OperationStatus.replayed;
        } else {
            syncedHashes[messageHash] = true;
        }

        mirrored[operationId] = MirrorOperation({
            operationId: operationId,
            messageHash: messageHash,
            status: status,
            syncedAt: block.timestamp
        });

        emit Mirrored(operationId, messageHash, status);
    }

    function setRelayer(address newRelayer) external onlyOwner {
        require(newRelayer != address(0), "Invalid relayer");
        relayer = newRelayer;
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }
}
