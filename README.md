# 👗 FashionistAI

**Application de prise de mesures corporelles avec détection de pose IA (YOLO v8)**

FashionistAI utilise la détection de pose par intelligence artificielle pour calculer automatiquement les mensurations corporelles à partir d'une simple photo.

## 🎯 Fonctionnalités

- 📸 **Capture photo** : PC (webcam) ou Mobile (via QR Code)
- 🤖 **Détection de pose IA** : YOLOv8-Pose (17 points clés du corps)
- 📏 **Calcul automatique** : Mensurations réelles basées sur la taille
- �� **Architecture moderne** : TypeScript + Python + React
- 🔄 **Temps réel** : WebSocket (Socket.IO)

## 🚀 Installation

### Prérequis

- Node.js 18+ 
- Python 3.10 ou 3.11
- npm
- PyTorch < 2.6

### Installation

```powershell
.\setup.ps1
```

## 🎮 Utilisation

```powershell
.\run.ps1
```

**Accès :** http://localhost:3000

## 📊 Logs

```powershell
Get-Content logs\backend.log -Wait
Get-Content logs\python.log -Wait
Get-Content logs\frontend.log -Wait
```

## 🛠️ Développement

```bash
npm run dev           # Backend (watch mode)
cd frontend && npm start  # Frontend
```

## 📄 Licence

MIT
