import React, { useState, useEffect } from 'react';
import { 
  BrainCircuit, 
  Map, 
  Package, 
  MapPin, 
  Link as LinkIcon, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Clock,
  Route,
  Search,
  Database
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icons in React Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const CITY_COORDS = {
  'CABA': [-34.6037, -58.3816],
  'Mar del Plata': [-38.0055, -57.5426],
  'Rosario': [-32.9442, -60.6505],
  'Córdoba': [-31.4201, -64.1888],
  'Salta': [-24.7821, -65.4232],
  'Shanghai': [31.2304, 121.4737],
  'Rotterdam': [51.9244, 4.4777]
};

export default function App() {
  // ==========================================
  // ESTADO: SECCIÓN 1 - Agente IA (Enrutamiento)
  // ==========================================
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [routeData, setRouteData] = useState(null);
  const [isRouting, setIsRouting] = useState(false);
  const [routeError, setRouteError] = useState(null);

  // ==========================================
  // ESTADO: SECCIÓN 2 - Oráculo Web3 (Avalanche + OCI)
  // ==========================================
  const [packageId, setPackageId] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [txResult, setTxResult] = useState(null);
  const [isTransacting, setIsTransacting] = useState(false);
  const [txError, setTxError] = useState(null);
  const [txLoadingMessage, setTxLoadingMessage] = useState('');

  // ==========================================
  // ESTADO: SECCIÓN 3 - Tracking Portal
  // ==========================================
  const [trackId, setTrackId] = useState('');
  const [trackResult, setTrackResult] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [trackError, setTrackError] = useState(null);

  // ==========================================
  // ESTADO: SECCIÓN 4 - Real-time WebSockets
  // ==========================================
  const [latestIoTUpdate, setLatestIoTUpdate] = useState(null);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_API_URL.replace(/^http/, 'ws') + '/ws/tracking';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "PACKAGE_UPDATED") {
          setLatestIoTUpdate(data);
          setTimeout(() => setLatestIoTUpdate(null), 5000);
          
          setTrackResult(prev => {
            // Check loosely using parseInt to match trackId which might be string
            if (prev && prev.package_id == data.package_id) {
              return {
                ...prev,
                current_location: data.ciphertext,
                last_tx_hash: data.tx_hash
              };
            }
            return prev;
          });
        }
      } catch (err) {
        console.error("Error WS", err);
      }
    };

    return () => ws.close();
  }, []);

  // Efecto para la simulación de pasos de la transacción Web3
  useEffect(() => {
    let timeout1, timeout2, timeout3;
    if (isTransacting) {
      setTxLoadingMessage('Construyendo Tx...');
      timeout1 = setTimeout(() => setTxLoadingMessage('Firmando Off-Chain...'), 800);
      timeout2 = setTimeout(() => setTxLoadingMessage('Enviando a Oracle DB...'), 1600);
      timeout3 = setTimeout(() => setTxLoadingMessage('Minando en Avalanche...'), 2400);
    }
    return () => {
      clearTimeout(timeout1);
      clearTimeout(timeout2);
      clearTimeout(timeout3);
    };
  }, [isTransacting]);

  // ==========================================
  // HANDLERS
  // ==========================================
  const handleOptimizeRoute = async (e) => {
    e.preventDefault();
    if (!origin || !destination) return;

    setIsRouting(true);
    setRouteError(null);
    setRouteData(null);

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/route/optimize?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`);
      
      if (!res.ok) throw new Error('No se pudo encontrar una ruta óptima entre estos puntos.');
      
      const data = await res.json();
      setRouteData(data);
      setOrigin('');
      setDestination('');
    } catch (err) {
      setRouteError(err.message || 'Error de conexión con el Agente IA.');
    } finally {
      setIsRouting(false);
    }
  };

  const handleBlockchainUpdate = async (e) => {
    e.preventDefault();
    if (!packageId || !newLocation) return;

    setIsTransacting(true);
    setTxError(null);
    setTxResult(null);

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/package/update`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': import.meta.env.VITE_API_SECRET_KEY
        },
        body: JSON.stringify({
          package_id: parseInt(packageId, 10),
          new_location: newLocation
        })
      });

      if (!res.ok) throw new Error('Fallo al minar la transacción en la red.');
      
      const data = await res.json();
      setTxResult(data);
    } catch (err) {
      setTxError(err.message || 'Error del Oráculo OCI/Avalanche.');
    } finally {
      setIsTransacting(false);
    }
  };

  const handleTrackPackage = async (e) => {
    e.preventDefault();
    if (!trackId) return;

    setIsTracking(true);
    setTrackError(null);
    setTrackResult(null);

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/package/${trackId}`);
      if (!res.ok) throw new Error('Paquete no encontrado en el Ledger de Oracle.');
      const data = await res.json();
      setTrackResult(data.data);
    } catch (err) {
      setTrackError(err.message);
    } finally {
      setIsTracking(false);
    }
  };

  // ==========================================
  // UI COMPONENTS
  // ==========================================
  return (
    <div className="min-h-screen bg-[#0A0E17] text-slate-300 font-sans selection:bg-cyan-500/30">
      
      {/* HEADER CORPORATIVO WEB3 */}
      <header className="border-b border-slate-800/60 bg-[#0F1423]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <svg className="w-11 h-11 drop-shadow-[0_0_12px_rgba(34,211,238,0.4)]" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#22D3EE" />
                  <stop offset="50%" stopColor="#2563EB" />
                  <stop offset="100%" stopColor="#EF4444" />
                </linearGradient>
              </defs>
              <path d="M140 340 C140 220, 220 140, 256 140 C292 140, 372 220, 372 340" stroke="url(#logoGrad)" strokeWidth="32" strokeLinecap="round"/>
              <path d="M180 370 C220 280, 292 280, 332 370" stroke="url(#logoGrad)" strokeWidth="24" strokeLinecap="round" opacity="0.8"/>
              <circle cx="256" cy="140" r="20" fill="#22D3EE" />
              <circle cx="140" cy="340" r="16" fill="#2563EB" />
              <circle cx="372" cy="340" r="16" fill="#EF4444" />
            </svg>
            <div>
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400 tracking-tight">
                Waterline Protocol
              </h1>
              <p className="text-xs text-slate-500 font-medium tracking-widest uppercase">dApp Logística Híbrida</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#EA4335]/10 border border-[#EA4335]/20">
              <span className="w-2 h-2 rounded-full bg-[#EA4335] animate-pulse"></span>
              <span className="text-xs font-semibold text-[#EA4335] tracking-wide">OCI Oracle DB Active</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              <span className="text-xs font-semibold text-cyan-400 tracking-wide">Avalanche C-Chain</span>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN GRID LAYOUT */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

          {/* ================================================== */}
          {/* CARD 1: AGENTE IA (ENRUTAMIENTO)                     */}
          {/* ================================================== */}
          <div className="bg-[#13192B] border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl relative hover:border-slate-700/80 hover:shadow-[0_0_40px_rgba(34,211,238,0.07)] transition-all duration-700">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            
            <div className="p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-blue-500/10 rounded-lg text-blue-400 border border-blue-500/20">
                  <BrainCircuit className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">Óptimizador de Rutas IA</h2>
                  <p className="text-sm text-slate-400">Calcula eficiencia logística global</p>
                </div>
              </div>

              <form onSubmit={handleOptimizeRoute} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                      <Map className="w-3.5 h-3.5" /> Puerto Origen
                    </label>
                    <select 
                      required
                      value={origin} 
                      onChange={e => setOrigin(e.target.value)}
                      className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium appearance-none cursor-pointer hover:border-blue-500/50 hover:bg-[#0f1423]"
                    >
                      <option value="" disabled>Seleccionar origen...</option>
                      {['CABA', 'Mar del Plata', 'Rosario', 'Córdoba', 'Salta', 'Shanghai', 'Rotterdam'].map(city => (
                        <option key={city} value={city} disabled={destination === city}>{city}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                      <MapPin className="w-3.5 h-3.5" /> Puerto Destino
                    </label>
                    <select 
                      required
                      value={destination} 
                      onChange={e => setDestination(e.target.value)}
                      className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium appearance-none cursor-pointer hover:border-blue-500/50 hover:bg-[#0f1423]"
                    >
                      <option value="" disabled>Seleccionar destino...</option>
                      {['CABA', 'Mar del Plata', 'Rosario', 'Córdoba', 'Salta', 'Shanghai', 'Rotterdam'].map(city => (
                        <option key={city} value={city} disabled={origin === city}>{city}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={isRouting}
                  className="w-full bg-blue-600/90 hover:bg-blue-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-[0_4px_20px_rgba(37,99,235,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-[0.98] transform-gpu"
                >
                  {isRouting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Route className="w-5 h-5" />}
                  {isRouting ? 'Procesando tensores...' : 'Calcular Ruta Óptima con IA'}
                </button>
              </form>

              {/* ESTADOS DE RESULTADO - IA */}
              {routeError && (
                <div className="mt-8 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 animate-in fade-in slide-in-from-bottom-2">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <p className="text-sm">{routeError}</p>
                </div>
              )}

              {routeData && !isRouting && (
                <div className="mt-8 p-6 bg-[#0A0E17] border border-slate-800 rounded-xl animate-in fade-in slide-in-from-bottom-2">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">Recomendación del Modelo</h3>
                  
                  <div className="flex flex-wrap gap-2 items-center mb-6">
                    {routeData.route?.map((r, idx) => (
                      <React.Fragment key={idx}>
                        <div className="px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 font-medium rounded-lg text-sm">
                          {r}
                        </div>
                        {idx < routeData.route.length - 1 && <span className="text-slate-600 font-black">→</span>}
                      </React.Fragment>
                    ))}
                  </div>

                  {/* MAPA INTERACTIVO */}
                  <div className="w-full h-64 rounded-xl overflow-hidden border border-slate-700/50 mb-6 relative z-0">
                    <MapContainer 
                      center={CITY_COORDS[routeData.route[0]] || [-34.6037, -58.3816]} 
                      zoom={4} 
                      scrollWheelZoom={false} 
                      className="w-full h-full"
                    >
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
                        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                      />
                      {routeData.route.map((city, idx) => {
                        const position = CITY_COORDS[city];
                        if (!position) return null;
                        return (
                          <Marker key={city} position={position}>
                            <Popup>
                              <strong className="text-slate-800">{city}</strong>
                              <p className="text-xs text-slate-500 m-0 leading-tight">Parada #{idx + 1}</p>
                            </Popup>
                          </Marker>
                        );
                      })}
                      {routeData.route.length > 1 && (
                        <Polyline 
                          positions={routeData.route.map(city => CITY_COORDS[city]).filter(Boolean)} 
                          pathOptions={{ color: '#22d3ee', weight: 4, dashArray: '10, 10' }} 
                        />
                      )}
                    </MapContainer>
                  </div>

                  <div className="grid grid-cols-2 gap-4 border-t border-slate-800/50 pt-5">
                    <div>
                      <p className="text-xs text-slate-500 uppercase mb-1">Distancia Total</p>
                      <p className="text-2xl font-mono text-white flex items-baseline gap-1">
                        {routeData.distance} <span className="text-sm text-slate-400 font-sans">km</span>
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 uppercase mb-1 flex items-center gap-1"><Clock className="w-3 h-3"/> ETA</p>
                      <p className="text-2xl font-mono text-white flex items-baseline gap-1">
                        {routeData.time} <span className="text-sm text-slate-400 font-sans">hrs</span>
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ================================================== */}
          {/* CARD 2: ORÁCULO WEB3 (AVALANCHE + OCI)               */}
          {/* ================================================== */}
          <div className="bg-[#13192B] border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl relative hover:border-slate-700/80 hover:shadow-[0_0_40px_rgba(34,211,238,0.07)] transition-all duration-700">
            {/* Ambient Red/Cyan subtle glow */}
            <div className="absolute top-0 right-0 w-full h-1 bg-gradient-to-r from-cyan-400 via-blue-500 to-[#EA4335]"></div>
            
            <div className="p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-cyan-500/10 rounded-lg text-cyan-400 border border-cyan-500/20">
                  <Package className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">Oráculo Web3 Ledger</h2>
                  <p className="text-sm text-slate-400">Inyección Blockchain & Oracle DB</p>
                </div>
              </div>

              <form onSubmit={handleBlockchainUpdate} className="space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Identificador (ID Paquete)</label>
                  <input 
                    type="number" required
                    value={packageId} onChange={e => setPackageId(e.target.value)}
                    placeholder="Ej. 994021"
                    className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-cyan-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-mono text-lg transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Lectura de Ubicación</label>
                  <input 
                    type="text" required
                    value={newLocation} onChange={e => setNewLocation(e.target.value)}
                    placeholder="Coordenadas o Ciudad actual"
                    className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all font-medium"
                  />
                </div>

                <button 
                  type="submit" 
                  disabled={isTransacting}
                  className="w-full relative overflow-hidden bg-cyan-600/90 hover:bg-cyan-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-[0_4px_20px_rgba(34,211,238,0.2)] disabled:opacity-80 disabled:cursor-not-allowed group hover:scale-[1.02] active:scale-[0.98] transform-gpu"
                >
                  {isTransacting ? (
                    <div className="flex items-center justify-center gap-3 relative z-10 w-full">
                       <Loader2 className="w-5 h-5 text-cyan-200 animate-spin" />
                       <span className="w-52 text-left">{txLoadingMessage}</span>
                    </div>
                  ) : (
                    <span className="flex items-center justify-center gap-2">Firmar Transacción y Registrar</span>
                  )}
                  {/* Animación de carga progresiva simulada en el fondo del botón */}
                  {isTransacting && <div className="absolute top-0 left-0 h-full bg-cyan-400/20 animate-[pulse_1.5s_ease-in-out_infinite] w-full"></div>}
                </button>
              </form>

              {/* ESTADOS DE RESULTADO - BLOCKCHAIN */}
              {txError && (
                <div className="mt-8 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 animate-in fade-in slide-in-from-bottom-2">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <p className="text-sm">{txError}</p>
                </div>
              )}

              {txResult && !isTransacting && (
                <div className="mt-8 bg-[#0A0E17] border border-emerald-500/30 rounded-xl p-5 shadow-[0_0_15px_rgba(16,185,129,0.05)] animate-in fade-in slide-in-from-bottom-2">
                  <div className="flex items-center gap-3 mb-4">
                    <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                    <div>
                      <h3 className="text-emerald-500 font-bold text-sm">Registro Web3 Exitoso</h3>
                      <p className="text-slate-400 text-xs">{txResult.message || 'Sincronizado con Oracle DB & Avalanche'}</p>
                    </div>
                  </div>
                  
                  <div className="bg-[#13192B] rounded-lg p-3 border border-slate-800">
                    <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Transaction Hash (TxID)</p>
                    <a 
                      href={`https://testnet.snowtrace.io/tx/${txResult.tx_hash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400 font-mono text-sm break-all font-semibold hover:underline flex items-center gap-1"
                    >
                      {txResult.tx_hash}
                      <LinkIcon className="w-3 h-3 inline" />
                    </a>
                  </div>
                  {txResult.encrypted_location_ciphertext && (
                    <div className="bg-[#13192B] rounded-lg p-3 border border-slate-800 mt-2">
                      <p className="text-[10px] text-purple-400 uppercase tracking-widest mb-1">Dato Privado Cifrado (EncryptedERC)</p>
                      <p className="text-slate-400 font-mono text-xs break-all">
                        {txResult.encrypted_location_ciphertext}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ================================================== */}
          {/* CARD 3: PORTAL DE TRAZABILIDAD (TRACKING)            */}
          {/* ================================================== */}
          <div className="bg-[#13192B] border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl relative lg:col-span-2 hover:border-slate-700/80 hover:shadow-[0_0_40px_rgba(34,211,238,0.07)] transition-all duration-700">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500 to-pink-600"></div>
            
            <div className="p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-purple-500/10 rounded-lg text-purple-400 border border-purple-500/20">
                  <Database className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">Portal de Trazabilidad RWA</h2>
                  <p className="text-sm text-slate-400">Consulta histórica en Oracle DB Ledger</p>
                </div>
              </div>

              <form onSubmit={handleTrackPackage} className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <input 
                    type="number" required
                    value={trackId} onChange={e => setTrackId(e.target.value)}
                    placeholder="Ingrese el ID del paquete..."
                    className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all font-mono text-lg"
                  />
                </div>
                <button 
                  type="submit" 
                  disabled={isTracking}
                  className="bg-purple-600/90 hover:bg-purple-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all shadow-[0_4px_20px_rgba(168,85,247,0.2)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 whitespace-nowrap hover:scale-[1.02] active:scale-[0.98] transform-gpu"
                >
                  {isTracking ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                  Consultar Ledger
                </button>
              </form>

              {trackError && (
                <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 animate-in fade-in slide-in-from-bottom-2">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <p className="text-sm">{trackError}</p>
                </div>
              )}

              {trackResult && !isTracking && (
                <div className="mt-8 bg-[#0A0E17] border border-purple-500/30 rounded-xl p-6 shadow-[0_0_15px_rgba(168,85,247,0.05)] animate-in fade-in slide-in-from-bottom-2">
                  <h3 className="text-purple-400 font-bold text-sm uppercase tracking-widest mb-4 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Registro Encontrado
                  </h3>
                  
                  <div className="space-y-4">
                    {trackResult.history ? (
                      <div className="relative border-l border-purple-500/30 ml-3 space-y-6 mt-6">
                        {trackResult.history.map((step, idx) => (
                          <div key={idx} className="relative pl-6">
                            <div className={`absolute -left-1.5 top-1.5 w-3 h-3 border-2 border-purple-500 rounded-full shadow-[0_0_8px_rgba(168,85,247,0.8)] ${idx === trackResult.history.length - 1 ? 'bg-purple-500 animate-pulse shadow-[0_0_15px_rgba(168,85,247,1)]' : 'bg-[#0A0E17]'}`}></div>
                            <div className="bg-[#13192B] rounded-lg p-4 border border-slate-800 transition-all hover:border-purple-500/50">
                              <div className="flex items-center justify-between mb-2">
                                <p className="text-[10px] text-purple-400 uppercase tracking-widest">
                                  Paso {idx + 1} {idx === trackResult.history.length - 1 && "(Actual)"}
                                </p>
                              </div>
                              <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Ubicación Cifrada (Oracle DB)</p>
                              <p className="text-slate-300 font-mono text-xs break-all mb-3">
                                {step.location}
                              </p>
                              <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">TxHash On-Chain (Avalanche)</p>
                              <a 
                                href={`https://testnet.snowtrace.io/tx/${step.tx_hash}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-cyan-400 font-mono text-xs break-all font-semibold hover:underline flex items-center gap-1 w-fit"
                              >
                                {step.tx_hash}
                                <LinkIcon className="w-3 h-3 inline" />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-[#13192B] rounded-lg p-4 border border-slate-800">
                          <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Última Ubicación Cifrada (Oracle DB)</p>
                          <p className="text-slate-300 font-mono text-sm break-all">
                            {trackResult.current_location}
                          </p>
                        </div>
                        <div className="bg-[#13192B] rounded-lg p-4 border border-slate-800">
                          <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">TxHash On-Chain (Avalanche)</p>
                          <a 
                            href={`https://testnet.snowtrace.io/tx/${trackResult.last_tx_hash}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan-400 font-mono text-sm break-all font-semibold hover:underline flex items-center gap-1 w-fit"
                          >
                            {trackResult.last_tx_hash}
                            <LinkIcon className="w-4 h-4 inline" />
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </main>

      {/* NOTIFICACIÓN WEBSOCKET FLOTANTE */}
      {latestIoTUpdate && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-right-8 fade-in duration-300">
          <div className="bg-[#13192B]/95 backdrop-blur-md border-l-4 border-emerald-500 rounded-lg shadow-[0_10px_40px_rgba(16,185,129,0.15)] p-4 max-w-sm">
            <h4 className="text-emerald-400 font-bold text-xs uppercase tracking-wider mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Evento IoT Detectado
            </h4>
            <p className="text-sm text-white mb-1">
              Paquete <span className="font-mono text-emerald-300">#{latestIoTUpdate.package_id}</span> actualizó ubicación a <strong>{latestIoTUpdate.new_location}</strong>.
            </p>
            <p className="text-[10px] text-slate-500 font-mono break-all truncate">
              Tx: {latestIoTUpdate.tx_hash}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
