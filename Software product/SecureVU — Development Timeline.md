# 

# 

# 

# 

# **SECURE VU**

# **Product Roadmap & Development Plan**

**Version:** 1.0

**Document Type:** Product Strategy & Development Roadmap

**Status:** Active

**Project:** SecureVU On-Premise AI Surveillance Platform

---

# 

# 

# **1\. Objective**

This roadmap defines the development strategy for SecureVU as a fully installable on-premise AI CCTV surveillance software platform.

The roadmap has been prepared considering the following team structure:

* One Core Engineer  
* One QA Engineer  
* One DevOps Engineer  
* PM / Architect Ownership  
* UI/UX Ownership

The product strategy transitions SecureVU from an AWS-hosted AI processing architecture to a commercially deployable software platform that operates entirely on customer-owned infrastructure.

## **Primary Objectives**

* Deliver a stable MVP within 30–45 days  
* Enable early commercial pilot deployments  
* Minimize engineering complexity  
* Validate the product with real customers  
* Expand functionality through controlled feature releases  
* Avoid premature enterprise architecture

# **2\. Product Strategy**

Rather than building a complete enterprise surveillance ecosystem in the initial release, SecureVU will follow a phased rollout strategy.

| Phase | Primary Goal |
| ----- | ----- |
| **MVP – Essential CPU** | Fast Launch & Commercial Validation |
| **Phase 1 – Professional CPU** | Commercial Pilot Expansion |
| **Phase 2 – Enterprise GPU** | Enterprise Scaling |

## **Strategic Priorities**

* Fast deployment  
* Minimum viable commercial software  
* Early pilot launches  
* Stable customer deployments  
* Progressive feature expansion

**Feature velocity should never compromise platform stability.**

# **3\. Product Overview**

SecureVU is being repositioned from an AWS-based AI processing solution into a fully installable on-premise AI CCTV surveillance software platform.

All AI processing, recording, and analytics are performed locally on customer infrastructure.

No surveillance video leaves customer premises.

SecureVU will be sold as an annual subscription software product including licensing, updates, and technical support.

## **Customer Responsibilities**

* CCTV Cameras  
* Server Hardware  
* Storage  
* Network Infrastructure

## **SecureVU Responsibilities**

* AI Analytics Software  
* Surveillance Dashboard  
* Licensing System  
* Software Updates  
* Technical Support  
* Installation Guidance

## **Revenue Model**

Revenue is generated through:

* Annual Software Subscriptions  
* Feature Licensing  
* Support & Maintenance

# **4\. Important Architecture Shift**

## **Previous Architecture**

AWS-hosted AI Processing System

## **New Architecture**

Fully Installable On-Premise Surveillance Software Platform

As a result, SecureVU must now include the following core components:

* AI Engine  
* RTSP Handling  
* Recording Engine  
* Dashboard Software  
* Deployment System  
* Licensing  
* Authentication  
* Update Mechanism  
* Docker Packaging  
* Monitoring  
* Stability Handling

The product is no longer limited to AI inference and must function as a complete surveillance software platform.

# **5\. Team Structure**

| Role | Responsibility |
| ----- | ----- |
| **Core Engineer** | AI, Backend, Video Pipeline, Frontend, Deployment |
| **QA Engineer** | Testing & Stability |
| **DevOps Engineer** | Docker, CI/CD & Infrastructure |
| **PM / Architect** | Product Planning & Architecture |
| **UI/UX Designer** | User Experience & Design |

All technical and architectural decisions should assume this resource allocation.

Large-scale enterprise complexity should only be introduced when supported by real customer requirements.

# **6\. MVP Scope (Essential CPU)**

## **Target Delivery**

**30–45 Days**

## **Target Customers**

* Small Offices  
* Warehouses  
* Clinics  
* Shops  
* Apartments  
* Schools

## 

## 

## **Recommended Hardware**

| Component | Specification |
| ----- | ----- |
| **CPU** | Intel i7 / Ryzen 7 |
| **RAM** | 16 GB |
| **GPU** | Not Required |
| **Camera Count** | Up to 4 |
| **Resolution** | 720p |
| **Operating System** | Ubuntu 22.04 |
| **Deployment** | Docker |

