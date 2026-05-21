import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { createHash, randomUUID } from 'crypto';

const app = express();

const allowedOrigins = (process.env.CORS_ORIGINS || '*')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);

app.use(cors({ origin: allowedOrigins.includes('*') ? '*' : allowedOrigins }));
app.use(express.json());

const server = createServer(app);
const io = new Server(server, {
  cors: {
    origin: allowedOrigins.includes('*') ? '*' : allowedOrigins,
    methods: ['GET', 'POST']
  }
});

const state = {
  market: {
    ts: Date.now(),
    prices: { BTC: 0, ETH: 0 },
    heatmap: [],
    exchanges: [],
    chainlink: {
      status: 'mocked',
      network: process.env.CHAINLINK_NETWORK || 'ethereum',
      feeds: ['BTC/USD', 'ETH/USD']
    },
    tradingView: {
      status: process.env.TRADINGVIEW_ENABLED === 'true' ? 'connected' : 'mocked',
      symbols: ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT']
    }
  },
  identities: new Map(),
  identityAttestations: new Map(),
  alerts: [],
  chain: {
    supported: ['ethereum', 'starknet', 'hedera'],
    omnichainBridge: process.env.OMNICHAIN_BRIDGE || 'LayerZero-ready'
  }
};

function buildTraceHash(payload) {
  return createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

app.get('/health', (_, res) => {
  res.json({
    ok: true,
    ts: Date.now(),
    services: {
      chainlink: state.market.chainlink.status,
      tradingView: state.market.tradingView.status,
      youtubeLiveChat: process.env.YOUTUBE_API_KEY ? 'configured' : 'missing_key'
    }
  });
});

app.get('/api/market', (_, res) => res.json(state.market));
app.get('/api/chains', (_, res) => res.json(state.chain));
app.get('/api/alerts', (_, res) => res.json(state.alerts));

app.post('/api/identity/register', (req, res) => {
  const { wallet, network, zkProof, starknetAccount, accountAbstraction } = req.body || {};
  if (!wallet || !network) {
    return res.status(400).json({ ok: false, error: 'wallet y network son requeridos' });
  }

  if (!state.chain.supported.includes(network)) {
    return res.status(400).json({ ok: false, error: `network no soportada: ${network}` });
  }

  const sessionId = randomUUID();
  const identity = {
    wallet,
    network,
    zkVerified: Boolean(zkProof),
    zkProofType: zkProof?.type || null,
    starknetAccount: starknetAccount || null,
    accountAbstraction: accountAbstraction || {
      enabled: true,
      walletStandard: network === 'starknet' ? 'Cairo AA' : 'ERC-4337-ready'
    },
    sessionId,
    lastSeen: Date.now()
  };

  const tracePayload = {
    wallet: wallet.toLowerCase(),
    network,
    sessionId,
    zkVerified: identity.zkVerified,
    starknetAccount: identity.starknetAccount,
    ts: identity.lastSeen
  };

  const traceHash = buildTraceHash(tracePayload);
  identity.traceHash = traceHash;

  state.identities.set(wallet.toLowerCase(), identity);
  state.identityAttestations.set(traceHash, tracePayload);

  io.emit('identity:update', identity);
  return res.json({ ok: true, identity });
});

app.post('/api/identity/attest', (req, res) => {
  const { wallet, traceHash, signedMessage } = req.body || {};
  if (!wallet || !traceHash || !signedMessage) {
    return res.status(400).json({ ok: false, error: 'wallet, traceHash y signedMessage son requeridos' });
  }

  const identity = state.identities.get(wallet.toLowerCase());
  if (!identity) {
    return res.status(404).json({ ok: false, error: 'identidad no encontrada' });
  }

  if (identity.traceHash !== traceHash || !state.identityAttestations.get(traceHash)) {
    return res.status(400).json({ ok: false, error: 'traceHash inválido' });
  }

  const attestation = {
    wallet,
    traceHash,
    signatureDigest: buildTraceHash({ signedMessage, traceHash }).slice(0, 32),
    confirmedAt: Date.now()
  };

  identity.attestation = attestation;
  io.emit('identity:attested', attestation);
  return res.json({ ok: true, attestation });
});

app.get('/api/identity/:wallet', (req, res) => {
  const wallet = req.params.wallet.toLowerCase();
  const identity = state.identities.get(wallet);
  if (!identity) {
    return res.status(404).json({ ok: false, error: 'identidad no encontrada' });
  }

  return res.json({ ok: true, identity });
});

app.post('/api/contracts/event', (req, res) => {
  const { chain, contract, event, payload } = req.body || {};
  if (!chain || !contract || !event) {
    return res.status(400).json({ ok: false, error: 'chain, contract y event son requeridos' });
  }

  if (!state.chain.supported.includes(chain)) {
    return res.status(400).json({ ok: false, error: `chain no soportada: ${chain}` });
  }

  const smartEvent = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    ts: Date.now(),
    chain,
    contract,
    event,
    payload: payload || {},
    eventHash: buildTraceHash({ chain, contract, event, payload: payload || {} })
  };

  io.emit('contract:event', smartEvent);
  return res.json({ ok: true, smartEvent });
});

io.on('connection', (socket) => {
  socket.emit('market:update', state.market);
  socket.emit('chains:update', state.chain);
});

function mockRealtimeTick() {
  const btc = 60000 + Math.round(Math.random() * 3000);
  const eth = 3000 + Math.round(Math.random() * 250);

  state.market = {
    ...state.market,
    ts: Date.now(),
    prices: { BTC: btc, ETH: eth },
    heatmap: [
      { exchange: 'Binance', liquidity: Math.round(Math.random() * 100), side: 'long' },
      { exchange: 'Bybit', liquidity: Math.round(Math.random() * 100), side: 'short' },
      { exchange: 'OKX', liquidity: Math.round(Math.random() * 100), side: 'neutral' }
    ],
    exchanges: [
      { name: 'Binance', spread: 0.03, volume24h: 1200000000, funding: 0.01 },
      { name: 'Bybit', spread: 0.05, volume24h: 850000000, funding: -0.01 },
      { name: 'OKX', spread: 0.04, volume24h: 760000000, funding: 0.0 }
    ]
  };

  io.emit('market:update', state.market);
}

const tickMs = Number(process.env.MARKET_TICK_MS || 5000);
setInterval(mockRealtimeTick, Number.isFinite(tickMs) ? tickMs : 5000);

const PORT = process.env.PORT || 4100;
server.listen(PORT, () => {
  console.log(`MONADFLOW backend running on :${PORT}`);
});
