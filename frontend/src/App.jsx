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
  Route
} from 'lucide-react';

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
        headers: { 'Content-Type': 'application/json' },
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

  // ==========================================
  // UI COMPONENTS
  // ==========================================
  return (
    <div className="min-h-screen bg-[#0A0E17] text-slate-300 font-sans selection:bg-cyan-500/30">
      
      {/* HEADER CORPORATIVO WEB3 */}
      <header className="border-b border-slate-800/60 bg-[#0F1423]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_20px_rgba(34,211,238,0.3)]">
              <LinkIcon className="text-white w-5 h-5" />
            </div>
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
          <div className="bg-[#13192B] border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl relative">
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
                    <input 
                      type="text" required
                      value={origin} onChange={e => setOrigin(e.target.value)}
                      placeholder="Ej. Shanghai"
                      className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                      <MapPin className="w-3.5 h-3.5" /> Puerto Destino
                    </label>
                    <input 
                      type="text" required
                      value={destination} onChange={e => setDestination(e.target.value)}
                      placeholder="Ej. Róterdam"
                      className="w-full bg-[#0A0E17] border border-slate-700/50 rounded-xl px-4 py-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium"
                    />
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={isRouting}
                  className="w-full bg-blue-600/90 hover:bg-blue-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-[0_4px_20px_rgba(37,99,235,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
          <div className="bg-[#13192B] border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl relative">
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
                  className="w-full relative overflow-hidden bg-cyan-600/90 hover:bg-cyan-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-[0_4px_20px_rgba(34,211,238,0.2)] disabled:opacity-80 disabled:cursor-not-allowed group"
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
                    <p className="text-cyan-400 font-mono text-sm break-all font-semibold">
                      {txResult.tx_hash}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
