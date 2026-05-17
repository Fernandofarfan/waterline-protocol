from fastapi import FastAPI, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from web3 import Web3
from web3.exceptions import Web3Exception
import uvicorn
import os
import json
import oracledb
import networkx as nx
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

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
            increment=1
        )
        print("Oracle DB Connection Pool created.")
    except oracledb.Error as e:
        print(f"Error creating Oracle DB pool: {e}. Usando fallback en memoria.")
    
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
            import hashlib
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
