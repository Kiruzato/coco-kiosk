#!/usr/bin/env python
"""
Phase 18 Automated Validation Script
=====================================

Orchestrates complete Phase 18 acceptance testing:
1. Re-ingests all PDFs from ./documents_to_ingest using layout-aware parsing
2. Runs unit tests (test_layout_aware_ingestion.py)
3. Validates metadata enrichment (validate_phase18_metadata.py)
4. Executes smoke queries against running app
5. Reports PASS/FAIL summary

Exit code: 0 on success, non-zero on any failure

Usage:
    python validate_phase18.py

Prerequisites:
    - System dependencies installed (libmagic-dev, poppler-utils)
    - unstructured[pdf] installed (pip install -r campus_rag_chatbot/requirements.txt)
    - App running on localhost:8000 (python campus_rag_chatbot/app.py)
"""

import sys
import os
import subprocess
import json
import time
import shutil
import requests
from pathlib import Path
from typing import List, Dict, Tuple

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CAMPUS_RAG_DIR = PROJECT_ROOT / "campus_rag_chatbot"
DOCUMENTS_DIR = CAMPUS_RAG_DIR / "documents_to_ingest"
VECTOR_STORE_PATH = CAMPUS_RAG_DIR / "vector_store"
REGISTRY_PATH = CAMPUS_RAG_DIR / "document_registry.json"

