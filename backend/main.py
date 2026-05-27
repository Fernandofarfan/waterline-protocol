from fastapi import FastAPI, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from web3 import Web3
from web3.exceptions import Web3Exception
import uvicorn
import os
import json
import oracledb
import networkx as nx
import asyncio
import hashlib
import secrets
import time
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

MAX_LOCATION_LENGTH = int(os.getenv("MAX_LOCATION_LENGTH", "120"))
MAX_PACKAGE_ID = int(os.getenv("MAX_PACKAGE_ID", "1000000000"))
MOCK_MODE_ENABLED = os.getenv("MOCK_MODE_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------
# VARIABLES DE ENTORNO
# ---------------------------------------------------------
PAYLOAD_ENCRYPTION_KEY = os.getenv("PAYLOAD_ENCRYPTION_KEY", "")
FRONTEND_CORS_ORIGIN = os.getenv("FRONTEND_CORS_ORIGIN", "http://localhost:5173")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

# ---------------------------------------------------------
# CONEXIÓN ORACLE DB (THIN MODE)
# ---------------------------------------------------------
MOCK_PACKAGE_LOGS = []
oracle_pool = None


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
            increment=1,
        )
        print("Oracle DB Connection Pool created.")
    except oracledb.Error:
        print("Oracle DB pool unavailable; using in-memory fallback.")

    yield

    if oracle_pool:
        oracle_pool.close()
        print("Oracle DB Connection Pool closed.")


def get_oracle_connection():
    if oracle_pool:
        try:
            return oracle_pool.acquire()
        except oracledb.Error:
            return None
    return None


AVALANCHE_RPC_URL = os.getenv("AVALANCHE_RPC_URL", "https://api.avax-test.network/ext/bc/C/rpc")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000")
ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS", "0x0000000000000000000000000000000000000000")

w3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC_URL, request_kwargs={"timeout": 20}))

