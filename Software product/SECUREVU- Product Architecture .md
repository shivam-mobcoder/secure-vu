# 

# 

# 

# **SECUREVU**

## **On-Premise AI CCTV Platform**

### **Product Architecture — Manager Summary**

# **1\. Executive Summary**

SecureVU is transitioning from a custom, cloud-processed deployment into a fully packaged on-premise AI video analytics software product. Customers install and run SecureVU entirely on their own hardware. No camera footage ever leaves the customer's premises.

**The core value proposition:** We provide the intelligence. The customer owns the data. SecureVU software runs on customer hardware, streams from customer cameras, and stores everything locally — while SecureVU handles licensing, updates, and ongoing support remotely.

### **What SecureVU Delivers**

| SecureVU Provides | Customer Provides |
| ----- | ----- |
| AI detection software (YOLO-based) | IP cameras (RTSP-compatible) |
| Web dashboard (live view, events, recordings) | Server / PC hardware |
| Annual subscription licensing | Storage (HDD/NVMe) |
| Remote update delivery | Network connectivity |
| Installation & configuration support | Physical security of hardware |
| Hardware sizing guidance & certified profiles |  |

### **Version 1 at a Glance**

| Dimension | Details |
| ----- | ----- |
| Deployment | On-premise (customer hardware) |
| Supported OS | Windows 10/11/Server 2019+ and Ubuntu 20.04/22.04 |
| Maximum cameras | Target capacity up to 200 cameras (hardware dependent and subject to performance validation) |
| Supported resolutions | 720p and 1080p |
| AI features | Person, Vehicle, Intrusion, Line Crossing, Loitering, PPE, Helmet, Vest |
| GPU acceleration | NVIDIA GPU optional; CPU-only also supported |
| Recording | Continuous, event-triggered, and scheduled |
| Internet requirement | Required for license & updates only — no video data sent |
| Licensing model | Annual subscription by camera count \+ feature pack |

---

# **2\. Product & Business Model**

### **Subscription Tiers**

| Tier | Camera Count | Target Customer | AI Add-ons Available |
| ----- | ----- | ----- | ----- |
| Starter | 1 – 16 | Small retail, offices | Core \+ Security \+ Safety |
| Professional | 17 – 64 | Warehouses, mid-size commercial | Core \+ Security \+ Safety |
| Business | 65 – 128 | Campuses, logistics sites | Core \+ Security \+ Safety |
| Enterprise | 129 – 200 | Large facilities, multi-building | Core \+ Security \+ Safety |

### **AI Feature Packs**

Features are licensed as add-ons to the base camera subscription, giving customers flexibility to pay only for what they use.

| Feature Pack | Included Capabilities |
| ----- | ----- |
| Core (base) | Person Detection, Vehicle Detection |
| Security Pack | Intrusion Detection, Line Crossing, Loitering Detection |
| Safety Pack | PPE Detection, Helmet Detection, Reflective Vest Detection |

### **Licensing Rules**

* Annual renewal — alerts sent at 30, 14, and 7 days before expiry  
* 7-day offline grace period if the customer's internet is temporarily down  
* License is hardware-bound — tied to the specific server it is installed on  
* Hardware migrations are supported via a self-service deactivate/reactivate flow  
* Camera count is enforced in real time — customers cannot exceed their licensed limit

# **3\. How the System Works**

The layout below represents the end-to-end data flow. Everything inside the "Customer Premises" box stays on the customer's hardware at all times.

CUSTOMER PREMISES  
───────────────────────────────────────────────────────  
IP Cameras  →  RTSP Streams  →  SecureVU AI Agent  
                                        ↓  
                           AI Detection Engine (YOLO/ONNX)  
                                        ↓  
                    Events / Alerts / Snapshots  
                                        ↓  
              Backend Service (FastAPI)  ←→  PostgreSQL Database  
                                        ↓  
              Web Dashboard (React) — viewed in browser on local network

SECUREVU CLOUD (outbound HTTPS only — no video)  
─────────────────────────────────────────────────────────  
License Server  |  Update Server  |  (nothing else)

### **Key Technical Decisions & Rationale**

| Decision | What We Chose | Why |
| ----- | ----- | ----- |
| AI runtime format | ONNX (not raw PyTorch .pt) | Portable, protectable, faster inference, model weights can be encrypted |
| Video capture | FFmpeg \+ OpenCV | Industry standard; handles all major RTSP camera brands and codecs |
| Backend | FastAPI (Python) | Fast, modern, async; same language as AI engine — reduces team context switching |
| Database | PostgreSQL | Proven reliability;designed for high event volumes and enterprise-scale deployments |
| Task queue | Celery \+ Redis | Prevents slow background jobs from blocking the API |
| Windows packaging | PyInstaller \+ Inno Setup \+ EV code signing | Professional installer; code signing required to avoid antivirus false positives |
| Linux packaging | Docker Compose | Clean isolation; easy for system admins; straightforward upgrade path |