# Test configuration
APP_URL = "http://localhost:8000"
SMOKE_QUERIES = [
    "list all the deans",
    "how to attain honorable mention",
    "list academic awards"
]

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print section header"""
    print(f"\n{'=' * 70}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{'=' * 70}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠ {text}{RESET}")


def check_app_running() -> bool:
    """Check if app is running on localhost:8000"""
    try:
        response = requests.get(f"{APP_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def backup_vector_store():
    """Backup existing vector store"""
    if VECTOR_STORE_PATH.exists():
        backup_path = VECTOR_STORE_PATH.parent / "vector_store_backup_pre_phase18"
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(VECTOR_STORE_PATH, backup_path)
        print_success(f"Backed up vector store to: {backup_path.name}")
        return True
    return False


def clear_vector_store():
    """Clear existing vector store for clean re-ingestion"""
    if VECTOR_STORE_PATH.exists():
        shutil.rmtree(VECTOR_STORE_PATH)
        print_success("Cleared existing vector store")
    
    if REGISTRY_PATH.exists():
        # Backup registry
        backup_registry = REGISTRY_PATH.parent / "document_registry_backup.json"
        shutil.copy(REGISTRY_PATH, backup_registry)
        # Clear registry
        with open(REGISTRY_PATH, 'w') as f:
            json.dump({}, f)
        print_success("Cleared document registry")


def reingest_pdfs() -> Tuple[bool, str]:
    """Re-ingest all PDFs from documents_to_ingest directory"""
    print_header("STEP 1: Re-ingesting PDFs with Phase 18 Layout-Aware Parsing")
    
    # Check documents directory
    if not DOCUMENTS_DIR.exists():
        return False, f"Documents directory not found: {DOCUMENTS_DIR}"
    
    pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))
    if not pdf_files:
        return False, f"No PDF files found in {DOCUMENTS_DIR}"
    
    print(f"Found {len(pdf_files)} PDF(s) to ingest:")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    print()
    
    # Backup and clear existing vector store
    backup_vector_store()
    clear_vector_store()
    
    # Import document manager
    sys.path.insert(0, str(CAMPUS_RAG_DIR))
    try:
        from document_manager import DocumentManager, LAYOUT_AWARE_PARSER
        
        if not LAYOUT_AWARE_PARSER:
            print_warning("unstructured library not available - will use fallback linear chunking")
        else:
            print_success("Layout-aware parser available (unstructured library loaded)")
        
        # Initialize document manager
        manager = DocumentManager(
            registry_path=REGISTRY_PATH,
            vector_store_path=VECTOR_STORE_PATH
        )
        
        # Ingest each PDF
        success_count = 0
        failed_count = 0
        
        for pdf_file in pdf_files:
            print(f"\nIngesting: {pdf_file.name}")
            success, message = manager.ingest_document(
                file_path=pdf_file,
                chunk_size=500,
                chunk_overlap=50,
                skip_duplicates=False
            )
            
            if success:
                print_success(message)
                success_count += 1
            else:
                print_error(message)
                failed_count += 1
        
        print(f"\n{'-' * 70}")
        print(f"Ingestion complete: {success_count} succeeded, {failed_count} failed")
        
        if failed_count > 0:
            return False, f"{failed_count} PDF(s) failed to ingest"
        
        return True, f"Successfully ingested {success_count} PDF(s)"
        
    except Exception as e:
        return False, f"Ingestion error: {str(e)}"


def run_unit_tests() -> Tuple[bool, str]:
    """Run unit tests for Phase 18 functions"""
    print_header("STEP 2: Running Unit Tests")
    
    test_file = CAMPUS_RAG_DIR / "test_layout_aware_ingestion.py"
    if not test_file.exists():
        return False, f"Test file not found: {test_file}"
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            cwd=CAMPUS_RAG_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            return True, "Unit tests passed"
        else:
            return False, f"Unit tests failed (exit code {result.returncode})"
            
    except subprocess.TimeoutExpired:
        return False, "Unit tests timed out"
    except Exception as e:
        return False, f"Error running unit tests: {str(e)}"


def validate_metadata() -> Tuple[bool, str]:
    """Run metadata validation script"""
    print_header("STEP 3: Validating Phase 18 Metadata Enrichment")
    
    validation_script = CAMPUS_RAG_DIR / "validate_phase18_metadata.py"
    if not validation_script.exists():
        return False, f"Validation script not found: {validation_script}"
    
    try:
        result = subprocess.run(
            [sys.executable, str(validation_script)],
            cwd=CAMPUS_RAG_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # Check for "VALIDATION PASSED" in output
        if "VALIDATION PASSED" in result.stdout:
            return True, "Metadata validation passed"
        else:
            return False, "Metadata validation failed"
            
    except subprocess.TimeoutExpired:
        return False, "Metadata validation timed out"
    except Exception as e:
        return False, f"Error running metadata validation: {str(e)}"


def execute_smoke_queries() -> Tuple[bool, str]:
    """Execute smoke test queries against running app"""
    print_header("STEP 4: Executing Smoke Test Queries")
    
    if not check_app_running():
        return False, "App not running on localhost:8000. Start with: python campus_rag_chatbot/app.py"
    
    print_success("App is running")
    print()
    
    # Wait for vector store to be loaded
    print("Waiting for vector store to load...")
    time.sleep(2)
    
    results = []
    session_id = None
    
    for i, query in enumerate(SMOKE_QUERIES, 1):
        print(f"\nQuery {i}: \"{query}\"")
        
        try:
            payload = {"message": query}
            if session_id:
                payload["session_id"] = session_id
            
            response = requests.post(
                f"{APP_URL}/chat",
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                print_error(f"HTTP {response.status_code}")
                results.append(False)
                continue
            
            data = response.json()
            session_id = data.get("session_id")
            
            # Check response quality
            answer = data.get("answer", "")
            confidence = data.get("confidence_level", "")
            rejected = data.get("rejected", True)
            mode = data.get("mode", "")
            sources = data.get("sources", [])
            
            print(f"  Mode: {mode}")
            print(f"  Confidence: {confidence}")
            print(f"  Rejected: {rejected}")
            print(f"  Sources: {len(sources)}")
            print(f"  Answer preview: {answer[:150]}...")
            
            # Success criteria: not rejected, has sources, reasonable confidence
            if not rejected and len(sources) > 0 and confidence in ["Medium", "High"]:
                print_success("Query succeeded")
                results.append(True)
            else:
                print_warning("Query returned low-quality answer")
                results.append(False)
                
        except requests.Timeout:
            print_error("Query timed out")
            results.append(False)
        except Exception as e:
            print_error(f"Query error: {str(e)}")
            results.append(False)
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n{'-' * 70}")
    print(f"Smoke tests: {success_count}/{total_count} queries succeeded")
    
    if success_count == total_count:
        return True, f"All {total_count} smoke queries passed"
    elif success_count > 0:
        return False, f"Only {success_count}/{total_count} smoke queries passed"
    else:
        return False, "All smoke queries failed"


def main():
    """Main validation orchestration"""
    print_header("Phase 18 Automated Validation")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Documents: {DOCUMENTS_DIR}")
    print()
    
    # Track results
    steps = []
    
    # Step 1: Re-ingest PDFs
    success, message = reingest_pdfs()
    steps.append(("Re-ingestion", success, message))
    if not success:
        print_error(f"FAILED: {message}")
        print_warning("Stopping validation due to ingestion failure")
        print_final_summary(steps)
        sys.exit(1)
    
    # Step 2: Unit tests
    success, message = run_unit_tests()
    steps.append(("Unit Tests", success, message))
    if not success:
        print_error(f"FAILED: {message}")
    
    # Step 3: Metadata validation
    success, message = validate_metadata()
    steps.append(("Metadata Validation", success, message))
    if not success:
        print_error(f"FAILED: {message}")
    
    # Step 4: Smoke queries
    success, message = execute_smoke_queries()
    steps.append(("Smoke Queries", success, message))
    if not success:
        print_error(f"FAILED: {message}")
    
    # Final summary
    print_final_summary(steps)
    
    # Exit with appropriate code
    all_passed = all(success for _, success, _ in steps)
    sys.exit(0 if all_passed else 1)


def print_final_summary(steps: List[Tuple[str, bool, str]]):
    """Print final validation summary"""
    print_header("VALIDATION SUMMARY")
    
    for step_name, success, message in steps:
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"{step_name:.<40} {status}")
        if not success:
            print(f"  └─ {message}")
    
    print()
    
    all_passed = all(success for _, success, _ in steps)
    passed_count = sum(1 for _, success, _ in steps if success)
    total_count = len(steps)
    
    if all_passed:
        print(f"{GREEN}{'=' * 70}")
        print(f"✓ PHASE 18 VALIDATION PASSED ({passed_count}/{total_count})")
        print(f"{'=' * 70}{RESET}\n")
    else:
        print(f"{RED}{'=' * 70}")
        print(f"✗ PHASE 18 VALIDATION FAILED ({passed_count}/{total_count})")
        print(f"{'=' * 70}{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Validation interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
