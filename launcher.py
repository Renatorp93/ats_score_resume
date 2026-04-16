from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from streamlit.web import bootstrap


def _runtime_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _entry_script() -> Path:
    return _runtime_root() / "packaged_app.py"


def _find_free_port() -> int:
    requested_port = os.getenv("ATS_SCORE_RESUME_PORT")
    if requested_port:
        return int(requested_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _open_browser_when_ready(port: int) -> None:
    if os.getenv("ATS_SCORE_RESUME_NO_BROWSER") == "1":
        return

    url = f"http://127.0.0.1:{port}"

    def _open() -> None:
        for _ in range(60):
            time.sleep(1)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    webbrowser.open(url, new=2)
                    return
            except OSError:
                continue

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    main_script_path = str(_entry_script())
    port = _find_free_port()
    flag_options = {
        "server_port": port,
        "server_headless": True,
        "server_fileWatcherType": "none",
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }

    bootstrap.load_config_options(flag_options)
    _open_browser_when_ready(port)
    bootstrap.run(main_script_path, False, [], flag_options)


if __name__ == "__main__":
    main()