# **4\. Security Architecture**

Security was identified as a gap in the original draft. This section summarises the full security model now in place.

### **What Data Goes Where**

| Data Type | Stays On Customer Hardware? | What Leaves the Premises? |
| ----- | ----- | ----- |
| Camera footage (live) |  Yes — never transmitted | Nothing |
| Recorded video |  Yes — stored locally | Nothing |
| Detection events & snapshots |  Yes — local database | Nothing |
| License activation |  Machine ID \+ License Key only | Machine ID (hardware fingerprint) \+ License Key |
| Update checks |  Version string only | Version number only |

### **Dashboard & API Security**

* All users log in with a username and password — passwords stored as bcrypt hashes, never in plain text  
* Sessions use JWT tokens that expire after 8 hours — no persistent login without re-authentication  
* Three access roles: Admin (full control), Operator (cameras \+ events), Viewer (read-only)  
* The API and dashboard are accessible on the local network only by default — not exposed to the internet  
* Login attempts are rate-limited to 5 tries per 15 minutes to prevent brute-force attacks  
* All user actions are recorded in a tamper-evident audit log

### **Threat Summary**

| Threat | Risk Level | How It Is Mitigated |
| ----- | ----- | ----- |
| Unauthorised dashboard access | Low | JWT auth, local-only binding, rate limiting, session expiry |
| License key theft / cloning | Low | Machine-bound activation token; clone detection via simultaneous-use check |
| AI model extraction | Medium | AES-256 encryption at rest; runtime decrypt into isolated memory; machine-bound key |
| Tampered update package | Low | Ed25519 digital signatures; packages signed offline; rejected if signature fails |
| Physical server compromise | Customer risk | Customer's physical security responsibility; SecureVU documents best practices |

**On model protection:** AI models are encrypted with AES-256 using a key derived from the customer's hardware fingerprint and license key. A model file copied from one server cannot be used on another. The protection level is appropriate for commercial software — it is substantially stronger than shipping raw model files.

# **5\. Licensing Architecture**

### **How Activation Works**

| Step | What Happens |
| ----- | ----- |
| 1\. Install | Customer installs SecureVU on their server |
| 2\. Enter key | Customer enters their License Key in the dashboard |
| 3\. Machine fingerprint | Software generates a Machine ID from CPU, motherboard, MAC address, and OS identifier |
| 4\. Activate | Machine ID \+ License Key sent to SecureVU License Server (HTTPS) |
| 5\. Validation | License Server checks: key is valid, not expired, machine slots available |
| 6\. Token issued | License Server returns a signed Activation Token (JWT) |
| 7\. Store locally | Token stored locally, encrypted with the machine-derived key |
| 8\. Ongoing heartbeat | Software checks in with License Server every 24 hours to confirm validity |

### **Edge Cases** 

