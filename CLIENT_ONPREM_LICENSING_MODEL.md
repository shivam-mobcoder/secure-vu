# Secure View — On-Premise Client-Owned Hardware: Business & Delivery Model

**Document Classification**: Internal Strategy & Pre-Sales Architecture  
**Version**: 1.0 | **Date**: June 2026  
**Prepared For**: Management / Product Team  
**Purpose**: Define how Secure View can be packaged, distributed, and licensed when clients procure their own GPU/CPU/storage hardware and run the software on their own premises, with pricing tied to traffic/usage.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Core Problem This Solves](#2-the-core-problem-this-solves)
3. [How the Client-Owned Hardware Model Works](#3-how-the-client-owned-hardware-model-works)
4. [Software Packaging & Distribution](#4-software-packaging--distribution)
5. [License Key & Enforcement Architecture](#5-license-key--enforcement-architecture)
6. [Traffic-Based Pricing Tiers](#6-traffic-based-pricing-tiers)
7. [Metering: How We Measure "Traffic"](#7-metering-how-we-measure-traffic)
8. [Onboarding Flow (Client Journey)](#8-onboarding-flow-client-journey)
9. [Hardware Procurement Guidance for Clients](#9-hardware-procurement-guidance-for-clients)
10. [Remote Update & Support Strategy](#10-remote-update--support-strategy)
11. [Security & Anti-Piracy Controls](#11-security--anti-piracy-controls)
12. [Revenue & Billing Architecture](#12-revenue--billing-architecture)
13. [Technical Implementation Roadmap](#13-technical-implementation-roadmap)
14. [Risks & Mitigations](#14-risks--mitigations)

---

## 1. Executive Summary

Secure View can be distributed as a **self-contained software package** (Docker bundle / installer) that clients deploy on hardware they procure themselves (GPU server, storage, networking). We license the software using a **traffic-based subscription model** — the client pays based on how many camera streams they run, how many AI modules are active, and how much data the system processes each month.

This model gives clients:
- Full control over their hardware and data
- No vendor lock-in on infrastructure
- Predictable, scalable cost that grows with their business

And gives us:
- Recurring revenue without hosting costs
- A scalable distribution model with zero marginal cost per deployment
- Protection against piracy via license enforcement

---

## 2. The Core Problem This Solves

| Problem | Our Solution |
|---|---|
| Client wants data sovereignty (no cloud) | Software runs entirely on their hardware |
| Client doesn't want vendor-managed infra | They buy their own GPU server; we provide the software |
| We can't afford to host GPU compute for free | Client owns the GPU — we just charge for the software license |
| Pricing should match actual usage | License tied to active camera count + AI module usage |
| We need to prevent unauthorized sharing/piracy | Hardware-bound license keys + periodic license server check-in |

---

## 3. How the Client-Owned Hardware Model Works

### High-Level Flow

```
[Client Buys Hardware]
        ↓
[Client Contacts Us / Signs Contract]
        ↓
[We Issue License Key (tied to their server's hardware ID)]
        ↓
[Client Downloads Software Installer / Docker Bundle]
        ↓
[Client Installs on Their Server — Fully Self-Hosted]
        ↓
[Software Phones Home Monthly for License Renewal]
        ↓
[We Bill Client Monthly Based on Usage Metrics]
        ↓
[Client Scales Hardware Themselves; License Tier Adjusts]
```

### Key Principle: Software Is the Product, Hardware Is the Client's

We are a **software company**, not an infrastructure company. The client buys and owns the server. We provide, maintain, and update the software. Our revenue comes from the software license — not from hardware margins or cloud hosting.

---

## 4. Software Packaging & Distribution

### 4.1 Delivery Format

The software should be delivered in **two formats** to cover different client IT maturity levels:

| Format | What It Is | Best For |
|---|---|---|
| **Docker Bundle (Primary)** | A `docker-compose.yml` + all images saved as `.tar.gz`. Client runs `docker compose up` | IT-mature clients, server teams |
| **Offline Installer (Secondary)** | A shell script that pulls, verifies, and starts the Docker stack automatically | Less-technical clients, single-server deployments |

### 4.2 Offline Capability

The entire software bundle must be distributable **without internet access**:

```bash
# On our build server:
docker save secureview-app secureview-nginx secureview-db \
  secureview-redis secureview-prometheus secureview-grafana \
  | gzip > secureview-v2.1.0-bundle.tar.gz

# Client receives this file and runs:
docker load < secureview-v2.1.0-bundle.tar.gz
docker compose up -d
```

This is critical for government, banking, and defence clients who cannot reach the internet from their server network.

### 4.3 What Is Included in the Package

| Component | Included? | Notes |
|---|---|---|
| Backend API (Python/aiohttp) | ✅ Yes | Core application |
| AI model files (YOLO, FaceID, LPR, etc.) | ✅ Yes | Bundled in Docker image |
| Frontend Dashboard (React SPA) | ✅ Yes | Served via NGINX |
| PostgreSQL database | ✅ Yes | Containerized |
| Redis | ✅ Yes | Containerized |
| NGINX reverse proxy | ✅ Yes | TLS termination |
| Monitoring (Prometheus + Grafana) | ✅ Yes | Optional, can disable |
| License enforcement agent | ✅ Yes | Embedded in backend |
| Installer / setup script | ✅ Yes | One-command setup |
| Hardware sizing guide | ✅ Yes | PDF sent pre-sales |

### 4.4 Version Control & Updates

- Releases are version-tagged (e.g., `v2.1.0`)
- Updates delivered as new Docker bundles or via authenticated pull from our private registry
- Changelogs accompany every release
- Critical security patches are push-notified to all active license holders

---

## 5. License Key & Enforcement Architecture

This is the most critical technical component for protecting our revenue.

### 5.1 License Key Components

A license key encodes:

```
CLIENT_ID | TIER | MAX_CAMERAS | ENABLED_MODULES | EXPIRY_DATE | HARDWARE_FINGERPRINT | SIGNATURE
```

| Field | Description |
|---|---|
| `CLIENT_ID` | Unique identifier for the client account |
| `TIER` | Pricing tier (Starter / Professional / Enterprise) |
| `MAX_CAMERAS` | Hard cap on simultaneous active camera streams |
| `ENABLED_MODULES` | Bitmask of which AI modules are licensed (Face, LPR, Fire, Pose) |
| `EXPIRY_DATE` | UTC timestamp; license invalid after this date |
| `HARDWARE_FINGERPRINT` | Hash of client's server MAC address + CPU serial + motherboard UUID |
| `SIGNATURE` | RSA-2048 signature signed with our private key; client validates with our public key |

### 5.2 Hardware Fingerprinting

On first install, the license agent collects:

```python
import hashlib, subprocess

def get_hardware_fingerprint():
    mac = subprocess.check_output("cat /sys/class/net/eth0/address", shell=True).decode().strip()
    cpu_serial = subprocess.check_output("dmidecode -s processor-serial-number", shell=True).decode().strip()
    board_uuid = subprocess.check_output("dmidecode -s system-uuid", shell=True).decode().strip()
    raw = f"{mac}|{cpu_serial}|{board_uuid}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

This fingerprint is sent to our license server during activation. The license is then **bound to that hardware**. If the client moves the software to a new server, they must request a license transfer.

### 5.3 License Validation Flow

```
[Software Starts]
      ↓
[Read license.key file from /etc/secureview/]
      ↓
[Verify RSA signature with embedded public key]
      ↓
[Check EXPIRY_DATE — if expired, enter grace period (7 days)]
      ↓
[Check HARDWARE_FINGERPRINT matches current server]
      ↓
[Phone home to license.secureview.io/v1/validate (if internet available)]
      ↓ (offline mode if no internet)
[Enforce MAX_CAMERAS — refuse to start streams above the cap]
      ↓
[Enforce ENABLED_MODULES — disable unlicensed AI modules in UI]
```

### 5.4 Offline Grace Period

For air-gapped clients, the software must work without internet:

- License is validated locally via cryptographic signature (no internet needed for day-to-day operation)
- Phone-home is attempted **once per month**
- If phone-home fails for **90 days**, the license enters **degraded mode** (alerts still work, but no new camera additions allowed)
- This protects us while not disrupting air-gapped deployments

### 5.5 What Happens When License Expires

| State | Software Behavior |
|---|---|
| Active (valid) | Full functionality per tier |
| Grace Period (0–7 days expired) | Warning banner in dashboard; full functionality |
| Expired (>7 days) | Cannot add new cameras; existing streams continue (no disruption to monitoring) |
| Expired (>30 days) | All streams paused; dashboard shows renewal CTA only |
| Suspended (non-payment) | Immediate pause; admin notified |

> **Design principle**: We never hard-cut a client's live security feed without warning. This protects client safety and our reputation. The escalation gives 30+ days of warnings before impact.

---

## 6. Traffic-Based Pricing Tiers

"Traffic" in our context = **number of simultaneously active camera streams + AI modules enabled**.

### 6.1 Pricing Structure

| Tier | Active Cameras | AI Modules | Monthly Price (INR) | Monthly Price (USD) |
|---|---|---|---|---|
| **Starter** | Up to 5 cameras | Object Detection + Tracking only | ₹15,000 / mo | ~$180 / mo |
| **Professional** | Up to 20 cameras | + Face Recognition + LPR | ₹45,000 / mo | ~$540 / mo |
| **Enterprise** | Up to 50 cameras | All modules (Fire, Pose, Anomaly) | ₹1,00,000 / mo | ~$1,200 / mo |
| **Enterprise+** | 50+ cameras (custom) | All modules + SLA + priority support | Custom quote | Custom quote |

> **Note**: These are suggested reference prices. Final pricing should be validated with your sales and finance team based on target market, competition, and desired margins.

### 6.2 Add-On Pricing

Clients can purchase add-ons to expand capability without upgrading their full tier:

| Add-On | Price (per month) |
|---|---|
| +5 additional cameras | ₹8,000 / mo |
| Face Recognition module | ₹10,000 / mo |
| License Plate Recognition module | ₹8,000 / mo |
| Fire & Smoke Detection module | ₹6,000 / mo |
| Priority Support (4-hour SLA) | ₹15,000 / mo |
| Annual prepay discount | 15% off monthly rate |

### 6.3 Overage Policy

If a client exceeds their licensed camera count:

1. Dashboard shows overage warning
2. Client can add cameras by purchasing add-on immediately (self-serve via client portal)
3. Unauthorized overage: new camera connections refused after 24-hour grace window

---

## 7. Metering: How We Measure "Traffic"

### 7.1 What We Meter

| Metric | How Measured | Billing Impact |
|---|---|---|
| **Active Camera Streams** | Count of cameras with status = `RUNNING` in DB | Primary billing driver |
| **AI Modules Enabled** | Feature flags enabled per deployment | Determines tier |
| **Peak Camera Count** | Highest simultaneous streams in the billing period | Billed at peak, not average |
| **Total Events Generated** | Alert count per month (for analytics) | Informational; not billed separately |

### 7.2 Usage Telemetry Payload (Monthly Phone-Home)

```json
{
  "client_id": "CLIENT-0042",
  "license_key_id": "LK-2024-XYZ",
  "reporting_period": "2026-05",
  "hardware_fingerprint": "a3f9c2...",
  "software_version": "2.1.0",
  "peak_cameras": 18,
  "avg_cameras": 14,
  "modules_active": ["detection", "face_recognition", "lpr"],
  "total_events_generated": 12847,
  "uptime_hours": 714,
  "timestamp": "2026-05-31T23:59:59Z",
  "signature": "HMAC-SHA256(...)"
}
```

### 7.3 Client Privacy: What We Do NOT Collect

To maintain trust and data sovereignty promises:

| Data | Collected? |
|---|---|
| Video frames or recordings | ❌ Never |
| Detected faces or biometrics | ❌ Never |
| Camera locations or names | ❌ Never |
| Event details or alert content | ❌ Never |
| Network topology | ❌ Never |
| Usage counts and module status | ✅ Yes (for billing) |

This must be stated explicitly in the client contract and privacy policy.

---

## 8. Onboarding Flow (Client Journey)

```
Step 1: PRE-SALES
─────────────────
Client contacts us → Sales call → Share hardware sizing guide →
Client decides on tier → Contract signed → Invoice raised

Step 2: HARDWARE PROCUREMENT (Client's responsibility)
──────────────────────────────────────────────────────
Client buys server per our hardware guide →
We provide a recommended hardware list (see Section 9) →
Client sets up OS (Ubuntu 22.04 LTS) + Docker + NVIDIA drivers

Step 3: ACTIVATION
──────────────────
Client shares server hardware fingerprint with us →
We generate license.key and send via secure channel →
Client places license.key in /etc/secureview/

Step 4: INSTALLATION
────────────────────
Client downloads software bundle (Docker tar.gz or runs installer script) →
Runs: ./secureview-install.sh or docker compose up -d →
System starts; license validated; dashboard accessible at https://localhost

Step 5: CONFIGURATION
─────────────────────
Client adds cameras via dashboard →
Configures zones, alerts, user accounts →
Our team provides remote setup assistance (optional paid service)

Step 6: ONGOING
───────────────
Monthly auto-billing → Software updates via new bundle →
Support via ticketing system → License renewal auto-handled
```

---

## 9. Hardware Procurement Guidance for Clients

We must give clients a clear hardware shopping list. This removes the guesswork and reduces support overhead.

### 9.1 Recommended Configurations by Scale

| Scale | CPU | RAM | GPU | Storage (NVMe) | Storage (HDD) | Approx. Hardware Cost |
|---|---|---|---|---|---|---|
| **Small** (5–10 cams) | Intel Core i7-13700 | 32 GB DDR5 | NVIDIA RTX 4060 (8 GB) | 1 TB | 4 TB | ₹1.5–2L |
| **Medium** (20–30 cams) | AMD Ryzen 9 7950X | 64 GB DDR5 | NVIDIA RTX 4080 (16 GB) | 2 TB | 16 TB RAID | ₹4–6L |
| **Large** (50 cams) | Dual Xeon / EPYC | 128 GB ECC | NVIDIA RTX 4090 or A6000 (24 GB) | 4 TB NVMe | 40 TB RAID-6 | ₹10–18L |
| **Enterprise** (100+ cams) | Dual EPYC | 256 GB ECC | 2× NVIDIA A6000 (48 GB each) | 8 TB NVMe RAID | 100+ TB SAN | ₹40L+ |

> Hardware cost is paid once by the client. Software license is paid monthly. Total cost of ownership is significantly lower than a cloud equivalent.

### 9.2 OS & Pre-Requisites (Client Must Provide)

```
Operating System:   Ubuntu 22.04 LTS (minimal server install)
Docker:             Docker Engine 24.x + Docker Compose v2
NVIDIA Drivers:     535.x or newer (for GPU tiers)
NVIDIA Container:   nvidia-container-toolkit
Network:            Static IP assigned to server
Storage:            Volumes mounted at /data/secureview/
```

We provide a **one-page server prep checklist** for the client's IT team.

---

## 10. Remote Update & Support Strategy

### 10.1 Software Updates

| Update Type | Delivery Method | Frequency |
|---|---|---|
| Feature releases | New Docker bundle download + release notes | Quarterly |
| Security patches | Automated pull from private registry (if internet allowed) | As needed |
| Emergency patches | Direct bundle sent to client via secure link | Immediate |
| Air-gapped clients | USB drive or internal artifact server (Harbor/Nexus) | Per request |

### 10.2 Remote Support Access

For troubleshooting, we offer:

- **SSH Tunnel via WireGuard**: Client installs WireGuard, we get a secure tunnel into their server for diagnosed issues — no persistent access
- **Log Export**: Client exports logs via dashboard; sends to our support team
- **Remote Desktop (optional)**: AnyDesk / TeamViewer session with client present

> All remote access must be **client-initiated and client-approved**. We maintain an access log for compliance.

---

## 11. Security & Anti-Piracy Controls

### 11.1 Layers of Protection

| Layer | Mechanism |
|---|---|
| **License signing** | RSA-2048 signed license; cannot be forged without our private key |
| **Hardware binding** | License tied to server fingerprint; non-transferable without our approval |
| **Periodic validation** | Monthly phone-home; extended offline = degraded mode |
| **Docker image protection** | Images distributed as signed, compressed bundles; model weights encrypted at rest |
| **Binary obfuscation** | Python source compiled to `.pyc` + Cython-compiled critical modules |
| **Audit logging** | All license checks logged server-side; anomalies flagged |

### 11.2 What We Cannot Prevent (and Accept)

- A technically sophisticated client could reverse-engineer the Docker containers — we accept this risk for enterprise clients who have signed contracts
- The license enforcement primarily deters casual copying, not nation-state actors
- Our primary protection is the **contract + relationship**, not pure DRM

---

## 12. Revenue & Billing Architecture

### 12.1 Billing System Requirements

To support this model, we need:

| Component | Tool / Service | Purpose |
|---|---|---|
| **Billing platform** | Stripe / Razorpay | Recurring subscription billing, invoicing |
| **License server** | Our hosted API (license.secureview.io) | License issuance, validation, usage reporting |
| **Client portal** | Simple web app | Clients view usage, upgrade tier, download invoices |
| **CRM** | HubSpot / Zoho | Track client accounts, contracts, renewal dates |
| **Support ticketing** | Freshdesk / Linear | Track support requests per client |

### 12.2 Billing Cycle

```
1st of Month:  Usage report received from all client deployments
2nd–3rd:       Invoice generated based on peak camera count + active modules
5th:           Invoice sent to client
15th:          Payment due
16th–22nd:     Grace period (7 days)
23rd+:         License degraded if unpaid; client notified
30th:          License suspended if still unpaid
```

### 12.3 Contract Structure

| Contract Type | Duration | Payment Terms | Discount |
|---|---|---|---|
| Monthly rolling | 1 month | Pay in advance | None |
| Annual | 12 months | Quarterly or upfront | 15% off |
| Multi-year | 24–36 months | Annual upfront | 20–25% off |

---

## 13. Technical Implementation Roadmap

To launch this model, the following engineering work is required:

### Phase 1: License Engine (4–6 weeks)

- [ ] Build hardware fingerprinting module
- [ ] Build license key generation tool (internal CLI)
- [ ] Build RSA signature validation in the backend
- [ ] Implement camera count enforcement (hard cap)
- [ ] Implement module feature flags per license
- [ ] Build offline grace period logic

### Phase 2: Telemetry & Phone-Home (2–3 weeks)

- [ ] Build usage telemetry collector (camera count, modules, uptime)
- [ ] Build HMAC-signed monthly phone-home payload
- [ ] Build license server API (hosted by us): `/activate`, `/validate`, `/report-usage`
- [ ] Build admin dashboard (internal) to view all client deployments

### Phase 3: Client Portal (3–4 weeks)

- [ ] Client login + account page
- [ ] Usage dashboard (current cameras, modules active, billing period)
- [ ] Tier upgrade self-serve flow
- [ ] Invoice download
- [ ] License key download after payment

### Phase 4: Distribution Pipeline (2 weeks)

- [ ] Automated Docker bundle builder (CI pipeline)
- [ ] Version-tagged signed releases
- [ ] Offline installer script
- [ ] Client-facing hardware setup checklist

### Phase 5: Billing Integration (2–3 weeks)

- [ ] Razorpay/Stripe subscription setup
- [ ] Auto-invoice generation on 1st of month
- [ ] Webhook: payment success → license renewal
- [ ] Webhook: payment failure → degraded mode trigger

**Total estimated timeline: 13–18 weeks (3–4 months)**

---

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Client shares license key with a second server | Medium | Revenue loss | Hardware fingerprint binding prevents reuse |
| Client reverse-engineers Docker image | Low | IP theft | Cython compilation + contracts + model encryption |
| Client refuses to renew after 1 year | Medium | Churn | Annual contracts with 3-month notice clause |
| License server downtime breaks client validation | Low | Client disruption | Offline cryptographic validation (no internet needed for daily ops) |
| Client buys wrong hardware, blames us | Medium | Support overhead | Detailed pre-sales hardware guide + optional paid setup service |
| Pirated copies in low-trust markets | Low-Medium | Revenue loss | Hardware binding + legal contract language |
| Client doesn't want telemetry | Medium | Billing gap | Offer air-gapped billing via manual usage declaration with audit rights |

---

## Summary: Why This Model Works

| Benefit | Who It Benefits |
|---|---|
| Client owns hardware = no cloud dependency | Client |
| Data never leaves client premises | Client (compliance) |
| Predictable monthly software cost | Client (finance) |
| Zero hosting cost for us | Us (margins) |
| Recurring revenue scales with client growth | Us (revenue) |
| License enforcement protects IP | Us (protection) |
| Distributable as a file, no infra needed | Both |

This model positions Secure View as a **premium on-premise software vendor** — similar to how enterprise software like Palo Alto, Splunk, or VMware is sold: the client buys their own hardware, we provide the software license, and everyone wins.
