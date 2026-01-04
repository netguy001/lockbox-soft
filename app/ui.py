import os
import sys
import customtkinter as ctk
import pyperclip
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from .vault import Vault
from .crypto import generate_password, check_password_strength
from .constants import COLORS, AUTO_LOCK_MINUTES, CLIPBOARD_CLEAR_SECONDS, VAULT_FILE
from .qr_share import QRShare

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class LockBoxUI:

    def __init__(self):
        self.vault = Vault(str(VAULT_FILE))
        self.qr_share = QRShare()
        self.app = ctk.CTk()
        self.logo_photo = None

        # Icon setup
        try:
            icon_paths = [
                get_resource_path("lcbx.ico"),
                os.path.join(os.path.dirname(__file__), "..", "lcbx.ico"),
                "lcbx.ico",
            ]
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    self.app.iconbitmap(icon_path)
                    break
        except Exception as e:
            print(f"Warning: Could not set icon: {e}")

        self.app.title("LockBox - Secure Vault")
        self.app.geometry("1100x700")
        self.app.minsize(900, 600)

        self.current_category = "passwords"
        self.clipboard_timer = None
        self.auto_lock_timer = None
        self.sort_by = "created_desc"
        self.search_var = None  # Initialize here to prevent memory leak

        self.show_login()
        self.setup_keyboard_shortcuts()

        self.filter_options = [
            "All Items",
            "Passwords",
            "API Keys",
            "Notes",
            "SSH Keys",
            "2FA/TOTP",
            "Files",
            "Folders",
        ]

    def setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts"""
        self.app.bind("<Control-l>", lambda e: self.lock_vault())
        self.app.bind(
            "<Control-f>",
            lambda e: self.toggle_search() if hasattr(self, "search_btn") else None,
        )
        self.app.bind(
            "<Control-n>",
            lambda e: (
                self.show_add_dialog()
                if self.current_category not in ["security", "bulk_delete"]
                else None
            ),
        )
        self.app.bind("<Control-b>", lambda e: self.show_backup_dialog())
        self.app.bind("<Control-q>", lambda e: self.app.quit())
        self.app.bind(
            "<Escape>",
            lambda e: (
                self.close_search()
                if hasattr(self, "search_visible") and self.search_visible
                else None
            ),
        )

    def create_dialog(self, title, width, height):
        """Create a dialog window"""
        dialog = ctk.CTkToplevel(self.app)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(self.app)
        dialog.grab_set()
        dialog.minsize(width, height)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - width) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f"+{x}+{y}")

        return dialog

    def run(self):
        """Start the application"""
        self.app.mainloop()

    def setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts"""
        self.app.bind(
            "<Control-l>",
            lambda e: self.lock_vault() if not self.vault.is_locked else None,
        )
        self.app.bind(
            "<Control-f>",
            lambda e: self.toggle_search() if hasattr(self, "search_btn") else None,
        )
        self.app.bind(
            "<Control-n>",
            lambda e: (
                self.show_add_dialog()
                if hasattr(self, "current_category")
                and self.current_category not in ["security", "bulk_delete"]
                else None
            ),
        )
        self.app.bind(
            "<Control-b>",
            lambda e: self.show_backup_dialog() if not self.vault.is_locked else None,
        )
        self.app.bind("<Control-q>", lambda e: self.app.quit())
        self.app.bind(
            "<Escape>",
            lambda e: (
                self.close_search()
                if hasattr(self, "search_visible") and self.search_visible
                else None
            ),
        )

    def clear(self):
        """Clear all widgets"""
        for widget in self.app.winfo_children():
            widget.destroy()

    def start_auto_lock_timer(self):
        """Start auto-lock countdown"""
        if self.auto_lock_timer:
            self.app.after_cancel(self.auto_lock_timer)
        self.auto_lock_timer = self.app.after(
            AUTO_LOCK_MINUTES * 60 * 1000, self.auto_lock
        )

    def auto_lock(self):
        """Auto lock vault after inactivity"""
        self.vault.lock()
        self.show_login()
        messagebox.showinfo(
            "Auto-Locked",
            f"Vault locked after {AUTO_LOCK_MINUTES} minutes of inactivity",
        )

    def reset_activity(self):
        """Reset activity timer"""
        self.start_auto_lock_timer()

    def show_vault(self):
        """Display main vault interface"""
        self.clear()
        self.start_auto_lock_timer()
        self.setup_keyboard_shortcuts()  # ADD THIS LINE

    def show_login(self):
        """Display login screen with recovery option"""
        self.clear()

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
        title_row.pack(pady=(40, 8))

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
                        light_image=logo_image, dark_image=logo_image, size=(60, 60)
                    )
                    logo_label = ctk.CTkLabel(title_row, image=self.logo_photo, text="")
                    logo_label.pack(side="left", padx=(0, 12))
                    break
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")

        ctk.CTkLabel(
            title_row,
            text="LockBox",
            font=("Segoe UI", 36, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        ctk.CTkLabel(
            login_box,
            text="Secure Password Vault",
            font=("Segoe UI", 14),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 30))

        pwd_entry = ctk.CTkEntry(
            login_box,
            width=380,
            height=45,
            placeholder_text="Master Password",
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
                if not password:
                    status.configure(text="Enter your master password")
                    return

                self.vault.unlock(password)

                # Check if new vault - show recovery phrase
                if (
                    hasattr(self.vault, "show_recovery_phrase")
                    and self.vault.show_recovery_phrase
                ):
                    self.show_recovery_phrase_setup(self.vault.recovery_phrase)
                    delattr(self.vault, "show_recovery_phrase")
                    delattr(self.vault, "recovery_phrase")
                else:
                    self.show_vault()

            except ValueError as e:
                status.configure(text=str(e))
            except Exception as e:
                status.configure(text="Unexpected error occurred")
                print("Unlock error:", e)

        pwd_entry.bind("<Return>", lambda e: unlock())

        ctk.CTkButton(
            login_box,
            text="Unlock Vault",
            width=380,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=10,
            command=unlock,
        ).pack(pady=(15, 10))

        # Recovery button ONLY if recovery phrase exists
        try:
            from .recovery import RecoverySystem

            recovery = RecoverySystem(self.vault.path)

            if recovery.has_recovery_phrase():
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
            text="First time? Any password creates a new vault",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(10, 0))

        pwd_entry.focus()

    def show_vault(self):
        """Display main vault interface"""
        self.clear()
        self.start_auto_lock_timer()

        main = ctk.CTkFrame(self.app, fg_color=COLORS["bg_primary"])
        main.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ctk.CTkFrame(main, fg_color=COLORS["bg_secondary"], width=250)
        sidebar.pack(side="left", fill="y", padx=(0, 2))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="🔒 LockBox",
            font=("Segoe UI", 24, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=30)

        categories = [
            ("🔒 Passwords", "passwords"),
            ("🔑 API Keys", "api_keys"),
            ("📝 Secure Notes", "notes"),
            ("🗝️ SSH Keys", "ssh_keys"),
            ("🔐 2FA/TOTP", "totp_codes"),  # ← ADD THIS LINE
            ("📄 Files", "files"),
            ("📁 Folders", "encrypted_folders"),
            ("📊 Security", "security"),
            ("🗑️ Bulk Delete", "bulk_delete"),
        ]
        self.category_buttons = {}
        for label, cat in categories:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                width=210,
                height=40,
                font=("Segoe UI", 13),
                fg_color=(
                    COLORS["accent"] if cat == self.current_category else "transparent"
                ),
                hover_color=COLORS["accent_hover"],
                anchor="w",
                corner_radius=8,
                command=lambda c=cat: self.switch_category(c),
            )
            btn.pack(pady=5, padx=20)
            self.category_buttons[cat] = btn

        stats = self.vault.get_vault_stats()
        stats_frame = ctk.CTkFrame(
            sidebar, fg_color=COLORS["bg_card"], corner_radius=10, height=60
        )
        stats_frame.pack(pady=20, padx=20, fill="x")
        stats_frame.pack_propagate(False)

        ctk.CTkLabel(
            stats_frame,
            text=f"📊 Total Items: {stats['total']}",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=10)

        ctk.CTkButton(
            sidebar,
            text="💾 Backup",
            width=210,
            height=38,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=COLORS["text_primary"],
            corner_radius=8,
            command=self.show_backup_dialog,
        ).pack(pady=5, padx=20)

        ctk.CTkButton(
            sidebar,
            text="📥 Restore",
            width=210,
            height=38,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=COLORS["text_primary"],
            corner_radius=8,
            command=self.show_restore_dialog,
        ).pack(pady=5, padx=20)

        ctk.CTkButton(
            sidebar,
            text="🔐 Change Password",
            width=210,
            height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=COLORS["text_primary"],
            corner_radius=8,
            command=self.show_change_master_password,
        ).pack(pady=10, padx=20)
        ctk.CTkButton(
            sidebar,
            text="⌨️ Shortcuts",
            width=210,
            height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=COLORS["text_primary"],
            corner_radius=8,
            command=self.show_shortcuts_help,
        ).pack(pady=5, padx=20)
        ctk.CTkButton(
            sidebar,
            text="🔒 Lock Vault",
            width=210,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["danger"],
            hover_color="#c0392b",
            corner_radius=8,
            command=self.lock_vault,
        ).pack(side="bottom", pady=20, padx=20)

        # Content area
        self.content_area = ctk.CTkFrame(main, fg_color=COLORS["bg_primary"])
        self.content_area.pack(side="right", fill="both", expand=True)

        # CRITICAL FIX: Don't use trace_add, create new StringVar each time
        self.search_var = None

        self.display_category()

    def switch_category(self, category):
        """Switch between categories"""
        self.reset_activity()
        if self.current_category == category:
            return

        # Cancel TOTP auto-refresh when leaving
        if hasattr(self, "_totp_timer"):
            self.app.after_cancel(self._totp_timer)
            delattr(self, "_totp_timer")

        # Clear TOTP cards cache when switching away
        if hasattr(self, "_totp_cards"):
            delattr(self, "_totp_cards")

        # FIX: Properly cleanup search StringVar
        if hasattr(self, "search_var") and self.search_var is not None:
            try:
                traces = self.search_var.trace_info()
                for trace in traces:
                    self.search_var.trace_remove(trace[0], trace[1])
            except:
                pass
            self.search_var = None

        # FIX: Destroy search widgets before switching
        if hasattr(self, "search_entry"):
            try:
                self.search_entry.destroy()
            except:
                pass

        if hasattr(self, "search_container"):
            try:
                self.search_container.destroy()
            except:
                pass

        self.current_category = category

        # Update buttons
        for c, btn in self.category_buttons.items():
            btn.configure(
                fg_color=(
                    COLORS["accent"] if c == self.current_category else "transparent"
                )
            )

        self.app.update_idletasks()
        self.display_category()

    def display_category(self):
        """Display content for current category"""
        # Disable visual updates during rebuild
        self.content_area.update_idletasks()

        # Quick destroy
        for widget in self.content_area.winfo_children():
            widget.destroy()

        # Header
        header = ctk.CTkFrame(self.content_area, fg_color="transparent", height=80)
        header.pack(fill="x", padx=20, pady=(20, 10))

        category_names = {
            "passwords": "🔒 Passwords",
            "api_keys": "🔑 API Keys",
            "notes": "📝 Secure Notes",
            "ssh_keys": "🗝️ SSH Keys",
            "totp_codes": "📱 2FA/TOTP Codes",
            "files": "📄 Files",
            "encrypted_folders": "📁 Folders",
            "security": "📊 Security Dashboard",
            "bulk_delete": "🗑️ Bulk Delete Manager",
        }

        ctk.CTkLabel(
            header,
            text=category_names.get(self.current_category, "Vault"),
            font=("Segoe UI", 28, "bold"),
        ).pack(side="left")

        # Search toggle button (not for security or bulk_delete)
        if self.current_category not in ["security", "bulk_delete"]:
            self.search_btn = ctk.CTkButton(
                header,
                text="🔍",
                width=50,
                height=40,
                font=("Segoe UI", 18),
                fg_color="transparent",
                hover_color=COLORS["bg_secondary"],
                corner_radius=8,
                command=self.toggle_search,
            )
            self.search_btn.pack(side="right", padx=(10, 0))

        # Sort dropdown
        if self.current_category not in ["security", "bulk_delete"]:
            sort_options = [
                "⬇️ Newest First",
                "⬆️ Oldest First",
                "🔤 A-Z",
                "🔤 Z-A",
                "✏️ Recently Modified",
            ]

            self.sort_dropdown = ctk.CTkOptionMenu(
                header,
                values=sort_options,
                width=160,
                height=40,
                font=("Segoe UI", 12),
                dropdown_font=("Segoe UI", 11),
                fg_color=COLORS["bg_secondary"],
                button_color=COLORS["accent"],
                button_hover_color=COLORS["accent_hover"],
                command=self.change_sort,
            )
            self.sort_dropdown.set("⬇️ Newest First")
            self.sort_dropdown.pack(side="right", padx=(10, 0))

        # Add button (not for security)
        if self.current_category not in ["security", "bulk_delete"]:
            ctk.CTkButton(
                header,
                text="+ Add New",
                width=140,
                height=40,
                font=("Segoe UI", 13, "bold"),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=8,
                command=self.show_add_dialog,
            ).pack(side="right")

        # Search bar container (hidden by default)
        if self.current_category not in ["security", "bulk_delete"]:
            # Search bar container (hidden by default)
            if self.current_category not in ["security", "bulk_delete"]:
                # CRITICAL FIX: Properly cleanup old StringVar
                if hasattr(self, "search_var") and self.search_var is not None:
                    try:
                        traces = self.search_var.trace_info()
                        for trace in traces:
                            self.search_var.trace_remove(trace[0], trace[1])
                    except:
                        pass
                    self.search_var = None

                # Create fresh StringVar AFTER cleanup
                self.search_var = tk.StringVar()

                self.search_container = ctk.CTkFrame(
                    self.content_area,
                    fg_color=COLORS["bg_card"],
                    corner_radius=10,
                    height=50,
                    border_width=1,
                    border_color=COLORS["bg_secondary"],
                )

                ctk.CTkLabel(
                    self.search_container, text="🔍", font=("Segoe UI", 16)
                ).pack(side="left", padx=(15, 5))

                self.search_entry = ctk.CTkEntry(
                    self.search_container,
                    textvariable=self.search_var,
                    height=40,
                    placeholder_text=f"Search {self.current_category.replace('_', ' ')}...",
                    font=("Segoe UI", 13),
                    border_width=0,
                    fg_color="transparent",
                )
                self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
                self.search_entry.bind(
                    "<KeyRelease>", lambda e: self.on_search_change()
                )

                self.search_close_btn = ctk.CTkButton(
                    self.search_container,
                    text="✕",
                    width=35,
                    height=35,
                    font=("Segoe UI", 16, "bold"),
                    fg_color="transparent",
                    hover_color=COLORS["danger"],
                    corner_radius=6,
                    command=self.close_search,
                )
                self.search_close_btn.pack(side="right", padx=(5, 10))

                self.search_visible = False
        # Items container (NON-SCROLLABLE - only bulk delete scrolls internally)
        self.items_container = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.items_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.display_items()

    def toggle_search(self):
        """Toggle search bar visibility"""
        if not hasattr(self, "search_visible"):
            return

        if self.search_visible:
            self.close_search()
        else:
            # Show search bar - insert after header, don't use 'before'
            self.search_container.pack(fill="x", padx=30, pady=(0, 20))
            self.search_visible = True
            self.search_entry.focus()
            # Change icon to indicate it's open
            self.search_btn.configure(text="🔍", fg_color=COLORS["accent"])

    def change_sort(self, choice):
        """Handle sort option change"""
        self.reset_activity()

        # Map display text to internal sort key
        sort_map = {
            "⬇️ Newest First": "created_desc",
            "⬆️ Oldest First": "created_asc",
            "🔤 A-Z": "name_asc",
            "🔤 Z-A": "name_desc",
            "✏️ Recently Modified": "modified_desc",
        }

        self.sort_by = sort_map.get(choice, "created_desc")
        self.display_items()

    def sort_items(self, items):
        """Sort items based on current sort setting"""
        if not items:
            return items

        # Determine the name field based on item type
        def get_name(item):
            for key in ["title", "service", "name", "filename", "folder_name"]:
                if key in item:
                    return item.get(key, "").lower()
            return ""

        # Sort based on selection
        if self.sort_by == "created_desc":
            # Newest first (default)
            return sorted(items, key=lambda x: x.get("created", ""), reverse=True)

        elif self.sort_by == "created_asc":
            # Oldest first
            return sorted(items, key=lambda x: x.get("created", ""))

        elif self.sort_by == "name_asc":
            # A-Z
            return sorted(items, key=get_name)

        elif self.sort_by == "name_desc":
            # Z-A
            return sorted(items, key=get_name, reverse=True)

        elif self.sort_by == "modified_desc":
            # Recently modified
            return sorted(
                items,
                key=lambda x: x.get("modified", x.get("created", "")),
                reverse=True,
            )

        return items

    def close_search(self):
        """Close and clear search bar"""
        if not hasattr(self, "search_visible"):
            return

        # Hide search bar
        self.search_container.pack_forget()
        self.search_visible = False
        # Clear search
        self.search_var.set("")
        # Reset button appearance
        self.search_btn.configure(text="🔍", fg_color="transparent")
        # Refresh items
        self.display_items()

    def display_items(self):
        """Display items for current category"""
        for widget in self.items_container.winfo_children():
            widget.destroy()

        if self.current_category == "passwords":
            items = self.vault.list_passwords()
            display_fn = self.display_password_items
        elif self.current_category == "api_keys":
            items = self.vault.list_api_keys()
            display_fn = self.display_api_key_items
        elif self.current_category == "notes":
            items = self.vault.list_notes()
            display_fn = self.display_note_items
        elif self.current_category == "ssh_keys":
            items = self.vault.list_ssh_keys()
            display_fn = self.display_ssh_key_items
        elif self.current_category == "totp_codes":  # ← ADD THIS
            items = self.vault.list_totp()
            display_fn = self.display_totp_items
        elif self.current_category == "files":
            items = self.vault.list_files()
            display_fn = self.display_file_items
        elif self.current_category == "encrypted_folders":
            items = self.vault.list_encrypted_folders()
            display_fn = self.display_encrypted_folder_items
        elif self.current_category == "security":
            self.display_security_dashboard()
            return
        elif self.current_category == "bulk_delete":  # NEW
            self.display_bulk_delete()
            return

        # Search filter
        search_q = self.search_var.get().strip().lower()
        if search_q:

            def item_matches(it):
                text_parts = []
                for k in (
                    "title",
                    "service",
                    "name",
                    "filename",
                    "folder_name",
                    "username",
                    "url",
                    "description",
                    "content",
                ):
                    v = it.get(k, "")
                    if v:
                        text_parts.append(str(v).lower())
                return search_q in " ".join(text_parts)

            items = [it for it in items if item_matches(it)]

        # APPLY SORTING (NEW)
        items = self.sort_items(items)

        display_fn(items)

        if not items and self.current_category != "security":
            message = (
                "No results found"
                if search_q
                else f"No {self.current_category.replace('_', ' ')} yet\nClick '+ Add New' to create one"
            )
            ctk.CTkLabel(
                self.items_container,
                text=message,
                font=("Segoe UI", 16),
                text_color=COLORS["text_secondary"],
            ).pack(pady=100)

    def on_search_change(self):
        """Handle search input changes"""
        self.reset_activity()
        if hasattr(self, "_search_timer"):
            self.app.after_cancel(self._search_timer)
        self._search_timer = self.app.after(300, self.display_items)

    def display_password_items(self, items):
        """Display password entries"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", pady=(0, 8), padx=5)

            ctk.CTkLabel(
                title_row,
                text=item.get("title", "Untitled"),
                font=("Segoe UI", 16, "bold"),
            ).pack(side="left", anchor="w", padx=5)

            if item.get("favorite"):
                ctk.CTkLabel(title_row, text="⭐", font=("Segoe UI", 14)).pack(
                    side="left", padx=10
                )

            info_row = ctk.CTkFrame(card, fg_color="transparent")
            info_row.pack(fill="x", pady=(0, 5), padx=5)

            ctk.CTkLabel(
                info_row,
                text=f"👤 {item.get('username', 'N/A')}",
                font=("Segoe UI", 12),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 20))

            # CLICKABLE URL BUTTON
            if item.get("url"):
                url_text = (
                    item["url"][:35] + "..." if len(item["url"]) > 35 else item["url"]
                )
                ctk.CTkButton(
                    info_row,
                    text=f"🌐 {url_text}",
                    width=len(url_text) * 8 + 40,
                    height=28,
                    font=("Segoe UI", 11),
                    fg_color="transparent",
                    hover_color=COLORS["accent"],
                    text_color=COLORS["accent"],
                    corner_radius=6,
                    command=lambda u=item["url"]: self.open_url(u),
                ).pack(side="left")

            # DATE INFO ROW (NEW)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]  # Show only date, not time

            ctk.CTkLabel(
                date_row,
                text=f"📅 Created: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 15))

            modified = item.get("modified", created)
            if modified != "Unknown" and len(modified) > 10:
                modified = modified[:10]

            ctk.CTkLabel(
                date_row,
                text=f"✏️ Modified: {modified}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)  # Added padx

            ctk.CTkButton(
                actions,
                text="📋 Copy Password",
                width=130,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda p=item["password"]: self.copy_to_clipboard(
                    p, "Password"
                ),
            ).pack(side="left", padx=(5, 8))
            # QR CODE BUTTON (ADD THIS)
            ctk.CTkButton(
                actions,
                text="📱 QR",
                width=70,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_password_qr(i),
            ).pack(side="left", padx=(0, 8))
            # ADD THIS NEW BUTTON - Breach Check
            ctk.CTkButton(
                actions,
                text="🔍 Check",
                width=90,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.check_password_breach(i),
            ).pack(side="left", padx=(0, 8))
            # Increased left padding

            ctk.CTkButton(
                actions,
                text="👤 Copy User",
                width=110,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda u=item.get("username", ""): self.copy_to_clipboard(
                    u, "Username"
                ),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="✏️ Edit",
                width=80,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_edit_password(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="📜 History",
                width=90,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_password_history(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "password"),
            ).pack(
                side="right", padx=(0, 5)
            )  # Added right padding

    def open_url(self, url):
        """Open URL in default browser"""
        import webbrowser

        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open URL: {str(e)}")

    def display_api_key_items(self, items):
        """Display API key entries"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            ctk.CTkLabel(
                card,
                text=item.get("service", "Untitled"),
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", padx=5, pady=(0, 5))

            if item.get("description"):
                ctk.CTkLabel(
                    card,
                    text=item["description"],
                    font=("Segoe UI", 12),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", pady=(5, 5), padx=5)

            # DATE INFO ROW (NEW)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Created: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 15))

            modified = item.get("modified", created)
            if modified != "Unknown" and len(modified) > 10:
                modified = modified[:10]

            ctk.CTkLabel(
                date_row,
                text=f"✏️ Modified: {modified}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            ctk.CTkButton(
                actions,
                text="📋 Copy Key",
                width=120,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda k=item["key"]: self.copy_to_clipboard(k, "API Key"),
            ).pack(side="left", padx=(5, 8))
            ctk.CTkButton(
                actions,
                text="📱 QR",
                width=70,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_api_key_qr(i),
            ).pack(side="left", padx=(0, 8))
            # EDIT BUTTON (NEW)
            ctk.CTkButton(
                actions,
                text="✏️ Edit",
                width=80,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_edit_api_key(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "api_key"),
            ).pack(side="right", padx=(0, 5))
        # Auto-refresh every 1 second if there are TOTP items
        if items and self.current_category == "totp_codes":
            # Cancel previous timer if exists
            if hasattr(self, "_totp_timer"):
                self.app.after_cancel(self._totp_timer)

            # Schedule next refresh in 1 second
            self._totp_timer = self.app.after(1000, self._refresh_totp)

    def _refresh_totp(self):
        """Auto-refresh TOTP display every second"""
        # Only refresh if still on TOTP page and unlocked
        if (
            hasattr(self, "current_category")
            and self.current_category == "totp_codes"
            and not self.vault.is_locked
            and hasattr(self, "_totp_cards")
        ):
            # DON'T rebuild everything - just update the codes!
            self._update_totp_codes_only()

    def _update_totp_codes_only(self):
        """Update TOTP codes without rebuilding widgets"""
        import pyotp

        items = self.vault.list_totp()

        for item in items:
            item_id = item["id"]
            if item_id not in self._totp_cards:
                continue

            card_data = self._totp_cards[item_id]

            try:
                # Check if widget still exists
                if not card_data["code_label"].winfo_exists():
                    continue

                totp = pyotp.TOTP(item["secret"])
                code = totp.now()
                remaining = 30 - (int(datetime.now().timestamp()) % 30)

                # Format and update
                formatted_code = f"{code[:3]} {code[3:]}"
                card_data["code_label"].configure(text=formatted_code)

                timer_color = COLORS["danger"] if remaining <= 5 else COLORS["success"]
                card_data["timer_label"].configure(
                    text=f"⏱️ {remaining}s", text_color=timer_color
                )

                card_data["copy_btn"].configure(
                    command=lambda c=code: self.copy_to_clipboard(c, "TOTP Code")
                )
            except Exception as e:
                continue

        # Schedule next update
        if self.current_category == "totp_codes" and not self.vault.is_locked:
            if hasattr(self, "_totp_timer"):
                self.app.after_cancel(self._totp_timer)
            self._totp_timer = self.app.after(1000, self._refresh_totp)

    def display_note_items(self, items):
        """Display secure notes"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            ctk.CTkLabel(
                card, text=item.get("title", "Untitled"), font=("Segoe UI", 16, "bold")
            ).pack(anchor="w", padx=5, pady=(0, 5))

            preview = (
                item.get("content", "")[:100] + "..."
                if len(item.get("content", "")) > 100
                else item.get("content", "")
            )
            ctk.CTkLabel(
                card,
                text=preview,
                font=("Segoe UI", 12),
                text_color=COLORS["text_secondary"],
                wraplength=700,
            ).pack(anchor="w", pady=(5, 5), padx=5)

            # DATE INFO ROW (NEW)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Created: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 15))

            modified = item.get("modified", created)
            if modified != "Unknown" and len(modified) > 10:
                modified = modified[:10]

            ctk.CTkLabel(
                date_row,
                text=f"✏️ Modified: {modified}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            ctk.CTkButton(
                actions,
                text="👁️ View",
                width=100,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda n=item: self.view_note(n),
            ).pack(side="left", padx=(5, 8))
            ctk.CTkButton(
                actions,
                text="📱 QR",
                width=70,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_note_qr(i),
            ).pack(side="left", padx=(0, 8))
            # EDIT BUTTON (NEW)
            ctk.CTkButton(
                actions,
                text="✏️ Edit",
                width=80,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_edit_note(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "note"),
            ).pack(side="right", padx=(0, 5))

    def display_ssh_key_items(self, items):
        """Display SSH keys"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            ctk.CTkLabel(
                card, text=item.get("name", "Untitled"), font=("Segoe UI", 16, "bold")
            ).pack(anchor="w", padx=5, pady=(0, 5))

            # DATE INFO ROW (UPDATED)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Created: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 15))

            modified = item.get("modified", created)
            if modified != "Unknown" and len(modified) > 10:
                modified = modified[:10]

            ctk.CTkLabel(
                date_row,
                text=f"✏️ Modified: {modified}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            ctk.CTkButton(
                actions,
                text="📋 Copy Private",
                width=130,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda k=item["private_key"]: self.copy_to_clipboard(
                    k, "SSH Key"
                ),
            ).pack(side="left", padx=(5, 8))

            # COPY PUBLIC KEY BUTTON (NEW)
            if item.get("public_key"):
                ctk.CTkButton(
                    actions,
                    text="📋 Copy Public",
                    width=120,
                    height=32,
                    fg_color="gray30",
                    hover_color="gray40",
                    corner_radius=6,
                    command=lambda k=item["public_key"]: self.copy_to_clipboard(
                        k, "Public SSH Key"
                    ),
                ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                actions,
                text="📱 QR",
                width=70,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_ssh_key_qr(i),
            ).pack(side="left", padx=(0, 8))
            # EDIT BUTTON (NEW)
            ctk.CTkButton(
                actions,
                text="✏️ Edit",
                width=80,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item: self.show_edit_ssh_key(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "ssh_key"),
            ).pack(side="right", padx=(0, 5))

    def display_file_items(self, items):
        """Display encrypted files"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            ctk.CTkLabel(
                card,
                text=item.get("filename", "Untitled"),
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", padx=5, pady=(0, 5))

            # FILE INFO ROW
            info_row = ctk.CTkFrame(card, fg_color="transparent")
            info_row.pack(fill="x", pady=(5, 5), padx=5)

            size_kb = item.get("size", 0) / 1024
            ctk.CTkLabel(
                info_row,
                text=f"💾 Size: {size_kb:.2f} KB",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 0))

            # DATE INFO ROW (NEW)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Added: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 0))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            ctk.CTkButton(
                actions,
                text="💾 Export",
                width=100,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda i=item["id"], n=item["filename"]: self.export_file(i, n),
            ).pack(side="left", padx=(5, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "file"),
            ).pack(side="right", padx=(0, 5))

    def display_encrypted_folder_items(self, items):
        """Display folder metadata"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=5)

            folder_title = f"📁 {item.get('folder_name', 'Untitled')}"
            if item.get("zip_password"):
                folder_title += " 🔒"

            ctk.CTkLabel(
                title_row,
                text=folder_title,
                font=("Segoe UI", 16, "bold"),
            ).pack(side="left", padx=5)

            info_row = ctk.CTkFrame(card, fg_color="transparent")
            info_row.pack(fill="x", pady=(8, 0), padx=5)

            size_mb = item.get("size", 0) / (1024 * 1024)
            ctk.CTkLabel(
                info_row,
                text=f"💾 Size: {size_mb:.2f} MB",
                font=("Segoe UI", 12),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(0, 20))

            ctk.CTkLabel(
                info_row,
                text=f"📊 Files: {item.get('file_count', 0)}",
                font=("Segoe UI", 12),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

            if item.get("description"):
                ctk.CTkLabel(
                    card,
                    text=item["description"],
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", pady=(5, 5), padx=5)

            # DATE INFO ROW (NEW)
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Added: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 0))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            ctk.CTkButton(
                actions,
                text="📦 Download ZIP",
                width=140,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda i=item["id"], n=item[
                    "folder_name"
                ]: self.download_folder_zip(i, n),
            ).pack(side="left", padx=(5, 8))

            ctk.CTkButton(
                actions,
                text="🔒 Set Password",
                width=130,
                height=32,
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=6,
                command=lambda i=item["id"]: self.set_folder_password(i),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_item(i, "encrypted_folder"),
            ).pack(side="right", padx=(0, 5))

    def display_security_dashboard(self):
        """Display comprehensive security dashboard"""
        report = self.vault.get_security_report()

        # Stats cards
        stats_row = ctk.CTkFrame(
            self.items_container, fg_color="transparent", height=120
        )
        stats_row.pack(fill="x", padx=20, pady=(0, 20))
        stats_row.pack_propagate(False)

        # Card 1: Total
        card1 = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_card"], corner_radius=10)
        card1.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(
            card1,
            text=str(report["total_passwords"]),
            font=("Segoe UI", 36, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(20, 2))
        ctk.CTkLabel(
            card1,
            text="📊 Total",
            font=("Segoe UI", 12),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 20))

        # Card 2: Weak
        card2 = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_card"], corner_radius=10)
        card2.pack(side="left", fill="both", expand=True, padx=5)
        weak_count = len(report["weak_passwords"])
        color = COLORS["danger"] if weak_count > 0 else COLORS["success"]
        ctk.CTkLabel(
            card2, text=str(weak_count), font=("Segoe UI", 36, "bold"), text_color=color
        ).pack(pady=(20, 2))
        ctk.CTkLabel(
            card2,
            text="⚠️ Weak",
            font=("Segoe UI", 12),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 20))

        # Card 3: Reused
        card3 = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_card"], corner_radius=10)
        card3.pack(side="left", fill="both", expand=True, padx=5)
        reused_count = len(report["reused_passwords"])
        color = COLORS["danger"] if reused_count > 0 else COLORS["success"]
        ctk.CTkLabel(
            card3,
            text=str(reused_count),
            font=("Segoe UI", 36, "bold"),
            text_color=color,
        ).pack(pady=(20, 2))
        ctk.CTkLabel(
            card3,
            text="🔄 Reused",
            font=("Segoe UI", 12),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 20))

        # Card 4: Old
        card4 = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_card"], corner_radius=10)
        card4.pack(side="left", fill="both", expand=True, padx=5)
        old_count = len(report["old_passwords"])
        color = COLORS["warning"] if old_count > 0 else COLORS["success"]
        ctk.CTkLabel(
            card4, text=str(old_count), font=("Segoe UI", 36, "bold"), text_color=color
        ).pack(pady=(20, 2))
        ctk.CTkLabel(
            card4,
            text="📅 Old (1yr+)",
            font=("Segoe UI", 12),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 20))

        # Strength gauge
        strength_frame = ctk.CTkFrame(
            self.items_container,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            height=100,
        )
        strength_frame.pack(fill="x", padx=20, pady=(0, 20))
        strength_frame.pack_propagate(False)

        ctk.CTkLabel(
            strength_frame,
            text="💪 Average Strength",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(15, 5))

        avg_strength = int(report["average_strength"])
        if avg_strength >= 80:
            strength_text = "Excellent"
            strength_color = COLORS["success"]
        elif avg_strength >= 60:
            strength_text = "Good"
            strength_color = COLORS["accent"]
        elif avg_strength >= 40:
            strength_text = "Fair"
            strength_color = COLORS["warning"]
        else:
            strength_text = "Weak"
            strength_color = COLORS["danger"]

        ctk.CTkLabel(
            strength_frame,
            text=f"{avg_strength}% - {strength_text}",
            font=("Segoe UI", 22, "bold"),
            text_color=strength_color,
        ).pack(pady=(0, 15))

        # NON-SCROLLABLE CONTAINER FOR SECTIONS
        content_container = ctk.CTkFrame(self.items_container, fg_color="transparent")
        content_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Weak passwords
        if report["weak_passwords"]:
            weak_section = ctk.CTkFrame(
                content_container, fg_color=COLORS["bg_card"], corner_radius=10
            )
            weak_section.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(
                weak_section,
                text=f"⚠️ Weak Passwords ({len(report['weak_passwords'])})",
                font=("Segoe UI", 15, "bold"),
                text_color=COLORS["danger"],
            ).pack(anchor="w", padx=15, pady=(12, 8))

            for pwd in report["weak_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    weak_section, fg_color=COLORS["bg_secondary"], corner_radius=8
                )
                item_row.pack(fill="x", padx=15, pady=5, ipady=10, ipadx=12)

                ctk.CTkLabel(
                    item_row,
                    text=pwd["title"],
                    font=("Segoe UI", 12, "bold"),
                    text_color=COLORS["text_primary"],
                ).pack(side="left", padx=8)

                ctk.CTkLabel(
                    item_row,
                    text=f"Strength: {pwd['score']}%",
                    font=("Segoe UI", 11),
                    text_color=COLORS["danger"],
                ).pack(side="right", padx=8)

            if len(report["weak_passwords"]) > 5:
                ctk.CTkLabel(
                    weak_section,
                    text=f"+ {len(report['weak_passwords']) - 5} more",
                    font=("Segoe UI", 10),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", padx=15, pady=(5, 12))
            else:
                ctk.CTkFrame(weak_section, height=8, fg_color="transparent").pack()

        # Reused passwords
        if report["reused_passwords"]:
            reused_section = ctk.CTkFrame(
                content_container, fg_color=COLORS["bg_card"], corner_radius=10
            )
            reused_section.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(
                reused_section,
                text=f"🔄 Reused Passwords ({len(report['reused_passwords'])})",
                font=("Segoe UI", 15, "bold"),
                text_color=COLORS["warning"],
            ).pack(anchor="w", padx=15, pady=(12, 8))

            for reused in report["reused_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    reused_section, fg_color=COLORS["bg_secondary"], corner_radius=8
                )
                item_row.pack(fill="x", padx=15, pady=5, ipady=10, ipadx=12)

                used_in_text = ", ".join(reused["used_in"][:3])
                if len(reused["used_in"]) > 3:
                    used_in_text += f" +{len(reused['used_in']) - 3} more"

                ctk.CTkLabel(
                    item_row,
                    text=f"Used in: {used_in_text}",
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_primary"],
                ).pack(side="left", padx=8)

            if len(report["reused_passwords"]) > 5:
                ctk.CTkLabel(
                    reused_section,
                    text=f"+ {len(report['reused_passwords']) - 5} more",
                    font=("Segoe UI", 10),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", padx=15, pady=(5, 12))
            else:
                ctk.CTkFrame(reused_section, height=8, fg_color="transparent").pack()

        # Old passwords
        if report["old_passwords"]:
            old_section = ctk.CTkFrame(
                content_container, fg_color=COLORS["bg_card"], corner_radius=10
            )
            old_section.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(
                old_section,
                text=f"📅 Old Passwords ({len(report['old_passwords'])})",
                font=("Segoe UI", 15, "bold"),
                text_color=COLORS["warning"],
            ).pack(anchor="w", padx=15, pady=(12, 8))

            for old in report["old_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    old_section, fg_color=COLORS["bg_secondary"], corner_radius=8
                )
                item_row.pack(fill="x", padx=15, pady=5, ipady=10, ipadx=12)

                ctk.CTkLabel(
                    item_row,
                    text=old["title"],
                    font=("Segoe UI", 12, "bold"),
                    text_color=COLORS["text_primary"],
                ).pack(side="left", padx=8)

                ctk.CTkLabel(
                    item_row,
                    text=f"{old['age_days']} days old",
                    font=("Segoe UI", 11),
                    text_color=COLORS["warning"],
                ).pack(side="right", padx=8)

            if len(report["old_passwords"]) > 5:
                ctk.CTkLabel(
                    old_section,
                    text=f"+ {len(report['old_passwords']) - 5} more",
                    font=("Segoe UI", 10),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", padx=15, pady=(5, 12))
            else:
                ctk.CTkFrame(old_section, height=8, fg_color="transparent").pack()

        # RECOMMENDATIONS - NOW FULLY VISIBLE
        rec_section = ctk.CTkFrame(
            content_container, fg_color=COLORS["bg_card"], corner_radius=10
        )
        rec_section.pack(fill="x", pady=(0, 30))

        ctk.CTkLabel(
            rec_section,
            text="💡 Security Recommendations",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=20, pady=(20, 15))

        tips = []
        if weak_count > 0:
            tips.append(
                f"• Update {weak_count} weak password(s) with stronger alternatives"
            )
        if reused_count > 0:
            tips.append(f"• Change {reused_count} reused password(s) to unique ones")
        if old_count > 0:
            tips.append(f"• Refresh {old_count} password(s) older than 1 year")
        if not tips:
            tips.append("✅ Your password security is excellent! Keep it up.")

        for tip in tips:
            ctk.CTkLabel(
                rec_section,
                text=tip,
                font=("Segoe UI", 13),
                text_color=COLORS["text_primary"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", fill="x", padx=20, pady=(0, 12))

        ctk.CTkFrame(rec_section, height=10, fg_color="transparent").pack()

    def scan_all_passwords_for_breaches(self):
        """Scan all passwords for breaches"""
        from .breach_checker import scan_all_passwords

        progress = self.create_dialog("Scanning...", 500, 300)
        ctk.CTkLabel(
            progress, text="🔍 Scanning passwords...", font=("Segoe UI", 16, "bold")
        ).pack(pady=40)
        status = ctk.CTkLabel(progress, text="Please wait...", font=("Segoe UI", 12))
        status.pack(pady=20)
        progress.update()

        results = scan_all_passwords(self.vault)
        progress.destroy()

        # Show results
        dlg = self.create_dialog("Scan Results", 700, 600)
        ctk.CTkLabel(
            dlg,
            text=f"✅ Scanned {results['total_checked']} passwords",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=20)

        if results["breached"]:
            ctk.CTkLabel(
                dlg,
                text=f"⚠️ {len(results['breached'])} BREACHED!",
                font=("Segoe UI", 14, "bold"),
                text_color=COLORS["danger"],
            ).pack()
            scroll = ctk.CTkScrollableFrame(dlg, width=650, height=350)
            scroll.pack(pady=10)
            for item in results["breached"]:
                card = ctk.CTkFrame(scroll, fg_color=COLORS["danger"], corner_radius=8)
                card.pack(fill="x", pady=5, ipady=8, ipadx=10)
                ctk.CTkLabel(
                    card, text=f"🚨 {item['title']}", font=("Segoe UI", 12, "bold")
                ).pack(anchor="w", padx=10)
                ctk.CTkLabel(
                    card, text=item["breach_info"]["message"], font=("Segoe UI", 10)
                ).pack(anchor="w", padx=10)
        else:
            ctk.CTkLabel(
                dlg,
                text="✅ All passwords safe!",
                font=("Segoe UI", 16),
                text_color=COLORS["success"],
            ).pack(pady=50)

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy).pack(pady=20)

    def display_bulk_delete(self):
        """Display bulk delete manager"""

        # Selection tracking
        self.bulk_selected = []
        self.bulk_category_filter = "All Items"

        # Create FIXED top controls container (doesn't scroll)
        top_controls = ctk.CTkFrame(self.items_container, fg_color="transparent")
        top_controls.pack(fill="x", padx=20, pady=(0, 10))

        # Top control bar - SINGLE clean header
        control_bar = ctk.CTkFrame(
            top_controls,  # ← CHANGED from self.items_container
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            height=75,
        )
        control_bar.pack(fill="x", pady=(0, 15), ipady=12, ipadx=25)
        control_bar.pack_propagate(False)

        # Left side - Title and count
        left_side = ctk.CTkFrame(control_bar, fg_color="transparent")
        left_side.pack(side="left", fill="y", pady=8)

        self.selection_label = ctk.CTkLabel(
            left_side,
            text="0 items selected",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
        )
        self.selection_label.pack(anchor="w", pady=(4, 0))

        # Right side - Delete button
        def update_selection_label():
            count = len(self.bulk_selected)
            self.selection_label.configure(
                text=f"{count} item{'s' if count != 1 else ''} selected",
                text_color=COLORS["accent"] if count > 0 else COLORS["text_secondary"],
            )

        def delete_selected():
            if not self.bulk_selected:
                messagebox.showinfo("No Selection", "Please select items to delete")
                return

            count = len(self.bulk_selected)
            if not messagebox.askyesno(
                "Confirm Bulk Delete",
                f"Are you sure you want to permanently delete {count} item{'s' if count != 1 else ''}?\n\n⚠️ This action cannot be undone!",
            ):
                return

            deleted = 0
            for checkbox_id in self.bulk_selected:
                category, item_id = checkbox_id.split(":", 1)

                try:
                    if category == "passwords":
                        self.vault.delete_password(item_id)
                    elif category == "api_keys":
                        self.vault.delete_api_key(item_id)
                    elif category == "notes":
                        self.vault.delete_note(item_id)
                    elif category == "ssh_keys":
                        self.vault.delete_ssh_key(item_id)
                    elif category == "files":
                        self.vault.delete_file(item_id)
                    elif category == "encrypted_folders":
                        self.vault.delete_encrypted_folder(item_id)
                    deleted += 1
                except Exception as e:
                    print(f"Failed to delete {checkbox_id}: {e}")

            messagebox.showinfo(
                "Success",
                f"✅ Deleted {deleted} item{'s' if deleted != 1 else ''} successfully!",
            )
            self.display_items()

        ctk.CTkButton(
            control_bar,
            text="🗑️ Delete Selected",
            width=160,
            height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["danger"],
            hover_color="#c0392b",
            corner_radius=8,
            command=delete_selected,
        ).pack(side="right", pady=8, padx=10)

        # Category filter pills (IN THE CONTROL BAR)
        ctk.CTkLabel(
            control_bar,
            text="Filter:",
            font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(20, 8))

        # Category pill buttons
        self.filter_options = [
            "All Items",
            "Passwords",
            "API Keys",
            "Notes",
            "SSH Keys",
            "2FA/TOTP",
            "Files",
            "Folders",
        ]
        self.category_pill_buttons = {}

        def switch_filter(category):
            self.bulk_category_filter = category
            for cat, btn in self.category_pill_buttons.items():
                if cat == category:
                    btn.configure(
                        fg_color=COLORS["accent"],
                        text_color=COLORS["text_primary"],
                        border_color=COLORS["accent"],
                    )
                else:
                    btn.configure(
                        fg_color="transparent",
                        text_color=COLORS["text_secondary"],
                        border_color=COLORS["bg_secondary"],
                    )
            self.display_bulk_delete_items()

        for label in self.filter_options:
            btn = ctk.CTkButton(
                control_bar,  # ← DIRECT TO CONTROL BAR
                text=label,
                width=90,
                height=30,
                font=("Segoe UI", 10),
                fg_color=COLORS["accent"] if label == "All Items" else "transparent",
                hover_color=COLORS["accent_hover"],
                text_color=(
                    COLORS["text_primary"]
                    if label == "All Items"
                    else COLORS["text_secondary"]
                ),
                corner_radius=15,
                border_width=1,
                border_color=(
                    COLORS["accent"] if label == "All Items" else COLORS["bg_secondary"]
                ),
                command=lambda c=label: switch_filter(c),
            )
            btn.pack(side="left", padx=2)
            self.category_pill_buttons[label] = btn

        # Items container - SCROLLABLE ONLY
        self.bulk_items_scroll = ctk.CTkScrollableFrame(
            self.items_container, fg_color="transparent"
        )
        self.bulk_items_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # Display items
        self.display_bulk_delete_items()

    def display_bulk_delete_items(self):
        """Display items in bulk delete view"""
        # Clear existing
        for widget in self.bulk_items_scroll.winfo_children():
            widget.destroy()

        # Get all items based on filter
        all_items_with_meta = []
        filter_choice = self.bulk_category_filter

        if filter_choice in ["All Items", "Passwords"]:
            for item in self.vault.list_passwords():
                all_items_with_meta.append(
                    {
                        "category": "passwords",
                        "category_label": "🔒 Password",
                        "item": item,
                        "checkbox_id": f"passwords:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        if filter_choice in ["All Items", "API Keys"]:
            for item in self.vault.list_api_keys():
                all_items_with_meta.append(
                    {
                        "category": "api_keys",
                        "category_label": "🔐 API Key",
                        "item": item,
                        "checkbox_id": f"api_keys:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        if filter_choice in ["All Items", "Notes"]:
            for item in self.vault.list_notes():
                all_items_with_meta.append(
                    {
                        "category": "notes",
                        "category_label": "📝 Note",
                        "item": item,
                        "checkbox_id": f"notes:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        if filter_choice in ["All Items", "SSH Keys"]:
            for item in self.vault.list_ssh_keys():
                all_items_with_meta.append(
                    {
                        "category": "ssh_keys",
                        "category_label": "🗝️ SSH Key",
                        "item": item,
                        "checkbox_id": f"ssh_keys:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        if filter_choice in ["All Items", "Files"]:
            for item in self.vault.list_files():
                all_items_with_meta.append(
                    {
                        "category": "files",
                        "category_label": "📄 File",
                        "item": item,
                        "checkbox_id": f"files:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        if filter_choice in ["All Items", "Folders"]:
            for item in self.vault.list_encrypted_folders():
                all_items_with_meta.append(
                    {
                        "category": "encrypted_folders",
                        "category_label": "📁 Folder",
                        "item": item,
                        "checkbox_id": f"encrypted_folders:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )

        # Sort by creation date (newest first)
        all_items_with_meta.sort(
            key=lambda x: x["item"].get("created", ""), reverse=True
        )

        # SIMPLE empty state - NO SCROLL, just centered text
        if not all_items_with_meta:
            ctk.CTkLabel(
                self.bulk_items_scroll,
                text=f"No {filter_choice.lower()} to display",
                font=("Segoe UI", 16),
                text_color=COLORS["text_secondary"],
            ).pack(
                expand=True
            )  # ← CHANGED: removed pady, added expand
            return

        # Select All checkbox at top
        select_all_frame = ctk.CTkFrame(
            self.bulk_items_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            height=52,
        )
        select_all_frame.pack(fill="x", pady=(0, 12), padx=5, ipady=10, ipadx=15)
        select_all_frame.pack_propagate(False)

        select_all_var = tk.BooleanVar(value=False)

        def update_selection_label():
            count = len(self.bulk_selected)
            self.selection_label.configure(
                text=f"{count} item{'s' if count != 1 else ''} selected",
                text_color=COLORS["accent"] if count > 0 else COLORS["text_secondary"],
            )

        def toggle_select_all():
            if select_all_var.get():
                self.bulk_selected = [
                    item["checkbox_id"] for item in all_items_with_meta
                ]
                for item in all_items_with_meta:
                    item["var"].set(True)
            else:
                self.bulk_selected = []
                for item in all_items_with_meta:
                    item["var"].set(False)
            update_selection_label()

        ctk.CTkCheckBox(
            select_all_frame,
            text=f"Select All ({len(all_items_with_meta)} items)",
            variable=select_all_var,
            font=("Segoe UI", 13, "bold"),
            command=toggle_select_all,
            checkbox_width=24,
            checkbox_height=24,
        ).pack(side="left", padx=15, pady=8)

        # Display each item - MATCHING YOUR PASSWORD DESIGN
        for meta in all_items_with_meta:
            item = meta["item"]
            category = meta["category"]

            card = ctk.CTkFrame(
                self.bulk_items_scroll,
                fg_color=COLORS["bg_card"],
                corner_radius=12,
                height=80,  # ← ADD THIS
            )
            card.pack(
                fill="x", pady=8, padx=10, ipady=15, ipadx=20
            )  # ← Increased padding
            card.pack_propagate(False)  # ← ADD THIS LINE

            # Top row - checkbox + badge + title
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", pady=(0, 5))

            def on_checkbox_change(checkbox_id=meta["checkbox_id"], var=meta["var"]):
                if var.get():
                    if checkbox_id not in self.bulk_selected:
                        self.bulk_selected.append(checkbox_id)
                else:
                    if checkbox_id in self.bulk_selected:
                        self.bulk_selected.remove(checkbox_id)
                update_selection_label()

            # Checkbox
            ctk.CTkCheckBox(
                top_row,
                text="",
                variable=meta["var"],
                command=on_checkbox_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(side="left", padx=(15, 12))

            # Category badge (small, subtle)
            ctk.CTkLabel(
                top_row,
                text=meta["category_label"],
                font=("Segoe UI", 9, "bold"),
                text_color=COLORS["bg_primary"],
                fg_color=COLORS["accent"],
                corner_radius=5,
                padx=8,
                pady=2,
            ).pack(side="left", padx=(0, 10))

            # Title/Name
            name = ""
            if category == "passwords":
                name = item.get("title", "Untitled")
            elif category == "api_keys":
                name = item.get("service", "Untitled")
            elif category == "notes":
                name = item.get("title", "Untitled")
            elif category == "ssh_keys":
                name = item.get("name", "Untitled")
            elif category == "files":
                name = item.get("filename", "Untitled")
            elif category == "encrypted_folders":
                name = item.get("folder_name", "Untitled")

            ctk.CTkLabel(
                top_row,
                text=name,
                font=("Segoe UI", 14, "bold"),
            ).pack(side="left")

            # Info row - exactly like your password section
            info_row = ctk.CTkFrame(card, fg_color="transparent")
            info_row.pack(fill="x", padx=5)

            if category == "passwords":
                username = item.get("username", "N/A")
                ctk.CTkLabel(
                    info_row,
                    text=f"👤 {username}",
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left", padx=(35, 15))
            elif category == "files":
                size_kb = item.get("size", 0) / 1024
                ctk.CTkLabel(
                    info_row,
                    text=f"💾 {size_kb:.1f} KB",
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left", padx=(35, 15))
            elif category == "encrypted_folders":
                ctk.CTkLabel(
                    info_row,
                    text=f"📊 {item.get('file_count', 0)} files",
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left", padx=(35, 15))
            else:
                # For other types, just add padding
                ctk.CTkLabel(info_row, text="", width=35).pack(side="left")

            # Date
            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                info_row,
                text=f"📅 {created}",
                font=("Segoe UI", 10),
                text_color=COLORS["text_secondary"],
            ).pack(side="left")

    def show_add_dialog(self):
        """Show add dialog based on category"""
        self.reset_activity()

        if self.current_category == "passwords":
            self.show_add_password_dialog()
        elif self.current_category == "api_keys":
            self.show_add_api_key_dialog()
        elif self.current_category == "notes":
            self.show_add_note_dialog()
        elif self.current_category == "ssh_keys":
            self.show_add_ssh_key_dialog()
        elif self.current_category == "totp_codes":  # ← ADD THIS
            self.show_add_totp_dialog()
        elif self.current_category == "files":
            self.show_add_file_dialog()
        elif self.current_category == "encrypted_folders":
            self.show_add_folder_dialog()

    def show_edit_ssh_key(self, item):
        """Dialog to edit SSH key"""
        dialog = self.create_dialog("Edit SSH Key", 600, 550)

        ctk.CTkLabel(dialog, text="Edit SSH Key", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        name_entry = ctk.CTkEntry(
            dialog, width=500, height=40, placeholder_text="Key Name (e.g., GitHub)"
        )
        name_entry.insert(0, item.get("name", ""))
        name_entry.pack(pady=10)

        private_entry = ctk.CTkTextbox(dialog, width=500, height=150)
        private_entry.insert("1.0", item.get("private_key", ""))
        private_entry.pack(pady=10)

        public_entry = ctk.CTkTextbox(dialog, width=500, height=80)
        public_entry.insert("1.0", item.get("public_key", ""))
        public_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            name = name_entry.get().strip()
            private = private_entry.get("1.0", "end").strip()
            public = public_entry.get("1.0", "end").strip()

            if not name or not private:
                status.configure(
                    text="❌ Name and private key required", text_color=COLORS["danger"]
                )
                return

            try:
                # You'll need to add this method to vault.py
                self.vault.update_ssh_key(item["id"], name, private, public)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "SSH key updated successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Changes",
            width=500,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_edit_ssh_key(self, item):
        """Dialog to edit SSH key"""
        dialog = self.create_dialog("Edit SSH Key", 600, 550)

        ctk.CTkLabel(dialog, text="Edit SSH Key", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        name_entry = ctk.CTkEntry(
            dialog, width=500, height=40, placeholder_text="Key Name (e.g., GitHub)"
        )
        name_entry.insert(0, item.get("name", ""))
        name_entry.pack(pady=10)

        private_entry = ctk.CTkTextbox(dialog, width=500, height=150)
        private_entry.insert("1.0", item.get("private_key", ""))
        private_entry.pack(pady=10)

        public_entry = ctk.CTkTextbox(dialog, width=500, height=80)
        public_entry.insert("1.0", item.get("public_key", ""))
        public_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            name = name_entry.get().strip()
            private = private_entry.get("1.0", "end").strip()
            public = public_entry.get("1.0", "end").strip()

            if not name or not private:
                status.configure(
                    text="❌ Name and private key required", text_color=COLORS["danger"]
                )
                return

            try:
                # You'll need to add this method to vault.py
                self.vault.update_ssh_key(item["id"], name, private, public)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "SSH key updated successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Changes",
            width=500,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_edit_note(self, item):
        """Dialog to edit secure note"""
        dialog = self.create_dialog("Edit Secure Note", 600, 600)

        ctk.CTkLabel(
            dialog, text="Edit Secure Note", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        title_entry = ctk.CTkEntry(
            dialog, width=500, height=40, placeholder_text="Note Title"
        )
        title_entry.insert(0, item.get("title", ""))
        title_entry.pack(pady=10)

        content_entry = ctk.CTkTextbox(dialog, width=500, height=300)
        content_entry.insert("1.0", item.get("content", ""))
        content_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            title = title_entry.get().strip()
            content = content_entry.get("1.0", "end").strip()

            if not title or not content:
                status.configure(
                    text="❌ Title and content required", text_color=COLORS["danger"]
                )
                return

            try:
                # You'll need to add this method to vault.py
                self.vault.update_note(item["id"], title, content)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Note updated successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Changes",
            width=500,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_edit_api_key(self, item):
        """Dialog to edit API key"""
        dialog = self.create_dialog("Edit API Key", 500, 450)

        ctk.CTkLabel(dialog, text="Edit API Key", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        service_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="Service Name"
        )
        service_entry.insert(0, item.get("service", ""))
        service_entry.pack(pady=10)

        key_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="API Key"
        )
        key_entry.insert(0, item.get("key", ""))
        key_entry.pack(pady=10)

        desc_entry = ctk.CTkTextbox(dialog, width=400, height=100)
        desc_entry.insert("1.0", item.get("description", ""))
        desc_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            service = service_entry.get().strip()
            key = key_entry.get().strip()
            desc = desc_entry.get("1.0", "end").strip()

            if not service or not key:
                status.configure(
                    text="❌ Service and key required", text_color=COLORS["danger"]
                )
                return

            try:
                # You'll need to add this method to vault.py
                self.vault.update_api_key(item["id"], service, key, desc)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "API key updated successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Changes",
            width=400,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_add_password_dialog(self):
        """Dialog to add new password"""
        dialog = self.create_dialog("Add Password", 500, 680)

        ctk.CTkLabel(
            dialog, text="Add New Password", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        title_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="Title (e.g., Gmail)"
        )
        title_entry.pack(pady=10)

        username_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="Username/Email"
        )
        username_entry.pack(pady=10)

        # Password frame with toggle visibility - FIXED WIDTH
        password_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        password_frame.pack(pady=10)
        password_frame.pack_propagate(False)  # Prevent resizing
        password_frame.configure(width=400, height=40)

        password_entry = ctk.CTkEntry(
            password_frame, width=240, height=40, placeholder_text="Password", show="●"
        )
        password_entry.place(x=0, y=0)  # Use place instead of pack

        # Toggle show/hide password
        show_password = [False]

        def toggle_password_visibility():
            if show_password[0]:
                password_entry.configure(show="●")
                toggle_btn.configure(text="🔒")  # Lock when hidden
                show_password[0] = False
            else:
                password_entry.configure(show="")
                toggle_btn.configure(text="🔓")  # Unlock when shown
                show_password[0] = True

        toggle_btn = ctk.CTkButton(
            password_frame,
            text="🔒",  # Start with lock (password hidden)
            width=40,
            height=40,
            font=("Segoe UI", 16),
            fg_color="gray30",  # FIXED: Now matches other buttons
            hover_color="gray40",
            corner_radius=6,
            command=toggle_password_visibility,
        )
        toggle_btn.place(x=245, y=0)

        def show_generator():
            gen_dialog = self.create_dialog("Password Generator", 500, 600)

            ctk.CTkLabel(
                gen_dialog, text="Generate Password", font=("Segoe UI", 18, "bold")
            ).pack(pady=20)

            # Generated password preview with proper container
            preview_container = ctk.CTkFrame(
                gen_dialog, fg_color=COLORS["bg_card"], corner_radius=10, height=90
            )
            preview_container.pack(pady=10, padx=20, fill="x")
            preview_container.pack_propagate(False)

            ctk.CTkLabel(
                preview_container,
                text="Generated Password:",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=15, pady=(12, 8))

            preview_row = ctk.CTkFrame(preview_container, fg_color="transparent")
            preview_row.pack(fill="x", padx=15, pady=(0, 12))

            preview_entry = ctk.CTkEntry(
                preview_row,
                width=380,
                height=40,
                font=("Consolas", 14),
                show="●",
                fg_color=COLORS["bg_secondary"],
                border_width=2,
                border_color=COLORS["accent"],
            )
            preview_entry.pack(side="left", padx=(0, 8))

            show_preview = [False]

            def toggle_preview():
                if show_preview[0]:
                    preview_entry.configure(show="●")
                    preview_toggle.configure(text="🔒")  # Lock when hidden
                    show_preview[0] = False
                else:
                    preview_entry.configure(show="")
                    preview_toggle.configure(text="🔓")  # Unlock when shown
                    show_preview[0] = True

            preview_toggle = ctk.CTkButton(
                preview_row,
                text="🔒",  # Start with lock (password hidden)
                width=40,
                height=40,
                font=("Segoe UI", 16),
                fg_color="gray30",  # FIXED: Now matches other buttons
                hover_color="gray40",
                corner_radius=6,
                command=toggle_preview,
            )
            preview_toggle.pack(side="left", padx=5)
            # Length slider
            length_frame = ctk.CTkFrame(gen_dialog, fg_color="transparent")
            length_frame.pack(pady=15, padx=20, fill="x")

            ctk.CTkLabel(
                length_frame, text="Length:", font=("Segoe UI", 13, "bold")
            ).pack(side="left")

            length_var = tk.IntVar(value=16)
            length_label = ctk.CTkLabel(
                length_frame,
                text="16",
                font=("Segoe UI", 13, "bold"),
                text_color=COLORS["accent"],
            )
            length_label.pack(side="right")

            def update_length(val):
                length_label.configure(text=str(int(float(val))))
                generate_preview()

            length_slider = ctk.CTkSlider(
                gen_dialog,
                from_=8,
                to=32,
                number_of_steps=24,
                variable=length_var,
                command=update_length,
                width=420,
                button_color=COLORS["accent"],
                button_hover_color=COLORS["accent_hover"],
                progress_color=COLORS["accent"],
            )
            length_slider.pack(pady=(0, 20), padx=20)

            # Options checkboxes
            options_frame = ctk.CTkFrame(
                gen_dialog, fg_color=COLORS["bg_card"], corner_radius=10
            )
            options_frame.pack(pady=10, padx=20, fill="x", ipady=10)

            uppercase_var = tk.BooleanVar(value=True)
            lowercase_var = tk.BooleanVar(value=True)
            numbers_var = tk.BooleanVar(value=True)
            symbols_var = tk.BooleanVar(value=True)

            def on_option_change():
                generate_preview()

            ctk.CTkCheckBox(
                options_frame,
                text="Uppercase (A-Z)",
                variable=uppercase_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Lowercase (a-z)",
                variable=lowercase_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Numbers (0-9)",
                variable=numbers_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Symbols (!@#$%^&*)",
                variable=symbols_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            status = ctk.CTkLabel(gen_dialog, text="", font=("Segoe UI", 11))
            status.pack(pady=5)

            def generate_preview():
                import random
                import string

                length = length_var.get()
                chars = ""

                if uppercase_var.get():
                    chars += string.ascii_uppercase
                if lowercase_var.get():
                    chars += string.ascii_lowercase
                if numbers_var.get():
                    chars += string.digits
                if symbols_var.get():
                    chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"

                if not chars:
                    status.configure(
                        text="❌ Select at least one option!",
                        text_color=COLORS["danger"],
                    )
                    preview_entry.delete(0, "end")
                    return

                status.configure(text="")
                generated = "".join(random.choice(chars) for _ in range(length))
                preview_entry.delete(0, "end")
                preview_entry.insert(0, generated)

            def use_password():
                pwd = preview_entry.get()
                if pwd:
                    password_entry.delete(0, "end")
                    password_entry.insert(0, pwd)
                    gen_dialog.destroy()

            # Button row
            button_row = ctk.CTkFrame(gen_dialog, fg_color="transparent")
            button_row.pack(pady=20)

            ctk.CTkButton(
                button_row,
                text="🔄 Regenerate",
                width=170,
                height=45,
                font=("Segoe UI", 13, "bold"),
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=8,
                command=generate_preview,
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                button_row,
                text="✅ Use This Password",
                width=240,
                height=45,
                font=("Segoe UI", 13, "bold"),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=8,
                command=use_password,
            ).pack(side="left", padx=5)

            # Generate initial password
            generate_preview()

        ctk.CTkButton(
            password_frame,
            text="🎲 Generate",
            width=105,
            height=40,
            command=show_generator,
        ).place(
            x=290, y=0
        )  # Use place for fixed position

        url_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="URL (optional)"
        )
        url_entry.pack(pady=10)

        notes_entry = ctk.CTkTextbox(dialog, width=400, height=100)
        notes_entry.insert("1.0", "Notes (optional)")
        notes_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            title = title_entry.get().strip()
            username = username_entry.get().strip()
            password = password_entry.get()
            url = url_entry.get().strip()
            notes = notes_entry.get("1.0", "end").strip()

            if not title or not password:
                status.configure(
                    text="❌ Title and password required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.add_password(title, username, password, url, notes)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Password added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Password",
            width=400,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_add_api_key_dialog(self):
        """Dialog to add API key"""
        dialog = self.create_dialog("Add API Key", 500, 450)

        ctk.CTkLabel(
            dialog, text="Add New API Key", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        service_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="Service Name (e.g., OpenAI)"
        )
        service_entry.pack(pady=10)

        key_entry = ctk.CTkEntry(
            dialog, width=400, height=40, placeholder_text="API Key"
        )
        key_entry.pack(pady=10)

        desc_entry = ctk.CTkTextbox(dialog, width=400, height=100)
        desc_entry.insert("1.0", "Description (optional)")
        desc_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            service = service_entry.get().strip()
            key = key_entry.get().strip()
            desc = desc_entry.get("1.0", "end").strip()

            if not service or not key:
                status.configure(
                    text="❌ Service and key required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.add_api_key(service, key, desc)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "API key added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save API Key",
            width=400,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_add_note_dialog(self):
        """Dialog to add secure note"""
        dialog = self.create_dialog("Add Secure Note", 600, 600)

        ctk.CTkLabel(
            dialog, text="Add Secure Note", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        title_entry = ctk.CTkEntry(
            dialog, width=500, height=40, placeholder_text="Note Title"
        )
        title_entry.pack(pady=10)

        content_entry = ctk.CTkTextbox(dialog, width=500, height=300)
        content_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            title = title_entry.get().strip()
            content = content_entry.get("1.0", "end").strip()

            if not title or not content:
                status.configure(
                    text="❌ Title and content required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.add_note(title, content)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Note added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Note",
            width=500,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_add_ssh_key_dialog(self):
        """Dialog to add SSH key"""
        dialog = self.create_dialog("Add SSH Key", 600, 550)

        ctk.CTkLabel(dialog, text="Add SSH Key", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        name_entry = ctk.CTkEntry(
            dialog, width=500, height=40, placeholder_text="Key Name (e.g., GitHub)"
        )
        name_entry.pack(pady=10)

        private_entry = ctk.CTkTextbox(dialog, width=500, height=150)
        private_entry.insert("1.0", "Private Key")
        private_entry.pack(pady=10)

        public_entry = ctk.CTkTextbox(dialog, width=500, height=80)
        public_entry.insert("1.0", "Public Key (optional)")
        public_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            name = name_entry.get().strip()
            private = private_entry.get("1.0", "end").strip()
            public = public_entry.get("1.0", "end").strip()

            if not name or not private:
                status.configure(
                    text="❌ Name and private key required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.add_ssh_key(name, private, public)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "SSH key added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save SSH Key",
            width=500,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_add_file_dialog(self):
        """Dialog to add encrypted file"""
        file_path = filedialog.askopenfilename(title="Select File to Encrypt")
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            filename = Path(file_path).name
            self.vault.add_file(filename, file_data)
            self.display_items()
            messagebox.showinfo("Success", f"File '{filename}' encrypted and added!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add file: {str(e)}")

    def show_add_folder_dialog(self):
        """Dialog to add folder"""
        folder_path = filedialog.askdirectory(title="Select Folder to Track")
        if not folder_path:
            return

        dialog = self.create_dialog("Add Folder", 500, 400)

        ctk.CTkLabel(dialog, text="Add Folder", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        ctk.CTkLabel(
            dialog, text=f"Selected: {Path(folder_path).name}", font=("Segoe UI", 12)
        ).pack(pady=10)

        desc_entry = ctk.CTkTextbox(dialog, width=400, height=100)
        desc_entry.insert("1.0", "Description (optional)")
        desc_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            desc = desc_entry.get("1.0", "end").strip()
            status.configure(text="⏳ Adding folder...", text_color=COLORS["warning"])
            dialog.update()

            try:
                self.vault.add_encrypted_folder(folder_path, desc)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Folder added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Add Folder",
            width=400,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def show_edit_password(self, item):
        """Dialog to edit password"""
        dialog = self.create_dialog("Edit Password", 500, 680)

        ctk.CTkLabel(dialog, text="Edit Password", font=("Segoe UI", 20, "bold")).pack(
            pady=20
        )

        title_entry = ctk.CTkEntry(dialog, width=400, height=40)
        title_entry.insert(0, item.get("title", ""))
        title_entry.pack(pady=10)

        username_entry = ctk.CTkEntry(dialog, width=400, height=40)
        username_entry.insert(0, item.get("username", ""))
        username_entry.pack(pady=10)

        # Password frame with toggle visibility - FIXED WIDTH
        password_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        password_frame.pack(pady=10)
        password_frame.pack_propagate(False)  # Prevent resizing
        password_frame.configure(width=400, height=40)

        password_entry = ctk.CTkEntry(password_frame, width=240, height=40, show="●")
        password_entry.insert(0, item.get("password", ""))
        password_entry.place(x=0, y=0)  # Use place instead of pack

        # Toggle show/hide password
        show_password = [False]

        def toggle_password_visibility():
            if show_password[0]:
                password_entry.configure(show="●")
                toggle_btn.configure(text="🔒")  # Lock when hidden
                show_password[0] = False
            else:
                password_entry.configure(show="")
                toggle_btn.configure(text="🔓")  # Unlock when shown
                show_password[0] = True

        toggle_btn = ctk.CTkButton(
            password_frame,
            text="🔒",  # Start with lock (password hidden)
            width=40,
            height=40,
            font=("Segoe UI", 16),
            fg_color="gray30",  # FIXED: Now matches other buttons
            hover_color="gray40",
            corner_radius=6,
            command=toggle_password_visibility,
        )
        toggle_btn.place(x=245, y=0)

        def show_generator():
            gen_dialog = self.create_dialog("Password Generator", 500, 600)

            ctk.CTkLabel(
                gen_dialog, text="Generate Password", font=("Segoe UI", 18, "bold")
            ).pack(pady=20)

            # Generated password preview with proper container
            preview_container = ctk.CTkFrame(
                gen_dialog, fg_color=COLORS["bg_card"], corner_radius=10, height=100
            )
            preview_container.pack(pady=10, padx=20, fill="x")
            preview_container.pack_propagate(False)

            ctk.CTkLabel(
                preview_container,
                text="Generated Password:",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"],
            ).pack(anchor="w", padx=15, pady=(12, 8))

            preview_row = ctk.CTkFrame(preview_container, fg_color="transparent")
            preview_row.pack(fill="x", padx=15, pady=(0, 12))

            preview_entry = ctk.CTkEntry(
                preview_row,
                width=340,
                height=40,
                font=("Consolas", 14),
                show="●",
                fg_color=COLORS["bg_secondary"],
                border_width=2,
                border_color=COLORS["accent"],
            )
            preview_entry.pack(side="left", padx=(0, 8))

            show_preview = [False]

            def toggle_preview():
                if show_preview[0]:
                    preview_entry.configure(show="●")
                    preview_toggle.configure(text="🔒")  # Lock when hidden
                    show_preview[0] = False
                else:
                    preview_entry.configure(show="")
                    preview_toggle.configure(text="🔓")  # Unlock when shown
                    show_preview[0] = True

            preview_toggle = ctk.CTkButton(
                preview_row,
                text="🔒",  # Start with lock (password hidden)
                width=40,
                height=40,
                font=("Segoe UI", 16),
                fg_color="gray30",  # FIXED: Now matches other buttons
                hover_color="gray40",
                corner_radius=6,
                command=toggle_preview,
            )
            preview_toggle.pack(side="left", padx=5)
            # Length slider
            length_frame = ctk.CTkFrame(gen_dialog, fg_color="transparent")
            length_frame.pack(pady=15, padx=20, fill="x")

            ctk.CTkLabel(
                length_frame, text="Length:", font=("Segoe UI", 13, "bold")
            ).pack(side="left")

            length_var = tk.IntVar(value=16)
            length_label = ctk.CTkLabel(
                length_frame,
                text="16",
                font=("Segoe UI", 13, "bold"),
                text_color=COLORS["accent"],
            )
            length_label.pack(side="right")

            def update_length(val):
                length_label.configure(text=str(int(float(val))))
                generate_preview()

            length_slider = ctk.CTkSlider(
                gen_dialog,
                from_=8,
                to=32,
                number_of_steps=24,
                variable=length_var,
                command=update_length,
                width=420,
                button_color=COLORS["accent"],
                button_hover_color=COLORS["accent_hover"],
                progress_color=COLORS["accent"],
            )
            length_slider.pack(pady=(0, 20), padx=20)

            # Options checkboxes
            options_frame = ctk.CTkFrame(
                gen_dialog, fg_color=COLORS["bg_card"], corner_radius=10
            )
            options_frame.pack(pady=10, padx=20, fill="x", ipady=10)

            uppercase_var = tk.BooleanVar(value=True)
            lowercase_var = tk.BooleanVar(value=True)
            numbers_var = tk.BooleanVar(value=True)
            symbols_var = tk.BooleanVar(value=True)

            def on_option_change():
                generate_preview()

            ctk.CTkCheckBox(
                options_frame,
                text="Uppercase (A-Z)",
                variable=uppercase_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Lowercase (a-z)",
                variable=lowercase_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Numbers (0-9)",
                variable=numbers_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            ctk.CTkCheckBox(
                options_frame,
                text="Symbols (!@#$%^&*)",
                variable=symbols_var,
                font=("Segoe UI", 12),
                command=on_option_change,
                checkbox_width=22,
                checkbox_height=22,
            ).pack(anchor="w", padx=20, pady=5)

            status = ctk.CTkLabel(gen_dialog, text="", font=("Segoe UI", 11))
            status.pack(pady=5)

            def generate_preview():
                import random
                import string

                length = length_var.get()
                chars = ""

                if uppercase_var.get():
                    chars += string.ascii_uppercase
                if lowercase_var.get():
                    chars += string.ascii_lowercase
                if numbers_var.get():
                    chars += string.digits
                if symbols_var.get():
                    chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"

                if not chars:
                    status.configure(
                        text="❌ Select at least one option!",
                        text_color=COLORS["danger"],
                    )
                    preview_entry.delete(0, "end")
                    return

                status.configure(text="")
                generated = "".join(random.choice(chars) for _ in range(length))
                preview_entry.delete(0, "end")
                preview_entry.insert(0, generated)

            def use_password():
                pwd = preview_entry.get()
                if pwd:
                    password_entry.delete(0, "end")
                    password_entry.insert(0, pwd)
                    gen_dialog.destroy()

            # Button row
            button_row = ctk.CTkFrame(gen_dialog, fg_color="transparent")
            button_row.pack(pady=20)

            ctk.CTkButton(
                button_row,
                text="🔄 Regenerate",
                width=170,
                height=45,
                font=("Segoe UI", 13, "bold"),
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=8,
                command=generate_preview,
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                button_row,
                text="✅ Use This Password",
                width=240,
                height=45,
                font=("Segoe UI", 13, "bold"),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=8,
                command=use_password,
            ).pack(side="left", padx=5)

            # Generate initial password
            generate_preview()

        ctk.CTkButton(
            password_frame,
            text="🎲 Generate",
            width=105,
            height=40,
            command=show_generator,
        ).place(
            x=290, y=0
        )  # Use place for fixed position

        url_entry = ctk.CTkEntry(dialog, width=400, height=40)
        url_entry.insert(0, item.get("url", ""))
        url_entry.pack(pady=10)

        notes_entry = ctk.CTkTextbox(dialog, width=400, height=100)
        notes_entry.insert("1.0", item.get("notes", ""))
        notes_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            updates = {
                "title": title_entry.get().strip(),
                "username": username_entry.get().strip(),
                "password": password_entry.get(),
                "url": url_entry.get().strip(),
                "notes": notes_entry.get("1.0", "end").strip(),
            }

            if not updates["title"] or not updates["password"]:
                status.configure(
                    text="❌ Title and password required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.update_password(item["id"], **updates)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Password updated successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="💾 Save Changes",
            width=400,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def view_note(self, note):
        """View secure note in dialog"""
        dialog = self.create_dialog(note.get("title", "Note"), 700, 500)

        ctk.CTkLabel(
            dialog, text=note.get("title", "Untitled"), font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        content_box = ctk.CTkTextbox(dialog, width=650, height=350)
        content_box.insert("1.0", note.get("content", ""))
        content_box.configure(state="disabled")
        content_box.pack(pady=10)

        ctk.CTkButton(
            dialog, text="Close", width=200, height=40, command=dialog.destroy
        ).pack(pady=20)

    def show_password_history(self, item):
        """Show password change history"""
        dialog = self.create_dialog("Password History", 600, 600)

        ctk.CTkLabel(
            dialog,
            text=f"Password History - {item.get('title', 'Unknown')}",
            font=("Segoe UI", 20, "bold"),
        ).pack(pady=20)

        history = self.vault.get_password_history(item["id"])

        if not history:
            ctk.CTkLabel(
                dialog,
                text="No password history available",
                font=("Segoe UI", 14),
                text_color=COLORS["text_secondary"],
            ).pack(pady=50)
        else:
            scroll = ctk.CTkScrollableFrame(dialog, width=550, height=350)
            scroll.pack(pady=10, padx=20)

            for h in history:
                card = ctk.CTkFrame(
                    scroll, fg_color=COLORS["bg_card"], corner_radius=10
                )
                card.pack(fill="x", pady=8, ipady=10, ipadx=10)

                date = datetime.fromisoformat(h["changed_at"]).strftime(
                    "%Y-%m-%d %H:%M"
                )
                ctk.CTkLabel(
                    card, text=f"Changed: {date}", font=("Segoe UI", 12, "bold")
                ).pack(anchor="w")

                pwd_frame = ctk.CTkFrame(card, fg_color="transparent")
                pwd_frame.pack(fill="x", pady=(5, 0))

                ctk.CTkLabel(
                    pwd_frame,
                    text=f"Password: {'●' * 10}",
                    font=("Segoe UI", 11),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left")

                ctk.CTkButton(
                    pwd_frame,
                    text="📋 Copy",
                    width=80,
                    height=28,
                    fg_color=COLORS["accent"],
                    command=lambda p=h["old_password"]: self.copy_to_clipboard(
                        p, "Old Password"
                    ),
                ).pack(side="right")

        ctk.CTkButton(
            dialog, text="Close", width=200, height=40, command=dialog.destroy
        ).pack(pady=20)

    def set_folder_password(self, folder_id):
        """Set password for folder ZIP download"""
        dialog = self.create_dialog("Set Folder Password", 450, 400)

        ctk.CTkLabel(
            dialog, text="Set ZIP Password", font=("Segoe UI", 18, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            dialog,
            text="Enter password to protect ZIP file:",
            font=("Segoe UI", 12),
        ).pack(pady=10)

        pwd_entry = ctk.CTkEntry(
            dialog, width=350, height=40, placeholder_text="ZIP Password", show="●"
        )
        pwd_entry.pack(pady=10)

        confirm_entry = ctk.CTkEntry(
            dialog, width=350, height=40, placeholder_text="Confirm Password", show="●"
        )
        confirm_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def save():
            password = pwd_entry.get()
            confirm = confirm_entry.get()

            if not password:
                status.configure(
                    text="❌ Password required", text_color=COLORS["danger"]
                )
                return

            if password != confirm:
                status.configure(
                    text="❌ Passwords don't match", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.set_folder_password(folder_id, password)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "Folder password set successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        ctk.CTkButton(
            dialog,
            text="🔐 Set Password",
            width=350,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=save,
        ).pack(pady=20)

    def download_folder_zip(self, folder_id, folder_name):
        """Download folder as ZIP file"""
        self.reset_activity()

        save_path = filedialog.asksaveasfilename(
            title="Save ZIP File",
            initialfile=f"{folder_name}.zip",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )

        if not save_path:
            return

        try:
            self.vault.download_folder_as_zip(folder_id, save_path)
            messagebox.showinfo("Success", f"Folder downloaded as ZIP:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Download failed: {str(e)}")

    def show_backup_dialog(self):
        """Create vault backup"""
        self.reset_activity()
        save_path = filedialog.asksaveasfilename(
            title="Save Backup",
            defaultextension=".vault",
            filetypes=[("Vault files", "*.vault"), ("All files", "*.*")],
        )

        if save_path:
            try:
                self.vault.backup_vault(save_path)
                messagebox.showinfo("Success", f"Backup saved to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Backup failed: {str(e)}")

    def show_restore_dialog(self):
        """Restore from backup"""
        self.reset_activity()
        backup_path = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Vault files", "*.vault"), ("All files", "*.*")],
        )

        if not backup_path:
            return

        dialog = self.create_dialog("Restore Backup", 400, 280)

        ctk.CTkLabel(
            dialog, text="Restore from Backup", font=("Segoe UI", 18, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            dialog,
            text="Enter backup password:",
            font=("Segoe UI", 12),
        ).pack(pady=10)

        pwd_entry = ctk.CTkEntry(dialog, width=300, height=40, show="●")
        pwd_entry.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def restore():
            password = pwd_entry.get()
            if not password:
                status.configure(
                    text="❌ Password required", text_color=COLORS["danger"]
                )
                return

            try:
                self.vault.restore_vault(backup_path, password)
                dialog.destroy()
                self.show_vault()
                messagebox.showinfo("Success", "Vault restored successfully!")
            except Exception as e:
                status.configure(text=f"❌ {str(e)}", text_color=COLORS["danger"])

        ctk.CTkButton(
            dialog,
            text="🔄 Restore",
            width=300,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=restore,
        ).pack(pady=20)

        ctk.CTkButton(
            dialog,
            text="❌ Cancel",
            width=300,
            height=40,
            font=("Segoe UI", 12),
            fg_color="gray30",
            hover_color="gray40",
            command=dialog.destroy,
        ).pack(pady=(0, 20))

    def show_change_master_password(self):
        """Change master password dialog"""
        self.reset_activity()
        dialog = self.create_dialog("Change Master Password", 450, 400)

        ctk.CTkLabel(
            dialog, text="Change Master Password", font=("Segoe UI", 18, "bold")
        ).pack(pady=20)

        old_pwd = ctk.CTkEntry(
            dialog, width=350, height=40, placeholder_text="Current Password", show="●"
        )
        old_pwd.pack(pady=10)

        new_pwd = ctk.CTkEntry(
            dialog, width=350, height=40, placeholder_text="New Password", show="●"
        )
        new_pwd.pack(pady=10)

        confirm_pwd = ctk.CTkEntry(
            dialog,
            width=350,
            height=40,
            placeholder_text="Confirm New Password",
            show="●",
        )
        confirm_pwd.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def change():
            old = old_pwd.get()
            new = new_pwd.get()
            confirm = confirm_pwd.get()

            if not old or not new or not confirm:
                status.configure(
                    text="❌ All fields required", text_color=COLORS["danger"]
                )
                return

            if new != confirm:
                status.configure(
                    text="❌ Passwords don't match", text_color=COLORS["danger"]
                )
                return

            if len(new) < 8:
                status.configure(
                    text="❌ Password too short (min 8 chars)",
                    text_color=COLORS["danger"],
                )
                return

            try:
                self.vault.change_master_password(old, new)
                dialog.destroy()
                messagebox.showinfo("Success", "Master password changed successfully!")
            except Exception as e:
                status.configure(text=f"❌ {str(e)}", text_color=COLORS["danger"])

        ctk.CTkButton(
            dialog,
            text="🔐 Change Password",
            width=350,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=change,
        ).pack(pady=20)

    def show_shortcuts_help(self):
        """Display keyboard shortcuts"""
        dialog = self.create_dialog("Keyboard Shortcuts", 500, 450)

        ctk.CTkLabel(
            dialog, text="⌨️ Keyboard Shortcuts", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        shortcuts_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=10
        )
        shortcuts_frame.pack(pady=10, padx=20, fill="both", expand=True)

        shortcuts = [
            ("Ctrl + L", "Lock vault"),
            ("Ctrl + F", "Toggle search"),
            ("Ctrl + N", "Add new item"),
            ("Ctrl + B", "Create backup"),
            ("Ctrl + Q", "Quit application"),
            ("Escape", "Close search"),
        ]

        for key, action in shortcuts:
            row = ctk.CTkFrame(shortcuts_frame, fg_color="transparent")
            row.pack(fill="x", pady=8, padx=20)

            ctk.CTkLabel(
                row,
                text=key,
                font=("Consolas", 12, "bold"),
                text_color=COLORS["accent"],
                width=120,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(row, text=action, font=("Segoe UI", 12), anchor="w").pack(
                side="left"
            )

        ctk.CTkButton(
            dialog, text="Close", width=200, height=40, command=dialog.destroy
        ).pack(pady=20)

    def copy_to_clipboard(self, text, label="Data"):
        """Copy text to clipboard with auto-clear"""
        pyperclip.copy(text)
        messagebox.showinfo("Copied", f"{label} copied to clipboard!")

        if self.clipboard_timer:
            self.app.after_cancel(self.clipboard_timer)

        self.clipboard_timer = self.app.after(
            CLIPBOARD_CLEAR_SECONDS * 1000, lambda: pyperclip.copy("")
        )

    def delete_item(self, item_id, item_type):
        """Delete item with confirmation"""
        self.reset_activity()
        if not messagebox.askyesno(
            "Confirm Delete", "Are you sure you want to delete this item?"
        ):
            return

        try:
            if item_type == "password":
                self.vault.delete_password(item_id)
            elif item_type == "api_key":
                self.vault.delete_api_key(item_id)
            elif item_type == "note":
                self.vault.delete_note(item_id)
            elif item_type == "ssh_key":
                self.vault.delete_ssh_key(item_id)
            elif item_type == "file":
                self.vault.delete_file(item_id)
            elif item_type == "encrypted_folder":
                self.vault.delete_encrypted_folder(item_id)

            self.display_items()
            messagebox.showinfo("Success", "Item deleted successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {str(e)}")

    def export_file(self, file_id, filename):
        """Export encrypted file"""
        self.reset_activity()
        save_path = filedialog.asksaveasfilename(
            title="Export File",
            initialfile=filename,
            defaultextension=Path(filename).suffix,
        )

        if save_path:
            try:
                file_data = self.vault.get_file(file_id)
                with open(save_path, "wb") as f:
                    f.write(file_data)
                messagebox.showinfo("Success", f"File exported to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")

    def lock_vault(self):
        """Lock vault and return to login"""
        self.reset_activity()
        # Cancel TOTP auto-refresh when leaving
        if hasattr(self, "_totp_timer"):
            self.app.after_cancel(self._totp_timer)
            delattr(self, "_totp_timer")
        self.vault.lock()
        self.show_login()

    def check_password_breach(self, item):
        """Check if password has been breached"""
        self.reset_activity()

        from .breach_checker import check_password_breach

        # Show checking dialog
        dialog = self.create_dialog("Checking Password", 500, 450)

        # Title
        ctk.CTkLabel(
            dialog, text="🔍 Password Breach Check", font=("Segoe UI", 20, "bold")
        ).pack(pady=(20, 10))

        # Status label
        status_label = ctk.CTkLabel(
            dialog,
            text="⏳ Checking against Have I Been Pwned database...\nThis uses k-anonymity (your password is safe)",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
        )
        status_label.pack(pady=20)

        # Force UI update
        dialog.update_idletasks()
        dialog.update()

        # Check the password
        try:
            password = item.get("password", "")
            if not password:
                status_label.configure(
                    text="❌ No password found", text_color=COLORS["danger"]
                )
                return

            result = check_password_breach(password)

            # Update status with result
            status_label.configure(
                text=result["message"],
                text_color=result["color"],
                font=("Segoe UI", 16, "bold"),
            )

            # Add details based on result
            if result["breached"]:
                # DANGER - Password leaked
                details = f"""
⚠️ This password was found in {result['count']:,} data breaches!

What this means:
- Hackers have this password in their databases
- They can use it to try to access your accounts
- You should change it IMMEDIATELY

Password: {item.get('title', 'Unknown')}
"""
                ctk.CTkLabel(
                    dialog,
                    text=details,
                    font=("Segoe UI", 11),
                    text_color=COLORS["danger"],
                    wraplength=430,
                    justify="left",
                ).pack(pady=15, padx=20)

            elif result["breached"] == False:
                # SAFE - Not found
                details = """
✅ Good news! This password has not been found 
in any known data breaches.

However:
- Always use strong, unique passwords
- Enable 2FA when possible
- Change passwords regularly
"""
                ctk.CTkLabel(
                    dialog,
                    text=details,
                    font=("Segoe UI", 11),
                    text_color=COLORS["success"],
                    wraplength=430,
                    justify="left",
                ).pack(pady=15, padx=20)

            else:
                # ERROR - Could not check
                details = """
⚠️ Could not complete the check.
This might be due to:
- No internet connection
- API temporarily unavailable
- Firewall blocking the request

Try again later.
"""
                ctk.CTkLabel(
                    dialog,
                    text=details,
                    font=("Segoe UI", 11),
                    text_color=COLORS["warning"],
                    wraplength=430,
                    justify="left",
                ).pack(pady=15, padx=20)

        except Exception as e:
            status_label.configure(
                text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
            )

        # Close button
        ctk.CTkButton(
            dialog,
            text="Close",
            width=200,
            height=45,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["bg_secondary"],
            hover_color=COLORS["accent"],
            corner_radius=8,
            command=dialog.destroy,
        ).pack(pady=(15, 25))

    def display_totp_items(self, items):
        """Display TOTP/2FA codes with live countdown"""
        import pyotp

        # Always rebuild from scratch (simpler and more reliable)
        for widget in self.items_container.winfo_children():
            widget.destroy()

        if not items:
            ctk.CTkLabel(
                self.items_container,
                text="No 2FA codes yet\nClick '+ Add New' to create one",
                font=("Segoe UI", 16),
                text_color=COLORS["text_secondary"],
            ).pack(pady=100)
            return

        # Store references for updates
        self._totp_labels = {}

        for item in items:
            card = ctk.CTkFrame(
                self.items_container, fg_color=COLORS["bg_card"], corner_radius=12
            )
            card.pack(fill="x", pady=10, padx=10, ipady=15, ipadx=15)

            # Header
            header_row = ctk.CTkFrame(card, fg_color="transparent")
            header_row.pack(fill="x", pady=(0, 5), padx=5)

            ctk.CTkLabel(
                header_row,
                text=item.get("name", "Untitled"),
                font=("Segoe UI", 16, "bold"),
            ).pack(side="left", anchor="w")

            if item.get("issuer"):
                ctk.CTkLabel(
                    header_row,
                    text=f"({item['issuer']})",
                    font=("Segoe UI", 12),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left", padx=(10, 0))

            # Code display
            code_frame = ctk.CTkFrame(
                card, fg_color=COLORS["bg_secondary"], corner_radius=10
            )
            code_frame.pack(fill="x", pady=(10, 10), padx=5, ipady=12)

            code_row = ctk.CTkFrame(code_frame, fg_color="transparent")
            code_row.pack(fill="x", padx=15)

            # Generate initial code
            try:
                totp = pyotp.TOTP(item["secret"])
                code = totp.now()
                remaining = 30 - (int(datetime.now().timestamp()) % 30)
                formatted_code = f"{code[:3]} {code[3:]}"
            except:
                formatted_code = "ERROR"
                remaining = 0

            code_label = ctk.CTkLabel(
                code_row,
                text=formatted_code,
                font=("Consolas", 32, "bold"),
                text_color=COLORS["accent"],
            )
            code_label.pack(side="left")

            timer_color = COLORS["danger"] if remaining <= 5 else COLORS["success"]
            timer_label = ctk.CTkLabel(
                code_row,
                text=f"⏱️ {remaining}s",
                font=("Segoe UI", 14, "bold"),
                text_color=timer_color,
            )
            timer_label.pack(side="right")

            # Store for updates
            self._totp_labels[item["id"]] = {
                "secret": item["secret"],
                "code_label": code_label,
                "timer_label": timer_label,
            }

            # Date info
            date_row = ctk.CTkFrame(card, fg_color="transparent")
            date_row.pack(fill="x", pady=(5, 10), padx=5)

            created = item.get("created", "Unknown")
            if created != "Unknown" and len(created) > 10:
                created = created[:10]

            ctk.CTkLabel(
                date_row,
                text=f"📅 Created: {created}",
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(5, 0))

            # Actions
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", pady=(10, 0), padx=5)

            copy_btn = ctk.CTkButton(
                actions,
                text="📋 Copy Code",
                width=120,
                height=32,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=6,
                command=lambda s=item["secret"]: self._copy_current_totp(s),
            )
            copy_btn.pack(side="left", padx=(5, 8))

            ctk.CTkButton(
                actions,
                text="🗑️ Delete",
                width=90,
                height=32,
                fg_color=COLORS["danger"],
                hover_color="#c0392b",
                corner_radius=6,
                command=lambda i=item["id"]: self.delete_totp(i),
            ).pack(side="right", padx=(0, 5))

        # Start auto-refresh (updates every second)
        self._schedule_totp_refresh()

    def _schedule_totp_refresh(self):
        """Schedule the next TOTP refresh"""
        # Cancel any existing timer
        if hasattr(self, "_totp_timer"):
            self.app.after_cancel(self._totp_timer)

        # Only schedule if still on TOTP page and unlocked
        if (
            hasattr(self, "current_category")
            and self.current_category == "totp_codes"
            and not self.vault.is_locked
            and hasattr(self, "_totp_labels")
        ):
            self._totp_timer = self.app.after(1000, self._update_totp_display)

    def _copy_current_totp(self, secret):
        """Copy the CURRENT TOTP code (not cached)"""
        import pyotp

        try:
            totp = pyotp.TOTP(secret)
            current_code = totp.now()
            self.copy_to_clipboard(current_code, "TOTP Code")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate code: {str(e)}")

    def _update_totp_display(self):
        """Update TOTP codes and countdown without rebuilding"""
        import pyotp

        if not hasattr(self, "_totp_labels"):
            return

        for item_id, data in list(self._totp_labels.items()):
            try:
                # Check if widgets still exist
                if not data["code_label"].winfo_exists():
                    continue

                # Generate new code
                totp = pyotp.TOTP(data["secret"])
                code = totp.now()
                remaining = 30 - (int(datetime.now().timestamp()) % 30)

                # Update display
                formatted_code = f"{code[:3]} {code[3:]}"
                data["code_label"].configure(text=formatted_code)

                # Update timer color
                timer_color = COLORS["danger"] if remaining <= 5 else COLORS["success"]
                data["timer_label"].configure(
                    text=f"⏱️ {remaining}s", text_color=timer_color
                )

            except Exception as e:
                print(f"Error updating TOTP {item_id}: {e}")
                continue

        # Schedule next update
        self._schedule_totp_refresh()

    def _update_totp_codes_only(self):
        """Update TOTP codes without rebuilding widgets"""
        import pyotp

        # Safety check
        if not hasattr(self, "_totp_cards") or not self._totp_cards:
            return

        items = self.vault.list_totp()

        for item in items:
            item_id = item["id"]
            if item_id not in self._totp_cards:
                continue

            card_data = self._totp_cards[item_id]

            try:
                # Check if widget still exists
                if not card_data["code_label"].winfo_exists():
                    continue

                totp = pyotp.TOTP(item["secret"])
                code = totp.now()
                remaining = 30 - (int(datetime.now().timestamp()) % 30)

                # Format and update
                formatted_code = f"{code[:3]} {code[3:]}"
                card_data["code_label"].configure(text=formatted_code)

                timer_color = COLORS["danger"] if remaining <= 5 else COLORS["success"]
                card_data["timer_label"].configure(
                    text=f"⏱️ {remaining}s", text_color=timer_color
                )

                card_data["copy_btn"].configure(
                    command=lambda c=code: self.copy_to_clipboard(c, "TOTP Code")
                )
            except:
                continue

        # Schedule next update HERE
        if self.current_category == "totp_codes" and not self.vault.is_locked:
            self._totp_timer = self.app.after(1000, self._refresh_totp)

    def _refresh_totp(self):
        """Auto-refresh TOTP display every second"""
        # Only refresh if still on TOTP page and unlocked
        if (
            hasattr(self, "current_category")
            and self.current_category == "totp_codes"
            and not self.vault.is_locked
        ):
            self.display_items()

    def show_add_totp_dialog(self):
        """Dialog to add TOTP/2FA code"""
        dialog = self.create_dialog("Add 2FA/TOTP Code", 550, 500)

        ctk.CTkLabel(
            dialog, text="Add 2FA/TOTP Code", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            dialog,
            text="Scan QR code with your authenticator app, then paste the secret key here",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            wraplength=480,
        ).pack(pady=(0, 15))

        name_entry = ctk.CTkEntry(
            dialog, width=450, height=40, placeholder_text="Name (e.g., Google, GitHub)"
        )
        name_entry.pack(pady=10)

        issuer_entry = ctk.CTkEntry(
            dialog,
            width=450,
            height=40,
            placeholder_text="Issuer (optional, e.g., google.com)",
        )
        issuer_entry.pack(pady=10)

        secret_entry = ctk.CTkEntry(
            dialog, width=450, height=40, placeholder_text="Secret Key (from QR code)"
        )
        secret_entry.pack(pady=10)

        # Test code preview
        preview_label = ctk.CTkLabel(
            dialog,
            text="",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["accent"],
        )
        preview_label.pack(pady=10)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def test_code():
            """Test if secret key generates valid code"""
            import pyotp

            secret = secret_entry.get().strip().replace(" ", "").upper()

            if not secret:
                preview_label.configure(text="Enter secret key to test")
                return

            try:
                totp = pyotp.TOTP(secret)
                code = totp.now()
                formatted = f"{code[:3]} {code[3:]}"
                preview_label.configure(text=f"✅ Test Code: {formatted}")
                status.configure(text="", text_color=COLORS["success"])
            except Exception as e:
                preview_label.configure(text="")
                status.configure(
                    text=f"❌ Invalid secret: {str(e)}", text_color=COLORS["danger"]
                )

        def save():
            name = name_entry.get().strip()
            issuer = issuer_entry.get().strip()
            secret = secret_entry.get().strip().replace(" ", "").upper()

            if not name or not secret:
                status.configure(
                    text="❌ Name and secret required", text_color=COLORS["danger"]
                )
                return

            try:
                # Validate secret by generating a code
                import pyotp

                totp = pyotp.TOTP(secret)
                totp.now()  # This will raise error if invalid

                self.vault.add_totp(name, secret, issuer)
                dialog.destroy()
                self.display_items()
                messagebox.showinfo("Success", "2FA code added successfully!")
            except Exception as e:
                status.configure(
                    text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]
                )

        # Buttons
        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(pady=20)

        ctk.CTkButton(
            button_row,
            text="🧪 Test Code",
            width=180,
            height=45,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=test_code,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_row,
            text="💾 Save Code",
            width=240,
            height=45,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=save,
        ).pack(side="left", padx=5)

    def delete_totp(self, totp_id):
        """Delete TOTP code"""
        self.reset_activity()
        if not messagebox.askyesno(
            "Confirm Delete", "Are you sure you want to delete this 2FA code?"
        ):
            return

        try:
            self.vault.delete_totp(totp_id)
            self.display_items()
            messagebox.showinfo("Success", "2FA code deleted successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {str(e)}")

    def show_recovery_phrase_setup(self, recovery_phrase):
        """Show recovery phrase after new vault creation"""
        dialog = self.create_dialog("🔐 SAVE YOUR RECOVERY PHRASE", 700, 750)

        warning_frame = ctk.CTkFrame(
            dialog, fg_color="#8B0000", corner_radius=12, height=100
        )
        warning_frame.pack(fill="x", padx=20, pady=(20, 15))
        warning_frame.pack_propagate(False)

        ctk.CTkLabel(
            warning_frame,
            text="⚠️ CRITICAL: SAVE THIS RECOVERY PHRASE ⚠️",
            font=("Segoe UI", 18, "bold"),
            text_color="white",
        ).pack(pady=5)

        ctk.CTkLabel(
            warning_frame,
            text="If you forget your master password, THIS IS THE ONLY WAY to recover your vault.\nWrite it down on paper. DO NOT save digitally. Keep it safe.",
            font=("Segoe UI", 11),
            text_color="white",
            wraplength=620,
        ).pack(pady=5)

        ctk.CTkLabel(
            dialog, text="Your 24-Word Recovery Phrase:", font=("Segoe UI", 16, "bold")
        ).pack(pady=(15, 10))

        phrase_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=12, height=320
        )
        phrase_frame.pack(padx=20, pady=10, fill="both")

        from .recovery import RecoverySystem

        recovery = RecoverySystem(self.vault.path)
        formatted_words = recovery.format_phrase_for_display(recovery_phrase)

        columns = [[], [], []]
        for i, (num, word) in enumerate(formatted_words):
            columns[i % 3].append((num, word))

        grid_container = ctk.CTkFrame(phrase_frame, fg_color="transparent")
        grid_container.pack(expand=True, pady=20, padx=20)

        for col_idx, column in enumerate(columns):
            col_frame = ctk.CTkFrame(grid_container, fg_color="transparent")
            col_frame.grid(row=0, column=col_idx, padx=15, sticky="n")

            for num, word in column:
                word_row = ctk.CTkFrame(
                    col_frame, fg_color=COLORS["bg_secondary"], corner_radius=8
                )
                word_row.pack(pady=4, fill="x", ipady=8, ipadx=12)

                ctk.CTkLabel(
                    word_row,
                    text=f"{num}.",
                    font=("Consolas", 12, "bold"),
                    text_color=COLORS["text_secondary"],
                    width=30,
                    anchor="e",
                ).pack(side="left", padx=(5, 10))

                ctk.CTkLabel(
                    word_row,
                    text=word,
                    font=("Consolas", 13, "bold"),
                    text_color=COLORS["accent"],
                    anchor="w",
                ).pack(side="left")

        def copy_phrase():
            import pyperclip

            pyperclip.copy(recovery_phrase)
            copy_btn.configure(text="✅ Copied!")
            dialog.after(2000, lambda: copy_btn.configure(text="📋 Copy All Words"))

        copy_btn = ctk.CTkButton(
            dialog,
            text="📋 Copy All Words",
            width=300,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=copy_phrase,
        )
        copy_btn.pack(pady=10)

        verified = tk.BooleanVar(value=False)

        verify_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=10
        )
        verify_frame.pack(padx=20, pady=15, fill="x", ipady=10)

        ctk.CTkCheckBox(
            verify_frame,
            text="✅ I have written down my recovery phrase in a safe place",
            variable=verified,
            font=("Segoe UI", 12, "bold"),
            checkbox_width=24,
            checkbox_height=24,
        ).pack(pady=10, padx=20)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def confirm_and_close():
            if not verified.get():
                status.configure(
                    text="❌ You must confirm you saved the recovery phrase",
                    text_color=COLORS["danger"],
                )
                return

            self.verify_recovery_phrase_saved(recovery_phrase, dialog)

        ctk.CTkButton(
            dialog,
            text="✅ I've Saved It - Continue",
            width=400,
            height=50,
            font=("Segoe UI", 15, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=10,
            command=confirm_and_close,
        ).pack(pady=(10, 25))

        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    def verify_recovery_phrase_saved(self, original_phrase, parent_dialog):
        """Quiz user on 3 random words"""
        import random

        words = original_phrase.split()
        word_positions = random.sample(range(1, 25), 3)
        word_positions.sort()

        quiz_dialog = self.create_dialog("🧪 Verify You Saved It", 500, 400)

        ctk.CTkLabel(
            quiz_dialog, text="Quick Verification Test", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            quiz_dialog,
            text="Enter these 3 words from your recovery phrase\nto prove you saved it:",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
        ).pack(pady=10)

        entries = []
        for pos in word_positions:
            word_frame = ctk.CTkFrame(quiz_dialog, fg_color="transparent")
            word_frame.pack(pady=8)

            ctk.CTkLabel(
                word_frame,
                text=f"Word #{pos}:",
                font=("Segoe UI", 13, "bold"),
                width=80,
                anchor="e",
            ).pack(side="left", padx=5)

            entry = ctk.CTkEntry(
                word_frame, width=200, height=40, font=("Consolas", 13)
            )
            entry.pack(side="left", padx=5)
            entries.append((pos, entry))

        status = ctk.CTkLabel(quiz_dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=10)

        def check_answers():
            all_correct = True
            for pos, entry in entries:
                entered_word = entry.get().strip().lower()
                correct_word = words[pos - 1].lower()

                if entered_word != correct_word:
                    all_correct = False
                    entry.configure(border_color=COLORS["danger"], border_width=2)
                else:
                    entry.configure(border_color=COLORS["success"], border_width=2)

            if all_correct:
                status.configure(
                    text="✅ Perfect! You've saved your recovery phrase.",
                    text_color=COLORS["success"],
                )
                quiz_dialog.after(
                    1500, lambda: [quiz_dialog.destroy(), parent_dialog.destroy()]
                )
                self.show_vault()
            else:
                status.configure(
                    text="❌ Some words are incorrect. Check your notes and try again.",
                    text_color=COLORS["danger"],
                )

        ctk.CTkButton(
            quiz_dialog,
            text="✅ Verify",
            width=300,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=check_answers,
        ).pack(pady=20)

        entries[0][1].focus()

    def show_recovery_unlock_dialog(self):
        """Unlock vault with recovery phrase"""
        dialog = self.create_dialog("🔐 Recover Vault", 600, 600)

        ctk.CTkLabel(
            dialog, text="Recover Your Vault", font=("Segoe UI", 24, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            dialog,
            text="Enter your 24-word recovery phrase below.\nSeparate words with spaces.",
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

        count_label = ctk.CTkLabel(
            dialog,
            text="0 / 24 words",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
        )
        count_label.pack(pady=5)

        def update_word_count(*args):
            text = phrase_box.get("1.0", "end-1c").strip()
            word_count = len(text.split()) if text else 0

            color = COLORS["success"] if word_count == 24 else COLORS["text_secondary"]
            count_label.configure(text=f"{word_count} / 24 words", text_color=color)

        phrase_box.bind("<KeyRelease>", update_word_count)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=10)

        def attempt_recovery():
            phrase = phrase_box.get("1.0", "end-1c").strip()

            if not phrase:
                status.configure(
                    text="❌ Enter your recovery phrase", text_color=COLORS["danger"]
                )
                return

            from .recovery import RecoverySystem

            recovery = RecoverySystem(self.vault.path)

            valid, error = recovery.validate_phrase_format(phrase)
            if not valid:
                status.configure(text=f"❌ {error}", text_color=COLORS["danger"])
                return

            status.configure(text="⏳ Unlocking vault...", text_color=COLORS["warning"])
            dialog.update()

            try:
                self.vault.unlock_with_recovery(phrase)
                dialog.destroy()
                self.show_vault()
                messagebox.showinfo("Success", "✅ Vault unlocked successfully!")
            except Exception as e:
                status.configure(text=f"❌ {str(e)}", text_color=COLORS["danger"])

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

    def show_qr_code(self, qr_image, title: str, data_type: str):
        """Display QR code in popup"""
        dialog = self.create_dialog(f"📱 QR Code - {title}", 500, 650)

        ctk.CTkLabel(
            dialog, text=f"Scan with Phone Camera", font=("Segoe UI", 20, "bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            dialog,
            text=f"{data_type}: {title}",
            font=("Segoe UI", 14),
            text_color=COLORS["accent"],
        ).pack(pady=(0, 15))

        # Convert PIL image to CTkImage (FIX FOR WARNING)
        qr_image_resized = qr_image.resize((350, 350))
        ctk_image = ctk.CTkImage(
            light_image=qr_image_resized, dark_image=qr_image_resized, size=(350, 350)
        )

        # QR code display
        qr_frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_card"], corner_radius=10)
        qr_frame.pack(pady=10, padx=20, ipady=20, ipadx=20)

        qr_label = ctk.CTkLabel(qr_frame, image=ctk_image, text="")
        qr_label.image = ctk_image  # Keep reference
        qr_label.pack()

        # Instructions
        instructions_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=10
        )
        instructions_frame.pack(pady=15, padx=20, fill="x", ipady=10)

        instructions = [
            "1. Open camera app on your phone",
            "2. Point at QR code above",
            "3. Tap the text to select and copy",
            "4. Paste in any app/website",
        ]

        for instruction in instructions:
            ctk.CTkLabel(
                instructions_frame,
                text=instruction,
                font=("Segoe UI", 11),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w", padx=15, pady=2)

        # Countdown timer
        countdown_label = ctk.CTkLabel(
            dialog,
            text="⏱️ Expires in: 60 seconds",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["warning"],
        )
        countdown_label.pack(pady=10)

        # Auto-close countdown
        remaining = [60]

        def update_countdown():
            remaining[0] -= 1
            if remaining[0] <= 0:
                dialog.destroy()
                return

            color = COLORS["danger"] if remaining[0] <= 10 else COLORS["warning"]
            countdown_label.configure(
                text=f"⏱️ Expires in: {remaining[0]} seconds", text_color=color
            )
            dialog.after(1000, update_countdown)

        update_countdown()

        ctk.CTkButton(
            dialog,
            text="Close",
            width=200,
            height=40,
            font=("Segoe UI", 12),
            fg_color="gray30",
            hover_color="gray40",
            command=dialog.destroy,
        ).pack(pady=20)

    def show_password_qr(self, item):
        """Generate and show QR for password"""
        try:
            qr_image = self.qr_share.create_password_qr(
                title=item.get("title", "Password"),
                username=item.get("username", ""),
                password=item.get("password", ""),
            )
            self.show_qr_code(qr_image, item.get("title", "Password"), "Password")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate QR code: {str(e)}")

    def show_api_key_qr(self, item):
        """Generate and show QR for API key"""
        try:
            qr_image = self.qr_share.create_api_key_qr(
                service=item.get("service", "API Key"), key=item.get("key", "")
            )
            self.show_qr_code(qr_image, item.get("service", "API Key"), "API Key")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate QR code: {str(e)}")

    def show_ssh_key_qr(self, item):
        """Generate and show QR for SSH key"""
        try:
            qr_image = self.qr_share.create_ssh_key_qr(
                name=item.get("name", "SSH Key"),
                private_key=item.get("private_key", ""),
            )
            self.show_qr_code(qr_image, item.get("name", "SSH Key"), "SSH Key")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate QR code: {str(e)}")

    def show_note_qr(self, item):
        """Generate and show QR for note"""
        try:
            qr_image = self.qr_share.create_note_qr(
                title=item.get("title", "Note"), content=item.get("content", "")
            )
            self.show_qr_code(qr_image, item.get("title", "Note"), "Secure Note")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate QR code: {str(e)}")


# THIS SHOULD BE AT THE VERY END - OUTSIDE THE CLASS
def start():
    """Start the LockBox application"""
    app = LockBoxUI()
    app.run()
