# HumanityChain Contracts

## Deploy (Foundry suggested)

1. Install Foundry.
2. Compile:
```bash
forge build
```
3. Deploy Hub:
```bash
forge create contracts/HumanityHub.sol:HumanityHub --rpc-url $RPC_URL --private-key $PK --constructor-args $OWNER
```
4. Deploy Spoke:
```bash
forge create contracts/HumanitySpoke.sol:HumanitySpoke --rpc-url $RPC_URL --private-key $PK --constructor-args $HUB $OWNER $RELAYER
```

## Security checklist
- Run fuzz tests before deploy.
- Verify contract source on explorer.
- Set relayer immediately after deploy.
- Keep owner in multisig.
