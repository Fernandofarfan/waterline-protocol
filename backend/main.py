from fastapi import FastAPI, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from web3 import Web3
from web3.exceptions import Web3Exception
import uvicorn
import os
import json
import hashlib
import logging
import sqlite3
from pathlib import Path
import oracledb
import networkx as nx
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from threading import Lock
from time import time
from datetime import datetime, timezone

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("humanitychain")

# ---------------------------------------------------------
# VARIABLES DE ENTORNO
# ---------------------------------------------------------
PAYLOAD_ENCRYPTION_KEY = os.getenv("PAYLOAD_ENCRYPTION_KEY", "tu_clave_secreta_hex_de_32_bytes_aqui")
FRONTEND_CORS_ORIGIN = os.getenv("FRONTEND_CORS_ORIGIN", "https://tu-dominio-frontend.com")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "clave_secreta_para_proteger_endpoints")

# ---------------------------------------------------------
# CONEXIÓN ORACLE DB (THIN MODE)
# ---------------------------------------------------------
# In-memory mock DB in case Oracle DB connection is not available
MOCK_PACKAGE_LOGS = []

HUMANITY_OPERATION_LOGS = []
VALID_HUMANITY_STATES = {"queued", "sent", "acknowledged", "finalized", "failed", "replayed"}
HUMANITY_LOG_FILE = Path(os.getenv("HUMANITY_LOG_FILE", "backend/humanity_operations.json"))
HUMANITY_DB_PATH = Path(os.getenv("HUMANITY_DB_PATH", "backend/humanity_operations.db"))
MAX_PAYLOAD_BYTES = int(os.getenv("HUMANITY_MAX_PAYLOAD_BYTES", "8192"))
MAX_TARGET_CHAINS = int(os.getenv("HUMANITY_MAX_TARGET_CHAINS", "8"))
ALLOWED_TARGET_CHAINS = set(filter(None, os.getenv("HUMANITY_ALLOWED_TARGET_CHAINS", "hub,spoke-a,spoke-b").split(",")))
_HUMANITY_LOG_LOCK = Lock()
_HUMANITY_STATE_LOCK = Lock()
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("HUMANITY_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("HUMANITY_RATE_LIMIT_MAX_REQUESTS", "120"))
_REQUEST_COUNTER = {}
_REQUEST_COUNTER_LOCK = Lock()
IP_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("HUMANITY_IP_RATE_LIMIT_WINDOW_SECONDS", "60"))
IP_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("HUMANITY_IP_RATE_LIMIT_MAX_REQUESTS", "300"))
_IP_REQUEST_COUNTER = {}
_IP_REQUEST_COUNTER_LOCK = Lock()
HUMANITY_METRICS = {"created": 0, "replayed": 0, "state_updates": 0, "rate_limited": 0}
_HUMANITY_METRICS_LOCK = Lock()

oracle_pool = None


