// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title KnownHostsRegistry
/// @notice Lets a wallet owner publicly approve a new address ("rotation").
///         Only the old wallet can write its own entry, because entries are keyed by msg.sender.
contract KnownHostsRegistry {
    mapping(address => address) public rotatedTo;  // old address => approved new address
    mapping(address => uint256) public rotatedAt;  // old address => timestamp of approval

    event AddressRotated(address indexed oldAddress, address indexed newAddress, uint256 timestamp);
    event AddressRevoked(address indexed oldAddress, uint256 timestamp);

    function rotate(address newAddress) external {
        require(newAddress != address(0), "zero address");
        require(newAddress != msg.sender, "same address");
        require(rotatedTo[msg.sender] == address(0), "already rotated; revoke first");
        rotatedTo[msg.sender] = newAddress;
        rotatedAt[msg.sender] = block.timestamp;
        emit AddressRotated(msg.sender, newAddress, block.timestamp);
    }

    /// @notice Undo your own rotation. Used to reset the demo, and lets an owner cancel a mistake.
    function revoke() external {
        require(rotatedTo[msg.sender] != address(0), "nothing to revoke");
        delete rotatedTo[msg.sender];
        delete rotatedAt[msg.sender];
        emit AddressRevoked(msg.sender, block.timestamp);
    }
}
