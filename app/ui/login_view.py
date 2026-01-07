import json
import os
import sys
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from app.constants import COLORS, VAULT_FILE, CONFIG_FILE, EMPTY_VAULT
from app.core.crypto import derive_key, encrypt
from app.core.recovery import RecoverySystem
from app.core.security import SecurityManager
from app.core.storage import save_vault
from app.ui.dialogs.recovery_dialog import RecoveryDialogMixin


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class LoginViewMixin(RecoveryDialogMixin):
    def show_login(self):
        """Display login screen with recovery option"""
        self.clear()
        self.setup_state = None

        has_vault = VAULT_FILE.exists() and VAULT_FILE.stat().st_size > 0
        lock_seconds = self._get_setup_lock_seconds()

        container = ctk.CTkFrame(self.app, fg_color=COLORS["bg_primary"])
        container.pack(fill="both", expand=True)

        login_box = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=22,
            width=480,
            height=480,
            border_width=1,
            border_color=COLORS["bg_secondary"],
        )
        login_box.place(relx=0.5, rely=0.5, anchor="center")
        login_box.pack_propagate(False)

        title_row = ctk.CTkFrame(login_box, fg_color="transparent")
        title_row.pack(pady=(40, 6))

        try:
            logo_paths = [
                get_resource_path("logo.png"),
                os.path.join(os.path.dirname(__file__), "..", "logo.png"),
                "logo.png",
            ]
            for logo_path in logo_paths:
                if os.path.exists(logo_path):
                    logo_image = Image.open(logo_path).convert("RGBA")
                    self.logo_photo = ctk.CTkImage(
                        light_image=logo_image, dark_image=logo_image, size=(52, 52)
                    )
                    logo_label = ctk.CTkLabel(title_row, image=self.logo_photo, text="")
                    logo_label.pack(side="left", padx=(0, 2))
                    break
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")

        ctk.CTkLabel(
            title_row,
            text="LockBox",
            font=("Segoe UI", 34, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        ctk.CTkLabel(
            login_box,
            text="Private by default",
            font=("Segoe UI", 13),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 28))

        pwd_placeholder = (
            "Enter PIN/Password" if has_vault else "Create PIN/Password (5+ chars)"
        )

        pwd_entry = ctk.CTkEntry(
            login_box,
            width=380,
            height=45,
            placeholder_text=pwd_placeholder,
            show="●",
            font=("Segoe UI", 13),
            corner_radius=10,
            border_width=1,
            border_color=COLORS["bg_secondary"],
        )
        pwd_entry.pack(pady=(0, 10))

        status = ctk.CTkLabel(
            login_box,
            text="",
            font=("Segoe UI", 11),
            text_color=COLORS["danger"],
        )
        status.pack(pady=(0, 5))

        def unlock():
            try:
                password = pwd_entry.get()

                if len(password) < 5:
                    status.configure(text="⚠️ Password must be at least 5 characters")
                    return

                if not has_vault:
                    if lock_seconds > 0:
                        status.configure(
                            text=f"Setup locked. Try again in {self._format_countdown(lock_seconds)}"
                        )
                        return
                    self._start_new_account_flow(password)
                    return

                self.vault.unlock(password)
                self.show_vault()

            except ValueError as e:
                status.configure(text=str(e))
            except Exception as e:
                status.configure(text="Unexpected error occurred")
                print("Unlock error:", e)

        pwd_entry.bind("<Return>", lambda e: unlock())

        ctk.CTkButton(
            login_box,
            text="Unlock Vault" if has_vault else "Create Account",
            width=380,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=10,
            command=unlock,
        ).pack(pady=(15, 10))

        try:
            recovery = RecoverySystem(self.vault.path)

            if has_vault and recovery.has_recovery_phrase():
                ctk.CTkButton(
                    login_box,
                    text="🔑 Forgot Password? Use Recovery Phrase",
                    width=380,
                    height=40,
                    font=("Segoe UI", 12, "bold"),
                    fg_color="transparent",
                    hover_color=COLORS["bg_secondary"],
                    text_color=COLORS["accent"],
                    border_width=2,
                    border_color=COLORS["accent"],
                    corner_radius=10,
                    command=self.show_recovery_unlock_dialog,
                ).pack(pady=(5, 10))
        except Exception as e:
            print(f"Recovery check failed: {e}")

        ctk.CTkLabel(
            login_box,
            text="Enter your PIN/Password to unlock",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(10, 0))

        pwd_entry.focus()

    # === New Account Creation Flow ===
    def _start_new_account_flow(self, first_password: str):
        """Inline step 1: confirm password before recovery phrase."""
        self._render_setup_password_confirm(first_password)

    # === Recovery Phrase ===
    def _render_setup_password_confirm(self, first_password: str):
        screen = self._new_screen("Account Setup - Step 1")

        ctk.CTkLabel(
            screen,
            text="Confirm your PIN/Password",
            font=("Segoe UI", 22, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(10, 6))

        helper = "Enter the same PIN/Password again. This protects your vault and will be required to unlock."
        ctk.CTkLabel(
            screen,
            text=helper,
            font=("Segoe UI", 12),
            wraplength=460,
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 12))

        first_pwd_display = ctk.CTkEntry(
            screen, width=380, height=40, show="●", font=("Segoe UI", 13)
        )
        first_pwd_display.insert(0, first_password)
        first_pwd_display.configure(state="disabled")
        first_pwd_display.pack(pady=4)

        confirm_entry = ctk.CTkEntry(
            screen,
            width=380,
            height=40,
            placeholder_text="Re-enter",
            show="●",
            font=("Segoe UI", 13),
        )
        confirm_entry.pack(pady=10)

        status = ctk.CTkLabel(screen, text="", font=("Segoe UI", 12))
        status.pack(pady=6)

        def proceed_to_recovery():
            confirm_password = confirm_entry.get()
            if not confirm_password:
                status.configure(
                    text="⚠️ Please confirm your entry", text_color=COLORS["danger"]
                )
                return
            if first_password != confirm_password:
                status.configure(
                    text="❌ Entries don't match!", text_color=COLORS["danger"]
                )
                confirm_entry.delete(0, "end")
                confirm_entry.focus()
                return

            recovery = RecoverySystem(self.vault.path)
            phrase = recovery.generate_recovery_phrase()

            self.setup_state = {
                "password": first_password,
                "phrase": phrase,
                "salt": os.urandom(16),
                "copied": False,
                "downloaded": False,
            }

            self._render_recovery_show()

        confirm_entry.bind("<Return>", lambda e: proceed_to_recovery())

        button_row = ctk.CTkFrame(screen, fg_color="transparent")
        button_row.pack(pady=18)

        ctk.CTkButton(
            button_row,
            text="❌ Cancel",
            width=150,
            height=42,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=self._cancel_setup_and_return,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            button_row,
            text="✅ Next: Recovery Phrase",
            width=220,
            height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=proceed_to_recovery,
        ).pack(side="left", padx=8)

        confirm_entry.focus()

    def _render_recovery_show(self):
        if not self.setup_state:
            self._cancel_setup_and_return()
            return

        screen = self._new_screen("Account Setup - Step 2")
        phrase = self.setup_state["phrase"]

        ctk.CTkLabel(
            screen,
            text="Save your 24-word recovery phrase",
            font=("Segoe UI", 22, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(10, 6))

        ctk.CTkLabel(
            screen,
            text="You must copy or download these words. They are the only way to recover your vault.",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            wraplength=520,
        ).pack(pady=(0, 12))

        recovery = RecoverySystem(self.vault.path)
        formatted_words = recovery.format_phrase_for_display(phrase)

        grid = ctk.CTkFrame(screen, fg_color=COLORS["bg_card"], corner_radius=12)
        grid.pack(fill="x", padx=12, pady=10)

        grid_inner = ctk.CTkFrame(grid, fg_color="transparent")
        grid_inner.pack(padx=20, pady=16)

        label_refs = []
        hidden = {"visible": False}

        cols = [ctk.CTkFrame(grid_inner, fg_color="transparent") for _ in range(3)]
        for idx, col in enumerate(cols):
            col.grid(row=0, column=idx, padx=12, sticky="n")

        for num, word in formatted_words:
            col = cols[(num - 1) % 3]
            row = ctk.CTkFrame(col, fg_color=COLORS["bg_secondary"], corner_radius=8)
            row.pack(pady=4, fill="x", ipady=8, ipadx=10)

            ctk.CTkLabel(
                row,
                text=f"{num}.",
                font=("Consolas", 12, "bold"),
                text_color=COLORS["text_secondary"],
                width=26,
                anchor="e",
            ).pack(side="left", padx=(4, 8))

            val_label = ctk.CTkLabel(
                row,
                text="••••",
                font=("Consolas", 13, "bold"),
                text_color=COLORS["accent"],
                anchor="w",
            )
            val_label.pack(side="left")
            label_refs.append((val_label, word))

        status = ctk.CTkLabel(screen, text="", font=("Segoe UI", 12))
        status.pack(pady=6)

        def hide_words():
            for lbl, _w in label_refs:
                lbl.configure(text="••••")
            hidden["visible"] = False

        def reveal_words():
            for lbl, w in label_refs:
                lbl.configure(text=w)
            hidden["visible"] = True
            screen.after(12000, lambda: hide_words() if hidden["visible"] else None)

        def toggle_visibility():
            if hidden["visible"]:
                hide_words()
            else:
                reveal_words()

        def mark_copied():
            self.setup_state["copied"] = True
            maybe_enable_proceed()

        def mark_downloaded():
            self.setup_state["downloaded"] = True
            maybe_enable_proceed()

        action_row = ctk.CTkFrame(screen, fg_color="transparent")
        action_row.pack(pady=10)

        ctk.CTkButton(
            action_row,
            text="👁️ Reveal / Hide",
            width=170,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=toggle_visibility,
        ).pack(side="left", padx=6)

        def copy_phrase():
            import pyperclip

            pyperclip.copy(phrase)
            status.configure(text="Copied to clipboard", text_color=COLORS["success"])
            mark_copied()

        ctk.CTkButton(
            action_row,
            text="📋 Copy",
            width=120,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=copy_phrase,
        ).pack(side="left", padx=6)

        def download_phrase():
            save_path = filedialog.asksaveasfilename(
                title="Save Recovery Phrase",
                defaultextension=".txt",
                initialfile="LockBox_Recovery_Phrase.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )

            if save_path:
                try:
                    numbered = [f"{num}. {word}" for num, word in formatted_words]
                    content = [
                        "LOCKBOX RECOVERY PHRASE",
                        "IMPORTANT: Anyone with these words can unlock your vault. Keep offline and private.",
                        "",
                        "Words (numbered):",
                        *numbered,
                        "",
                        "Phrase (single line):",
                        phrase,
                        "",
                        "Store safely. Do not email or share.",
                    ]

                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

                    status.configure(text="Downloaded", text_color=COLORS["success"])
                    mark_downloaded()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")

        ctk.CTkButton(
            action_row,
            text="💾 Download",
            width=140,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=download_phrase,
        ).pack(side="left", padx=6)

        proceed_row = ctk.CTkFrame(screen, fg_color="transparent")
        proceed_row.pack(pady=18)

        proceed_btn = ctk.CTkButton(
            proceed_row,
            text="✅ Proceed to Verification",
            width=260,
            height=44,
            font=("Segoe UI", 15, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=10,
            state="disabled",
            command=self._render_recovery_verify,
        )
        proceed_btn.pack(side="left", padx=8)

        ctk.CTkButton(
            proceed_row,
            text="❌ Cancel",
            width=140,
            height=44,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=self._cancel_setup_and_return,
        ).pack(side="left", padx=8)

        def maybe_enable_proceed():
            if self.setup_state.get("copied") or self.setup_state.get("downloaded"):
                proceed_btn.configure(state="normal")

        hide_words()

    def _render_recovery_verify(self):
        if not self.setup_state:
            self._cancel_setup_and_return()
            return

        screen = self._new_screen("Account Setup - Step 3")
        phrase = self.setup_state["phrase"]
        words = phrase.split()

        ctk.CTkLabel(
            screen,
            text="Verify your recovery phrase",
            font=("Segoe UI", 22, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(10, 6))

        ctk.CTkLabel(
            screen,
            text="Enter the requested words. 3 attempts max before a 30-minute lock.",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            wraplength=520,
        ).pack(pady=(0, 12))

        positions = sorted(__import__("random").sample(range(1, 25), 4))
        entries = []

        form = ctk.CTkFrame(screen, fg_color="transparent")
        form.pack(pady=10)

        for pos in positions:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(pady=6)
            ctk.CTkLabel(
                row,
                text=f"Word #{pos}",
                font=("Segoe UI", 13, "bold"),
                width=90,
                anchor="e",
            ).pack(side="left", padx=6)
            entry = ctk.CTkEntry(row, width=220, height=38, font=("Consolas", 13))
            entry.pack(side="left", padx=6)
            entries.append((pos, entry))

        status = ctk.CTkLabel(screen, text="", font=("Segoe UI", 12))
        status.pack(pady=8)

        attempts = {"count": 0}

        def submit():
            attempts["count"] += 1
            correct = True
            for pos, entry in entries:
                entered = entry.get().strip().lower()
                if entered != words[pos - 1].lower():
                    correct = False
                    entry.configure(border_color=COLORS["danger"], border_width=2)
                else:
                    entry.configure(border_color=COLORS["success"], border_width=2)

            if correct:
                status.configure(
                    text="✅ Verified. Creating your vault...",
                    text_color=COLORS["success"],
                )
                screen.after(600, self._finalize_account_creation)
                return

            remaining = 3 - attempts["count"]
            if remaining <= 0:
                status.configure(
                    text="🔒 Verification failed 3 times. Locked for 30 minutes.",
                    text_color=COLORS["danger"],
                )
                screen.after(
                    800,
                    lambda: [self._set_setup_lock(30), self._cancel_setup_and_return()],
                )
                return

            status.configure(
                text=f"❌ Incorrect words. {remaining} attempt(s) left.",
                text_color=COLORS["danger"],
            )

        button_row = ctk.CTkFrame(screen, fg_color="transparent")
        button_row.pack(pady=16)

        ctk.CTkButton(
            button_row,
            text="❌ Cancel",
            width=150,
            height=42,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=self._cancel_setup_and_return,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            button_row,
            text="✅ Verify & Create",
            width=200,
            height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=submit,
        ).pack(side="left", padx=8)

        entries[0][1].focus()

    def _finalize_account_creation(self):
        """Write vault file and recovery hash after successful verification."""
        if not self.setup_state:
            self._cancel_setup_and_return()
            return

        password = self.setup_state["password"]
        phrase = self.setup_state["phrase"]
        salt = self.setup_state["salt"]

        raw = json.dumps(EMPTY_VAULT, indent=2).encode()
        key = derive_key(password, salt)
        encrypted = encrypt(raw, key)

        save_vault(salt + encrypted)

        recovery = RecoverySystem(VAULT_FILE)
        recovery.save_recovery_hash(phrase, vault_key=key)

        self._clear_setup_lock()
        self.setup_state = None

        try:
            messagebox.showinfo(
                "Welcome",
                "Account created successfully. Keep your recovery phrase safe!",
            )
        except Exception:
            pass

        self.vault.unlock(password)
        self.show_vault()

    def _cancel_setup_and_return(self):
        """Abort setup and return to login."""
        self.setup_state = None
        self.show_login()

    def _new_screen(self, title: str):
        """Reset main window content and return a container for the screen."""
        self.clear()
        container = ctk.CTkFrame(self.app, fg_color=COLORS["bg_primary"])
        container.pack(fill="both", expand=True)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(pady=(24, 10))
        ctk.CTkLabel(
            header,
            text=title,
            font=("Segoe UI", 26, "bold"),
            text_color=COLORS["text_primary"],
        ).pack()

        content = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["bg_secondary"],
        )
        content.pack(fill="both", expand=True, padx=30, pady=(0, 24))
        return content

    # === Recovery Unlock for existing users ===
    def show_recovery_unlock_dialog(self):
        """Unlock vault with recovery phrase with lockout rules."""
        dialog = self.create_dialog("🔐 Recover Vault", 600, 600)

        security = SecurityManager(VAULT_FILE.parent / "security.json")
        locked, minutes = security.is_locked_out()
        if locked:
            ctk.CTkLabel(
                dialog,
                text=f"Too many attempts. Try again in {minutes} minutes.",
                font=("Segoe UI", 13),
                text_color=COLORS["danger"],
            ).pack(pady=20)
            ctk.CTkButton(
                dialog,
                text="Close",
                width=200,
                height=40,
                fg_color="gray30",
                hover_color="gray40",
                command=dialog.destroy,
            ).pack(pady=10)
            return

        ctk.CTkLabel(
            dialog, text="Recover Your Vault", font=("Segoe UI", 24, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            dialog,
            text="Enter your 24-word recovery phrase below.",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
        ).pack(pady=10)

        phrase_box = ctk.CTkTextbox(
            dialog,
            width=540,
            height=200,
            font=("Consolas", 12),
            border_width=2,
            border_color=COLORS["bg_secondary"],
        )
        phrase_box.pack(pady=15, padx=30)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=10)

        def attempt_recovery():
            phrase = phrase_box.get("1.0", "end-1c").strip()

            recovery = RecoverySystem(self.vault.path)

            valid, error = recovery.validate_phrase_format(phrase)
            if not valid:
                status.configure(text=f"❌ {error}", text_color=COLORS["danger"])
                return

            try:
                self.vault.unlock_with_recovery(phrase)
                security.record_successful_login()
                dialog.destroy()
                self.show_vault()
                messagebox.showinfo("Success", "Vault unlocked successfully!")
            except Exception as e:
                remaining = security.record_failed_login()
                if remaining > 0:
                    status.configure(
                        text=f"❌ {str(e)} ({remaining} attempts left)",
                        text_color=COLORS["danger"],
                    )
                else:
                    status.configure(
                        text="🔒 Too many attempts. Locked for 30 minutes.",
                        text_color=COLORS["danger"],
                    )

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(pady=20)

        ctk.CTkButton(
            button_row,
            text="❌ Cancel",
            width=150,
            height=45,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_row,
            text="🔓 Unlock Vault",
            width=250,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=attempt_recovery,
        ).pack(side="left", padx=10)

    # === Setup lock helpers ===
    def _get_setup_lock_seconds(self) -> int:
        if not CONFIG_FILE.exists():
            return 0
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            lock_until = data.get("setup_lock_until")
            if not lock_until:
                return 0
            ts = datetime.fromisoformat(lock_until)
            remaining = (ts - datetime.now()).total_seconds()
            if remaining <= 0:
                self._clear_setup_lock()
                return 0
            return int(remaining)
        except Exception:
            return 0

    def _set_setup_lock(self, minutes: int):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["setup_lock_until"] = (
            datetime.now() + timedelta(minutes=minutes)
        ).isoformat()
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)

    def _clear_setup_lock(self):
        if not CONFIG_FILE.exists():
            return
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            data.pop("setup_lock_until", None)
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _format_countdown(self, seconds: int) -> str:
        minutes, secs = divmod(max(0, seconds), 60)
        return f"{int(minutes):02d}:{int(secs):02d}"
