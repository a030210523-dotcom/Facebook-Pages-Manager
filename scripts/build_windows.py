"""Windows build (Section 29, Phase 6). Run ON WINDOWS:
    python scripts/build_windows.py
Produces dist/FacebookPagesManager/FacebookPagesManager.exe via the PyInstaller spec,
then (if Inno Setup's iscc is on PATH) installer/FacebookPagesManager-Setup.exe.
NOTE: a Windows .exe can only be produced and tested on Windows — a build done on
Linux/macOS produces a binary for that OS instead (useful only as a packaging proof)."""
import shutil, subprocess, sys, os
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                           os.path.join(root, "requirements.txt"), "pyinstaller"], cwd=root)
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm",
                           "FacebookPagesManager.spec"], cwd=root)
    print("Built: dist/FacebookPagesManager/FacebookPagesManager.exe (on Windows)")
    iscc = shutil.which("iscc")
    if iscc:
        subprocess.check_call([iscc, os.path.join(root, "scripts", "installer.iss")], cwd=root)
        print("Installer built: installer/FacebookPagesManager-Setup.exe")
    else:
        print("Inno Setup (iscc) not found — skipping installer. Install it from jrsoftware.org to build the Setup .exe.")
if __name__ == "__main__":
    main()
