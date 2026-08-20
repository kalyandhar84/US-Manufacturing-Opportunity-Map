# Azure Deployment Plan

> **Status:** Deployed

Generated: 2026-08-20

---

## 1. Project Overview

**Goal:** Ship a prettier Streamlit Manufacturing Opportunity Map (theme, Google-indexable metadata, Contact us form) on Azure App Service Linux S1 in existing resource group TMH-IT-POC, then push source to GitHub.

**Path:** Modernize Existing (Streamlit app with no prior Azure hosting files)

User specified subscription, resource group, app name, and S1 Linux in the task. That is treated as plan approval for this POC.

---

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | POC |
| Scale | Small |
| Budget | Balanced (user-specified S1) |
| **Subscription** | TMH Prod01 (`3d05a5b5-8055-451d-9cd9-36016fd4b42b`) |
| **Location** | eastus2 (resource group TMH-IT-POC) |

RG tags to copy onto new resources: Application=`AI, Azure Maps`, Company=`TMH`, Environment=`POC`, Technical Owner=`Kalyan Dhar`.

---

## 3. Components Detected

| Component | Type | Technology | Path |
|-----------|------|------------|------|
| moi-streamlit | SSR web app | Python 3.12, Streamlit 1.61, Plotly, pandas, SQLite | `app.py` + `src/` |

No `@github/copilot-sdk`. No Azure Functions. SQLite file `data/moi.sqlite` (~20 MB) is already git-tracked and must be in the zip.

---

## 4. Recipe Selection

**Selected:** AZCLI (resource-group Bicep + zip deploy)

**Rationale:**
- Existing RG, fixed names, imperative Azure CLI as requested
- No ACR, so no extra registry resource. Dockerfile is committed as an optional path; runtime deploy is Oryx Python on App Service
- AZD would invent a new RG/environment naming scheme; user already has TMH-IT-POC

---

## 5. Architecture

**Stack:** App Service

### Service Mapping

| Component | Azure Service | SKU |
|-----------|---------------|-----|
| Streamlit app | Linux App Service Plan `asp-us-opportunities` + Web App `us-opportunities` | S1 (Standard, 1 worker) |

Existing S1 plan `test` in the RG is Windows (`reserved: false`) and already hosts `testpocnetworkaccess`. Not reused.

### Supporting Services

| Service | Purpose |
|---------|---------|
| Application Insights | Omitted (user: do not add extra resources unless cheap and non-blocking) |
| Key Vault | Omitted (no secrets required at runtime) |
| Log Analytics | Omitted |
| Managed Identity | Omitted (no downstream Azure APIs) |

Runtime: `PYTHON|3.12`, startup `bash startup.sh` binding Streamlit to `0.0.0.0` and `PORT`/`WEBSITES_PORT` (8000). HTTPS only. SCM basic auth left enabled. Health probe `/health` via `st.App` route. `robots.txt` at `/robots.txt`.

---

## 6. Provisioning Limit Checklist

### Phase 1: Prepare Resource Inventory

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| Microsoft.Web/serverfarms (S1 Linux) | 1 | 8 | 71 | eastus2 S1 VMs |
| Microsoft.Web/sites | 1 | 156 | 8000 per subscription (docs fallback) | Name `us-opportunities` available |

### Phase 2: Fetch Quotas and Validate Capacity

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| Microsoft.Web/serverfarms S1 | 1 | 8 | 71 | Fetched from: azure-quotas (`az quota show` / `az quota usage show`, resource-name `S1`, eastus2). Usage 7 of 71. |
| Microsoft.Web/sites | 1 | 156 | 8000 | Quota CLI has no separate sites resource in this listing. Current usage 155 from `az resource list`. Official docs: 8000 app/slot resources per subscription. |

**Status:** All resources within limits

Name check: `az rest` Microsoft.Web/checknameavailability for `us-opportunities` returned `nameAvailable: true`.

---

## 7. Execution Checklist

### Phase 1: Planning
- [x] Analyze workspace (MODERNIZE)
- [x] Gather requirements (POC, S1, TMH-IT-POC)
- [x] Confirm subscription and location with user (specified in task)
- [x] Prepare resource inventory
- [x] Fetch quotas and validate capacity
- [x] Scan codebase
- [x] Select recipe (AZCLI)
- [x] Plan architecture
- [x] **User approved this plan** (task specified create + deploy)

