"""
QR Code Password Sharing for LockBox
Generate temporary QR codes to transfer passwords to mobile
"""

import qrcode
import json
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageTk


class QRShare:
    """Generate QR codes for password sharing"""

    def generate_qr_image(self, text_data: str):
        """
        Generate QR code image from text

        Args:
            text_data: Text to encode in QR code

        Returns:
            PIL Image object
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(text_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        return img

    def create_password_qr(self, title: str, username: str, password: str):
        """Create QR for password entry - human readable format"""
        readable_text = f"""🔐 LOCKBOX PASSWORD

━━━━━━━━━━━━━━━━━━━━━
Title: {title}
━━━━━━━━━━━━━━━━━━━━━

👤 USERNAME:
{username}

🔑 PASSWORD:
{password}

━━━━━━━━━━━━━━━━━━━━━
⏱️ Expires in: 60 seconds

💡 TIP: Tap and hold text above
   to copy username or password!
━━━━━━━━━━━━━━━━━━━━━"""

        return self.generate_qr_image(readable_text)

    def create_api_key_qr(self, service: str, key: str):
        """Create QR for API key - human readable"""
        readable_text = f"""🔑 LOCKBOX API KEY

━━━━━━━━━━━━━━━━━━━━━
Service: {service}
━━━━━━━━━━━━━━━━━━━━━

🔐 API KEY:
{key}

━━━━━━━━━━━━━━━━━━━━━
⏱️ Expires in: 60 seconds

💡 TIP: Tap and hold key above
   to copy it to clipboard!
━━━━━━━━━━━━━━━━━━━━━"""

        return self.generate_qr_image(readable_text)

    def create_note_qr(self, title: str, content: str):
        """Create QR for secure note - human readable"""
        # Truncate long notes for QR code (max 500 chars)
        if len(content) > 500:
            preview = content[:497] + "..."
        else:
            preview = content

        readable_text = f"""📝 LOCKBOX NOTE

━━━━━━━━━━━━━━━━━━━━━
Title: {title}
━━━━━━━━━━━━━━━━━━━━━

📄 CONTENT:
{preview}

━━━━━━━━━━━━━━━━━━━━━
⏱️ Expires in: 60 seconds

💡 TIP: Tap and hold to copy!
━━━━━━━━━━━━━━━━━━━━━"""

        return self.generate_qr_image(readable_text)

    def create_ssh_key_qr(self, name: str, private_key: str):
        """Create QR for SSH key - human readable"""
        # Truncate very long keys
        if len(private_key) > 800:
            key_preview = private_key[:797] + "..."
            warning = "\n⚠️ Key truncated! Full key too long for QR."
        else:
            key_preview = private_key
            warning = ""

        readable_text = f"""🗝️ LOCKBOX SSH KEY

━━━━━━━━━━━━━━━━━━━━━
Name: {name}
━━━━━━━━━━━━━━━━━━━━━

🔐 PRIVATE KEY:
{key_preview}{warning}

━━━━━━━━━━━━━━━━━━━━━
⏱️ Expires in: 60 seconds

💡 TIP: Tap and hold to copy!
━━━━━━━━━━━━━━━━━━━━━"""

        return self.generate_qr_image(readable_text)

    def create_totp_secret_qr(self, name: str, secret: str, issuer: str = ""):
        """
        Create QR for TOTP secret (for adding to phone authenticator app)
        Uses standard otpauth:// URI format that Google Authenticator understands
        """
        # Standard TOTP URI format
        if issuer:
            otpauth_uri = (
                f"otpauth://totp/{issuer}:{name}?secret={secret}&issuer={issuer}"
            )
        else:
            otpauth_uri = f"otpauth://totp/{name}?secret={secret}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(otpauth_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        return img
