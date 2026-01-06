"""
Password Breach Checker for LockBox
Checks if passwords have been leaked using Have I Been Pwned API
"""

import hashlib
import requests


def check_password_breach(password: str) -> dict:
    """
    Check if password has been in a data breach using k-anonymity.
    Returns dict with breach metadata.
    """
    try:
        sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

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

        hashes = response.text.split("\r\n")
        for hash_line in hashes:
            if ":" not in hash_line:
                continue

            hash_suffix, count = hash_line.split(":")

            if hash_suffix == suffix:
                count = int(count)

                if count > 10000:
                    severity = "critical"
                    color = "#e74c3c"
                    msg = f"🚨 CRITICAL! Found {count:,} times in breaches!"
                elif count > 1000:
                    severity = "danger"
                    color = "#e67e22"
                    msg = f"⚠️ DANGER! Found {count:,} times in breaches!"
                elif count > 100:
                    severity = "warning"
                    color = "#f39c12"
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

        return {
            "breached": False,
            "count": 0,
            "severity": "safe",
            "message": "✅ Not found in known breaches",
            "color": "#2ecc71",
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
    Scan all passwords in vault for breaches.
    """
    passwords = vault.list_passwords()

    results = {"total_checked": 0, "breached": [], "safe": [], "failed_checks": []}

    for pwd_entry in passwords:
        password = pwd_entry.get("password", "")
        title = pwd_entry.get("title", "Untitled")

        if not password:
            continue

        result = check_password_breach(password)
        results["total_checked"] += 1

        entry_result = {
            "id": pwd_entry.get("id"),
            "title": title,
            "breach_info": result,
        }

        if result["breached"] is True:
            results["breached"].append(entry_result)
        elif result["breached"] is False:
            results["safe"].append(entry_result)
        else:
            results["failed_checks"].append(entry_result)

    return results
