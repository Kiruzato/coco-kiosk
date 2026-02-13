"""
CQE Application Diagnostic and Fix Script
==========================================
Run this script to diagnose and fix common issues that prevent the app from starting.

Usage:
    python diagnose_and_fix.py
"""

import os
import sys
import socket
import subprocess
import time


def check_port_available(port: int) -> tuple[bool, str]:
    """Check if a port is available for binding."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()

        if result == 0:
            return False, f"Port {port} is IN USE by another process"
        else:
            return True, f"Port {port} is available"
    except Exception as e:
        return False, f"Error checking port: {e}"


def find_python_processes() -> list:
    """Find all Python processes that might be the app."""
    processes = []
    try:
        # Windows: use tasklist
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True,
            timeout=10
        )
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:  # Skip header
            if 'python.exe' in line.lower():
                parts = line.replace('"', '').split(',')
                if len(parts) >= 2:
                    processes.append({'name': parts[0], 'pid': parts[1]})
    except Exception as e:
        print(f"  Warning: Could not list processes: {e}")

    return processes


def kill_python_processes(confirm: bool = True) -> int:
    """Kill all Python processes."""
    killed = 0
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/IM', 'python.exe'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if 'SUCCESS' in result.stdout:
            # Count successes
            killed = result.stdout.count('SUCCESS')
    except Exception as e:
        print(f"  Warning: Could not kill processes: {e}")

    return killed


def check_imports() -> tuple[bool, list]:
    """Check if all required modules can be imported."""
    errors = []
    modules = [
        'campus_index',
        'campus_query_parser',
        'campus_schema',
        'entity_manager',
        'entity_registry'
    ]

    # Change to app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)

    for module in modules:
        try:
            __import__(module)
        except Exception as e:
            errors.append(f"{module}: {e}")

    return len(errors) == 0, errors


def main():
    print("=" * 60)
    print("CQE Application Diagnostic Tool")
    print("=" * 60)
    print()

    # 1. Check port
    print("[1] Checking port 8000...")
    port_ok, port_msg = check_port_available(8000)
    print(f"    {port_msg}")

    # 2. Check for Python processes
    print()
    print("[2] Checking for running Python processes...")
    processes = find_python_processes()
    if processes:
        print(f"    Found {len(processes)} Python process(es):")
        for p in processes[:5]:  # Show first 5
            print(f"      - PID {p['pid']}")
        if len(processes) > 5:
            print(f"      ... and {len(processes) - 5} more")
    else:
        print("    No Python processes found")

    # 3. Check imports
    print()
    print("[3] Checking module imports...")
    imports_ok, import_errors = check_imports()
    if imports_ok:
        print("    All modules import correctly")
    else:
        print("    Import errors found:")
        for err in import_errors:
            print(f"      - {err}")

    # 4. Summary and recommendations
    print()
    print("=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)

    issues_found = 0

    if not port_ok:
        issues_found += 1
        print()
        print(f"ISSUE: Port 8000 is in use")
        print("  FIX: Kill existing processes or use a different port")

    if processes:
        issues_found += 1
        print()
        print(f"ISSUE: {len(processes)} Python process(es) running")
        print("  FIX: Run cleanup to kill these processes")

    if not imports_ok:
        issues_found += 1
        print()
        print("ISSUE: Module import errors")
        print("  FIX: Check the error messages above")

    if issues_found == 0:
        print()
        print("No issues detected! The app should start normally.")
        print()
        print("If you still have problems, try:")
        print("  1. Restart your computer")
        print("  2. Check antivirus/firewall settings")
        print("  3. Run the app with admin privileges")
        return 0

    # Offer to fix
    print()
    print(f"Found {issues_found} issue(s).")

    if processes and not port_ok:
        print()
        response = input("Would you like to kill all Python processes? (y/n): ").strip().lower()
        if response == 'y':
            print()
            print("Killing Python processes...")
            killed = kill_python_processes()
            print(f"  Killed {killed} process(es)")

            # Wait and recheck port
            time.sleep(2)
            port_ok, port_msg = check_port_available(8000)
            print(f"  {port_msg}")

            if port_ok:
                print()
                print("Port 8000 is now available. Try starting the app again!")
            else:
                print()
                print("Port 8000 still in use. Another program may be using it.")
                print("Try: netstat -ano | findstr :8000")

    return issues_found


if __name__ == "__main__":
    try:
        exit_code = main()
        print()
        input("Press Enter to exit...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
