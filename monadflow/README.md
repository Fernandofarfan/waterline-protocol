# MONADFLOW (MVP+ scaffold)

Plataforma inspirada en TapeSurf, TradingDifferent y CoinGlass.

## Stack
- Frontend: Next.js (App Router), Socket.IO client
- Backend: Node.js + Express + Socket.IO
- DB: Supabase/PostgreSQL (base preparada)
- Data realtime: Chainlink + TradingView adapters
- Chat: YouTube Live Chat API (pendiente de credenciales)
- Wallet/Identidad: MetaMask, Hedera, StarkNet + abstracción de cuenta ZK

## Flujo de datos
1. Chainlink obtiene precios y TradingView entrega señales técnicas
2. Backend normaliza y publica `market:update`
3. Frontend renderiza heatmap, comparador y paneles omnichain
4. YouTube API sincroniza chat en vivo
5. Webhooks/relayers publican eventos on-chain al endpoint `/api/contracts/event`
6. Registro de identidad genera `traceHash` para trazabilidad segura (`identity:update` / `identity:attested`)

## Endpoints backend (smart-contract friendly)
- `GET /health` (incluye estado de servicios)
- `GET /api/market`
- `GET /api/chains`
- `GET /api/alerts`
- `GET /api/identity/:wallet`
- `POST /api/identity/register` (wallet + network + zkProof + starknetAccount + accountAbstraction)
- `POST /api/identity/attest` (wallet + traceHash + signedMessage)
- `POST /api/contracts/event` (ingesta de eventos de contratos)

## Identidad descentralizada (ZK + StarkNet)
- El registro crea una sesión de identidad y un `traceHash` SHA-256 para trazabilidad.
- `accountAbstraction` permite modelar wallets AA (ERC-4337 o StarkNet AA nativo).
- La atestación (`/api/identity/attest`) confirma la trazabilidad con huella de firma.

## Variables de entorno sugeridas
### Backend
- `PORT=4100`
- `CORS_ORIGINS=*`
- `CHAINLINK_NETWORK=ethereum`
- `TRADINGVIEW_ENABLED=true`
- `OMNICHAIN_BRIDGE=LayerZero-ready`
- `MARKET_TICK_MS=5000`
- `YOUTUBE_API_KEY=...`

### Frontend (Vercel)
- `NEXT_PUBLIC_BACKEND_WS_URL`
- `NEXT_PUBLIC_BACKEND_HTTP_URL`

## Deploy (base Vercel + omnichain)
1. Subir `monadflow/frontend` a Vercel.
2. Configurar variables frontend en Vercel.
3. Backend en Railway/Render/Fly o servicio Node dedicado con websockets.
4. Conectar Supabase para persistir alerts/ranking/identidades/atestaciones.
5. Configurar claves de Chainlink, TradingView, YouTube, Telegram, X.
6. Agregar relayer omnichain para Ethereum/StarkNet/Hedera.

## Estado
Base lista para revisión técnica y merge a `main` como scaffold extensible.
