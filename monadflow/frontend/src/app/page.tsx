'use client';

import { useEffect, useMemo, useState } from 'react';
import { io } from 'socket.io-client';

type Market = {
  ts: number;
  prices: Record<string, number>;
  heatmap: Array<{ exchange: string; liquidity: number; side: string }>;
  exchanges: Array<{ name: string; spread: number; volume24h: number; funding: number }>;
  chainlink?: { status: string; network: string; feeds: string[] };
  tradingView?: { status: string; symbols: string[] };
};

type ChainSupport = { supported: string[]; omnichainBridge: string };
type Identity = {
  wallet: string;
  network: string;
  zkVerified: boolean;
  zkProofType?: string | null;
  starknetAccount?: string | null;
  traceHash?: string;
  sessionId?: string;
  accountAbstraction?: { enabled: boolean; walletStandard: string };
};

const ws = io(process.env.NEXT_PUBLIC_BACKEND_WS_URL || 'http://localhost:4100');

export default function Home() {
  const [market, setMarket] = useState<Market | null>(null);
  const [chains, setChains] = useState<ChainSupport | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [attestation, setAttestation] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    ws.on('market:update', (data) => setMarket(data));
    ws.on('chains:update', (data) => setChains(data));
    ws.on('identity:update', (data) => setIdentity(data));
    ws.on('identity:attested', (data) => setAttestation(data));

    return () => {
      ws.off('market:update');
      ws.off('chains:update');
      ws.off('identity:update');
      ws.off('identity:attested');
    };
  }, []);

  const totalLiquidity = useMemo(
    () => (market?.heatmap || []).reduce((acc, row) => acc + row.liquidity, 0),
    [market]
  );

  return (
    <main style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1>MONADFLOW</h1>
      <p>
        MVP mejorado para revisión técnica: account abstraction ZK/StarkNet, trazabilidad segura
        por huellas hash y backend compatible con eventos de smart contracts.
      </p>

      <section>
        <h2>Wallet login targets</h2>
        <ul>
          <li>MetaMask (EVM / ERC-4337-ready)</li>
          <li>Hedera wallet</li>
          <li>StarkNet account wallet (AA nativo)</li>
        </ul>
      </section>

      <section>
        <h2>Feeds en tiempo real</h2>
        <pre>{JSON.stringify({ prices: market?.prices, ts: market?.ts }, null, 2)}</pre>
      </section>

      <section>
        <h2>Mapa de calor de liquidez</h2>
        <p>Liquidez agregada: {totalLiquidity}</p>
        <pre>{JSON.stringify(market?.heatmap || [], null, 2)}</pre>
      </section>

      <section>
        <h2>Comparador de exchanges</h2>
        <pre>{JSON.stringify(market?.exchanges || [], null, 2)}</pre>
      </section>

      <section>
        <h2>Conectores de datos</h2>
        <pre>{JSON.stringify({ chainlink: market?.chainlink, tradingView: market?.tradingView }, null, 2)}</pre>
      </section>

      <section>
        <h2>Soporte omnichain</h2>
        <pre>{JSON.stringify(chains, null, 2)}</pre>
      </section>

      <section>
        <h2>Identidad descentralizada y trazabilidad (demo)</h2>
        <pre>{JSON.stringify(identity, null, 2)}</pre>
        <pre>{JSON.stringify(attestation, null, 2)}</pre>
      </section>
    </main>
  );
}
