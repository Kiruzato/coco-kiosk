You are working on the CoCo Campus RAG Chatbot project.

You will now execute the architectural unification plan defined in:

```
implementation_plan.md
```

located in the root directory.

This plan removes the special-case directory query path and unifies directory queries under the standard RAG orchestrator flow.

Execution is now authorized.

---

# Core Objective

Implement the plan exactly as specified.

The goal is to ensure:

* Directory-related queries follow the same standard RAG flow as all other queries.
* The early `is_directory_query()` interception in `app.py` is removed.
* The `handle_directory_query()` function is deleted.
* No pre-LLM HIGH-confidence gate remains for directory queries.
* No directory-specific hardcoded fallback message remains.
* Directory queries always reach the orchestrator and the LLM.
* `QueryIntent.DIRECTORY` classification remains intact.
* No entity logic is reintroduced.

---

# Execution Requirements

Follow the plan in `implementation_plan.md` step-by-step.

During implementation:

* Apply proper refactorization where necessary.
* Maintain clean modular boundaries.
* Remove unused imports.
* Remove dead code completely.
* Avoid duplication.
* Preserve system behavior for non-directory queries.
* Ensure streaming endpoint remains unaffected.

Do not redesign unrelated subsystems.

---

# Post-Implementation Validation

After implementation:

Verify and confirm:

* `handle_directory_query()` no longer exists.
* No early directory exit in `app.py`.
* Directory queries reach the LLM.
* Retrieved RAG context is passed to the LLM.
* No hardcoded directory fallback message exists.
* Non-directory queries behave identically to before.
* No unused imports remain.
* Application runs without errors.

Provide a structured summary including:

* Files modified
* Lines removed
* Any refactors performed
* Validation checklist results

---

Proceed with execution.
