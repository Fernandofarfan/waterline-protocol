// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract WaterlineProtocol {
    string public name = "Waterline RWA Logistics";
    
    struct Package {
        uint256 id;
        string location;
        bool isDelivered;
    }

    mapping(uint256 => Package) public packages;

    event LocationUpdated(uint256 indexed packageId, string newLocation);

    function updateLocation(uint256 _id, string memory _newLocation) public {
        packages[_id].location = _newLocation;
        emit LocationUpdated(_id, _newLocation);
    }
}
