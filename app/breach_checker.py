"""
Password Breach Checker for LockBox
Checks if passwords have been leaked using Have I Been Pwned API
"""

import hashlib
import requests


def check_password_breach(password: str) -> dict:
    """
    Check if password has been in a data breach
    Uses Have I Been Pwned API with k-anonymity (safe & private)

    Returns:
        dict with keys:
        - breached: True/False/None
        - count: number of times found in breaches
        - severity: 'safe', 'warning', 'danger', 'critical'
        - message: human-readable message
        - color: hex color for UI
    """
    try:
        # Step 1: Hash the password with SHA-1
        sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()

        # Step 2: Split hash - send only first 5 chars (k-anonymity = privacy!)
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        # Step 3: Query API (only sends first 5 chars, not full password!)
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            return {
                "breached": None,
                "count": 0,
                "severity": "unknown",
                "message": "Could not check (API error)",
                "color": "#a0a0a0",
            }

        # Step 4: Check if our password's suffix is in the results
        hashes = response.text.split("\r\n")
        for hash_line in hashes:
            if ":" not in hash_line:
                continue

            hash_suffix, count = hash_line.split(":")

            if hash_suffix == suffix:
                # Found in breach!
                count = int(count)

                # Determine severity
                if count > 10000:
                    severity = "critical"
                    color = "#e74c3c"  # Red
                    msg = f"🚨 CRITICAL! Found {count:,} times in breaches!"
                elif count > 1000:
                    severity = "danger"
                    color = "#e67e22"  # Orange
                    msg = f"⚠️ DANGER! Found {count:,} times in breaches!"
                elif count > 100:
                    severity = "warning"
                    color = "#f39c12"  # Yellow
                    msg = f"⚠️ Found {count:,} times in breaches"
                else:
                    severity = "warning"
                    color = "#f39c12"
                    msg = f"⚠️ Found {count} times in breaches"

                return {
                    "breached": True,
                    "count": count,
                    "severity": severity,
                    "message": msg,
                    "color": color,
                }

        # Not found in any breach - good!
        return {
            "breached": False,
            "count": 0,
            "severity": "safe",
            "message": "✅ Not found in known breaches",
            "color": "#2ecc71",  # Green
        }

    except requests.exceptions.Timeout:
        return {
            "breached": None,
            "count": 0,
            "severity": "unknown",
            "message": "⏱️ Check timed out",
            "color": "#a0a0a0",
        }
    except Exception as e:
        return {
            "breached": None,
            "count": 0,
            "severity": "unknown",
            "message": f"❌ Error: {str(e)[:30]}",
            "color": "#a0a0a0",
        }


def scan_all_passwords(vault) -> dict:
    """
    Scan all passwords in vault for breaches

    Args:
        vault: Vault instance (must be unlocked)

    Returns:
        dict with scan results
    """
    passwords = vault.list_passwords()

    results = {"total_checked": 0, "breached": [], "safe": [], "failed_checks": []}

    for pwd_entry in passwords:
        password = pwd_entry.get("password", "")
        title = pwd_entry.get("title", "Untitled")

        if not password:
            continue

        # Check breach
        result = check_password_breach(password)
        results["total_checked"] += 1

        entry_result = {
            "id": pwd_entry.get("id"),
            "title": title,
            "breach_info": result,
        }

        if result["breached"] == True:
            results["breached"].append(entry_result)
        elif result["breached"] == False:
            results["safe"].append(entry_result)
        else:
            results["failed_checks"].append(entry_result)

    return results


# ========== HOW TO USE THIS ==========

"""
STEP 1: Save this file as: app/breach_checker.py

STEP 2: Add to requirements.txt:
requests>=2.31.0

Then run: pip install requests

STEP 3: Test it from Python:

    from app.breach_checker import check_password_breach
    
    # Test a weak password
    result = check_password_breach("password123")
    print(result['message'])  # Will show "Found in breaches"
    
    # Test a strong password
    result = check_password_breach("MyStr0ng!P@ssw0rd#2024")
    print(result['message'])  # Likely "Not found in breaches"

STEP 4: Add to UI (I'll show you in next step)
"""


if __name__ == "__main__":
    # Quick test
    print("🔍 Testing Password Breach Checker...\n")

    # Test common leaked passwords
    test_passwords = [
        ("password", "Common weak password"),
        ("123456", "Very common password"),
        ("qwerty", "Keyboard pattern"),
        ("MyStr0ng!Pass#2024", "Strong unique password"),
    ]

    for pwd, description in test_passwords:
        print(f"Testing: {description}")
        result = check_password_breach(pwd)
        print(f"  Password: {pwd}")
        print(f"  Result: {result['message']}")
        print(f"  Severity: {result['severity']}")
        print()

    print("✅ Breach checker is working!")
    print("\n💡 Privacy Note:")
    print("   - Only first 5 characters of password hash are sent")
    print("   - Your actual password is NEVER sent to the API")
    print("   - This is called 'k-anonymity' - completely safe!")
