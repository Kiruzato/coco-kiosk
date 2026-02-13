# 📌 Antigravity Claude Opus – CQE Architecture Audit Prompt

Act as a senior systems architect performing a comprehensive architectural audit.

You are reviewing the current CQE implementation against the specification defined in:

`cqe_architecture_checklist.md`

Your objective is to evaluate whether the system faithfully implements the intended JSON-based CQE architecture, including:

* Single source-of-truth integrity
* Full schema correctness
* Admin management wiring
* Deletion rule enforcement
* Data load and restart integrity
* Proper schema integration into CQE
* Deterministic index rebuilding
* Structural consistency of the admin UI
* Absence of architectural drift

---

## Audit Expectations

Perform a deep, implementation-aware review.

For each section in the checklist:

1. Determine whether the implementation is:

   * Compliant
   * Partially compliant
   * Structurally incorrect

2. Identify mismatches or inconsistencies.

3. For each issue:

   * Explain the architectural impact.
   * Identify the root cause.
   * Apply corrections where appropriate.

This is not a feature expansion task.
It is an architectural compliance and integrity review.

---

## Areas of Focus

Give special attention to:

* Whether JSON is truly the only source of truth.
* Whether all mutations flow through registry → save → rebuild.
* Whether the CQE index strictly derives from stored entity data.
* Whether schema fields are fully and correctly integrated into CQE.
* Whether any schema fields are unused or partially mapped.
* Whether any CQE logic references outdated or mismatched structure.
* Whether admin UI operations are fully wired to persistence.
* Whether deletion rules are deterministic and hierarchy-safe.
* Whether restart behavior preserves full system integrity.

---

## Output Structure

Provide:

### 1. Executive Summary

Overall architectural health and maturity of CQE.

### 2. Section-by-Section Evaluation

For each major checklist category:

* Current state
* Compliance assessment
* Observations

### 3. Identified Issues & Corrections

For each mismatch:

* Description
* Impact
* Root cause
* Correction applied (if fixed)

### 4. Final Verdict

Answer clearly:

* Is CQE architecturally consistent?
* Is it deterministic and restart-safe?
* Is schema properly integrated into CQE?
* Is admin fully wired to the source of truth?
* Is any architectural redundancy remaining?

Approach this review with professional judgment and implementation awareness.

Begin the audit.
