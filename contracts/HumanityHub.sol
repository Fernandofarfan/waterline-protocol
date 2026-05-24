// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract HumanityHub is Ownable, Pausable {
    uint256 public constant MAX_PROFILE_LENGTH = 32;
    enum OperationStatus {
        queued,
        sent,
        acknowledged,
        finalized,
        failed,
        replayed
    }

    struct Operation {
        uint256 operationId;
        string criticalityProfile;
        bytes32 messageHash;
        OperationStatus status;
        uint256 updatedAt;
    }

    mapping(uint256 => Operation) public operations;
    mapping(bytes32 => bool) public consumedMessages;

    event OperationUpserted(uint256 indexed operationId, bytes32 indexed messageHash, OperationStatus status, string criticalityProfile);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function upsertOperation(
        uint256 operationId,
        string calldata criticalityProfile,
        bytes32 messageHash,
        OperationStatus status
    ) external onlyOwner whenNotPaused {
        require(operationId != 0, "Invalid operationId");
        require(messageHash != bytes32(0), "Invalid messageHash");
        require(bytes(criticalityProfile).length > 0 && bytes(criticalityProfile).length <= MAX_PROFILE_LENGTH, "Invalid criticalityProfile");
        if (consumedMessages[messageHash]) {
            status = OperationStatus.replayed;
        } else {
            consumedMessages[messageHash] = true;
        }

        operations[operationId] = Operation({
            operationId: operationId,
            criticalityProfile: criticalityProfile,
            messageHash: messageHash,
            status: status,
            updatedAt: block.timestamp
        });

        emit OperationUpserted(operationId, messageHash, status, criticalityProfile);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }
}
