from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from web3.exceptions import Web3Exception
import uvicorn
import os
import oracledb
import networkx as nx

# ---------------------------------------------------------
# CONEXIÓN ORACLE DB (THIN MODE)
# ---------------------------------------------------------
def get_oracle_connection():
    try:
        # El modo "thin" es el predeterminado, no requiere instalar Oracle Client
        connection = oracledb.connect(
            user=os.environ.get("ORACLE_USER", "admin"),
            password=os.environ.get("ORACLE_PASSWORD", "mock"),
            dsn=os.environ.get("ORACLE_DSN", "localhost/XEPDB1")
        )
        return connection
    except oracledb.Error as e:
        print(f"Error conectando a Oracle DB: {e}")
        raise

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

# ABI Mínimo del Smart Contract (WaterlineProtocol)
CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_id", "type": "uint256"},
            {"internalType": "string", "name": "_newLocation", "type": "string"}
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
    version="0.1.0"
)

# ---------------------------------------------------------
# MODELOS
# ---------------------------------------------------------
class LocationUpdate(BaseModel):
    package_id: int
    new_location: str

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
async def get_package(id: str):
    """
    Consulta un paquete del Smart Contract en Avalanche (Datos falsos por ahora)
    """
    # TODO: Interactuar con el Smart Contract usando web3.py
    # w3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC_URL))
    
    mock_data = {
        "package_id": id,
        "current_location": "Centro de Distribución Central",
        "status": "En Tránsito",
        "last_updated": "2026-05-16T14:30:00Z"
    }
    
    return {"status": "success", "data": mock_data}

@app.post("/package/update", tags=["Packages"])
async def update_package_location(update: LocationUpdate):
    """
    Actualiza la ubicación de un paquete invocando a Avalanche Fuji y guarda logs en Oracle DB.
    """
    try:
        # 1. Configurar Contrato
        contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
        
        # 2. Construir la Transacción
        nonce = w3.eth.get_transaction_count(w3.to_checksum_address(ACCOUNT_ADDRESS))
        chain_id = w3.eth.chain_id

        tx = contract.functions.updateLocation(update.package_id, update.new_location).build_transaction({
            'chainId': chain_id,
            'gas': 2000000,
            'maxFeePerGas': w3.to_wei('25', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('2', 'gwei'),
            'nonce': nonce,
        })
        
        # 3. Firmar la Transacción
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        
        # 4. Enviar la Transacción a la Red
        # Dependiendo de la versión de web3.py puede ser .rawTransaction o .raw_transaction
        raw_tx = getattr(signed_tx, 'raw_transaction', getattr(signed_tx, 'rawTransaction', None))
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        
        # 5. Esperar el recibo (Confirmación en la Blockchain)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status != 1:
            raise HTTPException(status_code=400, detail="La transacción falló en la blockchain.")
            
        real_tx_hash = w3.to_hex(tx_hash)
        
    except Web3Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de Web3/Avalanche: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar la TX: {str(e)}")
    
    # 6. Guardar en Oracle DB si la TX fue exitosa
    try:
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO package_logs (package_id, location, tx_hash)
                    VALUES (:1, :2, :3)
                """
                cursor.execute(sql, [update.package_id, update.new_location, real_tx_hash])
                connection.commit()
                
        return {
            "status": "success", 
            "message": f"Paquete {update.package_id} actualizado a '{update.new_location}' de forma exitosa.",
            "tx_hash": real_tx_hash
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
    cities = ["CABA", "Mar del Plata", "Rosario", "Córdoba", "Salta"]
    G.add_nodes_from(cities)
    
    # Aristas (origen, destino, distancia en km)
    # Se agregan ida y vuelta para simular rutas bidireccionales
    edges = [
        ("CABA", "Mar del Plata", 415), ("Mar del Plata", "CABA", 415),
        ("CABA", "Rosario", 300), ("Rosario", "CABA", 300),
        ("Rosario", "Córdoba", 400), ("Córdoba", "Rosario", 400),
        ("CABA", "Córdoba", 700), ("Córdoba", "CABA", 700),
        ("Córdoba", "Salta", 870), ("Salta", "Córdoba", 870),
        ("Rosario", "Salta", 1100), ("Salta", "Rosario", 1100)
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
            "total_distance_km": distance,
            "estimated_time_hours": round(estimated_hours, 2)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
