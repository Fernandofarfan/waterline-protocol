# 🌊 Waterline Protocol - Frontend Dashboard
### React + Vite Modern Logistical User Interface

This directory contains the user dashboard application for the **Waterline Protocol**, built on top of **React** and bundled using **Vite**. The frontend enables real-time visual tracking of real-world assets (RWA), triggers smart contract updates via the backend gateway, and queries the AI Routing Agent for logistical path optimization.

---

## 🎨 Features
* **Real-time Map/Status Viewer**: Input a Package ID to trace its location and locate the exact Avalanche transaction hash.
* **Smart-Contract Location Trigger**: Push updates to the Avalanche Fuji ledger from an interactive UI form.
* **AI Path Optimizer**: Connects with the Python Dijkstra backend to visualize optimal routes between CABA, Mar del Plata, Rosario, Córdoba, and Salta.
* **Premium UX/UI**: Clean layout, modern gradients, interactive indicators, and smooth state updates.

---

## 🛠️ Local Configuration & Setup

### 1. Prerequisites
Ensure you have the following installed on your machine:
* **Node.js** (v18.0.0 or higher is highly recommended)
* **npm** (Node Package Manager)

### 2. Environment Setup
Create a new `.env` configuration file in this directory by copying the example template:
```bash
cp .env.example .env
```
Ensure your environment variable points to the active FastAPI backend service. The default local setup is:
```env
VITE_API_URL=http://localhost:8000
VITE_API_SECRET_KEY=dev_api_key_change_me
```

### 3. Dependency Installation
Install all required Node modules and dependencies by running:
```bash
npm install
```

### 4. Running the Development Server
Launch the local development server with Hot Module Replacement (HMR):
```bash
npm run dev
```
Once initialized, the console will output the active local URL, typically **`http://localhost:5173`**. Open it in your browser to interact with the system.

---

## 📦 Build for Production
To generate an optimized production bundle, execute:
```bash
npm run build
```
This builds static assets ready to be served from any static hosting provider (OCI Object Storage, Vercel, Netlify, etc.) inside the `dist/` directory.
