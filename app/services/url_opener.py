import webbrowser
from tkinter import messagebox


def open_url(url: str):
    """Open URL in default browser with scheme guard."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open URL: {str(e)}")
