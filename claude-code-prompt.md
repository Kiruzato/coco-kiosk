You are assisting in validating the **technical accuracy of the Appendix – Source Code section** of a research paper for the project **CoCo: AI-Powered Campus Assistant**.

A file named:

`appendix_source_code_candidates.txt`

already exists. This file contains **candidate source code snippets** selected as representative implementations for the **Appendix – Source Code** section of the research paper.

However, it is important to ensure that the snippets included in the appendix represent **actual runtime behavior of the system**, and not **unused, deprecated, or dead code**.

Your task is to **verify whether the components listed in `appendix_source_code_candidates.txt` are truly used by the system during runtime**.

---

## Objective

Confirm that every code snippet listed in `appendix_source_code_candidates.txt` corresponds to **code that is actively used in the system’s execution path**.

The goal is to ensure that the appendix reflects **real implementation logic**, not:

* unused helper functions
* deprecated modules
* experimental features
* dead code
* unused alternative implementations

---

## Scope of Investigation

Focus your analysis on the project's main implementation directories, especially:

* `WEB_APP`
* `INGESTION_MODULE`

You may explore other relevant parts of the repository if necessary to trace execution paths.

---

## Verification Tasks

For each entry in `appendix_source_code_candidates.txt`:

1. Locate the referenced file and code snippet.

2. Determine whether the snippet is **actually used in the system's runtime execution**.

3. Trace where and how the code is invoked by:

   * main application entry points
   * API routes
   * ingestion pipelines
   * retrieval pipelines
   * background processes
   * other modules

4. Identify whether the code is:

   * actively used
   * indirectly used through other modules
   * configurable but currently unused
   * completely unused / dead code

Your conclusions must be based on **actual call paths and execution flow**, not assumptions.

---

## If Issues Are Found

If any code snippet in `appendix_source_code_candidates.txt` is determined to be:

* unused
* unreachable in the runtime
* deprecated
* misleading for understanding the system

Then update the file accordingly.

Possible updates include:

* removing the snippet
* replacing it with a more accurate snippet
* correcting the description
* clarifying how the component is used in runtime

Do **not remove entries unnecessarily**. Only modify the file if the runtime analysis confirms the code is not representative of the real system.

---

## Updating the File

Maintain the existing structure of:

`appendix_source_code_candidates.txt`

Each entry should still contain:

* file path
* description
* code snippet
* explanation of significance

If replacements are necessary, ensure the new snippets still **clearly represent the system’s actual implementation**.

---

## Best Practices

Follow **industry-standard software analysis practices** while performing this verification:

* Trace **actual execution paths** starting from system entry points.
* Confirm usage through **imports, function calls, and invocation chains**.
* Distinguish between **available implementations** and **runtime-executed implementations**.
* Avoid relying solely on comments, filenames, or assumptions.
* Prefer code snippets that are **self-contained and clearly demonstrate system functionality**.
* Ensure appendix snippets remain **concise, readable, and representative**.

---

## Deliverable

Update and finalize:

`appendix_source_code_candidates.txt`

The updated file should contain **only source code snippets that are confirmed to be used in the system runtime**, ensuring that the research paper appendix accurately represents the **actual implementation of the CoCo system**.