This edition is designed for pilot deployments and small commercial installations.

# **7\. MVP Features**

The SecureVU Essential CPU edition focuses on delivering a stable and commercially deployable AI surveillance platform rather than a feature-complete enterprise solution.

## **7.1 AI Analytics**

* Person Detection  
* Vehicle Detection  
* Intrusion Detection  
* Loitering Detection  
* Fire Detection

## **7.2 Video Processing**

* RTSP Stream Ingestion  
* Event Recording

## **7.3 Backend**

* FastAPI APIs  
* PostgreSQL Database

## **7.4 Dashboard**

* Live Camera View  
* Event Timeline  
* Camera Management

## **7.5 Authentication**

* JWT Authentication

## **7.6 Alerting**

* Email Alerts  
* Webhook Alerts

## **7.7 Deployment**

* Docker-Based Deployment

## **7.8 Licensing**

* Basic Software Activation

# **8\. Features Excluded from MVP**

The following capabilities are intentionally deferred to future phases to prioritize product stability and rapid commercial deployment.

## **Deferred Features**

* Face Recognition  
* ANPR  
* Crowd Analytics  
* Violence Detection  
* Weapon Detection  
* ReID  
* Cross-Camera Tracking  
* Windows Installer  
* Auto-Update Rollback  
* Multi-Site Management  
* Air-Gapped Deployment  
* LDAP / Active Directory  
* Enterprise GPU Orchestration

These features will be introduced only after successful MVP validation and pilot deployments.

# **9\. Current Technology Stack**

The SecureVU technology stack has been selected to prioritize stability, maintainability, and ease of deployment for a small engineering team while providing a clear upgrade path for future enterprise capabilities.

## **9.1 AI Stack**

* YOLO  
* ONNX Runtime  
* Python 3.11

## **9.2 Backend**

* FastAPI  
* Uvicorn

## **9.3 Frontend**

* React  
* Vite  
* Tailwind CSS

## **9.4 Database**

* PostgreSQL

## **9.5 Cache & Task Queue**

* Redis  
* Celery

## **9.6 Video Processing**

* FFmpeg  
* OpenCV  
* RTSP

## **9.7 Deployment**

* Docker Compose

## **9.8 Packaging**

* Linux Docker Bundle  
* Windows Installer (Future)

## **9.9 Update Mechanism**

* Signed Update Packages  
* Rollback Support

# **10\. Business Model**

SecureVU operates as a software company rather than a hardware vendor.

## **Customer Responsibilities**

* CCTV Cameras  
* Server Hardware  
* Storage Infrastructure  
* Network Infrastructure

## **SecureVU Responsibilities**

* AI Surveillance Software  
* Dashboard  
* Licensing  
* Software Updates  
* Technical Support  
* Installation Guidance

## **Revenue Sources**

* Annual Software Subscription  
* Feature Licensing  
* Support Services

# **11\. Security Model**

The product is designed with an on-premise, security-first architecture.

## **Design Principles**

* Video data never leaves customer premises.  
* License validation and update communication transmit only minimal metadata.  
* JWT Authentication with RBAC-ready architecture.  
* Login Rate Limiting.  
* Audit Logging.  
* Signed Software Updates.  
* Hardware-Bound Licensing.  
* Offline Grace Period for License Validation.

This architecture ensures customer privacy while supporting commercial software licensing.

# 

# 

# **12\. Product Philosophy**

SecureVU development follows five fundamental priorities.

| Priority | Description |
| ----- | ----- |
| **Priority 1** | Platform Stability |
| **Priority 2** | Reliable RTSP Handling |
| **Priority 3** | Reliable Recording Engine |
| **Priority 4** | Easy Deployment |
| **Priority 5** | Customer Validation |

Feature velocity should never compromise product reliability.

# **13\. Architectural Principles**

The architecture intentionally avoids unnecessary complexity.

## **Core Principles**

* Avoid Premature Microservices  
* Prefer Modular Monolith Architecture  
* Use Separated Workers Only When Necessary  
* Optimize for Maintainability by a Small Engineering Team  
* Docker Compose is Sufficient for MVP and Early Commercial Pilots  
* Performance Optimization Should Be Driven by Real Customer Usage Data

