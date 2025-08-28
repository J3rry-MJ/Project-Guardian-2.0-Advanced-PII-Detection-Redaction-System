# Deployment Strategy — Project Guardian 2.0

---

## Summary (one line)
Run a lightweight PII scanner at the cluster edge (Ingress plugin) with a local sidecar for heavy work, plus defensive layers for logs, mesh traffic and internal UIs — keep raw PII out of storage, keep latency tiny, and start in shadow mode.

---

## Where it runs (primary)
•⁠  ⁠*Ingress layer*: NGINX or Kong as the recommended place to enforce PII redaction.
  - Intercepts all HTTP JSON payloads (ingress/egress).
  - No application code changes required.

*Why:* single choke point, lowest blast radius, simplest rollout.

---

## Small footprint architecture (simple view)
•⁠  ⁠*Edge (Ingress Controller)* — NGINX/Kong plugin (Lua or njs)
  - Streams body → Unix Domain Socket (UDS) → local sidecar ⁠ /scan ⁠
  - Receives redacted body → forwards to backend (Express + MCP)
•⁠  ⁠*Sidecar* — ⁠ guardian-scan ⁠ (FastAPI/uvicorn or lightweight process)
  - Runs the PII logic from ⁠ detector_full_candidate_name.py ⁠ generalized for JSON
  - Exposes ⁠ /scan ⁠ over UDS or localhost
•⁠  ⁠*Backend* — Express + MCP (unchanged apps)
  - Receives only redacted payloads
•⁠  ⁠*Logs pipeline* — Fluent Bit DaemonSet → sidecar ⁠ /scan ⁠ → SIEM (store redacted logs)
•⁠  ⁠*Optional* — Envoy WASM filter for sensitive east-west paths
•⁠  ⁠*Optional* — Browser extension for internal UIs to mask DOM PII

---

## How requests flow (simple)
1.⁠ ⁠Client → Ingress (TLS terminated).  
2.⁠ ⁠Ingress plugin streams request/response body to sidecar using UDS.  
3.⁠ ⁠Sidecar scans & returns redacted JSON quickly (⁠ [REDACTED] ⁠ fields).  
4.⁠ ⁠Ingress forwards redacted payload to backend.  
5.⁠ ⁠Backend logs/store only redacted data.

*Important:* original unredacted data is never written to DB or logs.

---

## Latency & performance targets
•⁠  ⁠*Goal:* PII scan + redact *p95 < 10 ms* for typical JSON (<256 KB).
•⁠  ⁠*Techniques:*
  - UDS for IPC (sub-ms transport).
  - Compiled regex / DFA cache for fast pattern matching.
  - Shallow streaming JSON traversal (don’t parse deep unless needed).
  - Short-circuit: stop scanning once match/redaction done for non-combinatorial rules.
  - Chunked streaming for large bodies to avoid OOM.

---

## Scale & cost model (simple)
•⁠  ⁠*Sidecar as a Kubernetes Deployment* (or part of ingress pod if supported):
  - HPA: target CPU 60%, min=2 replicas, max=N by load.
  - Keep hot worker pool; reuse compiled regex across requests.
•⁠  ⁠*Zero-copy / streaming* reduces CPU & memory cost.
•⁠  ⁠*Canary traffic* at ingress to validate rules before full rollout.

---

## Defense-in-Depth (secondary layers)
•⁠  ⁠*Logging*: Fluent Bit DaemonSet → sidecar ⁠ /scan ⁠ → SIEM (only redacted logs).
•⁠  ⁠*Service Mesh (optional)*: Envoy WASM filter mirrors payloads to sidecar for sensitive services (users/orders/payments).
•⁠  ⁠*Browser Extension*: DOM scrubbing for legacy internal tools (client-side defense).

---

## Observability & guardrails (keep it simple)
•⁠  ⁠Expose Prometheus metrics:
  - ⁠ pii_scan_latency_ms ⁠ (p50/p95/p99)
  - ⁠ pii_detect_count{type=...} ⁠
  - ⁠ pii_fp_sample ⁠ (small sampled list for QA)
•⁠  ⁠Logging:
  - Structured JSON logs *after* redaction.
•⁠  ⁠Circuit-breaker:
  - If sidecar unhealthy or scan latency > threshold → fallback to *critical-field-only* redaction (phone/ID/passport) and pass-through.
•⁠  ⁠Start in *shadow mode* (detect only) → observe FP/FN → switch to enforce.

---

## Rules & change management (easy ops)
•⁠  ⁠*Rulebook* stored in a ConfigMap (regex + field allow/deny lists).
•⁠  ⁠*Hot reload* the sidecar when ConfigMap changes.
•⁠  ⁠*Feature flags* to toggle categories: ⁠ names ⁠, ⁠ ids ⁠, ⁠ payments ⁠, ⁠ emails ⁠.
•⁠  ⁠*Versioned, signed rule bundles* for auditability and compliance.
•⁠  ⁠Admin workflow: Dev → Staging Shadow → Canary → Enforce.

---

## Failure modes & safe defaults
•⁠  ⁠*Sidecar down*: ingress passes traffic through but triggers audit log and critical-field redaction.
•⁠  ⁠*High latency*: automatically switch to minimal redaction mode (prevent outages).
•⁠  ⁠*False positives*: sample FP records (no PII in sample) and expose to analysts via admin UI for tuning.

---

## Quick rollout checklist
1.⁠ ⁠Implement sidecar ⁠ /scan ⁠ using your detector logic (FastAPI).  
2.⁠ ⁠Add ingress plugin (Lua or njs) to forward bodies to sidecar via UDS.  
3.⁠ ⁠Deploy Fluent Bit DaemonSet with sidecar redaction for logs.  
4.⁠ ⁠Run in *shadow mode* for 48–72 hours (collect metrics & FP samples).  
5.⁠ ⁠Canary ingress traffic (10%) for 24–48 hours.  
6.⁠ ⁠Promote to full enforcement and enable SIEM redaction.

---