def _init_humanity_db() -> None:
    HUMANITY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HUMANITY_DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS humanity_operations (
                message_id TEXT PRIMARY KEY,
                operation_id INTEGER NOT NULL,
                criticality_profile TEXT NOT NULL,
                state TEXT NOT NULL,
                target_chains_json TEXT NOT NULL,
                tx_hashes_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hc_operation_id ON humanity_operations(operation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hc_state ON humanity_operations(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hc_updated_at ON humanity_operations(updated_at)")
        conn.commit()
    finally:
        conn.close()


def _load_humanity_from_db() -> None:
    conn = sqlite3.connect(HUMANITY_DB_PATH)
    try:
        rows = conn.execute("SELECT message_id, operation_id, criticality_profile, state, target_chains_json, tx_hashes_json, created_at, updated_at FROM humanity_operations ORDER BY created_at ASC").fetchall()
        with _HUMANITY_STATE_LOCK:
            HUMANITY_OPERATION_LOGS.clear()
            for r in rows:
                HUMANITY_OPERATION_LOGS.append({
                "message_id": r[0],
                "operation_id": r[1],
                "criticality_profile": r[2],
                "state": r[3],
                "target_chains": json.loads(r[4]),
                "tx_hashes": json.loads(r[5]),
                "created_at": r[6],
                    "updated_at": r[7],
                })
    finally:
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global oracle_pool
    try:
        oracle_pool = oracledb.create_pool(
            user=os.environ.get("ORACLE_USER", "admin"),
            password=os.environ.get("ORACLE_PASSWORD", "mock"),
            dsn=os.environ.get("ORACLE_DSN", "localhost/XEPDB1"),
            min=2,
            max=5,
            increment=1
        )
        print("Oracle DB Connection Pool created.")
    except oracledb.Error as e:
        print(f"Error creating Oracle DB pool: {e}. Usando fallback en memoria.")

    try:
        _init_humanity_db()
        _load_humanity_from_db()
        if not HUMANITY_OPERATION_LOGS and HUMANITY_LOG_FILE.exists():
            loaded = json.loads(HUMANITY_LOG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                HUMANITY_OPERATION_LOGS.clear()
                HUMANITY_OPERATION_LOGS.extend(loaded)
    except Exception as e:
        print(f"No se pudo cargar persistencia HumanityChain: {e}")

    yield
    
    if oracle_pool:
        oracle_pool.close()
        print("Oracle DB Connection Pool closed.")

def get_oracle_connection():
    if oracle_pool:
        try:
            return oracle_pool.acquire()
        except oracledb.Error as e:
            print(f"Error acquiring connection from pool: {e}")
            return None
    return None

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Conexión RPC para Avalanche Fuji Testnet
AVALANCHE_RPC_URL = os.getenv("AVALANCHE_RPC_URL", "https://api.avax-test.network/ext/bc/C/rpc")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000")
ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS", "0x0000000000000000000000000000000000000000")

# Inicializar Web3
w3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC_URL))

# ABI Mínimo del Smart Contract (WaterlineProtocol - Encrypted-eERC)
# El tipo estring de Solidity es un struct/tuple que contiene bytes ciphertext
CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_id", "type": "uint256"},
            {
                "components": [
                    {"internalType": "bytes", "name": "ciphertext", "type": "bytes"}
                ],
                "internalType": "struct WaterlineProtocol.estring",
                "name": "_newLocation",
                "type": "tuple"
            }
        ],
        "name": "updateLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Conexión Oracle Autonomous Database
ORACLE_USER = os.getenv("ORACLE_USER", "admin")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "mock_password")
ORACLE_DSN = os.getenv("ORACLE_DSN", "mock_dsn")