The objective is to build a commercially deployable and maintainable product before introducing enterprise-scale infrastructure.

# 

# **14\. Revised MVP Development Timeline (45-Day Plan)**

The MVP development plan is structured around a five-week schedule, balancing feature implementation with platform stability and deployment readiness.

## **Week 1 – Core Foundation**

### **Objectives**

* Finalize System Architecture  
* Complete UI Wireframes  
* Design Database Schema  
* Configure Docker Environment  
* Implement RTSP Pipeline  
* Initialize FastAPI Backend  
* Configure PostgreSQL

### **Deliverables**

* Backend Application Skeleton  
* Camera Ingestion Pipeline  
* Dockerized Development Environment  
* Initial Database Structure  
* Development Infrastructure Ready

## **Week 2 – AI Pipeline**

### **Objectives**

* Integrate YOLO Models  
* Configure ONNX Runtime  
* Implement Frame Extraction  
* Build Event Generation Pipeline  
* Develop Detection APIs

### **Deliverables**

* Person Detection  
* Vehicle Detection  
* Intrusion Detection  
* AI Event Generation  
* Detection APIs

## **Week 3 – Recording & Dashboard**

### **Objectives**

* Implement Event Recording  
* Snapshot Management  
* Dashboard Development  
* Live Camera View  
* Event Timeline

### **Deliverables**

* Functional Surveillance Dashboard  
* Recording Engine  
* Live Camera Streaming  
* Event Timeline Interface  
* Snapshot Support

## **Week 4 – Productization Layer**

### **Objectives**

* Authentication  
* Licensing  
* Alert System  
* Camera Management  
* Docker Deployment  
* Basic Configuration Management

### **Deliverables**

* Deployable MVP Software  
* JWT Authentication  
* Licensing Module  
* Email & Webhook Alerts  
* Camera Configuration Module  
* Docker Deployment Package

## **Week 5 – QA, Stabilization & Pilot Buffer**

### **Objectives**

* Bug Fixing  
* RTSP Stability Testing  
* Memory Optimization  
* Long-Duration Testing  
* Packaging Cleanup  
* Pilot Deployment  
* Customer Environment Setup  
* Monitoring  
* Emergency Fixes

### **Deliverables**

* Stable Pilot Candidate  
* Production Docker Package  
* Performance Validation  
* Customer Deployment  
* Live MVP Environment

# 

# 

# 

# 

# **15\. Realistic Deliverables After 45 Days**

The following functionality is expected to be production-ready after the MVP timeline.

| Component | Status |
| ----- | ----- |
| AI Detections | Working |
| RTSP Handling | Stable |
| Recording | Basic & Stable |
| Dashboard | Functional |
| Alerts | Working |
| Docker Deployment | Stable |
| Basic Licensing | Working |
| Authentication | Working |
| Pilot Deployment | Possible |

These deliverables represent a stable commercial MVP suitable for pilot customer deployments while providing a foundation for future Professional CPU and Enterprise GPU editions.

# **16\. Functionality Not Included After MVP**

The following enterprise capabilities are intentionally excluded from the MVP release to ensure a stable and commercially viable first version.

| Feature | Status |
| ----- | ----- |
| Enterprise Scaling | Not Included |
| Windows Software Installer | Not Included |
| Multi-GPU Optimization | Not Included |
| Cross-Camera Tracking | Not Included |
| Enterprise RBAC | Not Included |
| Auto-Update Rollback | Not Included |
| Large-Scale Face Recognition | Not Included |

These capabilities are planned for subsequent product phases after successful MVP validation and pilot deployments.

# **17\. Phase 1 Roadmap – Professional CPU**

## **Timeline**

**45–60 Days After MVP**

## **Objective**

Commercial Pilot Expansion

## **Target Environment**

* Higher-End CPU Systems  
* Commercial Clients  
* 4–8 Camera Deployments

## **Features Included**

* Face Detection  
* Face Recognition  
* ANPR  
* Crowd Counting  
* Tracking  
* Smoke Detection  
* Continuous Recording  
* RBAC  
* Audit Logs  
* Windows Installer  
* TensorRT Optimization

