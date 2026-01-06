import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.constants import COLORS, VAULT_FILE
from app.core.recovery import RecoverySystem


class RecoveryDialogMixin:
    def show_recovery_phrase_setup(
        self,
        recovery_phrase: str,
        on_proceed,
        on_cancel,
        on_copied=None,
        on_downloaded=None,
    ):
        """Recovery phrase display for new setup. Proceed visible only after copy/download."""
        dialog = self.create_dialog("🔐 SAVE YOUR RECOVERY PHRASE", 720, 820)

        dialog.protocol(
            "WM_DELETE_WINDOW",
            lambda: [dialog.destroy(), on_cancel() if on_cancel else None],
        )
        dialog.attributes("-topmost", False)

        warning_frame = ctk.CTkFrame(
            dialog, fg_color="#8B0000", corner_radius=12, height=120
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
            text="Anyone with these words can unlock your vault. Write them down and keep offline.",
            font=("Segoe UI", 11),
            text_color="white",
            wraplength=650,
        ).pack(pady=5)

        ctk.CTkLabel(
            dialog, text="Your 24-Word Recovery Phrase:", font=("Segoe UI", 16, "bold")
        ).pack(pady=(15, 10))

        recovery = RecoverySystem(self.vault.path)
        formatted_words = recovery.format_phrase_for_display(recovery_phrase)

        phrase_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=12, height=320
        )
        phrase_frame.pack(padx=20, pady=10, fill="both")

        grid_container = ctk.CTkFrame(phrase_frame, fg_color="transparent")
        grid_container.pack(expand=True, pady=20, padx=20)

        label_refs = []
        hidden = {"visible": False}

        for col_idx in range(3):
            col_frame = ctk.CTkFrame(grid_container, fg_color="transparent")
            col_frame.grid(row=0, column=col_idx, padx=15, sticky="n")

        for num, word in formatted_words:
            col_idx = (num - 1) % 3
            col_frame = grid_container.grid_slaves(row=0, column=col_idx)[0]
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

            val_label = ctk.CTkLabel(
                word_row,
                text="••••",
                font=("Consolas", 13, "bold"),
                text_color=COLORS["accent"],
                anchor="w",
            )
            val_label.pack(side="left")
            label_refs.append((val_label, word))

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def hide_words():
            for lbl, _word in label_refs:
                lbl.configure(text="••••")
            hidden["visible"] = False

        def reveal_words():
            for lbl, word in label_refs:
                lbl.configure(text=word)
            hidden["visible"] = True
            dialog.after(12000, lambda: hide_words() if hidden["visible"] else None)

        def toggle_visibility():
            if hidden["visible"]:
                hide_words()
            else:
                reveal_words()

        def mark_exported(kind: str):
            if kind == "copy" and on_copied:
                on_copied()
            if kind == "download" and on_downloaded:
                on_downloaded()
            show_proceed()

        action_row = ctk.CTkFrame(dialog, fg_color="transparent")
        action_row.pack(pady=10)

        ctk.CTkButton(
            action_row,
            text="👁️ Reveal / Hide",
            width=180,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=toggle_visibility,
        ).pack(side="left", padx=6)

        def copy_phrase():
            import pyperclip

            pyperclip.copy(recovery_phrase)
            status.configure(text="Copied to clipboard", text_color=COLORS["success"])
            mark_exported("copy")

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
                        recovery_phrase,
                        "",
                        "Store safely. Do not email or share.",
                    ]

                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

                    status.configure(text="Downloaded", text_color=COLORS["success"])
                    mark_exported("download")
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

        proceed_row = ctk.CTkFrame(dialog, fg_color="transparent")
        proceed_shown = {"shown": False}

        def show_proceed():
            if proceed_shown["shown"]:
                return
            proceed_shown["shown"] = True
            proceed_row.pack(pady=(18, 25))

            ctk.CTkButton(
                proceed_row,
                text="❌ Cancel",
                width=180,
                height=45,
                font=("Segoe UI", 13),
                fg_color="gray30",
                hover_color="gray40",
                corner_radius=8,
                command=lambda: [dialog.destroy(), on_cancel() if on_cancel else None],
            ).pack(side="left", padx=8)

            ctk.CTkButton(
                proceed_row,
                text="✅ Proceed to Verification",
                width=280,
                height=45,
                font=("Segoe UI", 15, "bold"),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                corner_radius=10,
                command=lambda: [dialog.destroy(), on_proceed()],
            ).pack(side="left", padx=8)

        # Auto-hide by default
        hide_words()

    def show_recovery_phrase_mandatory(self, recovery_phrase, master_password):
        """MANDATORY recovery phrase setup with explicit proceed/cancel controls"""
        dialog = self.create_dialog("🔐 SAVE YOUR RECOVERY PHRASE", 700, 800)

        # Allow closing via an explicit cancel flow instead of a hard modal block
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._cancel_recovery_setup(dialog))
        dialog.attributes("-topmost", False)

        warning_frame = ctk.CTkFrame(
            dialog, fg_color="#8B0000", corner_radius=12, height=120
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
            text="This is the ONLY way to recover your vault if you forget your password!\n"
            "You CANNOT proceed without saving this phrase.\n"
            "Write it down on paper. DO NOT save digitally. Keep it safe.",
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
                        recovery_phrase,
                        "",
                        "Store safely. Do not email or share.",
                    ]

                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

                    download_btn.configure(text="✅ Downloaded!")
                    dialog.after(
                        2000, lambda: download_btn.configure(text="💾 Download as File")
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")

        download_btn = ctk.CTkButton(
            dialog,
            text="💾 Download as File",
            width=300,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=download_phrase,
        )
        download_btn.pack(pady=10)

        verified = tk.BooleanVar(value=False)
        proceed_btn_holder = {"btn": None}
        verify_frame = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"], corner_radius=10
        )
        verify_frame.pack(padx=20, pady=15, fill="x", ipady=10)

        def _toggle_proceed_state():
            btn = proceed_btn_holder.get("btn")
            if btn:
                btn.configure(state="normal" if verified.get() else "disabled")

        ctk.CTkCheckBox(
            verify_frame,
            text="✅ I have saved my recovery phrase in a safe place",
            variable=verified,
            font=("Segoe UI", 12, "bold"),
            checkbox_width=24,
            checkbox_height=24,
            command=_toggle_proceed_state,
        ).pack(pady=10, padx=20)

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=5)

        def proceed_to_verification():
            if not verified.get():
                status.configure(
                    text="❌ You must confirm you saved the recovery phrase",
                    text_color=COLORS["danger"],
                )
                return

            self.verify_recovery_phrase_mandatory(
                recovery_phrase, dialog, master_password
            )

        action_row = ctk.CTkFrame(dialog, fg_color="transparent")
        action_row.pack(pady=(10, 25))

        ctk.CTkButton(
            action_row,
            text="❌ Cancel",
            width=170,
            height=45,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=lambda: self._cancel_recovery_setup(dialog),
        ).pack(side="left", padx=8)

        proceed_btn = ctk.CTkButton(
            action_row,
            text="✅ Continue to Verification",
            width=250,
            height=45,
            font=("Segoe UI", 15, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=10,
            state="disabled",
            command=proceed_to_verification,
        )
        proceed_btn.pack(side="left", padx=8)
        proceed_btn_holder["btn"] = proceed_btn

    def verify_recovery_phrase_mandatory(
        self, original_phrase, parent_dialog, master_password
    ):
        """MANDATORY quiz - Account creation FAILS if quiz fails"""
        import random

        words = original_phrase.split()
        word_positions = random.sample(range(1, 25), 3)
        word_positions.sort()
        quiz_dialog = self.create_dialog("🧪 Verification Required", 500, 450)

        quiz_dialog.protocol(
            "WM_DELETE_WINDOW", lambda: self._cancel_recovery_setup(quiz_dialog)
        )
        quiz_dialog.attributes("-topmost", False)
        ctk.CTkLabel(
            quiz_dialog, text="🔐 Verification Test", font=("Segoe UI", 20, "bold")
        ).pack(pady=20)
        ctk.CTkLabel(
            quiz_dialog,
            text="Enter these 3 words from your recovery phrase.\n"
            "⚠️ If you fail, your vault creation will be CANCELLED.",
            font=("Segoe UI", 12),
            text_color=COLORS["warning"],
            wraplength=450,
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
        attempts = [0]

        def check_answers():
            attempts[0] += 1
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
                    text="✅ Verification successful! Creating your vault...",
                    text_color=COLORS["success"],
                )
                quiz_dialog.after(
                    1500,
                    lambda: [
                        quiz_dialog.destroy(),
                        parent_dialog.destroy(),
                        self.show_vault(),
                    ],
                )
            else:
                if attempts[0] >= 3:
                    status.configure(
                        text="❌ Verification failed 3 times. Vault creation cancelled.",
                        text_color=COLORS["danger"],
                    )
                    quiz_dialog.after(
                        2000,
                        lambda: [
                            self.vault.lock(),
                            VAULT_FILE.unlink(missing_ok=True),
                            quiz_dialog.destroy(),
                            parent_dialog.destroy(),
                            self.show_login(),
                            messagebox.showerror(
                                "Vault Creation Failed",
                                "You failed the verification test.\n\n"
                                "Your vault has been deleted for security.\n"
                                "Please start over and SAVE your recovery phrase properly.",
                            ),
                        ],
                    )
                else:
                    status.configure(
                        text=f"❌ Incorrect words. Attempts remaining: {3 - attempts[0]}",
                        text_color=COLORS["danger"],
                    )

        action_row = ctk.CTkFrame(quiz_dialog, fg_color="transparent")
        action_row.pack(pady=20)

        ctk.CTkButton(
            action_row,
            text="❌ Cancel",
            width=140,
            height=45,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=lambda: self._cancel_recovery_setup(quiz_dialog),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            action_row,
            text="✅ Verify",
            width=180,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=check_answers,
        ).pack(side="left", padx=8)
        entries[0][1].focus()

    def verify_recovery_phrase_full(self, correct_phrase: str, on_success, on_lock):
        """Verify by asking 4 random words instead of full phrase."""
        import random

        dialog = self.create_dialog("🧪 Verify Recovery Phrase", 640, 440)

        ctk.CTkLabel(
            dialog,
            text="Enter the requested words from your recovery phrase.",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=15)

        words = correct_phrase.split()
        positions = sorted(random.sample(range(1, 25), 4))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(pady=10)

        entries = []
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

        status = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 12))
        status.pack(pady=8)

        attempts = {"count": 0}

        def check_phrase():
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
                dialog.destroy()
                on_success()
                return

            remaining = 3 - attempts["count"]
            if remaining <= 0:
                status.configure(
                    text="🔒 Verification failed 3 times. Locked for 30 minutes.",
                    text_color=COLORS["danger"],
                )
                dialog.after(800, lambda: [dialog.destroy(), on_lock()])
                return

            status.configure(
                text=f"❌ Incorrect words. {remaining} attempt(s) left.",
                text_color=COLORS["danger"],
            )

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(pady=16)

        ctk.CTkButton(
            button_row,
            text="❌ Cancel",
            width=150,
            height=45,
            font=("Segoe UI", 13),
            fg_color="gray30",
            hover_color="gray40",
            corner_radius=8,
            command=lambda: dialog.destroy(),
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_row,
            text="✅ Verify",
            width=200,
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=check_phrase,
        ).pack(side="left", padx=10)
        entries[0][1].focus()

    def _cancel_recovery_setup(self, dialog):
        """Abort recovery setup safely and return to login."""
        try:
            self.vault.lock()
        except Exception:
            pass

        try:
            VAULT_FILE.unlink(missing_ok=True)
        except Exception:
            pass

        try:
            dialog.destroy()
        except Exception:
            pass

        try:
            self.show_login()
        except Exception:
            pass

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
