import sys
import winreg
from pathlib import Path

PYTHONW_EXE = str(Path(sys.executable).parent / "pythonw.exe")
HANDLER_SCRIPT = str(Path(__file__).resolve().parent / "upload_handler.py")

# HKCU path — no admin required
REG_ROOT = winreg.HKEY_CURRENT_USER
SHELL_KEY = r"Software\Classes\*\shell\ShareToMyServer"
COMMAND_KEY = SHELL_KEY + r"\command"


def install():
    try:
        key = winreg.CreateKeyEx(REG_ROOT, SHELL_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WRITE)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Share to My Server")
        winreg.CloseKey(key)

        cmd_key = winreg.CreateKeyEx(REG_ROOT, COMMAND_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WRITE)
        command = f'"{PYTHONW_EXE}" "{HANDLER_SCRIPT}" "%1"'
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
        winreg.CloseKey(cmd_key)

        print("Context menu installed.")
        print(f"  pythonw: {PYTHONW_EXE}")
        print(f"  handler: {HANDLER_SCRIPT}")
        print(f"  command: {command}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def uninstall():
    try:
        try:
            winreg.DeleteKey(REG_ROOT, COMMAND_KEY)
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteKey(REG_ROOT, SHELL_KEY)
        except FileNotFoundError:
            pass
        print("Context menu removed.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("--install", "--uninstall"):
        print("Usage: python context_menu.py --install | --uninstall")
        sys.exit(1)

    if sys.argv[1] == "--install":
        install()
    else:
        uninstall()