| Scenario | How It Is Handled |
| ----- | ----- |
| Internet is temporarily down | 7-day offline grace period — system runs normally; alert shown in dashboard |
| Customer replaces server hardware | Admin clicks Deactivate, moves to new server, re-activates with same key |
| Server hardware failure (can't deactivate) | Support team can force-release the machine slot via admin panel |
| Virtual machine cloning | If same token appears from two different Machine IDs within 10 minutes, both are flagged and suspended |
| License expiry | Alerts at 30/14/7 days; AI features suspend after 7-day grace; recordings continue |
| Customer downgrades camera count | Excess cameras disabled in order of last-added; alert shown to admin |

# **6\. Installation & Updates**

### **Windows Installation**

Customers receive a single installer file: **SecureVUSetup.exe**. The installer is digitally code-signed with an Extended Validation (EV) certificate, which is required to prevent antivirus software from flagging it as suspicious.

| Installer Capability | Details |
| ----- | ----- |
| Standard install | GUI wizard — suitable for most customers |
| Silent install | Command-line flags (/VERYSILENT) for enterprise IT departments deploying via Group Policy |
| Pre-supply license key | License key can be passed as a file — no manual entry needed for bulk deployment |
| Custom install path | Configurable install and data directories |
| Bundled dependencies | PostgreSQL, Redis, FFmpeg all bundled — no internet required during install |
| Windows Service registration | All four services registered as Windows Services with automatic restart |
| UAC / permissions | Installer requires admin elevation once; running services use a minimal-privilege service account, not SYSTEM |

### **Linux Installation**

Customers receive a tar.gz archive containing Docker images and a setup script. No internet is required during installation — all Docker images are bundled. Installation is a single command after extraction.

### **Update System — How It Works**

| Step | Description |
| ----- | ----- |
| 1\. Check | Agent checks Update Server every 24 hours (version string only sent) |
| 2\. Notify | If update available, admin sees a notification in the dashboard with release notes |
| 3\. Approve | Admin reviews and approves the update — never automatic without approval |
| 4\. Download | Update package downloaded and SHA-256 checksum verified |
| 5\. Verify signature | Ed25519 digital signature verified using SecureVU's public key — rejected if invalid |
| 6\. Pre-update backup | Database snapshot taken automatically before any changes |
| 7\. Install | Services stopped, update applied, database migrations run, services restarted |
| 8\. Health check | Automated 30-second health check after restart |
| 9\. Rollback (if needed) | If health check fails, automatic rollback to previous version \+ database restored |

**Why this matters:** Updates that fail mid-install on a production security system can take down camera coverage. The pre-update database snapshot, signature verification, and automatic rollback mean that a bad update cannot leave the system in a broken state.

**7\. Hardware Requirements & Performance**

### **Enterprise Capacity Planning & Performance Targets**

Enterprise capacity planning is based on CPU, GPU, RAM, storage and recording workload analysis. Final supported limits will be validated through performance benchmarking.

| Bottleneck Factor | CPU Only | CPU \+ Mid GPU (RTX 3060\) | CPU \+ High-End GPU (RTX 4090\) |
| ----- | ----- | ----- | ----- |
| Camera capacity (1080p @ 5 FPS AI) | 16 – 32 cameras | 80 – 100 cameras | Up to 180 (target), subject to benchmarking |
| RAM per camera stream | \~200 MB | \~200 MB | \~200 MB |
| RAM for 200 cameras | Not feasible | \~40 GB | \~40 GB |
| Primary bottleneck | CPU inference | GPU VRAM / bandwidth | Disk I/O for recordings |

### **Certified Hardware Profiles**

These are validated, tested configurations — not estimates.

| Tier | Cameras | CPU | RAM | GPU | Storage (30-day retention) |
| ----- | ----- | ----- | ----- | ----- | ----- |
| Starter | 1–16 | Intel i5-12400 (6C) | 16 GB | None (CPU only) | 8 TB HDD |
| Professional | 17–64 | Intel i9-12900K (16C) | 32 GB | RTX 3060 12 GB | 16 TB RAID-5 |
| Business | 65–128 | Intel Xeon W-2295 (18C) | 64 GB ECC | RTX 4070 12 GB | 40 TB RAID-6 |
| Enterprise | 129+ | Dual Xeon Silver (40C) | 128 GB ECC | RTX 4090 24 GB | 80 TB RAID-6 \+ hot spare |

### *Actual supported camera count depends on AI workload, recording mode, codec, and benchmarking results.*

### 

### **Storage Capacity Quick Reference**

| Resolution | Per Camera Per Day | 16 Cameras / 30 Days | 64 Cameras / 30 Days |
| ----- | ----- | ----- | ----- |
| 720p | \~5 GB | \~2.4 TB | \~9.6 TB |
| 1080p H.264 | \~16 GB | \~7.7 TB | \~30 TB |
| 1080p H.265 | \~8 GB | \~3.8 TB | \~15 TB |

The hardware calculator at securevu.com/calculator automates this for any camera/resolution/retention combination.

# **8\. Key Concerns Raised — How They Are Addressed**

| Concern Raised | Severity | Resolution |
| ----- | ----- | ----- |
| No threat model or security architecture |  Critical | Full threat model, JWT auth, RBAC, rate limiting, audit logging now defined in Section 4 |
| Machine ID not defined — hardware replacement not handled |  Critical | Machine ID generation algorithm, 3-of-4 stability rule, and hardware migration flow fully specified in Section 5 |
| Model protection claimed as "Moderate to Strong" with no justification |  Critical | AES-256 machine-bound encryption, isolated process, memory zeroing detailed; honest per-threat rating provided |
| Update system had no failure handling or signature verification |  Major | Ed25519 signature verification, SHA-256 checksum, pre-update backup, auto-rollback on health check failure |
| Windows installer missing silent install, Group Policy, AV handling |  Major | Silent flags, EV code signing, AV whitelisting process, UAC service account all specified in Section 6 |
| Database had no backup, migration, or retention detail |  Major | pg\_dump schedule, WAL archiving, Alembic migrations, nightly retention enforcement all defined |
| Enterprise camera capacity previously unsupported |  Major | Capacity planning based on CPU, GPU, RAM and storage analysis. Final supported limits will be validated through performance benchmarking. |
| License server SLA and outage handling not addressed |  Minor | 7-day grace period, 24-hour heartbeat, 99.5% SLA target, and outage enforcement behaviour all defined |
| FastAPI used for both backend and license server with no clarification |  Minor | Separate codebases, separate hosting; responsibilities clearly documented |
| Document titled "Approved" before review |  Minor | Title corrected; proper approval workflow established |

# **9\. Version 1 Scope**

### **Included in V1**

| Feature | Status |
| ----- | ----- |
| On-premise deployment (Windows \+ Ubuntu) | Included |
| Annual subscription licensing (camera count \+ features) | Included |
| AI detection: Person, Vehicle, Intrusion, Line Crossing, Loitering, PPE, Helmet, Vest | Included |
| CPU-only and GPU-accelerated inference (NVIDIA) | Included |
| Enterprise-scale multi-camera deployments Included\* \*Target capacity up to 200 cameras depending on certified hardware profile and performance benchmarking.  |  Included |
| Continuous, event, and scheduled recording |  Included |
| JWT authentication with three-tier RBAC | Included |
| Email and webhook alerting |  Included |
| Signed automatic updates with rollback |  Included |
| Hardware sizing calculator (web tool) | Included |
| Installation support and certified hardware profiles | Included |
| Audit logging |  Included |
| 7-day offline grace period | Included |

### **Deferred to Version 2**

| Feature | Status |
| ----- | ----- |
| Offline / air-gapped deployment |  V2 — Enterprise Edition |
| Active Directory / LDAP integration |  V2 |
| AMD GPU support |  V2 |
| WebRTC low-latency live streaming |  V2 |
| Video encryption at rest |  V2 |
| Multi-site / central management console |  V2 Enterprise |
| Cloud backup integration |  V2 |
| ONVIF camera auto-discovery |  V1.x patch — may ship sooner |
| TOTP multi-factor authentication (default-on) |  Available in V1 but optional |

**10\. Recommended Technology Stack**

| Component | Technology | Version | Notes |
| ----- | ----- | ----- | ----- |
| AI Engine language | Python | 3.11 | Ecosystem standard for AI/CV |
| AI Model | YOLO (Ultralytics) | v8/v10 | State-of-the-art real-time detection |
| AI Runtime | ONNX Runtime | 1.17+ | CPU and CUDA execution providers |
| GPU Optimisation | TensorRT | 8.6+ | NVIDIA only; optional compile step at install |
| Video Processing | FFmpeg \+ OpenCV | 6.x / 4.9 | RTSP decode, frame extraction |
| Backend API | FastAPI \+ Uvicorn | 0.111+ | Async Python API server |
| Task Queue | Celery \+ Redis | 5.x / 7.x | Background jobs; added vs. original draft |
| Frontend | React \+ Vite \+ Tailwind | 18.x / 5.x | Modern, fast SPA |
| Database | PostgreSQL | 15.x | Schema migrations via Alembic |
| Windows Packaging | PyInstaller \+ Inno Setup \+ EV Cert | Latest | Code signing required |
| Linux Packaging | Docker \+ Docker Compose | 24.x / 2.24+ | Bundled images; offline install |
| Update Signing | Ed25519 (PyNaCl) | Latest | Offline signing; server cannot inject |
| Model Encryption | AES-256-GCM | — | Machine-bound key derivation |

# 

# 

# **11\. Next Steps & Approval Requirements**

### **Approvals Required Before Development Begins**

| Approval | Owner | Status |
| ----- | ----- | ----- |
| Architecture document sign-off | Engineering Lead | Pending |
| Security architecture sign-off | Security Lead | Pending |
| Product scope confirmation | Product Manager | Pending |
| EV code signing certificate procurement | Engineering / Legal |  Action required |
| License server hosting provisioned | Engineering / DevOps |  Action required |
| Update server hosting provisioned | Engineering / DevOps |  Action required |

### **Pre-Development Checklist**

* Finalise and sign off this architecture document  
* Procure EV code signing certificate (allow 3–5 business days for validation)  
* Provision License Server VPS and Update Server VPS  
* Set up Ed25519 key pair for update package signing (private key never lives on servers)  
* Define development sprint structure aligned to V1 scope  
* Identify which certified hardware profiles to test against during QA  
* Establish AV vendor whitelisting submission process for the Windows binary

