"""Starts cloudflared quick tunnel and writes the public URL to tunnel_url.txt."""
import subprocess
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TUNNEL_URL_FILE = BASE_DIR / "tunnel_url.txt"
CLOUDFLARED = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"


def main():
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", "http://localhost:713"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    url_found = False
    for line in proc.stdout:
        print(line, end="", flush=True)
        if not url_found:
            match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
            if match:
                tunnel_url = match.group(1)
                TUNNEL_URL_FILE.write_text(tunnel_url)
                print(f"\n>>> Tunnel URL saved: {tunnel_url}\n", flush=True)
                url_found = True

    proc.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