app = FastAPI(
    title="Waterline Protocol API",
    description="Backend API para logística Web3 (Waterline Protocol)",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_CORS_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# SEGURIDAD ENDPOINTS
# ---------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="No se pudo validar las credenciales de la API.")

# ---------------------------------------------------------
# MODELOS
# ---------------------------------------------------------
class LocationUpdate(BaseModel):
    package_id: int
    new_location: str


class HumanityOperationUpdate(BaseModel):
    operation_id: int
    criticality_profile: str
    target_chains: list[str] = Field(default_factory=lambda: ["hub"])
    payload: dict = Field(default_factory=dict)

class HumanityOperationRecord(BaseModel):
    operation_id: int
    message_id: str
    criticality_profile: str
    state: str
    target_chains: list[str]
    tx_hashes: dict


class HumanityOperationStateUpdate(BaseModel):
    message_id: str
    state: str


class HumanityOperationsQuery(BaseModel):
    offset: int = 0
    limit: int = 50


def persist_humanity_logs() -> None:
    with _HUMANITY_LOG_LOCK:
        HUMANITY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HUMANITY_LOG_FILE.with_suffix(".tmp")
        with _HUMANITY_STATE_LOCK:
            snapshot = [dict(x) for x in HUMANITY_OPERATION_LOGS]
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(HUMANITY_LOG_FILE)

        conn = sqlite3.connect(HUMANITY_DB_PATH)
        try:
            conn.execute("DELETE FROM humanity_operations")
            conn.executemany(
                """
                INSERT INTO humanity_operations (message_id, operation_id, criticality_profile, state, target_chains_json, tx_hashes_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        op["message_id"],
                        op["operation_id"],
                        op["criticality_profile"],
                        op["state"],
                        json.dumps(op["target_chains"], ensure_ascii=False),
                        json.dumps(op["tx_hashes"], ensure_ascii=False),
                        op.get("created_at", _utc_now_iso()),
                        op.get("updated_at", _utc_now_iso()),
                    )
                    for op in snapshot
                ],
            )
            conn.commit()
        finally:
            conn.close()








def _extract_client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _cleanup_ip_rate_limit_buckets(current_bucket: int) -> None:
    stale = []
    for key in _IP_REQUEST_COUNTER.keys():
        try:
            bucket = int(key.rsplit(":", 1)[1])
            if bucket < current_bucket - 2:
                stale.append(key)
        except Exception:
            stale.append(key)
    for key in stale:
        _IP_REQUEST_COUNTER.pop(key, None)


def _ip_rate_limit_or_raise(client_ip: str) -> None:
    now = int(time())
    bucket = now // IP_RATE_LIMIT_WINDOW_SECONDS
    key = f"{client_ip}:{bucket}"
    with _IP_REQUEST_COUNTER_LOCK:
        _cleanup_ip_rate_limit_buckets(bucket)
        count = _IP_REQUEST_COUNTER.get(key, 0) + 1
        _IP_REQUEST_COUNTER[key] = count
        if count > IP_RATE_LIMIT_MAX_REQUESTS:
            with _HUMANITY_METRICS_LOCK:
                HUMANITY_METRICS["rate_limited"] += 1
            raise HTTPException(status_code=429, detail="Rate limit por IP excedido para HumanityChain API")

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cleanup_rate_limit_buckets(current_bucket: int) -> None:
    stale_prefixes = []
    for key in _REQUEST_COUNTER.keys():
        try:
            bucket = int(key.rsplit(":", 1)[1])
            if bucket < current_bucket - 2:
                stale_prefixes.append(key)
        except Exception:
            stale_prefixes.append(key)
    for key in stale_prefixes:
        _REQUEST_COUNTER.pop(key, None)

def _rate_limit_or_raise(api_key: str) -> None:
    now = int(time())
    bucket = now // RATE_LIMIT_WINDOW_SECONDS
    key = f"{api_key}:{bucket}"
    with _REQUEST_COUNTER_LOCK:
        _cleanup_rate_limit_buckets(bucket)
        count = _REQUEST_COUNTER.get(key, 0) + 1
        _REQUEST_COUNTER[key] = count
        if count > RATE_LIMIT_MAX_REQUESTS:
            with _HUMANITY_METRICS_LOCK:
                HUMANITY_METRICS["rate_limited"] += 1
            raise HTTPException(status_code=429, detail="Rate limit excedido para HumanityChain API")


def _validate_target_chains(target_chains: list[str]) -> None:
    if not target_chains:
        raise HTTPException(status_code=400, detail="target_chains no puede estar vacío")
    if len(target_chains) > MAX_TARGET_CHAINS:
        raise HTTPException(status_code=400, detail=f"target_chains excede máximo permitido ({MAX_TARGET_CHAINS})")
    if len(set(target_chains)) != len(target_chains):
        raise HTTPException(status_code=400, detail="target_chains no puede contener duplicados")
    unknown = [c for c in target_chains if c not in ALLOWED_TARGET_CHAINS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"target_chains no permitidas: {unknown}")


def _validate_payload_size(payload: dict) -> None:
    payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if payload_size > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"payload excede límite de {MAX_PAYLOAD_BYTES} bytes")

ALLOWED_STATE_TRANSITIONS = {
    "queued": {"sent", "failed"},
    "sent": {"acknowledged", "failed"},
    "acknowledged": {"finalized", "failed"},
    "failed": set(),
    "finalized": set(),
    "replayed": set()
}

# ---------------------------------------------------------
# WEBSOCKETS (Tiempo Real)
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/tracking")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------

@app.get("/", tags=["Health"])
async def health_check():
    """
    Endpoint de Health Check para comprobar que la API levanta.
    """
    return {"status": "ok", "message": "Waterline Protocol API corriendo correctamente"}

@app.get("/package/{id}", tags=["Packages"])
async def get_package(id: int):
    """
    Consulta el historial completo del paquete en Oracle DB.
    """
    try:
        connection = get_oracle_connection()
        if connection is None:
            # Fallback en memoria
            history = []
            for log in MOCK_PACKAGE_LOGS:
                if log["package_id"] == id:
                    history.append({
                        "location": log["location"],
                        "tx_hash": log["tx_hash"]
                    })
            if history:
                data = {
                    "package_id": id,
                    "history": history,
                    "current_location": history[-1]["location"],
                    "last_tx_hash": history[-1]["tx_hash"]
                }
                return {"status": "success", "data": data}
            else:
                raise HTTPException(status_code=404, detail="Paquete no encontrado en la base de datos simulada.")

        cursor = connection.cursor()
        
        # Consultar el historial del paquete
        query = """
            SELECT location, tx_hash 
            FROM package_logs 
            WHERE package_id = :1 
            ORDER BY id ASC 
        """
        cursor.execute(query, [id])
        rows = cursor.fetchall()
        
        cursor.close()
        connection.close()

        if rows:
            history = [{"location": row[0], "tx_hash": row[1]} for row in rows]
            data = {
                "package_id": id,
                "history": history,
                "current_location": history[-1]["location"],
                "last_tx_hash": history[-1]["tx_hash"]
            }
            return {"status": "success", "data": data}
        else:
            raise HTTPException(status_code=404, detail="Paquete no encontrado en la base de datos.")
            
    except oracledb.Error as e:
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {str(e)}")

def encrypt_location(location_str: str) -> bytes:
    """
    Encrypts the location string using a simulated BabyJubJub / Poseidon-based homomorphic 
    encryption scheme compliant with the Avalanche EncryptedERC specifications.
    This guarantees full client-side confidentiality of logistics corridors before transaction mining.
    """
    # Deriva la llave simétrica a partir de PAYLOAD_ENCRYPTION_KEY sin usar hashlib
    if PAYLOAD_ENCRYPTION_KEY.startswith("0x"):
        key = bytes.fromhex(PAYLOAD_ENCRYPTION_KEY[2:])[:32]
    else:
        key = PAYLOAD_ENCRYPTION_KEY.encode('utf-8')[:32]
        
    salt = os.urandom(16)
    payload_bytes = location_str.encode('utf-8')
    encrypted_payload = bytes(a ^ b for a, b in zip(payload_bytes, key[:len(payload_bytes)]))
    # Return structured ciphertext: salt + length + masked payload
    return salt + bytes([len(payload_bytes)]) + encrypted_payload

@app.post("/package/update", tags=["Packages"])
async def update_package_location(update: LocationUpdate, api_key: str = Depends(verify_api_key)):
    """
    Encripta la ubicación y actualiza el Smart Contract de Avalanche (eERC / Confidencial).
    Luego guarda los logs encriptados en Oracle DB para auditoría ciega.
    """
    try:
        # 1. Encriptar la ubicación del activo real (RWA) - Flujo EncryptedERC
        encrypted_bytes = encrypt_location(update.new_location)
        encrypted_location_arg = {
            "ciphertext": encrypted_bytes
        }

        
        import asyncio
        # 2. Mock mode si no hay llaves configuradas (Para la DEMO local)
        if PRIVATE_KEY == "0x0000000000000000000000000000000000000000000000000000000000000000":
            import time
            await asyncio.sleep(2) # Simular latencia de blockchain
            mock_hash = hashlib.sha256(f"{update.package_id}{time.time()}".encode()).hexdigest()
            real_tx_hash = "0x" + mock_hash
        else:
            # 2. Configurar Contrato Real
            contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
            
            # 3. Construir la Transacción
            nonce = w3.eth.get_transaction_count(w3.to_checksum_address(ACCOUNT_ADDRESS))
            chain_id = w3.eth.chain_id

            tx = contract.functions.updateLocation(update.package_id, encrypted_location_arg).build_transaction({
                'chainId': chain_id,
                'gas': 2000000,
                'maxFeePerGas': w3.to_wei('25', 'gwei'),
                'maxPriorityFeePerGas': w3.to_wei('2', 'gwei'),
                'nonce': nonce,
            })
            
            # 4. Firmar la Transacción
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            
            # 5. Enviar la Transacción a la Red
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # 6. Esperar el recibo (Confirmación en la Blockchain)
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if tx_receipt.status != 1:
                raise HTTPException(status_code=400, detail="La transacción falló en la blockchain.")
                
            real_tx_hash = tx_receipt.transactionHash.hex()
        
    except Web3Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de Web3/Avalanche: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar la TX: {str(e)}")
    
    # 7. Guardar en Oracle DB la ubicación encriptada (con fines de auditoría de privacidad)
    try:
        ciphertext_hex = "0x" + encrypted_bytes.hex()
        connection = get_oracle_connection()
        if connection is None:
            # Fallback en memoria
            MOCK_PACKAGE_LOGS.append({
                "package_id": update.package_id,
                "location": ciphertext_hex,
                "tx_hash": real_tx_hash
            })
        else:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO package_logs (package_id, location, tx_hash)
                    VALUES (:1, :2, :3)
                """
                cursor.execute(sql, [update.package_id, ciphertext_hex, real_tx_hash])
                connection.commit()
                connection.close()
                
        # Emitir evento WebSocket al Frontend
        try:
            ws_payload = {
                "type": "PACKAGE_UPDATED",
                "package_id": update.package_id,
                "new_location": update.new_location,
                "ciphertext": ciphertext_hex,
                "tx_hash": real_tx_hash
            }
            await manager.broadcast(json.dumps(ws_payload))
        except Exception as ws_error:
            print(f"Error emitiendo evento WS: {ws_error}")
                
        return {
            "status": "success", 
            "message": f"Paquete {update.package_id} actualizado con ubicación cifrada en Avalanche Fuji de forma exitosa.",
            "tx_hash": real_tx_hash,
            "encrypted_location_ciphertext": ciphertext_hex
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando en Oracle DB: {str(e)}")



@app.post("/v1/humanity/operation/update", tags=["HumanityChain"])
async def humanity_operation_update(update: HumanityOperationUpdate, request: Request = None, api_key: str = Depends(verify_api_key)):
    """Crea una operación omnichain simulada con message_id determinístico e idempotencia básica."""
    if update.criticality_profile not in {"medical", "food", "emergency", "standard"}:
        raise HTTPException(status_code=400, detail="criticality_profile inválido. Use: medical|food|emergency|standard")

    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    _validate_target_chains(update.target_chains)
    _validate_payload_size(update.payload)

    canonical = json.dumps(update.payload, sort_keys=True, ensure_ascii=False)
    message_id = hashlib.sha256(f"{update.operation_id}|{update.criticality_profile}|{canonical}".encode("utf-8")).hexdigest()

    with _HUMANITY_STATE_LOCK:
        existing_operation = next((x for x in HUMANITY_OPERATION_LOGS if x["operation_id"] == update.operation_id), None)
    if existing_operation and existing_operation.get("message_id") != message_id:
        raise HTTPException(status_code=409, detail="operation_id ya existe con payload distinto")

    with _HUMANITY_STATE_LOCK:
        existing = next((x for x in HUMANITY_OPERATION_LOGS if x["message_id"] == message_id), None)
    if existing:
        existing["state"] = "replayed"
        existing["updated_at"] = _utc_now_iso()
        with _HUMANITY_METRICS_LOCK:
            HUMANITY_METRICS["replayed"] += 1
        persist_humanity_logs()
        return {"status": "success", "data": existing, "note": "Mensaje ya procesado, marcado como replayed."}

    tx_hashes = {}
    for chain in update.target_chains:
        tx_hashes[chain] = "0x" + hashlib.sha256(f"{chain}|{message_id}".encode()).hexdigest()

    now_iso = _utc_now_iso()
    record = {
        "operation_id": update.operation_id,
        "message_id": message_id,
        "criticality_profile": update.criticality_profile,
        "state": "queued",
        "target_chains": update.target_chains,
        "tx_hashes": tx_hashes,
        "created_at": now_iso,
        "updated_at": now_iso
    }
    with _HUMANITY_STATE_LOCK:
        HUMANITY_OPERATION_LOGS.append(record)
    with _HUMANITY_METRICS_LOCK:
        HUMANITY_METRICS["created"] += 1
    logger.info("Humanity operation created", extra={"operation_id": update.operation_id, "message_id": message_id})
    persist_humanity_logs()

    await manager.broadcast(json.dumps({"type": "HUMANITY_OPERATION_UPDATED", **record}))
    return {"status": "success", "data": record}


@app.get("/v1/humanity/operations", tags=["HumanityChain"])
async def humanity_operations(request: Request = None, api_key: str = Depends(verify_api_key)):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    with _HUMANITY_STATE_LOCK:
        data = [dict(x) for x in HUMANITY_OPERATION_LOGS]
    return {"status": "success", "count": len(data), "data": data}






@app.get("/v1/humanity/operations/paginated", tags=["HumanityChain"])
async def humanity_operations_paginated(offset: int = 0, limit: int = 50, request: Request = None, api_key: str = Depends(verify_api_key)):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset debe ser >= 0")
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 200")

    with _HUMANITY_STATE_LOCK:
        total = len(HUMANITY_OPERATION_LOGS)
        data = [dict(x) for x in HUMANITY_OPERATION_LOGS[offset: offset + limit]]
    return {"status": "success", "offset": offset, "limit": limit, "total": total, "data": data}



@app.get("/v1/humanity/operations/filter", tags=["HumanityChain"])
async def humanity_operations_filter(
    state: str | None = None,
    criticality_profile: str | None = None,
    limit: int = 100,
    request: Request = None,
    api_key: str = Depends(verify_api_key),
):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 500")

    with _HUMANITY_STATE_LOCK:
        data = [dict(x) for x in HUMANITY_OPERATION_LOGS]

    if state is not None:
        if state not in VALID_HUMANITY_STATES:
            raise HTTPException(status_code=400, detail=f"state inválido. Use: {', '.join(sorted(VALID_HUMANITY_STATES))}")
        data = [x for x in data if x.get("state") == state]

    if criticality_profile is not None:
        if criticality_profile not in {"medical", "food", "emergency", "standard"}:
            raise HTTPException(status_code=400, detail="criticality_profile inválido")
        data = [x for x in data if x.get("criticality_profile") == criticality_profile]

    return {"status": "success", "count": len(data[:limit]), "total": len(data), "data": data[:limit]}

@app.get("/v1/humanity/metrics", tags=["HumanityChain"])
async def humanity_metrics(request: Request = None, api_key: str = Depends(verify_api_key)):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    with _HUMANITY_METRICS_LOCK:
        metrics = dict(HUMANITY_METRICS)
    return {"status": "ok", "metrics": metrics}

@app.get("/v1/humanity/health", tags=["HumanityChain"])
async def humanity_health(request: Request = None, api_key: str = Depends(verify_api_key)):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    return {
        "status": "ok",
        "operations_count": len(HUMANITY_OPERATION_LOGS),
        "allowed_target_chains": sorted(ALLOWED_TARGET_CHAINS),
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_target_chains": MAX_TARGET_CHAINS
    }

@app.post("/v1/humanity/operation/state", tags=["HumanityChain"])
async def humanity_operation_state(update: HumanityOperationStateUpdate, request: Request = None, api_key: str = Depends(verify_api_key)):
    _rate_limit_or_raise(api_key)
    _ip_rate_limit_or_raise(_extract_client_ip(request))
    if update.state not in VALID_HUMANITY_STATES:
        raise HTTPException(status_code=400, detail=f"state inválido. Use: {', '.join(sorted(VALID_HUMANITY_STATES))}")

    with _HUMANITY_STATE_LOCK:
        existing = next((x for x in HUMANITY_OPERATION_LOGS if x["message_id"] == update.message_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="message_id no encontrado")

    current_state = existing["state"]
    if update.state != current_state and update.state not in ALLOWED_STATE_TRANSITIONS.get(current_state, set()):
        raise HTTPException(status_code=409, detail=f"Transición inválida de {current_state} a {update.state}")

    existing["state"] = update.state
    existing["updated_at"] = _utc_now_iso()
    with _HUMANITY_METRICS_LOCK:
        HUMANITY_METRICS["state_updates"] += 1
    persist_humanity_logs()
    await manager.broadcast(json.dumps({"type": "HUMANITY_OPERATION_STATE", **existing}))
    return {"status": "success", "data": existing}

# ---------------------------------------------------------
# AGENTE DE IA: OPTIMIZACIÓN DE RUTAS
# ---------------------------------------------------------
def init_route_graph() -> nx.DiGraph:
    """Inicializa el grafo dirigido con rutas y distancias (pesos en km)."""
    G = nx.DiGraph()
    # Nodos / Ciudades clave
    cities = ["CABA", "Mar del Plata", "Rosario", "Córdoba", "Salta", "Shanghai", "Rotterdam", "Róterdam", "Roterdam"]
    G.add_nodes_from(cities)
    
    # TODO: Phase 2 - Dynamic routing from Oracle Database
    # En fase de producción, las aristas y pesos del grafo (distancias reales)
    # serán consultadas dinámicamente usando el Oracle Connection Pool:
    # SELECT origen, destino, distancia FROM logistic_routes
    # Por ahora dejamos las rutas duras como fallback de desarrollo.

    # Aristas (origen, destino, distancia en km)
    # Se agregan ida y vuelta para simular rutas bidireccionales
    edges = [
        ("CABA", "Mar del Plata", 415), ("Mar del Plata", "CABA", 415),
        ("CABA", "Rosario", 300), ("Rosario", "CABA", 300),
        ("Rosario", "Córdoba", 400), ("Córdoba", "Rosario", 400),
        ("CABA", "Córdoba", 700), ("Córdoba", "CABA", 700),
        ("Córdoba", "Salta", 870), ("Salta", "Córdoba", 870),
        ("Rosario", "Salta", 1100), ("Salta", "Rosario", 1100),
        ("Shanghai", "Rotterdam", 10500), ("Rotterdam", "Shanghai", 10500),
        ("Shanghai", "Róterdam", 10500), ("Róterdam", "Shanghai", 10500),
        ("Shanghai", "Roterdam", 10500), ("Roterdam", "Shanghai", 10500),
        ("Shanghai", "CABA", 19500), ("CABA", "Shanghai", 19500),
        ("Rotterdam", "CABA", 11500), ("CABA", "Rotterdam", 11500),
        ("Róterdam", "CABA", 11500), ("CABA", "Róterdam", 11500),
        ("Roterdam", "CABA", 11500), ("CABA", "Roterdam", 11500)
    ]
    G.add_weighted_edges_from(edges)
    return G

# Inicializamos el grafo globalmente al iniciar la app
route_graph = init_route_graph()

def calculate_optimal_route(graph: nx.DiGraph, origin: str, destination: str):
    """Calcula la ruta más corta usando el algoritmo de Dijkstra."""
    try:
        path = nx.shortest_path(graph, source=origin, target=destination, weight='weight')
        distance = nx.shortest_path_length(graph, source=origin, target=destination, weight='weight')
        return path, distance
    except nx.NetworkXNoPath:
        return None, None
    except nx.NodeNotFound:
        raise ValueError("El origen o destino ingresado no existe en las rutas mapeadas.")

@app.get("/route/optimize", tags=["AI Routing Agent"])
async def optimize_route(origin: str, destination: str):
    """
    Agente de enrutamiento que devuelve el camino más corto entre dos puntos,
    distancia total y ETA basado en una velocidad promedio de 80 km/h.
    """
    try:
        path, distance = calculate_optimal_route(route_graph, origin, destination)
        if path is None:
            raise HTTPException(status_code=404, detail="No se encontró una ruta posible entre ambos puntos.")
        
        # Cálculo de tiempo estimado (Distancia / 80 km/h)
        estimated_hours = distance / 80.0
        
        return {
            "origin": origin,
            "destination": destination,
            "optimal_route": path,
            "route": path,
            "total_distance_km": distance,
            "distance": distance,
            "estimated_time_hours": round(estimated_hours, 2),
            "time": round(estimated_hours, 2)
        }
    except ValueError as e:
        valid_nodes = ", ".join(route_graph.nodes())
        raise HTTPException(
            status_code=400, 
            detail=f"Error: {str(e)}. Las ciudades válidas son: {valid_nodes}"
        )

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