## **Expected Outcome**

A commercially mature CPU-based surveillance platform designed for medium-sized commercial deployments with enhanced AI capabilities and improved operational features.

# **18\. Phase 2 Roadmap – Enterprise GPU**

## **Timeline**

**4–6 Months After Phase 1**

## **Objective**

Enterprise Expansion

## **Target Deployments**

* Enterprise Organizations  
* Smart Cities  
* Large Campuses  
* GPU-Based Installations

## **Features Included**

* Violence Detection  
* Weapon Detection  
* ReID  
* Cross-Camera Tracking  
* Multi-Site Management  
* Air-Gapped Deployment  
* LDAP / Active Directory Integration  
* WebRTC Streaming  
* Multi-GPU Orchestration  
* **Target Enterprise-Scale Camera Capacity (subject to certified hardware profiles and benchmarking)**

## **Expected Outcome**

A full-scale enterprise AI surveillance platform optimized for large deployments using dedicated NVIDIA GPU infrastructure.

# **19\. Performance & Capacity Guidelines**

Current planning assumptions are intentionally conservative and should always be validated through benchmarking and real customer deployments.

| Edition | Recommended Capacity |
| ----- | ----- |
| **Essential CPU** | Up to 4 Cameras |
| **Professional CPU** | 4–8 Cameras |
| **Enterprise GPU** | Large GPU Deployments |

## **Essential CPU Edition**

* Designed for small deployments  
* Optimized for pilot customers  
* Primarily focused on object detection workloads

## **Professional CPU Edition**

* Suitable for medium commercial deployments  
* Supports additional analytics and continuous recording

## **Enterprise GPU Edition**

* Designed for dedicated NVIDIA GPU infrastructure  
* Supports enterprise-scale AI analytics  
* Final supported camera capacity depends on certified hardware configuration, AI workload, recording mode, and performance benchmarking

**Note:** Any higher camera count or performance figure should be treated as a design target rather than a guaranteed capability.

# **20\. Known Risks**

The following risks require the highest engineering focus throughout development.

| Risk | Severity |
| ----- | ----- |
| RTSP Instability | Critical |
| Memory Leaks | Critical |
| Recording Reliability | Critical |
| Long-Duration Uptime | Critical |
| Camera Compatibility | High |
| Multi-Threading Performance | High |
| GPU Bottlenecks | High |
| Docker Deployment Edge Cases | Medium |

Engineering effort should prioritize eliminating these risks before introducing additional AI capabilities.

# **21\. Recommended Strategic Priorities**

The SecureVU roadmap follows a stability-first development philosophy.

| Priority | Objective |
| ----- | ----- |
| **Priority 1** | Launch MVP Quickly |
| **Priority 2** | Acquire Pilot Customers |
| **Priority 3** | Validate Real Customer Deployments |
| **Priority 4** | Stabilize the Platform |
| **Priority 5** | Expand Product Features |

Long-term success depends on platform reliability and customer validation rather than rapid feature accumulation.

# **22\. Final Timeline Summary**

| Stage | Timeline | Expected Outcome |
| ----- | ----- | ----- |
| **MVP – Essential CPU** | 30–45 Days | Deployable AI Surveillance Software |
| **Professional CPU** | \+45–60 Days | Commercial Pilot Platform |
| **Enterprise GPU** | \+4–6 Months | Enterprise AI Surveillance Suite |

This phased approach enables rapid commercial deployment while maintaining a clear path toward enterprise capabilities.

# **23\. Conclusion**

SecureVU is being developed as a commercially deployable, on-premise AI surveillance software platform that prioritizes stability, maintainability, and ease of deployment over premature enterprise complexity.

The roadmap is intentionally designed around a lean engineering team and emphasizes:

* Reliable RTSP handling  
* Stable recording pipelines  
* Modular architecture  
* Docker-based deployment  
* Progressive feature expansion  
* Customer-driven validation

By focusing first on a stable MVP and real-world pilot deployments, SecureVU establishes a strong foundation for future Professional CPU and Enterprise GPU editions while minimizing technical debt and ensuring long-term maintainability.