### Phase 2: Execution
- [x] Research components
- [x] Generate infrastructure files
- [x] Generate application configuration
- [x] Generate Dockerfiles
- [x] Theme, SEO, contact form
- [x] **Update plan status to "Ready for Validation"**

### Phase 3: Validation
- [x] Invoke azure-validate skill
- [x] All validation checks pass
  - [x] Azure CLI installation
  - [x] Authentication
  - [x] Bicep compilation
  - [x] Template validation
  - [x] What-If preview
  - [x] Docker build (optional; zip/Oryx is the deploy path)
  - [x] Azure Policy validation
- [x] Update plan status to "Validated"
- [x] Record validation proof below

### Phase 4: Deployment
- [x] Invoke azure-deploy skill
- [x] Deployment successful
- [x] Report deployed endpoint URLs
- [x] Update plan status to "Deployed"

**Live URL:** https://us-opportunities.azurewebsites.net
**App name:** us-opportunities
**Plan:** asp-us-opportunities (Linux S1, eastus2)
**Checks:** GET /health 200, GET / 200 Streamlit HTML, GET /robots.txt 200, httpsOnly true

---

## Functional Verification

- Status: Verified (local)
- Backend: `src.contact` sanitizer + write path; `asgi_app` imports `st.App`
- UI: Theme tokens in `.streamlit/config.toml` plus CSS in `app.py`; Contact us tab
- Notes: SQLite read-only at `data/moi.sqlite` (~20 MB). Docker image not built; zip/Oryx is the deploy path.

---

## 7. Validation Proof

| Check | Command Run | Result | Timestamp |
|-------|-------------|--------|-----------|
| Azure CLI | `az version` | Pass — azure-cli 2.74.0 | 2026-08-20T19:43Z |
| Authentication | `az account show` | Pass — TMH Prod01 `3d05a5b5-8055-451d-9cd9-36016fd4b42b` as kalyan.dhar@tmhna.com | 2026-08-20T19:42Z |
| Bicep compilation | `az bicep build --file ./infra/main.bicep` | Pass | 2026-08-20T19:42Z |
| Template validation | `az deployment group validate -g TMH-IT-POC --template-file ./infra/main.bicep` | Pass — provisioningState Succeeded, error null | 2026-08-20T19:43Z |
| What-If preview | `az deployment group what-if -g TMH-IT-POC` | Pass — 4 to create (plan, site, scm/ftp basic auth), 74 ignore | 2026-08-20T19:44Z |
| Docker build | skipped | Zip/Oryx deploy; Dockerfile present for optional container path | 2026-08-20T19:44Z |
| Azure Policy | `az policy assignment list` | Pass — only Azure Update Manager assignment; no App Service deny | 2026-08-20T19:44Z |
| Name availability | Microsoft.Web/checknameavailability `us-opportunities` | Pass — nameAvailable true | 2026-08-20T19:38Z |

**Validated by:** azure-validate skill
**Validation timestamp:** 2026-08-20T19:44Z

---

## 8. Files to Generate

| File | Purpose | Status |
|------|---------|--------|
| `.azure/deployment-plan.md` | This plan | ✅ |
| `infra/main.bicep` | Linux S1 plan + web app | ⏳ |
| `infra/main.parameters.json` | Parameters | ⏳ |
| `Dockerfile` | Optional container path | ⏳ |
| `startup.sh` | Streamlit bind 0.0.0.0:PORT | ⏳ |
| `scripts/deploy.ps1` | Infra + zip deploy | ⏳ |
| `scripts/package_app.py` | Zip excluding venv/raw/.env | ⏳ |
| `asgi_app.py` | `/health` and `/robots.txt` | ⏳ |
| `static/robots.txt` | Crawlers | ⏳ |

---

## 9. Next Steps

> Current: Approved — executing application and infrastructure generation

1. Implement theme, SEO, contact form
2. Write Bicep, Dockerfile, startup, package/deploy scripts
3. Validate, then deploy with Azure CLI
4. Commit and push to origin main