CONTRACT_ABI = [{"inputs": [{"internalType": "uint256", "name": "_id", "type": "uint256"}, {"components": [{"internalType": "bytes", "name": "ciphertext", "type": "bytes"}], "internalType": "struct WaterlineProtocol.estring", "name": "_newLocation", "type": "tuple"}], "name": "updateLocation", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]

app = FastAPI(
    title="Waterline Protocol API",
    description="Backend API para logística Web3 (Waterline Protocol)",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_CORS_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_SECRET_KEY or len(API_SECRET_KEY) < 16:
        raise HTTPException(status_code=500, detail="API no inicializada de forma segura.")
    if not secrets.compare_digest(api_key, API_SECRET_KEY):
        raise HTTPException(status_code=403, detail="No se pudo validar las credenciales de la API.")


class LocationUpdate(BaseModel):
    package_id: int = Field(gt=0, le=MAX_PACKAGE_ID)
    new_location: str = Field(min_length=1, max_length=MAX_LOCATION_LENGTH)

    @field_validator("new_location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("La ubicación no puede estar vacía.")
        return cleaned


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
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws/tracking")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    allowed = {FRONTEND_CORS_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"}
    if origin not in allowed:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "Waterline Protocol API corriendo correctamente"}


@app.get("/package/{id}", tags=["Packages"])
async def get_package(id: int):
    if id <= 0 or id > MAX_PACKAGE_ID:
        raise HTTPException(status_code=400, detail="package_id inválido.")

    try:
        connection = get_oracle_connection()
        if connection is None:
            history = [
                {"location": log["location"], "tx_hash": log["tx_hash"]}
                for log in MOCK_PACKAGE_LOGS
                if log["package_id"] == id
            ]
            if not history:
                raise HTTPException(status_code=404, detail="Paquete no encontrado.")
            return {"status": "success", "data": {"package_id": id, "history": history, "current_location": history[-1]["location"], "last_tx_hash": history[-1]["tx_hash"]}}

        cursor = connection.cursor()
        cursor.execute("SELECT location, tx_hash FROM package_logs WHERE package_id = :1 ORDER BY id ASC", [id])
        rows = cursor.fetchall()
        cursor.close()
        connection.close()

        if not rows:
            raise HTTPException(status_code=404, detail="Paquete no encontrado.")

        history = [{"location": row[0], "tx_hash": row[1]} for row in rows]
        return {"status": "success", "data": {"package_id": id, "history": history, "current_location": history[-1]["location"], "last_tx_hash": history[-1]["tx_hash"]}}
    except HTTPException:
        raise
    except oracledb.Error:
        raise HTTPException(status_code=500, detail="Error de base de datos.")


def get_encryption_key() -> bytes:
    if PAYLOAD_ENCRYPTION_KEY.startswith("0x"):
        raw = PAYLOAD_ENCRYPTION_KEY[2:]
        if len(raw) != 64:
            raise HTTPException(status_code=500, detail="Configuración de cifrado inválida.")
        return bytes.fromhex(raw)
    key = PAYLOAD_ENCRYPTION_KEY.encode("utf-8")
    if len(key) < 32:
        raise HTTPException(status_code=500, detail="Configuración de cifrado inválida.")
    return key[:32]


def encrypt_location(location_str: str) -> bytes:
    key = get_encryption_key()
    payload_bytes = location_str.encode("utf-8")
    stream = hashlib.sha256(key + os.urandom(16)).digest()
    masked = bytes(a ^ b for a, b in zip(payload_bytes, stream[: len(payload_bytes)]))
    return stream[:16] + bytes([len(payload_bytes)]) + masked


@app.post("/package/update", tags=["Packages"])
async def update_package_location(update: LocationUpdate, api_key: str = Depends(verify_api_key)):
    try:
        encrypted_bytes = encrypt_location(update.new_location)
        encrypted_location_arg = {"ciphertext": encrypted_bytes}

        if PRIVATE_KEY == "0x0000000000000000000000000000000000000000000000000000000000000000":
            if not MOCK_MODE_ENABLED:
                raise HTTPException(status_code=500, detail="Mock mode deshabilitado y wallet no configurada.")
            await asyncio.sleep(1)
            mock_hash = hashlib.sha256(f"{update.package_id}{time.time()}".encode()).hexdigest()
            real_tx_hash = "0x" + mock_hash
        else:
            contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
            nonce = w3.eth.get_transaction_count(w3.to_checksum_address(ACCOUNT_ADDRESS))
            chain_id = w3.eth.chain_id
            tx = contract.functions.updateLocation(update.package_id, encrypted_location_arg).build_transaction({"chainId": chain_id, "gas": 300000, "maxFeePerGas": w3.to_wei("25", "gwei"), "maxPriorityFeePerGas": w3.to_wei("2", "gwei"), "nonce": nonce})
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if tx_receipt.status != 1:
                raise HTTPException(status_code=400, detail="La transacción falló en la blockchain.")
            real_tx_hash = tx_receipt.transactionHash.hex()

    except HTTPException:
        raise
    except Web3Exception:
        raise HTTPException(status_code=500, detail="Error de red blockchain.")
    except ValueError:
        raise HTTPException(status_code=500, detail="Error de configuración blockchain.")
    except Exception:
        raise HTTPException(status_code=500, detail="Error al enviar la TX.")

    try:
        ciphertext_hex = "0x" + encrypted_bytes.hex()
        connection = get_oracle_connection()
        if connection is None:
            MOCK_PACKAGE_LOGS.append({"package_id": update.package_id, "location": ciphertext_hex, "tx_hash": real_tx_hash})
        else:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO package_logs (package_id, location, tx_hash) VALUES (:1, :2, :3)", [update.package_id, ciphertext_hex, real_tx_hash])
                connection.commit()
                connection.close()

        ws_payload = {"type": "PACKAGE_UPDATED", "package_id": update.package_id, "ciphertext": ciphertext_hex, "tx_hash": real_tx_hash}
        await manager.broadcast(json.dumps(ws_payload))

        return {"status": "success", "message": f"Paquete {update.package_id} actualizado con ubicación cifrada en Avalanche Fuji de forma exitosa.", "tx_hash": real_tx_hash, "encrypted_location_ciphertext": ciphertext_hex}
    except Exception:
        raise HTTPException(status_code=500, detail="Error registrando en Oracle DB.")


def init_route_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    cities = ["CABA", "Mar del Plata", "Rosario", "Córdoba", "Salta", "Shanghai", "Rotterdam", "Róterdam", "Roterdam"]
    G.add_nodes_from(cities)
    edges = [("CABA", "Mar del Plata", 415), ("Mar del Plata", "CABA", 415), ("CABA", "Rosario", 300), ("Rosario", "CABA", 300), ("Rosario", "Córdoba", 400), ("Córdoba", "Rosario", 400), ("CABA", "Córdoba", 700), ("Córdoba", "CABA", 700), ("Córdoba", "Salta", 870), ("Salta", "Córdoba", 870), ("Rosario", "Salta", 1100), ("Salta", "Rosario", 1100), ("Shanghai", "Rotterdam", 10500), ("Rotterdam", "Shanghai", 10500), ("Shanghai", "Róterdam", 10500), ("Róterdam", "Shanghai", 10500), ("Shanghai", "Roterdam", 10500), ("Roterdam", "Shanghai", 10500), ("Shanghai", "CABA", 19500), ("CABA", "Shanghai", 19500), ("Rotterdam", "CABA", 11500), ("CABA", "Rotterdam", 11500), ("Róterdam", "CABA", 11500), ("CABA", "Róterdam", 11500), ("Roterdam", "CABA", 11500), ("CABA", "Roterdam", 11500)]
    G.add_weighted_edges_from(edges)
    return G


route_graph = init_route_graph()


@app.get("/route/optimize", tags=["AI Routing Agent"])
async def optimize_route(origin: str, destination: str):
    try:
        path = nx.shortest_path(route_graph, source=origin, target=destination, weight="weight")
        distance = nx.shortest_path_length(route_graph, source=origin, target=destination, weight="weight")
        estimated_hours = distance / 80.0
        return {"origin": origin, "destination": destination, "optimal_route": path, "route": path, "total_distance_km": distance, "distance": distance, "estimated_time_hours": round(estimated_hours, 2), "time": round(estimated_hours, 2)}
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=404, detail="No se encontró una ruta posible entre ambos puntos.")
    except nx.NodeNotFound:
        raise HTTPException(status_code=400, detail="El origen o destino ingresado no existe en las rutas mapeadas.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
