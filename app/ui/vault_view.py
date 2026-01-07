import os
import sys
import customtkinter as ctk
import pyperclip
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from app.core.vault import Vault
from app.core.crypto import generate_password, check_password_strength
from app.constants import COLORS, AUTO_LOCK_MINUTES, CLIPBOARD_CLEAR_SECONDS, VAULT_FILE
from app.services.qr_service import QRShare
from app.ui.login_view import LoginViewMixin

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)

# Professional UI Design System
CONTENT_MAX_WIDTH = 900
SIDEBAR_WIDTH = 260
SIDEBAR_COLLAPSED_WIDTH = 72

# Spacing scale (4px base)
SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32}

# Border radii
RAD = {"sm": 6, "md": 8, "lg": 12}

# Typography
FONT = {
    "h1": ("Segoe UI Semibold", 24),
    "h2": ("Segoe UI Semibold", 18),
    "h3": ("Segoe UI Semibold", 14),
    "body": ("Segoe UI", 14),
    "small": ("Segoe UI", 12),
    "button": ("Segoe UI Semibold", 13),
    "nav": ("Segoe UI", 14),
    "icon": ("Segoe UI", 18),
    "mono": ("Consolas", 12),
}

# Control sizes
CTL = {"h": 40, "h_lg": 44, "icon": 38, "nav": 42}


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class LockBoxUI(LoginViewMixin):
    def __init__(self):
        self.vault = Vault(str(VAULT_FILE))
        self.qr_share = QRShare()
        self.app = ctk.CTk()
        self.logo_photo = None
        self.sidebar_collapsed = False
        self.sidebar_hover_peek = False
        self.SIDEBAR_WIDTH = 280
        self.SIDEBAR_COLLAPSED_WIDTH = 76

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
        self.app.geometry("1280x820")
        self.app.minsize(1100, 720)

        self.current_category = "passwords"
        self.clipboard_timer = None
        self.auto_lock_timer = None
        self.sort_by = "created_desc"
        self.search_var = None

        # Load saved settings (theme, accent color)
        self._load_settings()

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

    def _load_settings(self):
        """Load saved settings from config file"""
        import json
        from app.constants import CONFIG_FILE, COLORS, DARK_THEME, LIGHT_THEME

        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    settings = json.load(f)

                # Apply saved theme
                saved_theme = settings.get("theme", "dark")
                if saved_theme == "light":
                    theme_colors = LIGHT_THEME
                else:
                    theme_colors = DARK_THEME

                for key, value in theme_colors.items():
                    COLORS[key] = value

                # Apply saved accent color
                saved_accent = settings.get("accent_color")
                if saved_accent:
                    COLORS["accent"] = saved_accent
                    COLORS["accent_hover"] = self._darken_color(saved_accent)
                    COLORS["accent_soft"] = self._soften_color(saved_accent)

                # Set customtkinter appearance mode
                ctk.set_appearance_mode(saved_theme)
        except Exception as e:
            print(f"Could not load settings: {e}")

    def _save_settings(self, theme=None, accent_color=None):
        """Save settings to config file"""
        import json
        from app.constants import CONFIG_FILE, DATA_DIR

        try:
            # Ensure data directory exists
            DATA_DIR.mkdir(parents=True, exist_ok=True)

            # Load existing settings or create new
            settings = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    settings = json.load(f)

            # Update with new values
            if theme is not None:
                settings["theme"] = theme.lower()
            if accent_color is not None:
                settings["accent_color"] = accent_color

            # Save
            with open(CONFIG_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Could not save settings: {e}")

    def setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts"""
        self.app.bind(
            "<Control-l>",
            lambda e: (
                self.lock_vault()
                if hasattr(self, "vault") and not self.vault.is_locked
                else None
            ),
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
            lambda e: (
                self.show_backup_dialog()
                if hasattr(self, "vault") and not self.vault.is_locked
                else None
            ),
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

    def show_login(self):
        """Display login screen with recovery option"""
        return LoginViewMixin.show_login(self)

    def show_new_vault_creation_flow(self, first_password):
        """COMPLETE vault creation flow - CANNOT be interrupted"""
        return LoginViewMixin.show_new_vault_creation_flow(self, first_password)

    def show_new_vault_setup(self, first_password):
        """Setup dialog for NEW vault creation with password confirmation"""
        return LoginViewMixin.show_new_vault_setup(self, first_password)

    def show_vault(self):
        """Display main vault interface"""
        self.clear()
        self.start_auto_lock_timer()

        # Root container
        main = ctk.CTkFrame(self.app, fg_color=COLORS["bg_primary"])
        main.pack(fill="both", expand=True)

        # ─────────────────────────────────────────────────────────────
        # SIDEBAR
        # ─────────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(
            main,
            fg_color=COLORS["bg_secondary"],
            width=SIDEBAR_WIDTH,
            corner_radius=0,
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        # Sidebar header
        sb_header = ctk.CTkFrame(sidebar, fg_color="transparent", height=56)
        sb_header.pack(fill="x", padx=SP["md"], pady=(SP["xl"], SP["md"]))
        sb_header.pack_propagate(False)

        self.sidebar_logo_label = ctk.CTkLabel(
            sb_header,
            text="LockBox",
            font=FONT["h1"],
            text_color=COLORS["text_primary"],
        )
        self.sidebar_logo_label.pack(side="left", anchor="w")

        self.sidebar_toggle_btn = ctk.CTkButton(
            sb_header,
            text="◀",
            width=CTL["icon"],
            height=CTL["icon"],
            font=("Segoe UI", 14),
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
            command=self.toggle_sidebar,
        )
        self.sidebar_toggle_btn.pack(side="right")

        # Category navigation
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=SP["md"], pady=(SP["sm"], 0))

        categories = [
            ("Passwords", "passwords", "🔑"),
            ("API Keys", "api_keys", "🔐"),
            ("Notes", "notes", "📝"),
            ("SSH Keys", "ssh_keys", "🗝"),
            ("2FA Codes", "totp_codes", "📱"),
            ("Files", "files", "📄"),
            ("Folders", "encrypted_folders", "📁"),
        ]

        self.category_buttons = {}
        for label, cat, icon in categories:
            is_active = cat == self.current_category
            # Use accent color directly for active items for better visibility
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}    {label}",
                width=SIDEBAR_WIDTH - SP["md"] * 2,
                height=CTL["nav"],
                font=FONT["nav"],
                fg_color=COLORS["accent"] if is_active else "transparent",
                hover_color=COLORS["bg_hover"],
                text_color="#ffffff" if is_active else COLORS["text_secondary"],
                anchor="w",
                corner_radius=RAD["md"],
                command=lambda c=cat: self.switch_category(c),
            )
            btn.pack(pady=3)
            btn._full_text = f"  {icon}    {label}"
            btn._icon_text = icon
            self.category_buttons[cat] = btn

        # Divider
        ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=SP["lg"], pady=SP["lg"]
        )

        # Tools section
        self.tools_label = ctk.CTkLabel(
            sidebar,
            text="TOOLS",
            font=FONT["small"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.tools_label.pack(fill="x", padx=SP["xl"], pady=(0, SP["sm"]))

        tool_items = [
            ("Security", "security", "📊"),
            ("Bulk Delete", "bulk_delete", "🗑"),
        ]
        for label, cat, icon in tool_items:
            is_active = cat == self.current_category
            # Use accent color directly for active items for better visibility
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {icon}    {label}",
                width=SIDEBAR_WIDTH - SP["md"] * 2,
                height=CTL["nav"],
                font=FONT["nav"],
                fg_color=COLORS["accent"] if is_active else "transparent",
                hover_color=COLORS["bg_hover"],
                text_color="#ffffff" if is_active else COLORS["text_secondary"],
                anchor="w",
                corner_radius=RAD["md"],
                command=lambda c=cat: self.switch_category(c),
            )
            btn.pack(pady=3, padx=SP["md"])
            btn._full_text = f"  {icon}    {label}"
            btn._icon_text = icon
            self.category_buttons[cat] = btn

        # Spacer
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Bottom actions
        self.utility_buttons = []

        bottom_actions = [
            ("Backup", self.show_backup_dialog, "💾"),
            ("Restore", self.show_restore_dialog, "📥"),
            ("Settings", self.show_settings_page, "⚙"),
        ]
        for label, cmd, icon in bottom_actions:
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {icon}    {label}",
                width=SIDEBAR_WIDTH - SP["md"] * 2,
                height=CTL["nav"],
                font=FONT["nav"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                anchor="w",
                corner_radius=RAD["md"],
                command=cmd,
            )
            btn.pack(pady=3, padx=SP["md"])
            btn._full_text = f"  {icon}    {label}"
            btn._icon_text = icon
            self.utility_buttons.append(btn)

        # Lock button
        lock_btn = ctk.CTkButton(
            sidebar,
            text="Lock Vault",
            width=SIDEBAR_WIDTH - SP["lg"] * 2,
            height=CTL["h_lg"],
            font=FONT["button"],
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            text_color="#ffffff",
            corner_radius=RAD["md"],
            command=self.lock_vault,
        )
        lock_btn.pack(pady=(SP["md"], SP["xl"]), padx=SP["lg"])
        lock_btn._full_text = "Lock Vault"
        lock_btn._icon_text = "🔒"
        self.utility_buttons.append(lock_btn)

        # ─────────────────────────────────────────────────────────────
        # CONTENT AREA
        # ─────────────────────────────────────────────────────────────
        self.content_area = ctk.CTkFrame(
            main, fg_color=COLORS["bg_primary"], corner_radius=0
        )
        self.content_area.pack(side="right", fill="both", expand=True)

        self.search_var = None
        self.display_category()
        self._apply_sidebar_state()

    def switch_category(self, category):
        """Switch between categories"""
        self.reset_activity()
        if self.current_category == category:
            return

        # Ensure sidebar state remains consistent
        self._apply_sidebar_state()

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
            is_active = c == self.current_category
            btn.configure(
                fg_color=COLORS["accent"] if is_active else "transparent",
                text_color=(
                    "#ffffff" if is_active else COLORS["text_secondary"]
                ),
            )

        self.app.update_idletasks()
        self.display_category()

    def display_category(self):
        """Display content for current category"""
        self.content_area.update_idletasks()

        for widget in self.content_area.winfo_children():
            widget.destroy()

        # Content wrapper with padding
        wrapper = ctk.CTkFrame(self.content_area, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=SP["2xl"], pady=SP["xl"])

        # ─────────────────────────────────────────────────────────────
        # HEADER BAR
        # ─────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(wrapper, fg_color="transparent", height=48)
        header.pack(fill="x", pady=(0, SP["lg"]))
        header.pack_propagate(False)

        category_labels = {
            "passwords": "Passwords",
            "api_keys": "API Keys",
            "notes": "Notes",
            "ssh_keys": "SSH Keys",
            "totp_codes": "2FA Codes",
            "files": "Files",
            "encrypted_folders": "Folders",
            "security": "Security",
            "bulk_delete": "Bulk Delete",
        }

        ctk.CTkLabel(
            header,
            text=category_labels.get(self.current_category, "Vault"),
            font=FONT["h2"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", anchor="w")

        # Right-side actions
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        if self.current_category not in ["security", "bulk_delete"]:
            # Search entry (always visible, inline)
            if hasattr(self, "search_var") and self.search_var is not None:
                try:
                    for trace in self.search_var.trace_info():
                        self.search_var.trace_remove(trace[0], trace[1])
                except:
                    pass
            self.search_var = tk.StringVar()

            # Search icon button (collapsed state)
            self.search_expanded = False

            self.search_container = ctk.CTkFrame(
                actions,
                fg_color="transparent",
            )
            self.search_container.pack(side="left", padx=(0, SP["sm"]))

            self.search_icon_btn = ctk.CTkButton(
                self.search_container,
                text="🔍",
                width=CTL["h"],
                height=CTL["h"],
                font=("Segoe UI", 14),
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["md"],
                command=self.toggle_search,
            )
            self.search_icon_btn.pack(side="left")

            # Search frame (expanded state - hidden initially)
            self.search_frame = ctk.CTkFrame(
                self.search_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["accent"],
            )

            # Search icon inside expanded frame
            self.search_icon_label = ctk.CTkLabel(
                self.search_frame,
                text="🔍",
                font=("Segoe UI", 14),
                text_color=COLORS["text_muted"],
            )

            self.search_entry = ctk.CTkEntry(
                self.search_frame,
                textvariable=self.search_var,
                width=180,
                height=CTL["h"] - 4,
                placeholder_text="Search...",
                placeholder_text_color=COLORS["text_muted"],
                font=FONT["body"],
                text_color=COLORS["text_primary"],
                border_width=0,
                fg_color="transparent",
            )
            self.search_entry.bind("<KeyRelease>", lambda e: self.on_search_change())
            self.search_entry.bind("<Escape>", lambda e: self.force_collapse_search())

            # Close button for search
            self.search_close_btn = ctk.CTkButton(
                self.search_frame,
                text="✕",
                width=28,
                height=28,
                font=("Segoe UI", 12),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                corner_radius=RAD["sm"],
                command=self.force_collapse_search,
            )

            # Sort dropdown
            sort_options = ["Newest", "Oldest", "A-Z", "Z-A", "Modified"]
            self.sort_dropdown = ctk.CTkOptionMenu(
                actions,
                values=sort_options,
                width=100,
                height=CTL["h"],
                font=FONT["body"],
                dropdown_font=FONT["body"],
                fg_color=COLORS["bg_card"],
                button_color=COLORS["bg_hover"],
                button_hover_color=COLORS["accent"],
                corner_radius=RAD["md"],
                command=self.change_sort,
            )
            self.sort_dropdown.set("Newest")
            self.sort_dropdown.pack(side="left", padx=(0, SP["sm"]))

            # Add button
            ctk.CTkButton(
                actions,
                text="+ Add",
                width=80,
                height=CTL["h"],
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["md"],
                command=self.show_add_dialog,
            ).pack(side="left")

        # ─────────────────────────────────────────────────────────────
        # ITEMS LIST
        # ─────────────────────────────────────────────────────────────
        if self.current_category in ["bulk_delete"]:
            self.items_container = ctk.CTkFrame(wrapper, fg_color="transparent")
        else:
            self.items_container = ctk.CTkScrollableFrame(
                wrapper,
                fg_color="transparent",
                scrollbar_button_color=COLORS["bg_hover"],
                scrollbar_button_hover_color=COLORS["accent"],
            )

        self.items_container.pack(fill="both", expand=True)
        self._content_max = wrapper
        self.display_items()

    def toggle_sidebar(self):
        """Collapse/expand sidebar manually."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.sidebar_hover_peek = False
        self._apply_sidebar_state()

    def _on_sidebar_enter(self, _event=None):
        """Hover peek disabled; keep sidebar stable."""
        return

    def _on_sidebar_leave(self, _event=None):
        """Hover peek disabled; keep sidebar stable."""
        return

    def _apply_sidebar_state(self, peek=False):
        """Apply current sidebar sizing and button text modes."""
        if not hasattr(self, "sidebar"):
            return

        collapsed = self.sidebar_collapsed and not peek
        width = SIDEBAR_COLLAPSED_WIDTH if collapsed else SIDEBAR_WIDTH
        try:
            self.sidebar.configure(width=width)
        except Exception:
            pass

        if hasattr(self, "sidebar_toggle_btn"):
            self.sidebar_toggle_btn.configure(text="▶" if collapsed else "◀")

        # Show/hide logo text
        if hasattr(self, "sidebar_logo_label"):
            self.sidebar_logo_label.configure(text="" if collapsed else "LockBox")

        # Show/hide tools label
        if hasattr(self, "tools_label"):
            self.tools_label.configure(text="" if collapsed else "TOOLS")

        # Update category buttons
        for btn in getattr(self, "category_buttons", {}).values():
            if not hasattr(btn, "_full_text"):
                continue
            btn.configure(
                text=btn._icon_text if collapsed else btn._full_text,
                anchor="center" if collapsed else "w",
                width=(
                    SIDEBAR_COLLAPSED_WIDTH - SP["md"] * 2
                    if collapsed
                    else SIDEBAR_WIDTH - SP["md"] * 2
                ),
            )

        # Update utility buttons
        for btn in getattr(self, "utility_buttons", []):
            if not hasattr(btn, "_full_text"):
                continue
            btn.configure(
                text=btn._icon_text if collapsed else btn._full_text,
                anchor="center" if collapsed else "w",
                width=(
                    SIDEBAR_COLLAPSED_WIDTH - SP["md"] * 2
                    if collapsed
                    else SIDEBAR_WIDTH - SP["md"] * 2
                ),
            )

    def change_sort(self, choice):
        """Handle sort option change"""
        self.reset_activity()

        sort_map = {
            "Newest": "created_desc",
            "Oldest": "created_asc",
            "A-Z": "name_asc",
            "Z-A": "name_desc",
            "Modified": "modified_desc",
        }

        self.sort_by = sort_map.get(choice, "created_desc")
        # Defer refresh to avoid layout glitch
        self.app.after(10, self.display_items)

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
        """Close and clear search"""
        if hasattr(self, "search_var") and self.search_var:
            self.search_var.set("")
        self.display_items()

    def display_items(self):
        """Display items for current category"""
        # Hide container during rebuild to prevent flicker
        if hasattr(self, "items_container"):
            try:
                self.items_container.pack_forget()
            except:
                pass

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
            # Pack items_container back after adding content
            if hasattr(self, "items_container"):
                self.items_container.update_idletasks()
                self.items_container.pack(fill="both", expand=True)
            return
        elif self.current_category == "bulk_delete":  # NEW
            self.display_bulk_delete()
            # Pack items_container back after adding content
            if hasattr(self, "items_container"):
                self.items_container.update_idletasks()
                self.items_container.pack(fill="both", expand=True)
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

        if not items and self.current_category not in ["security", "totp_codes"]:
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

        # Show container after rebuild is complete
        if hasattr(self, "items_container"):
            # Force all widget rendering to complete before displaying
            self.items_container.update_idletasks()
            self.items_container.pack(fill="both", expand=True)

    def toggle_search(self):
        """Toggle search bar between icon and expanded state"""
        if self.search_expanded:
            self.collapse_search()
        else:
            self.expand_search()

    def expand_search(self):
        """Expand the search bar"""
        if self.search_expanded:
            return
        self.search_expanded = True
        self.search_icon_btn.pack_forget()
        self.search_frame.pack(side="left")
        self.search_icon_label.pack(side="left", padx=(SP["sm"], 0))
        self.search_entry.pack(side="left", padx=(4, 0), pady=2)
        self.search_close_btn.pack(side="left", padx=(0, SP["xs"]))
        self.search_entry.focus_set()

    def collapse_search(self):
        """Collapse the search bar back to icon"""
        if not self.search_expanded:
            return
        # Only collapse if search is empty
        if self.search_var.get().strip():
            return
        self.search_expanded = False
        self.search_close_btn.pack_forget()
        self.search_entry.pack_forget()
        self.search_icon_label.pack_forget()
        self.search_frame.pack_forget()
        self.search_icon_btn.pack(side="left")

    def force_collapse_search(self):
        """Force collapse the search bar, clearing any text"""
        if not self.search_expanded:
            return
        # Check if we need to refresh (only if there was search text)
        had_search_text = bool(self.search_var.get().strip())
        self.search_var.set("")  # Clear the search text
        self.search_expanded = False
        self.search_close_btn.pack_forget()
        self.search_entry.pack_forget()
        self.search_icon_label.pack_forget()
        self.search_frame.pack_forget()
        self.search_icon_btn.pack(side="left")
        # Only refresh if there was search text to clear
        if had_search_text:
            self.app.after(50, self.display_items)

    def check_collapse_search(self):
        """Check if we should collapse search on focus out"""
        # Don't collapse if there's text in the search
        if hasattr(self, "search_var") and self.search_var.get().strip():
            return
        # Check if focus is still within the search widgets
        try:
            focused = self.app.focus_get()
            if focused in [
                self.search_entry,
                self.search_frame,
                self.search_icon_label,
            ]:
                return
        except:
            pass
        self.collapse_search()

    def on_search_change(self):
        """Handle search input changes"""
        self.reset_activity()
        if hasattr(self, "_search_timer"):
            self.app.after_cancel(self._search_timer)
        self._search_timer = self.app.after(300, self.display_items)

    def display_password_items(self, items):
        """Display password entries with professional Windows-native card design"""
        for item in items:
            # Determine security status
            password = item.get("password", "")
            strength = check_password_strength(password)
            is_weak = strength.get("score", 0) < 3
            is_old = False
            try:
                created = item.get("created", "")
                if created:
                    from datetime import datetime

                    created_date = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    )
                    is_old = (
                        datetime.now(created_date.tzinfo) - created_date
                    ).days > 365
            except:
                pass

            # Card container
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect - bind to card and all children
            def on_enter(e, c=card):
                c.configure(border_color=COLORS["accent"])

            def on_leave(e, c=card):
                c.configure(border_color=COLORS["border"])

            def bind_hover_recursive(widget, card_ref):
                """Bind hover events to widget and all its children"""
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            # Store card ref for later binding
            card._hover_bind_pending = True

            # Main content area (reduced vertical padding)
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header row: Security indicator + Title + Favorite
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            # Security health indicator (left dot)
            if is_weak:
                indicator_color = COLORS["danger"]
            elif is_old:
                indicator_color = COLORS["warning"]
            else:
                indicator_color = COLORS["success"]

            indicator = ctk.CTkFrame(
                header,
                width=8,
                height=8,
                corner_radius=4,
                fg_color=indicator_color,
            )
            indicator.pack(side="left", padx=(0, SP["sm"]))
            indicator.pack_propagate(False)

            # Title
            title = item.get("title", "Untitled")
            ctk.CTkLabel(
                header,
                text=title,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Favorite star
            if item.get("favorite"):
                ctk.CTkLabel(
                    header,
                    text="★",
                    font=FONT["body"],
                    text_color=COLORS["warning"],
                ).pack(side="left", padx=(SP["sm"], 0))

            # Metadata row (display-only username, clickable URL)
            meta = ctk.CTkFrame(content, fg_color="transparent")
            meta.pack(fill="x", pady=(SP["xs"], 0))

            username = item.get("username", "")
            url = item.get("url", "")

            # Username with label
            if username:
                ctk.CTkLabel(
                    meta,
                    text="👤",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")
                ctk.CTkLabel(
                    meta,
                    text=username,
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left", padx=(4, 0))

            if username and url:
                ctk.CTkLabel(
                    meta,
                    text="  •  ",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")

            # URL with icon (clickable)
            if url:
                ctk.CTkLabel(
                    meta,
                    text="🔗",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")
                display_url = (
                    url.replace("https://", "").replace("http://", "").rstrip("/")
                )
                if len(display_url) > 40:
                    display_url = display_url[:40] + "…"
                url_label = ctk.CTkLabel(
                    meta,
                    text=display_url,
                    font=FONT["small"],
                    text_color=COLORS["accent"],
                    cursor="hand2",
                )
                url_label.pack(side="left", padx=(4, 0))
                url_label.bind("<Button-1>", lambda e, u=url: self.open_url(u))
                url_label.bind(
                    "<Enter>",
                    lambda e, lbl=url_label: lbl.configure(
                        text_color=COLORS["accent_hover"]
                    ),
                )
                url_label.bind(
                    "<Leave>",
                    lambda e, lbl=url_label: lbl.configure(text_color=COLORS["accent"]),
                )

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # LEFT: Primary + Secondary actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            # PRIMARY: Copy Password
            ctk.CTkButton(
                left_actions,
                text="Copy Password",
                width=115,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda p=item["password"]: self.copy_to_clipboard(
                    p, "Password"
                ),
            ).pack(side="left", padx=(0, SP["sm"]))

            # SECONDARY: Edit
            ctk.CTkButton(
                left_actions,
                text="Edit",
                width=55,
                height=32,
                font=FONT["button"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=lambda i=item: self.show_edit_password(i),
            ).pack(side="left")

            # RIGHT: More menu button
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])

                # --- Quick Actions ---
                menu.add_command(
                    label="Copy Username",
                    command=lambda: self.copy_to_clipboard(
                        i.get("username", ""), "Username"
                    ),
                )
                menu.add_command(
                    label="Copy URL",
                    command=lambda: self.copy_to_clipboard(i.get("url", ""), "URL"),
                )
                menu.add_command(
                    label="Open URL in Browser",
                    command=lambda: self.open_url(i.get("url", "")),
                )

                menu.add_separator()

                # --- Security ---
                menu.add_command(
                    label="Check for Breach",
                    command=lambda: self.check_password_breach(i),
                )
                menu.add_command(
                    label="Show QR Code",
                    command=lambda: self.show_password_qr(i),
                )
                menu.add_command(
                    label="View History",
                    command=lambda: self.show_password_history(i),
                )

                menu.add_separator()

                # --- Danger Zone ---
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "password", i.get("title", "this item")
                    ),
                )

                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            more_btn = ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            )
            more_btn.pack(side="right")

            # Apply hover bindings to card and all children after card is fully built
            bind_hover_recursive(card, card)

        # Footer: Contextual security summary
        if items:
            weak_count = sum(
                1
                for i in items
                if check_password_strength(i.get("password", "")).get("score", 0) < 3
            )

            footer = ctk.CTkFrame(self.items_container, fg_color="transparent")
            footer.pack(fill="x", pady=(SP["lg"], SP["sm"]))

            if weak_count > 0:
                ctk.CTkLabel(
                    footer,
                    text=f"⚠  {weak_count} weak password{'s' if weak_count != 1 else ''} found",
                    font=FONT["small"],
                    text_color=COLORS["warning"],
                ).pack(side="left")
            else:
                ctk.CTkLabel(
                    footer,
                    text="✓  All passwords are strong",
                    font=FONT["small"],
                    text_color=COLORS["success"],
                ).pack(side="left")

            ctk.CTkLabel(
                footer,
                text=f"{len(items)} item{'s' if len(items) != 1 else ''}",
                font=FONT["small"],
                text_color=COLORS["text_muted"],
            ).pack(side="right")

    def confirm_delete_item(self, item_id, item_type, item_name):
        """Show confirmation dialog before deleting with Cancel as default"""
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Delete Password?")
        dialog.geometry("380x150")
        dialog.resizable(False, False)
        dialog.transient(self.app)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.app.winfo_x() + (self.app.winfo_width() - 380) // 2
        y = self.app.winfo_y() + (self.app.winfo_height() - 150) // 2
        dialog.geometry(f"+{x}+{y}")

        dialog.configure(fg_color=COLORS["bg_secondary"])

        # Content
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SP["xl"], pady=SP["lg"])

        # Title
        ctk.CTkLabel(
            content,
            text=f"Delete '{item_name}'?",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        # Message
        ctk.CTkLabel(
            content,
            text="This action cannot be undone.",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(SP["xs"], 0))

        # Buttons (right-aligned)
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(SP["lg"], 0))

        def do_cancel():
            dialog.destroy()

        def do_delete():
            dialog.destroy()
            self.delete_item(item_id, item_type)

        # Cancel button (default, on right)
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=90,
            height=32,
            font=FONT["button"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=RAD["sm"],
            command=do_cancel,
        )
        cancel_btn.pack(side="right")
        cancel_btn.focus_set()

        # Delete button (red, destructive)
        ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=90,
            height=32,
            font=FONT["button"],
            fg_color=COLORS["danger"],
            hover_color="#b91c1c",
            text_color="#ffffff",
            corner_radius=RAD["sm"],
            command=do_delete,
        ).pack(side="right", padx=(0, SP["sm"]))

        # Keyboard bindings
        dialog.bind("<Escape>", lambda e: do_cancel())
        dialog.bind("<Return>", lambda e: do_cancel())  # Enter = Cancel (safe default)

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
        """Display API key entries with professional card design"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect helper
            def bind_hover_recursive(widget, card_ref):
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: Title + Favorite
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            # Service name as title
            service = item.get("service", "Untitled")
            ctk.CTkLabel(
                header,
                text=service,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Metadata row
            meta = ctk.CTkFrame(content, fg_color="transparent")
            meta.pack(fill="x", pady=(SP["xs"], 0))

            # Description with icon
            if item.get("description"):
                ctk.CTkLabel(
                    meta,
                    text="📝",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")
                ctk.CTkLabel(
                    meta,
                    text=item["description"][:50]
                    + ("…" if len(item.get("description", "")) > 50 else ""),
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left", padx=(4, 0))

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="Copy API Key",
                width=100,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda k=item["key"]: self.copy_to_clipboard(k, "API Key"),
            ).pack(side="left", padx=(0, SP["sm"]))

            ctk.CTkButton(
                left_actions,
                text="Edit",
                width=55,
                height=32,
                font=FONT["button"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=lambda i=item: self.show_edit_api_key(i),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Show QR Code", command=lambda: self.show_api_key_qr(i)
                )
                menu.add_separator()
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "api_key", i.get("service", "this item")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)
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
        """Display secure notes with professional card design"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect helper
            def bind_hover_recursive(widget, card_ref):
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: Title
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            # Note icon
            ctk.CTkLabel(
                header,
                text="📄",
                font=FONT["body"],
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, SP["xs"]))

            title = item.get("title", "Untitled")
            ctk.CTkLabel(
                header,
                text=title,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Preview row
            meta = ctk.CTkFrame(content, fg_color="transparent")
            meta.pack(fill="x", pady=(SP["xs"], 0))

            preview = item.get("content", "")
            if len(preview) > 80:
                preview = preview[:80] + "…"
            if preview:
                ctk.CTkLabel(
                    meta,
                    text=preview,
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="View Note",
                width=85,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda n=item: self.view_note(n),
            ).pack(side="left", padx=(0, SP["sm"]))

            ctk.CTkButton(
                left_actions,
                text="Edit",
                width=55,
                height=32,
                font=FONT["button"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=lambda i=item: self.show_edit_note(i),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Copy Content",
                    command=lambda: self.copy_to_clipboard(
                        i.get("content", ""), "Note"
                    ),
                )
                menu.add_command(
                    label="Show QR Code", command=lambda: self.show_note_qr(i)
                )
                menu.add_separator()
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "note", i.get("title", "this item")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)

    def display_ssh_key_items(self, items):
        """Display SSH keys with professional card design"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect helper
            def bind_hover_recursive(widget, card_ref):
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: Key icon + Title
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            ctk.CTkLabel(
                header,
                text="🔑",
                font=FONT["body"],
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, SP["xs"]))

            name = item.get("name", "Untitled")
            ctk.CTkLabel(
                header,
                text=name,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="Copy Private",
                width=100,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda k=item["private_key"]: self.copy_to_clipboard(
                    k, "SSH Key"
                ),
            ).pack(side="left", padx=(0, SP["sm"]))

            if item.get("public_key"):
                ctk.CTkButton(
                    left_actions,
                    text="Copy Public",
                    width=100,
                    height=32,
                    font=FONT["button"],
                    fg_color="transparent",
                    hover_color=COLORS["bg_hover"],
                    text_color=COLORS["text_secondary"],
                    border_width=1,
                    border_color=COLORS["border"],
                    corner_radius=RAD["sm"],
                    command=lambda k=item["public_key"]: self.copy_to_clipboard(
                        k, "Public Key"
                    ),
                ).pack(side="left", padx=(0, SP["sm"]))

            ctk.CTkButton(
                left_actions,
                text="Edit",
                width=55,
                height=32,
                font=FONT["button"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=lambda i=item: self.show_edit_ssh_key(i),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Show QR Code", command=lambda: self.show_ssh_key_qr(i)
                )
                menu.add_separator()
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "ssh_key", i.get("name", "this item")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)

    def display_file_items(self, items):
        """Display encrypted files with professional card design"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect helper
            def bind_hover_recursive(widget, card_ref):
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: File icon + Filename + Size
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            ctk.CTkLabel(
                header,
                text="📁",
                font=FONT["body"],
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, SP["xs"]))

            filename = item.get("filename", "Untitled")
            ctk.CTkLabel(
                header,
                text=filename,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Size info on right
            size_kb = item.get("size", 0) / 1024
            size_text = (
                f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            )
            ctk.CTkLabel(
                header,
                text=size_text,
                font=FONT["small"],
                text_color=COLORS["text_muted"],
            ).pack(side="right")

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="Export File",
                width=90,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda i=item["id"], n=item["filename"]: self.export_file(i, n),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "file", i.get("filename", "this file")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)

    def display_encrypted_folder_items(self, items):
        """Display folder metadata with professional card design"""
        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            # Hover effect helper
            def bind_hover_recursive(widget, card_ref):
                widget.bind(
                    "<Enter>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
                )
                for child in widget.winfo_children():
                    bind_hover_recursive(child, card_ref)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: Folder icon + Name + Lock icon if protected
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            ctk.CTkLabel(
                header,
                text="📂",
                font=FONT["body"],
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, SP["xs"]))

            folder_name = item.get("folder_name", "Untitled")
            ctk.CTkLabel(
                header,
                text=folder_name,
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            if item.get("zip_password"):
                ctk.CTkLabel(
                    header,
                    text="🔒",
                    font=FONT["body"],
                    text_color=COLORS["success"],
                ).pack(side="left", padx=(SP["xs"], 0))

            # Size/count info on right
            size_mb = item.get("size", 0) / (1024 * 1024)
            file_count = item.get("file_count", 0)
            ctk.CTkLabel(
                header,
                text=f"{file_count} files · {size_mb:.1f} MB",
                font=FONT["small"],
                text_color=COLORS["text_muted"],
            ).pack(side="right")

            # Description row
            if item.get("description"):
                meta = ctk.CTkFrame(content, fg_color="transparent")
                meta.pack(fill="x", pady=(SP["xs"], 0))
                ctk.CTkLabel(
                    meta,
                    text=item["description"][:60]
                    + ("…" if len(item.get("description", "")) > 60 else ""),
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left")

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="Download",
                width=90,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda i=item["id"], n=item[
                    "folder_name"
                ]: self.download_folder_zip(i, n),
            ).pack(side="left", padx=(0, SP["sm"]))

            ctk.CTkButton(
                left_actions,
                text="Set Password",
                width=100,
                height=32,
                font=FONT["button"],
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=lambda i=item["id"]: self.set_folder_password(i),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "encrypted_folder", i.get("folder_name", "this folder")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)

    def display_security_dashboard(self):
        """Display comprehensive security dashboard with professional design"""
        report = self.vault.get_security_report()

        # Stats cards row
        stats_row = ctk.CTkFrame(self.items_container, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, SP["lg"]))

        # Create 4 stat cards
        stat_data = [
            {
                "value": str(report["total_passwords"]),
                "label": "Total",
                "icon": "📊",
                "color": COLORS["accent"],
            },
            {
                "value": str(len(report["weak_passwords"])),
                "label": "Weak",
                "icon": "⚠️",
                "color": (
                    COLORS["danger"]
                    if len(report["weak_passwords"]) > 0
                    else COLORS["success"]
                ),
            },
            {
                "value": str(len(report["reused_passwords"])),
                "label": "Reused",
                "icon": "🔄",
                "color": (
                    COLORS["danger"]
                    if len(report["reused_passwords"]) > 0
                    else COLORS["success"]
                ),
            },
            {
                "value": str(len(report["old_passwords"])),
                "label": "Old (1yr+)",
                "icon": "📅",
                "color": (
                    COLORS["warning"]
                    if len(report["old_passwords"]) > 0
                    else COLORS["success"]
                ),
            },
        ]

        for stat in stat_data:
            card = ctk.CTkFrame(
                stats_row,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(side="left", fill="both", expand=True, padx=SP["xs"])

            ctk.CTkLabel(
                card,
                text=stat["value"],
                font=("Segoe UI", 32, "bold"),
                text_color=stat["color"],
            ).pack(pady=(SP["lg"], SP["xs"]))

            ctk.CTkLabel(
                card,
                text=f"{stat['icon']} {stat['label']}",
                font=FONT["body"],
                text_color=COLORS["text_secondary"],
            ).pack(pady=(0, SP["lg"]))

        # Average strength card
        strength_card = ctk.CTkFrame(
            self.items_container,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        strength_card.pack(fill="x", pady=(0, SP["lg"]))

        strength_content = ctk.CTkFrame(strength_card, fg_color="transparent")
        strength_content.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        avg_strength = int(report["average_strength"])
        if avg_strength >= 80:
            strength_text, strength_color = "Excellent", COLORS["success"]
        elif avg_strength >= 60:
            strength_text, strength_color = "Good", COLORS["accent"]
        elif avg_strength >= 40:
            strength_text, strength_color = "Fair", COLORS["warning"]
        else:
            strength_text, strength_color = "Weak", COLORS["danger"]

        ctk.CTkLabel(
            strength_content,
            text="💪 Average Password Strength",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        ctk.CTkLabel(
            strength_content,
            text=f"{avg_strength}% - {strength_text}",
            font=("Segoe UI", 18, "bold"),
            text_color=strength_color,
        ).pack(side="right")

        # Hint text for improving security
        weak_count = len(report["weak_passwords"])
        reused_count = len(report["reused_passwords"])
        old_count = len(report["old_passwords"])

        hint_parts = []
        if weak_count > 0:
            hint_parts.append(
                f"Fix {weak_count} weak password{'s' if weak_count != 1 else ''}"
            )
        if reused_count > 0:
            hint_parts.append(
                f"change {reused_count} reused password{'s' if reused_count != 1 else ''}"
            )
        if old_count > 0:
            hint_parts.append(
                f"refresh {old_count} old password{'s' if old_count != 1 else ''}"
            )

        if hint_parts:
            hint_text = " • ".join(hint_parts) + " to improve security"
            hint_frame = ctk.CTkFrame(strength_card, fg_color="transparent")
            hint_frame.pack(fill="x", padx=SP["lg"], pady=(0, SP["md"]))
            ctk.CTkLabel(
                hint_frame,
                text=f"💡 {hint_text}",
                font=FONT["small"],
                text_color=COLORS["text_muted"],
            ).pack(anchor="w")

        # Content container for sections
        content_container = ctk.CTkFrame(self.items_container, fg_color="transparent")
        content_container.pack(fill="both", expand=True)

        # Weak passwords section
        if report["weak_passwords"]:
            weak_section = ctk.CTkFrame(
                content_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            weak_section.pack(fill="x", pady=(0, SP["sm"]))

            weak_header = ctk.CTkFrame(weak_section, fg_color="transparent")
            weak_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

            ctk.CTkLabel(
                weak_header,
                text=f"⚠️ Weak Passwords ({weak_count})",
                font=FONT["h3"],
                text_color=COLORS["danger"],
            ).pack(side="left")

            for pwd in report["weak_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    weak_section,
                    fg_color=COLORS["bg_hover"],
                    corner_radius=RAD["sm"],
                )
                item_row.pack(fill="x", padx=SP["lg"], pady=(0, SP["xs"]))

                item_content = ctk.CTkFrame(item_row, fg_color="transparent")
                item_content.pack(fill="x", padx=SP["md"], pady=SP["sm"])

                # Red accent bar on the left for weak passwords
                accent_bar = ctk.CTkFrame(
                    item_content,
                    width=3,
                    height=20,
                    corner_radius=2,
                    fg_color=COLORS["danger"],
                )
                accent_bar.pack(side="left", padx=(0, SP["sm"]))
                accent_bar.pack_propagate(False)

                # Warning icon
                ctk.CTkLabel(
                    item_content,
                    text="⚠",
                    font=FONT["small"],
                    text_color=COLORS["danger"],
                ).pack(side="left", padx=(0, SP["xs"]))

                ctk.CTkLabel(
                    item_content,
                    text=pwd["title"],
                    font=FONT["body"],
                    text_color=COLORS["text_primary"],
                ).pack(side="left")

                ctk.CTkLabel(
                    item_content,
                    text=f"Strength: {pwd['score']}%",
                    font=FONT["small"],
                    text_color=COLORS["danger"],
                ).pack(side="right")

            if weak_count > 5:
                ctk.CTkLabel(
                    weak_section,
                    text=f"+ {weak_count - 5} more",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(anchor="w", padx=SP["lg"], pady=(SP["xs"], SP["md"]))
            else:
                ctk.CTkFrame(
                    weak_section, height=SP["sm"], fg_color="transparent"
                ).pack()

        # Reused passwords section
        if report["reused_passwords"]:
            reused_section = ctk.CTkFrame(
                content_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            reused_section.pack(fill="x", pady=(0, SP["sm"]))

            reused_header = ctk.CTkFrame(reused_section, fg_color="transparent")
            reused_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

            ctk.CTkLabel(
                reused_header,
                text=f"🔄 Reused Passwords ({reused_count})",
                font=FONT["h3"],
                text_color=COLORS["warning"],
            ).pack(side="left")

            for reused in report["reused_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    reused_section,
                    fg_color=COLORS["bg_hover"],
                    corner_radius=RAD["sm"],
                )
                item_row.pack(fill="x", padx=SP["lg"], pady=(0, SP["xs"]))

                item_content = ctk.CTkFrame(item_row, fg_color="transparent")
                item_content.pack(fill="x", padx=SP["md"], pady=SP["sm"])

                used_in_text = ", ".join(reused["used_in"][:3])
                if len(reused["used_in"]) > 3:
                    used_in_text += f" +{len(reused['used_in']) - 3} more"

                ctk.CTkLabel(
                    item_content,
                    text=f"Used in: {used_in_text}",
                    font=FONT["body"],
                    text_color=COLORS["text_primary"],
                ).pack(side="left")

            if reused_count > 5:
                ctk.CTkLabel(
                    reused_section,
                    text=f"+ {reused_count - 5} more",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(anchor="w", padx=SP["lg"], pady=(SP["xs"], SP["md"]))
            else:
                ctk.CTkFrame(
                    reused_section, height=SP["sm"], fg_color="transparent"
                ).pack()

        # Old passwords section
        if report["old_passwords"]:
            old_section = ctk.CTkFrame(
                content_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            old_section.pack(fill="x", pady=(0, SP["sm"]))

            old_header = ctk.CTkFrame(old_section, fg_color="transparent")
            old_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

            ctk.CTkLabel(
                old_header,
                text=f"📅 Old Passwords ({old_count})",
                font=FONT["h3"],
                text_color=COLORS["warning"],
            ).pack(side="left")

            for old in report["old_passwords"][:5]:
                item_row = ctk.CTkFrame(
                    old_section,
                    fg_color=COLORS["bg_hover"],
                    corner_radius=RAD["sm"],
                )
                item_row.pack(fill="x", padx=SP["lg"], pady=(0, SP["xs"]))

                item_content = ctk.CTkFrame(item_row, fg_color="transparent")
                item_content.pack(fill="x", padx=SP["md"], pady=SP["sm"])

                ctk.CTkLabel(
                    item_content,
                    text=old["title"],
                    font=FONT["body"],
                    text_color=COLORS["text_primary"],
                ).pack(side="left")

                ctk.CTkLabel(
                    item_content,
                    text=f"{old['age_days']} days old",
                    font=FONT["small"],
                    text_color=COLORS["warning"],
                ).pack(side="right")

            if old_count > 5:
                ctk.CTkLabel(
                    old_section,
                    text=f"+ {old_count - 5} more",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(anchor="w", padx=SP["lg"], pady=(SP["xs"], SP["md"]))
            else:
                ctk.CTkFrame(
                    old_section, height=SP["sm"], fg_color="transparent"
                ).pack()

        # Security Recommendations
        rec_section = ctk.CTkFrame(
            content_container,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        rec_section.pack(fill="x", pady=(SP["md"], SP["lg"]))

        rec_header = ctk.CTkFrame(rec_section, fg_color="transparent")
        rec_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        ctk.CTkLabel(
            rec_header,
            text="💡 Security Recommendations",
            font=FONT["h3"],
            text_color=COLORS["accent"],
        ).pack(side="left")

        tips = []
        if weak_count > 0:
            tips.append(
                (
                    "⚠️",
                    f"Update {weak_count} weak password(s) with stronger alternatives",
                    COLORS["danger"],
                )
            )
        if reused_count > 0:
            tips.append(
                (
                    "🔄",
                    f"Change {reused_count} reused password(s) to unique ones",
                    COLORS["warning"],
                )
            )
        if old_count > 0:
            tips.append(
                (
                    "📅",
                    f"Refresh {old_count} password(s) older than 1 year",
                    COLORS["warning"],
                )
            )
        if not tips:
            tips.append(
                (
                    "✅",
                    "Your password security is excellent! Keep it up.",
                    COLORS["success"],
                )
            )

        for icon, tip, color in tips:
            tip_row = ctk.CTkFrame(
                rec_section,
                fg_color=COLORS["bg_hover"],
                corner_radius=RAD["sm"],
            )
            tip_row.pack(fill="x", padx=SP["lg"], pady=(0, SP["xs"]))

            tip_content = ctk.CTkFrame(tip_row, fg_color="transparent")
            tip_content.pack(fill="x", padx=SP["md"], pady=SP["sm"])

            ctk.CTkLabel(
                tip_content,
                text=f"{icon}  {tip}",
                font=FONT["body"],
                text_color=color,
            ).pack(side="left")

        ctk.CTkFrame(rec_section, height=SP["sm"], fg_color="transparent").pack()

    def scan_all_passwords_for_breaches(self):
        """Scan all passwords for breaches"""
        from app.services.breach_service import scan_all_passwords

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
                card.pack(fill="x", pady=8, ipady=15, ipadx=10)
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
        """Display bulk delete manager with professional design"""
        for widget in self.items_container.winfo_children():
            widget.destroy()
        if not hasattr(self, "bulk_selected"):
            self.bulk_selected = []
        if not hasattr(self, "bulk_category_filter"):
            self.bulk_category_filter = "All Items"

        # Fixed header with filter controls
        fixed_header = ctk.CTkFrame(self.items_container, fg_color="transparent")
        fixed_header.pack(fill="x", pady=(0, SP["md"]))

        # Control bar with filters and delete button
        control_bar = ctk.CTkFrame(
            fixed_header,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        control_bar.pack(fill="x", pady=(0, SP["sm"]))

        control_content = ctk.CTkFrame(control_bar, fg_color="transparent")
        control_content.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        # Filter label
        ctk.CTkLabel(
            control_content,
            text="Filter:",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, SP["sm"]))

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
        if not hasattr(self, "category_pill_buttons"):
            self.category_pill_buttons = {}

        def switch_filter(category):
            self.bulk_category_filter = category
            for cat, btn in self.category_pill_buttons.items():
                is_active = cat == category
                btn.configure(
                    fg_color=COLORS["accent"] if is_active else "transparent",
                    text_color=(
                        COLORS["text_primary"]
                        if is_active
                        else COLORS["text_secondary"]
                    ),
                    border_color=(COLORS["accent"] if is_active else COLORS["border"]),
                )
            if hasattr(self, "_bulk_scroll_frame"):
                for widget in self._bulk_scroll_frame.winfo_children():
                    widget.destroy()
                self.reload_bulk_items_content()

        for label in self.filter_options:
            is_current = label == self.bulk_category_filter
            btn = ctk.CTkButton(
                control_content,
                text=label,
                width=80,
                height=CTL["h"] - 8,
                font=FONT["small"],
                fg_color=COLORS["accent"] if is_current else "transparent",
                hover_color=COLORS["accent_hover"],
                text_color=(
                    COLORS["text_primary"] if is_current else COLORS["text_secondary"]
                ),
                corner_radius=RAD["lg"],
                border_width=1,
                border_color=COLORS["accent"] if is_current else COLORS["border"],
                command=lambda c=label: switch_filter(c),
            )
            btn.pack(side="left", padx=SP["xs"] // 2)
            self.category_pill_buttons[label] = btn

        def delete_selected():
            if not self.bulk_selected:
                messagebox.showinfo("No Selection", "Please select items to delete")
                return
            count = len(self.bulk_selected)
            if not messagebox.askyesno(
                "Confirm Bulk Delete",
                f"Delete {count} item{'s' if count != 1 else ''}?\n\n⚠️ Cannot be undone!",
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
                    print(f"Delete failed {checkbox_id}: {e}")
            messagebox.showinfo("Success", f"✅ Deleted {deleted} items!")
            self.bulk_selected = []
            if hasattr(self, "_bulk_scroll_frame"):
                for widget in self._bulk_scroll_frame.winfo_children():
                    widget.destroy()
                self.reload_bulk_items_content()

        ctk.CTkButton(
            control_content,
            text="🗑️ Delete Selected",
            width=160,
            height=CTL["h"] - 4,
            font=FONT["button"],
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            corner_radius=RAD["md"],
            command=delete_selected,
        ).pack(side="right")

        # Select all bar
        select_all_frame = ctk.CTkFrame(
            fixed_header,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        select_all_frame.pack(fill="x", pady=(0, SP["sm"]))
        self._select_all_frame = select_all_frame

        # Scrollable items container
        self._bulk_scroll_frame = ctk.CTkScrollableFrame(
            self.items_container, fg_color="transparent"
        )
        self._bulk_scroll_frame.pack(fill="both", expand=True)
        self.reload_bulk_items_content()

    def reload_bulk_items_content(self):
        """Reload items in bulk delete view with professional design"""
        for widget in self._bulk_scroll_frame.winfo_children():
            widget.destroy()
        for widget in self._select_all_frame.winfo_children():
            widget.destroy()

        # Define hover effect function
        def bind_hover_recursive(widget, default_color, hover_color):
            """Bind hover effect to widget and all its children"""

            def on_enter(e):
                try:
                    widget.configure(border_color=hover_color)
                except:
                    pass

            def on_leave(e):
                try:
                    widget.configure(border_color=default_color)
                except:
                    pass

            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            for child in widget.winfo_children():
                child.bind("<Enter>", on_enter, add="+")
                child.bind("<Leave>", on_leave, add="+")

        all_items = []
        filter_choice = self.bulk_category_filter
        if filter_choice in ["All Items", "Passwords"]:
            for item in self.vault.list_passwords():
                all_items.append(
                    {
                        "category": "passwords",
                        "label": "🔒 Password",
                        "item": item,
                        "id": f"passwords:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        if filter_choice in ["All Items", "API Keys"]:
            for item in self.vault.list_api_keys():
                all_items.append(
                    {
                        "category": "api_keys",
                        "label": "🔑 API Key",
                        "item": item,
                        "id": f"api_keys:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        if filter_choice in ["All Items", "Notes"]:
            for item in self.vault.list_notes():
                all_items.append(
                    {
                        "category": "notes",
                        "label": "📝 Note",
                        "item": item,
                        "id": f"notes:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        if filter_choice in ["All Items", "SSH Keys"]:
            for item in self.vault.list_ssh_keys():
                all_items.append(
                    {
                        "category": "ssh_keys",
                        "label": "🗝️ SSH Key",
                        "item": item,
                        "id": f"ssh_keys:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        if filter_choice in ["All Items", "Files"]:
            for item in self.vault.list_files():
                all_items.append(
                    {
                        "category": "files",
                        "label": "📄 File",
                        "item": item,
                        "id": f"files:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        if filter_choice in ["All Items", "Folders"]:
            for item in self.vault.list_encrypted_folders():
                all_items.append(
                    {
                        "category": "encrypted_folders",
                        "label": "📁 Folder",
                        "item": item,
                        "id": f"encrypted_folders:{item['id']}",
                        "var": tk.BooleanVar(value=False),
                    }
                )
        all_items.sort(key=lambda x: x["item"].get("created", ""), reverse=True)

        if not all_items:
            empty_frame = ctk.CTkFrame(
                self._bulk_scroll_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            empty_frame.pack(fill="x", pady=SP["xl"])

            ctk.CTkLabel(
                empty_frame,
                text=f"No {filter_choice.lower()} found",
                font=FONT["h3"],
                text_color=COLORS["text_secondary"],
            ).pack(pady=SP["2xl"])
            return

        select_all_var = tk.BooleanVar(value=False)
        select_all_checkbox = None

        def toggle_all():
            if select_all_var.get():
                self.bulk_selected = [item["id"] for item in all_items]
                for item in all_items:
                    item["var"].set(True)
            else:
                self.bulk_selected = []
                for item in all_items:
                    item["var"].set(False)
            update_selection_count()

        def update_selection_count():
            count = len(self.bulk_selected)
            if count == 0:
                text = f"Select All ({len(all_items)} items)"
            elif count == len(all_items):
                text = f"✓ All Selected ({count} items)"
            else:
                text = f"Selected {count} of {len(all_items)} items"
            try:
                if select_all_checkbox and select_all_checkbox.winfo_exists():
                    select_all_checkbox.configure(text=text)
            except:
                pass

        select_all_content = ctk.CTkFrame(
            self._select_all_frame, fg_color="transparent"
        )
        select_all_content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

        select_all_checkbox = ctk.CTkCheckBox(
            select_all_content,
            text=f"Select All ({len(all_items)} items)",
            variable=select_all_var,
            font=FONT["body"],
            command=toggle_all,
            checkbox_width=22,
            checkbox_height=22,
        )
        select_all_checkbox.pack(side="left")

        for meta in all_items:
            item = meta["item"]
            cat = meta["category"]

            # Professional card with border
            card = ctk.CTkFrame(
                self._bulk_scroll_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=(0, SP["sm"]))

            card_content = ctk.CTkFrame(card, fg_color="transparent")
            card_content.pack(fill="x", padx=SP["lg"], pady=SP["md"])

            # Checkbox column
            def on_check(cid=meta["id"], var=meta["var"]):
                if var.get():
                    if cid not in self.bulk_selected:
                        self.bulk_selected.append(cid)
                else:
                    if cid in self.bulk_selected:
                        self.bulk_selected.remove(cid)
                update_selection_count()

            ctk.CTkCheckBox(
                card_content,
                text="",
                variable=meta["var"],
                command=on_check,
                checkbox_width=22,
                checkbox_height=22,
                width=22,
            ).pack(side="left", padx=(0, SP["md"]))

            # Category badge
            ctk.CTkLabel(
                card_content,
                text=meta["label"],
                font=FONT["small"],
                text_color="white",
                fg_color=COLORS["accent"],
                corner_radius=RAD["sm"],
                padx=SP["sm"],
                pady=SP["xs"],
            ).pack(side="left", padx=(0, SP["md"]))

            # Title
            name = (
                item.get("title")
                or item.get("service")
                or item.get("name")
                or item.get("filename")
                or item.get("folder_name")
                or "Untitled"
            )
            ctk.CTkLabel(
                card_content,
                text=name,
                font=(
                    "Segoe UI",
                    FONT["body"].cget("size") if hasattr(FONT["body"], "cget") else 14,
                    "bold",
                ),
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            # Metadata on the right
            if cat == "passwords":
                ctk.CTkLabel(
                    card_content,
                    text=f"👤 {item.get('username', 'N/A')}",
                    font=FONT["small"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="right", padx=SP["sm"])
            elif cat == "files":
                size_kb = item.get("size", 0) / 1024
                ctk.CTkLabel(
                    card_content,
                    text=f"💾 {size_kb:.1f} KB",
                    font=FONT["small"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="right", padx=SP["sm"])
            elif cat == "api_keys":
                ctk.CTkLabel(
                    card_content,
                    text=f"📝 {item.get('service', 'N/A')}",
                    font=FONT["small"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="right", padx=SP["sm"])
            elif cat == "ssh_keys":
                ctk.CTkLabel(
                    card_content,
                    text=f"🔑 {item.get('name', 'N/A')}",
                    font=FONT["small"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="right", padx=SP["sm"])
            elif cat == "encrypted_folders":
                ctk.CTkLabel(
                    card_content,
                    text=f"📊 {item.get('file_count', 0)} files",
                    font=FONT["small"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="right", padx=SP["sm"])

            # Add hover effect
            bind_hover_recursive(card, COLORS["border"], COLORS["accent"])

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

        ctk.CTkLabel(dialog, text="Edit SSH Key", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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

        ctk.CTkLabel(dialog, text="Edit SSH Key", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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

        ctk.CTkLabel(dialog, text="Edit API Key", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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

        ctk.CTkLabel(dialog, text="Add New Password", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(pady=20)

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
            fg_color=COLORS["bg_hover"],  # FIXED: Now matches other buttons
            hover_color=COLORS["border"],
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
                fg_color=COLORS["bg_hover"],  # FIXED: Now matches other buttons
                hover_color=COLORS["border"],
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
                fg_color=COLORS["bg_hover"],
                hover_color=COLORS["border"],
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

        ctk.CTkLabel(dialog, text="Add SSH Key", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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

        ctk.CTkLabel(dialog, text="Add Folder", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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

        ctk.CTkLabel(dialog, text="Edit Password", font=("Segoe UI", 20, "bold"), text_color=COLORS["text_primary"]).pack(
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
            fg_color=COLORS["bg_hover"],  # FIXED: Now matches other buttons
            hover_color=COLORS["border"],
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
                fg_color=COLORS["bg_hover"],  # FIXED: Now matches other buttons
                hover_color=COLORS["border"],
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
                fg_color=COLORS["bg_hover"],
                hover_color=COLORS["border"],
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
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border"],
            command=dialog.destroy,
        ).pack(pady=(0, 20))

    def _change_theme(self, theme_name, dialog=None):
        """Change the application theme safely"""
        try:
            # Close dialog first to prevent freezing
            if dialog:
                dialog.destroy()

            # Apply theme change after dialog is closed
            self.app.after(100, lambda: self._apply_theme(theme_name))
        except Exception as e:
            print(f"Theme change error: {e}")

    def _apply_theme(self, theme_name):
        """Apply theme change and refresh UI"""
        from app.constants import COLORS, DARK_THEME, LIGHT_THEME

        try:
            # Determine which theme to use
            if theme_name.lower() == "light":
                theme_colors = LIGHT_THEME
            elif theme_name.lower() == "dark":
                theme_colors = DARK_THEME
            else:  # System - detect system preference
                # Default to dark for now, as system detection is complex
                theme_colors = DARK_THEME

            # Update COLORS dictionary in place
            for key, value in theme_colors.items():
                COLORS[key] = value

            # Also set customtkinter appearance mode
            ctk.set_appearance_mode(theme_name.lower())

            # Save the theme preference
            self._save_settings(theme=theme_name)

            # Refresh the entire vault view
            self.show_vault()

        except Exception as e:
            print(f"Theme apply error: {e}")
            messagebox.showerror("Error", f"Failed to change theme: {e}")

    def _darken_color(self, hex_color):
        """Darken a hex color by 15%"""
        hex_color = hex_color.lstrip("#")
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _soften_color(self, hex_color):
        """Create a soft/muted version of a color for backgrounds (theme-aware)"""
        hex_color = hex_color.lstrip("#")
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        # Get current theme background for mixing
        bg_hex = COLORS.get("bg_secondary", "#1e1e1e").lstrip("#")
        bg_r = int(bg_hex[0:2], 16)
        bg_g = int(bg_hex[2:4], 16)
        bg_b = int(bg_hex[4:6], 16)
        
        # For light themes (bright backgrounds), use more color, less background
        is_light = (bg_r + bg_g + bg_b) / 3 > 128
        if is_light:
            # Light theme: subtle tint (more background, less accent)
            r = int(r * 0.15 + bg_r * 0.85)
            g = int(g * 0.15 + bg_g * 0.85)
            b = int(b * 0.15 + bg_b * 0.85)
        else:
            # Dark theme: subtle glow (more background, less accent)
            r = int(r * 0.3 + bg_r * 0.7)
            g = int(g * 0.3 + bg_g * 0.7)
            b = int(b * 0.3 + bg_b * 0.7)
        return f"#{r:02x}{g:02x}{b:02x}"

    def show_settings_page(self):
        """Display the Settings page with all configuration options"""
        self.reset_activity()

        # Create settings dialog
        dialog = self.create_dialog("Settings", 520, 620)
        dialog.configure(fg_color=COLORS["bg_primary"])

        # Main scrollable container
        main_scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_hover"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        main_scroll.pack(fill="both", expand=True, padx=SP["lg"], pady=SP["lg"])

        # Header
        ctk.CTkLabel(
            main_scroll,
            text="⚙️ Settings",
            font=FONT["h1"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, SP["lg"]))

        # ═══════════════════════════════════════════════════════════════
        # APPEARANCE SECTION
        # ═══════════════════════════════════════════════════════════════
        appearance_section = ctk.CTkFrame(
            main_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        appearance_section.pack(fill="x", pady=(0, SP["md"]))

        appearance_header = ctk.CTkFrame(appearance_section, fg_color="transparent")
        appearance_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        ctk.CTkLabel(
            appearance_header,
            text="🎨 Appearance",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        appearance_content = ctk.CTkFrame(appearance_section, fg_color="transparent")
        appearance_content.pack(fill="x", padx=SP["lg"], pady=(0, SP["md"]))

        # Theme selector
        theme_row = ctk.CTkFrame(appearance_content, fg_color="transparent")
        theme_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            theme_row,
            text="Theme",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        theme_var = ctk.StringVar(value="Dark")
        theme_menu = ctk.CTkOptionMenu(
            theme_row,
            values=["System", "Dark", "Light"],
            variable=theme_var,
            width=120,
            height=CTL["h"] - 8,
            font=FONT["body"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            text_color=COLORS["text_primary"],
            corner_radius=RAD["sm"],
            command=lambda v: self._change_theme(v, dialog),
        )
        theme_menu.pack(side="right")

        # Accent color
        accent_row = ctk.CTkFrame(appearance_content, fg_color="transparent")
        accent_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            accent_row,
            text="Accent Color",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        accent_colors = [
            ("#3b82f6", "Blue"),
            ("#22c55e", "Green"),
            ("#f59e0b", "Orange"),
            ("#ef4444", "Red"),
            ("#8b5cf6", "Purple"),
        ]
        accent_frame = ctk.CTkFrame(accent_row, fg_color="transparent")
        accent_frame.pack(side="right")

        # Track selected accent
        self._accent_buttons = []
        current_accent = COLORS.get("accent", "#3b82f6")

        def select_accent(color, btn):
            # Update COLORS dict
            COLORS["accent"] = color
            COLORS["accent_hover"] = self._darken_color(color)
            COLORS["accent_soft"] = self._soften_color(color)

            # Determine border color based on theme (dark border for light theme)
            bg_hex = COLORS.get("bg_secondary", "#1e1e1e").lstrip("#")
            is_light = (int(bg_hex[0:2], 16) + int(bg_hex[2:4], 16) + int(bg_hex[4:6], 16)) / 3 > 128
            border_color = "#333333" if is_light else "#ffffff"

            # Update button visuals to show selection
            for b in self._accent_buttons:
                b.configure(border_width=0, border_color=COLORS["bg_card"])
            btn.configure(border_width=2, border_color=border_color)

            # Save accent color preference
            self._save_settings(accent_color=color)

            # Close dialog and refresh UI
            dialog.destroy()
            self.show_vault()

        # Determine border color based on theme
        bg_hex = COLORS.get("bg_secondary", "#1e1e1e").lstrip("#")
        is_light_theme = (int(bg_hex[0:2], 16) + int(bg_hex[2:4], 16) + int(bg_hex[4:6], 16)) / 3 > 128
        selection_border = "#333333" if is_light_theme else "#ffffff"

        for color, name in accent_colors:
            is_selected = color == current_accent
            color_btn = ctk.CTkButton(
                accent_frame,
                text="",
                width=28,
                height=28,
                fg_color=color,
                hover_color=color,
                corner_radius=14,
                border_width=2 if is_selected else 0,
                border_color=selection_border if is_selected else COLORS["bg_card"],
                command=lambda c=color: None,  # Will be set below
            )
            color_btn.pack(side="left", padx=2)
            self._accent_buttons.append(color_btn)
            # Set command with button reference
            color_btn.configure(
                command=lambda c=color, b=color_btn: select_accent(c, b)
            )

        # Custom color picker button
        def pick_custom_color():
            from tkinter import colorchooser

            color = colorchooser.askcolor(
                title="Choose Accent Color",
                initialcolor=COLORS.get("accent", "#3b82f6"),
            )
            if color[1]:  # color[1] is the hex value
                COLORS["accent"] = color[1]
                COLORS["accent_hover"] = self._darken_color(color[1])
                COLORS["accent_soft"] = self._soften_color(color[1])
                # Save accent color preference
                self._save_settings(accent_color=color[1])
                dialog.destroy()
                self.show_vault()

        custom_btn = ctk.CTkButton(
            accent_frame,
            text="⋯",
            width=28,
            height=28,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            corner_radius=14,
            font=("Segoe UI", 14, "bold"),
            command=pick_custom_color,
        )
        custom_btn.pack(side="left", padx=(6, 0))

        # ═══════════════════════════════════════════════════════════════
        # SECURITY SECTION
        # ═══════════════════════════════════════════════════════════════
        security_section = ctk.CTkFrame(
            main_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        security_section.pack(fill="x", pady=(0, SP["md"]))

        security_header = ctk.CTkFrame(security_section, fg_color="transparent")
        security_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        ctk.CTkLabel(
            security_header,
            text="🔒 Security",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        security_content = ctk.CTkFrame(security_section, fg_color="transparent")
        security_content.pack(fill="x", padx=SP["lg"], pady=(0, SP["md"]))

        # Auto-lock timeout
        autolock_row = ctk.CTkFrame(security_content, fg_color="transparent")
        autolock_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            autolock_row,
            text="Auto-lock after inactivity",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        autolock_var = ctk.StringVar(value="10 min")
        autolock_menu = ctk.CTkOptionMenu(
            autolock_row,
            values=["5 min", "10 min", "15 min", "30 min", "Never"],
            variable=autolock_var,
            width=100,
            height=CTL["h"] - 8,
            font=FONT["body"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            text_color=COLORS["text_primary"],
            corner_radius=RAD["sm"],
        )
        autolock_menu.pack(side="right")

        # Clipboard clear
        clipboard_row = ctk.CTkFrame(security_content, fg_color="transparent")
        clipboard_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            clipboard_row,
            text="Clear clipboard after copy",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        clipboard_var = ctk.StringVar(value="15 sec")
        clipboard_menu = ctk.CTkOptionMenu(
            clipboard_row,
            values=["10 sec", "15 sec", "30 sec", "1 min", "Never"],
            variable=clipboard_var,
            width=100,
            height=CTL["h"] - 8,
            font=FONT["body"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            text_color=COLORS["text_primary"],
            corner_radius=RAD["sm"],
        )
        clipboard_menu.pack(side="right")

        # Change Master Password button
        pwd_row = ctk.CTkFrame(security_content, fg_color="transparent")
        pwd_row.pack(fill="x", pady=(SP["sm"], 0))

        ctk.CTkLabel(
            pwd_row,
            text="Master Password",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        ctk.CTkButton(
            pwd_row,
            text="Change Password",
            width=140,
            height=CTL["h"] - 8,
            font=FONT["button"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["sm"],
            command=lambda: [dialog.destroy(), self.show_change_master_password()],
        ).pack(side="right")

        # ═══════════════════════════════════════════════════════════════
        # VAULT SETTINGS SECTION
        # ═══════════════════════════════════════════════════════════════
        vault_section = ctk.CTkFrame(
            main_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        vault_section.pack(fill="x", pady=(0, SP["md"]))

        vault_header = ctk.CTkFrame(vault_section, fg_color="transparent")
        vault_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        ctk.CTkLabel(
            vault_header,
            text="🗄️ Vault",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        vault_content = ctk.CTkFrame(vault_section, fg_color="transparent")
        vault_content.pack(fill="x", padx=SP["lg"], pady=(0, SP["md"]))

        # Export vault
        export_row = ctk.CTkFrame(vault_content, fg_color="transparent")
        export_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            export_row,
            text="Export vault backup",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        ctk.CTkButton(
            export_row,
            text="Export",
            width=80,
            height=CTL["h"] - 8,
            font=FONT["button"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["sm"],
            command=lambda: [dialog.destroy(), self.show_backup_dialog()],
        ).pack(side="right")

        # Danger zone divider
        danger_divider = ctk.CTkFrame(
            vault_content, height=1, fg_color=COLORS["border"]
        )
        danger_divider.pack(fill="x", pady=SP["md"])

        ctk.CTkLabel(
            vault_content,
            text="⚠️ Danger Zone",
            font=FONT["small"],
            text_color=COLORS["danger"],
        ).pack(anchor="w", pady=(0, SP["sm"]))

        # Delete vault
        delete_row = ctk.CTkFrame(vault_content, fg_color="transparent")
        delete_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            delete_row,
            text="Delete vault permanently",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        def confirm_delete_vault():
            """Confirm vault deletion with password"""
            dialog.destroy()
            self._show_delete_vault_confirm()

        ctk.CTkButton(
            delete_row,
            text="Delete Vault",
            width=110,
            height=CTL["h"] - 8,
            font=FONT["button"],
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            text_color="#ffffff",
            corner_radius=RAD["sm"],
            command=confirm_delete_vault,
        ).pack(side="right")

        # ═══════════════════════════════════════════════════════════════
        # ADVANCED SECTION
        # ═══════════════════════════════════════════════════════════════
        advanced_section = ctk.CTkFrame(
            main_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=RAD["md"],
            border_width=1,
            border_color=COLORS["border"],
        )
        advanced_section.pack(fill="x", pady=(0, SP["md"]))

        advanced_header = ctk.CTkFrame(advanced_section, fg_color="transparent")
        advanced_header.pack(fill="x", padx=SP["lg"], pady=SP["md"])

        ctk.CTkLabel(
            advanced_header,
            text="🔧 Advanced",
            font=FONT["h3"],
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        advanced_content = ctk.CTkFrame(advanced_section, fg_color="transparent")
        advanced_content.pack(fill="x", padx=SP["lg"], pady=(0, SP["md"]))

        # Reset UI layout
        reset_row = ctk.CTkFrame(advanced_content, fg_color="transparent")
        reset_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            reset_row,
            text="Reset UI layout",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        def reset_ui():
            self.sidebar_collapsed = False
            self._apply_sidebar_state()
            messagebox.showinfo("Reset", "UI layout has been reset.")

        ctk.CTkButton(
            reset_row,
            text="Reset",
            width=80,
            height=CTL["h"] - 8,
            font=FONT["button"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["sm"],
            command=reset_ui,
        ).pack(side="right")

        # Clear cache
        cache_row = ctk.CTkFrame(advanced_content, fg_color="transparent")
        cache_row.pack(fill="x", pady=SP["xs"])

        ctk.CTkLabel(
            cache_row,
            text="Clear temporary data",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        def clear_cache():
            # Clear internal caches
            if hasattr(self, "_totp_cards"):
                delattr(self, "_totp_cards")
            if hasattr(self, "bulk_selected"):
                self.bulk_selected = []
            messagebox.showinfo("Cleared", "Temporary data has been cleared.")

        ctk.CTkButton(
            cache_row,
            text="Clear",
            width=80,
            height=CTL["h"] - 8,
            font=FONT["button"],
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["sm"],
            command=clear_cache,
        ).pack(side="right")

        # Close button
        ctk.CTkButton(
            main_scroll,
            text="Close",
            width=120,
            height=CTL["h"],
            font=FONT["button"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
            command=dialog.destroy,
        ).pack(pady=(SP["md"], 0))

    def _show_delete_vault_confirm(self):
        """Show delete vault confirmation dialog with password requirement"""
        dialog = self.create_dialog("Delete Vault", 400, 320)
        dialog.configure(fg_color=COLORS["bg_primary"])

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SP["xl"], pady=SP["lg"])

        # Warning header
        ctk.CTkLabel(
            content,
            text="⚠️ Delete Vault",
            font=FONT["h2"],
            text_color=COLORS["danger"],
        ).pack(pady=(SP["md"], SP["sm"]))

        ctk.CTkLabel(
            content,
            text="This action cannot be undone.\nAll data will be permanently deleted.",
            font=FONT["body"],
            text_color=COLORS["text_secondary"],
            justify="center",
        ).pack(pady=(0, SP["lg"]))

        # Password confirmation
        pwd_entry = ctk.CTkEntry(
            content,
            width=300,
            height=CTL["h"],
            placeholder_text="Enter Master Password to confirm",
            show="●",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
        )
        pwd_entry.pack(pady=(0, SP["sm"]))

        status = ctk.CTkLabel(content, text="", font=FONT["small"])
        status.pack(pady=SP["xs"])

        def delete_vault():
            password = pwd_entry.get()
            if not password:
                status.configure(
                    text="❌ Password required", text_color=COLORS["danger"]
                )
                return

            # Verify password
            if not self.vault.verify_password(password):
                status.configure(
                    text="❌ Invalid password", text_color=COLORS["danger"]
                )
                return

            # Delete the vault file
            try:
                import os
                from app.constants import VAULT_FILE, DATA_DIR

                if VAULT_FILE.exists():
                    os.remove(VAULT_FILE)

                # Also remove recovery files
                recovery_file = DATA_DIR / "recovery.json"
                if recovery_file.exists():
                    os.remove(recovery_file)

                dialog.destroy()
                messagebox.showinfo(
                    "Deleted", "Vault has been deleted. The application will now close."
                )
                self.app.quit()
            except Exception as e:
                status.configure(text=f"❌ {str(e)}", text_color=COLORS["danger"])

        # Action buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(SP["md"], 0))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=CTL["h"],
            font=FONT["button"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
            command=dialog.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="Delete Vault",
            width=140,
            height=CTL["h"],
            font=FONT["button"],
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            text_color="#ffffff",
            corner_radius=RAD["md"],
            command=delete_vault,
        ).pack(side="right")

    def show_change_master_password(self):
        """Change master password dialog - compact and focused"""
        self.reset_activity()
        dialog = self.create_dialog("Change Master Password", 380, 360)
        dialog.configure(fg_color=COLORS["bg_primary"])

        # Content container with padding
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SP["xl"], pady=SP["lg"])

        # Header with icon
        ctk.CTkLabel(
            content,
            text="🔐 Change Master Password",
            font=FONT["h2"],
            text_color=COLORS["text_primary"],
        ).pack(pady=(SP["md"], SP["lg"]))

        # Form fields
        old_pwd = ctk.CTkEntry(
            content,
            width=300,
            height=CTL["h"],
            placeholder_text="Current Password",
            show="●",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
        )
        old_pwd.pack(pady=(0, SP["sm"]))

        new_pwd = ctk.CTkEntry(
            content,
            width=300,
            height=CTL["h"],
            placeholder_text="New Password",
            show="●",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
        )
        new_pwd.pack(pady=(0, SP["sm"]))

        confirm_pwd = ctk.CTkEntry(
            content,
            width=300,
            height=CTL["h"],
            placeholder_text="Confirm New Password",
            show="●",
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
        )
        confirm_pwd.pack(pady=(0, SP["sm"]))

        status = ctk.CTkLabel(content, text="", font=FONT["small"])
        status.pack(pady=SP["xs"])

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

        # Action buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(SP["md"], 0))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=90,
            height=CTL["h"],
            font=FONT["button"],
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=RAD["md"],
            command=dialog.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="Change Password",
            width=180,
            height=CTL["h"],
            font=FONT["button"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=RAD["md"],
            command=change,
        ).pack(side="right")

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

            ctk.CTkLabel(row, text=action, font=("Segoe UI", 12), anchor="w", text_color=COLORS["text_primary"]).pack(
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

        from app.services.breach_service import check_password_breach

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
        """Display TOTP/2FA codes with live countdown and professional card design"""
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

        # Hover effect helper
        def bind_hover_recursive(widget, card_ref):
            widget.bind(
                "<Enter>",
                lambda e, c=card_ref: c.configure(border_color=COLORS["accent"]),
            )
            widget.bind(
                "<Leave>",
                lambda e, c=card_ref: c.configure(border_color=COLORS["border"]),
            )
            for child in widget.winfo_children():
                bind_hover_recursive(child, card_ref)

        # Store references for updates
        self._totp_labels = {}

        for item in items:
            card = ctk.CTkFrame(
                self.items_container,
                fg_color=COLORS["bg_card"],
                corner_radius=RAD["md"],
                border_width=1,
                border_color=COLORS["border"],
            )
            card.pack(fill="x", pady=3, padx=0)

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=SP["lg"], pady=SP["sm"])

            # Header: 2FA icon + Name + Issuer
            header = ctk.CTkFrame(content, fg_color="transparent")
            header.pack(fill="x")

            ctk.CTkLabel(
                header,
                text="🔐",
                font=FONT["body"],
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, SP["xs"]))

            ctk.CTkLabel(
                header,
                text=item.get("name", "Untitled"),
                font=FONT["h3"],
                text_color=COLORS["text_primary"],
            ).pack(side="left")

            if item.get("issuer"):
                ctk.CTkLabel(
                    header,
                    text=f"• {item['issuer']}",
                    font=FONT["small"],
                    text_color=COLORS["text_muted"],
                ).pack(side="left", padx=(SP["sm"], 0))

            # Code display row
            code_row = ctk.CTkFrame(content, fg_color="transparent")
            code_row.pack(fill="x", pady=(SP["sm"], 0))

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
                font=("Consolas", 28, "bold"),
                text_color=COLORS["accent"],
            )
            code_label.pack(side="left")

            timer_color = COLORS["danger"] if remaining <= 5 else COLORS["success"]
            timer_label = ctk.CTkLabel(
                code_row,
                text=f"⏱ {remaining}s",
                font=FONT["body"],
                text_color=timer_color,
            )
            timer_label.pack(side="left", padx=(SP["md"], 0))

            # Store for updates
            self._totp_labels[item["id"]] = {
                "secret": item["secret"],
                "code_label": code_label,
                "timer_label": timer_label,
            }

            # Actions row
            actions = ctk.CTkFrame(content, fg_color="transparent")
            actions.pack(fill="x", pady=(SP["sm"], 0))

            # Left actions
            left_actions = ctk.CTkFrame(actions, fg_color="transparent")
            left_actions.pack(side="left")

            ctk.CTkButton(
                left_actions,
                text="Copy Code",
                width=90,
                height=32,
                font=FONT["button"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=RAD["sm"],
                command=lambda s=item["secret"]: self._copy_current_totp(s),
            ).pack(side="left")

            # Right actions (more menu)
            right_actions = ctk.CTkFrame(actions, fg_color="transparent")
            right_actions.pack(side="right")

            def _open_more(event=None, i=item):
                menu = tk.Menu(self.app, tearoff=0, font=FONT["body"])
                menu.add_command(
                    label="Delete...",
                    foreground="#ef4444",
                    command=lambda: self.confirm_delete_item(
                        i["id"], "totp", i.get("name", "this code")
                    ),
                )
                menu.tk_popup(self.app.winfo_pointerx(), self.app.winfo_pointery())

            ctk.CTkButton(
                right_actions,
                text="•••",
                width=40,
                height=32,
                font=("Segoe UI", 16),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=RAD["sm"],
                command=_open_more,
            ).pack(side="right")

            # Apply hover bindings
            bind_hover_recursive(card, card)

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
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border"],
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

    def show_recovery_phrase_mandatory(self, recovery_phrase, master_password):
        """MANDATORY recovery phrase setup - CANNOT be skipped"""
        return LoginViewMixin.show_recovery_phrase_mandatory(
            self, recovery_phrase, master_password
        )

    def verify_recovery_phrase_mandatory(
        self, original_phrase, parent_dialog, master_password
    ):
        """MANDATORY quiz - Account creation FAILS if quiz fails"""
        return LoginViewMixin.verify_recovery_phrase_mandatory(
            self, original_phrase, parent_dialog, master_password
        )

    def show_recovery_unlock_dialog(self):
        """Unlock vault with recovery phrase"""
        return LoginViewMixin.show_recovery_unlock_dialog(self)

    def show_qr_code(self, qr_image, title: str, data_type: str):
        """Display QR code in popup"""
        dialog = self.create_dialog(f"📱 QR Code - {title}", 500, 720)

        ctk.CTkLabel(
            dialog, text=f"Scan with Phone Camera", font=("Segoe UI", 20, "bold")
        ).pack(pady=(8, 2))

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
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border"],
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
