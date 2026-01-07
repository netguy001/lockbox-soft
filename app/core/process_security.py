"""
Process Security Module for LockBox
Anti-debugging, memory protection, and suspicious process detection
"""

import os
import sys
import ctypes
import psutil
from datetime import datetime
from typing import List, Dict


class ProcessSecurity:
    """Monitors and protects against malicious processes"""

    def __init__(self):
        self.suspicious_processes = [
            "wireshark",
            "fiddler",
            "processhacker",
            "procexp",
            "ida",
            "ollydbg",
            "x64dbg",
            "cheatengine",
            "dumper",
            "memoryreader",
            "keylogger",
        ]
        self.is_windows = os.name == "nt"

    def is_debugger_attached(self) -> bool:
        """Check if debugger is attached to process"""
        if not self.is_windows:
            return False

        try:
            return ctypes.windll.kernel32.IsDebuggerPresent() != 0
        except:
            return False

    def detect_suspicious_processes(self) -> List[Dict]:
        """Detect potentially malicious processes accessing memory"""
        suspicious = []

        try:
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)

            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    proc_name = proc.info["name"].lower() if proc.info["name"] else ""

                    # Check against known suspicious names
                    for sus_name in self.suspicious_processes:
                        if sus_name in proc_name:
                            suspicious.append(
                                {
                                    "pid": proc.info["pid"],
                                    "name": proc.info["name"],
                                    "reason": "Known suspicious process",
                                }
                            )
                            break

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            print(f"Process detection error: {e}")

        return suspicious

    def check_screen_capture(self) -> bool:
        """Detect if screen capture software is running"""
        capture_processes = [
            "obs",
            "streamlabs",
            "xsplit",
            "bandicam",
            "fraps",
            "camtasia",
            "snagit",
            "sharex",
        ]

        try:
            for proc in psutil.process_iter(["name"]):
                proc_name = proc.info["name"].lower() if proc.info["name"] else ""
                for capture in capture_processes:
                    if capture in proc_name:
                        return True
        except:
            pass

        return False

    def enable_memory_protection(self):
        """Enable DEP (Data Execution Prevention) for current process"""
        if not self.is_windows:
            return False

        try:
            PROCESS_DEP_ENABLE = 0x00000001
            ctypes.windll.kernel32.SetProcessDEPPolicy(PROCESS_DEP_ENABLE)
            return True
        except:
            return False

    def clear_clipboard(self):
        """Clear clipboard for security"""
        try:
            import pyperclip

            pyperclip.copy("")
        except:
            pass

    def get_process_connections(self) -> List[Dict]:
        """Get network connections from current process"""
        connections = []

        try:
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)

            for conn in current_process.connections():
                if conn.status == "ESTABLISHED":
                    connections.append(
                        {
                            "local": f"{conn.laddr.ip}:{conn.laddr.port}",
                            "remote": (
                                f"{conn.raddr.ip}:{conn.raddr.port}"
                                if conn.raddr
                                else "N/A"
                            ),
                            "status": conn.status,
                        }
                    )

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return connections

    def check_vm_environment(self) -> bool:
        """Detect if running in virtual machine (basic check)"""
        vm_indicators = [
            "vmware",
            "virtualbox",
            "vbox",
            "qemu",
            "xen",
            "parallels",
            "hyperv",
        ]

        try:
            # Check running processes
            for proc in psutil.process_iter(["name"]):
                proc_name = proc.info["name"].lower() if proc.info["name"] else ""
                for vm in vm_indicators:
                    if vm in proc_name:
                        return True

            # Check system info on Windows
            if self.is_windows:
                import platform

                system_info = platform.uname()
                system_str = str(system_info).lower()
                for vm in vm_indicators:
                    if vm in system_str:
                        return True

        except:
            pass

        return False

    def secure_memory_cleanup(self):
        """Attempt to clear sensitive data from memory"""
        try:
            import gc

            gc.collect()

            if self.is_windows:
                try:
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
                except:
                    pass

        except:
            pass

    def get_security_report(self) -> Dict:
        """Generate comprehensive security report"""
        return {
            "debugger_detected": self.is_debugger_attached(),
            "suspicious_processes": self.detect_suspicious_processes(),
            "screen_capture_active": self.check_screen_capture(),
            "vm_environment": self.check_vm_environment(),
            "network_connections": self.get_process_connections(),
            "timestamp": datetime.now().isoformat(),
        }

    def is_safe_to_proceed(self) -> tuple:
        """Check if environment is safe to run sensitive operations"""
        issues = []

        if self.is_debugger_attached():
            issues.append("Debugger detected")

        suspicious = self.detect_suspicious_processes()
        if suspicious:
            issues.append(f"{len(suspicious)} suspicious processes detected")

        if issues:
            return False, ", ".join(issues)

        return True, "Environment is safe"
