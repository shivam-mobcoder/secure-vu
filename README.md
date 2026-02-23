# 🚀 AI Surveillance System (YOLO + ArcFace + WebRTC)

Real-time person & animal detection, face recognition, and ROI-based alerts using YOLOv8, ArcFace, DeepSORT, and WebRTC.

---

## ✨ Features

- **Real-time Detection**: People + 17 animal types (cat, dog, bird, snake, reptile, horse, rabbit, etc.)
- **Face Recognition**: ArcFace with persistent identity database
- **ROI Alerts**: Configurable zones with entry/exit detection
- **WebRTC Streaming**: Low-latency video with DataChannel alerts
- **Production Ready**: GPU/CPU switch, modular architecture
- **Alert System**: Real-time notifications via WebRTC DataChannel

---

## 🏗️ Project Structure

\`\`\`
object-detection-main/
├── server.py                    # Main production server
├── requirements.txt             # Python dependencies
├── runtime.txt                  # Python 3.10.12
├── render.yaml                  # Render.com deployment config
├── .gitignore                  # Git ignore patterns
├── cert.pem                    # SSL certificate
├── key.pem                     # SSL key
├── tracker_id_map.json         # Tracker persistence
├── static/                     # Frontend
│   ├── index.html             # Main interface
│   ├── css/                   # Stylesheets
│   └── js/                    # JavaScript modules
├── server_pkg/                 # Backend modules
│   ├── models.py              # Model loading (GPU/CPU switch)
│   ├── processing.py          # Frame processing
│   ├── webrtc.py              # WebRTC handlers
│   ├── alerts.py              # Alert system
│   ├── routes.py              # HTTP routes
│   └── utils.py               # Utilities
├── models/                     # Trained models
│   ├── yolo/best.pt           # YOLOv8 (17 animals + person)
│   ├── arcface/face_db.npz    # Face recognition database
│   └── roi/                   # ROI configurations
└── yolo_51/code/modules/      # Face recognition library
\`\`\`

---

## 🚀 Quick Start (Development)

### 1. Clone & Setup
\`\`\`bash
git clone https://gitlab.com/hardik477/object-detection.git
cd object-detection-main
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
\`\`\`

### 2. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 3. Generate SSL Certificates
\`\`\`bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
\`\`\`

### 4. Start Server
\`\`\`bash
cd app
source ../.venv/bin/activate
python server.py
\`\`\`

### 5. Open in Browser
\`\`\`
https://localhost:8000
\`\`\`

---

## 🧭 Super Admin React Dashboard (Run Guide)

The React app lives in frontend/superadmin-react and is mounted by the backend at:

https://localhost:8000/super-admin/dashboard

### Option A: Production-style (recommended)

1) Build React frontend
\`\`\`bash
cd frontend/superadmin-react
npm install
npm run build
\`\`\`

2) Start backend server
\`\`\`bash
cd app
source ../.venv/bin/activate
python server.py
\`\`\`

3) Open dashboard
\`\`\`
https://localhost:8000/super-admin/dashboard
\`\`\`

### Option B: Frontend dev mode (hot reload)

Keep backend running from app/server.py, then in a second terminal:

\`\`\`bash
cd frontend/superadmin-react
npm run dev
\`\`\`

Open:

http://localhost:5173/super-admin/dashboard

### Notes

- If browser warns about certificate, use Advanced → Proceed (self-signed local cert).
- The clients page uses /api/super-admin/clients, so backend and login must be active.

---

## 🎮 Usage Modes

### 🔵 **Device Mode** (PM Mode)
- Uses **your device camera** via WebRTC
- Server processes frames on GPU/CPU
- Real-time alerts in browser

### 🔴 **CCTV Mode** (Test Mode)
- Server uses **local webcam** (camera index 0)
- For testing without device camera

### 🟡 **ROI Management**
1. Click **Edit ROI** to draw zone
2. Drag/resize rectangle
3. Click **Save** to persist
4. Alerts trigger on: \`ENTERED WEBROI\`, \`EXITED WEBROI\`

---

## ⚙️ Configuration

### GPU/CPU Switching
\`\`\`bash
# Use GPU (default)
cd app && source ../.venv/bin/activate && python server.py

# Force CPU mode
cd app && source ../.venv/bin/activate && USE_GPU=false python server.py

# Force CPU (override)
cd app && source ../.venv/bin/activate && FORCE_CPU=true python server.py
\`\`\`

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| \`USE_GPU\` | \`true\` | Enable/disable GPU acceleration |
| \`FORCE_CPU\` | \`false\` | Force CPU mode (overrides USE_GPU) |
| \`PORT\` | \`8000\` | Server port |

---

## 🚀 Production Deployment (Render.com)

### 1. Update Files
Ensure you have:
- \`requirements.txt\` - Dependencies
- \`runtime.txt\` - Python 3.10.12
- \`render.yaml\` - Render configuration
- \`.gitignore\` - Exclude cache files

### 2. Push to Git
\`\`\`bash
git add .
git commit -m "Production ready"
git push origin main
\`\`\`

### 3. Deploy on Render
1. Go to [render.com](https://render.com)
2. Create **New Web Service**
3. Connect your GitHub/GitLab repository
4. Auto-configures from \`render.yaml\`
5. Starts with **CPU mode** (\`USE_GPU=false\`)

### 4. Upgrade to GPU (Optional)
1. Change plan to \`standard-gpu\`
2. Update environment: \`USE_GPU=true\`
3. Restart service

---

## 🔧 Troubleshooting

### ❌ No Video/Audio
- Ensure HTTPS (\`https://localhost:8000\`)
- Check browser console for WebRTC errors
- Verify SSL certificates exist

### ❌ No Alerts
- Check DataChannel connection in browser console
- Verify server logs: \`DataChannel from client: alerts\`
- Ensure ROI is defined and visible

### ❌ Model Loading Failures
\`\`\`bash
# Test model loading
python3 -c "from server_pkg.models import load_models; load_models()"
\`\`\`

### ❌ CUDA Errors on Render
- Set \`USE_GPU=false\` for CPU-only plans
- Render standard plans don't include GPU
- Upgrade to \`standard-gpu\` plan for GPU acceleration

---

## 📊 Model Information

### YOLO Model (\`best.pt\`)
- **Classes**: 18 total (person + 17 animals)
- **Animals**: cat, dog, bird, snake, reptile, horse, rabbit, ferret, raccoon, turtle, tortoise, scorpion, spider, mouse, hamster, rat, guinea_pig
- **Performance**: ~27ms/frame (GPU), ~200ms/frame (CPU)

### Face Recognition
- **Model**: InsightFace Buffalo_L
- **Database**: \`models/arcface/face_db.npz\`
- **Identities**: 'shivam' (add more via face registration)

---

## 📝 License

Proprietary – for internal use only.

---

## 🔗 Links
- **Repository**: https://github.com/Shivam-432-bit/object-detection-main.git
- **Live Demo**: [Your Render URL after deployment]
- **Issues**: https://github.com/Shivam-432-bit/object-detection/-/issues
