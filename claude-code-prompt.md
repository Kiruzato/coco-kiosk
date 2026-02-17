# Generate Architecture Documentation

You are working inside the CoCo project repository.

Your task is to generate a complete architecture documentation file using the existing template:

* The template file is `architecture_template.md` located at the root of the repository.
* You must use this template as the structural foundation.
* Create a new file named `architecture.md`.
* Do NOT modify `architecture_template.md`.

---

# ⚠️ Critical Constraint

* You must NOT make any code changes.
* Do NOT refactor, modify, move, rename, or delete any source files.
* Do NOT change configurations, dependencies, or project structure.
* Your task is documentation only.

---

# Scope Restriction — Web Application Runtime Only

The documentation must cover only the web application runtime architecture and its directly related production components.

You must EXCLUDE the following from the documentation:

* Testing scripts
* Testing tools or testing infrastructure
* Testing data
* Test-only modules
* Experimental or unused modules
* Backup files or backup modules
* Old, deprecated, or unused files
* Old requirements files or legacy configuration files
* Report-generation components not required for runtime operation
* Any non-runtime utilities

Focus strictly on the components required for the web application to function in production.

---

# Platform Documentation Scope Clarification

The documentation must reflect the production deployment architecture of the system.

The production deployment environment is Raspberry Pi OS, and its runtime architecture and deployment structure must be documented normally.

Windows is used only as a development and testing environment and is not part of the production runtime architecture.

Therefore:

* Do NOT document Windows-specific setup scripts, setup instructions, or platform-specific configurations.
* Do NOT include Windows-specific deployment steps or environment configuration.
* Do NOT describe Windows as a deployment target.

However:

* Raspberry Pi OS deployment architecture, runtime structure, and system integration must be fully documented.
* Platform-agnostic architectural components must be documented normally.

Windows may be mentioned briefly as a development or testing environment if necessary for context, but must not be documented as part of the production deployment architecture.

---

# Additional Explicit Exclusions

## Do NOT include Directory Entity Components

Treat directory entity components as not part of the system architecture.

Do NOT include:

* directory_entities.json
* Entity registry components
* Entity-specific ingestion logic
* Entity-specific retrieval logic
* Any directory entity framework or subsystem

Do not reference or document these components.

---

## Do NOT include Debugging or Development-only Components

Exclude all debugging, development-only, or observability tools that are not part of the production runtime architecture.

This includes:

* Debug panels
* Developer panels
* /dev endpoints
* Debug-only RAG tools
* Internal debugging interfaces
* Developer-only utilities

Only document production runtime components.

---

## Do NOT use "Phase" Terminology

Do NOT use:

* "Phase 1", "Phase 2", etc.
* Any phased implementation descriptions
* Any roadmap-style or staged explanations

The documentation must describe the architecture as a complete, cohesive runtime system.

---

# Objectives

1. Analyze the current codebase structure.
2. Identify the actual architectural layers and system components used in the runtime web application.
3. Map real implementation details into the template sections.
4. Ensure the documentation reflects the real implemented runtime architecture — not an idealized or theoretical design.
5. Keep the documentation high-level but technically precise.
6. Focus only on production runtime web application architecture.

---

# What the Documentation Must Include

Include only runtime-relevant architectural components, such as:

* System overview
* Architectural principles
* Layered architecture (UI, Application, Domain, Infrastructure, AI/RAG, etc.)
* Actual RAG architecture type (Naive, Hybrid, Agentic, Graph, etc.) based on implementation
* STT → LLM → TTS processing flow
* Data ingestion pipeline used by the runtime system
* Vector store architecture
* Model provider abstraction layer
* Production deployment architecture (Raspberry Pi OS)
* Scalability considerations
* Known limitations or technical debt (if applicable)

---

# Constraints

* Do not invent features that are not implemented.
* If something is unclear in the codebase, explicitly state assumptions.
* Use Mermaid diagrams in markdown where appropriate.
* Be concise, structured, and professional.
* The output must be production-grade architecture documentation.
* Focus strictly on runtime architecture relevant to the web application.

---

# Output Requirements

* Create a new file: `architecture.md`
* Follow the structure defined in `architecture_template.md`
* Ensure formatting is clean and consistent
* Use consistent terminology throughout the document
* Focus strictly on documentation generation