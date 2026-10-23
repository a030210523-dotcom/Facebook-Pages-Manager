# PyInstaller ONE-FILE spec — Facebook Pages Manager
# Produces a SINGLE dist/FacebookPagesManager.exe containing Python, PySide6 and the app.
# The end user needs NOTHING installed: double-click the .exe and it runs (Windows 10/11).
# Build on Windows:  pyinstaller FacebookPagesManager-OneFile.spec
a = Analysis(
    ['app.py'],
    pathex=[], binaries=[], datas=[],
    hiddenimports=['desktop.ui.main_window'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['licensing_server'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='FacebookPagesManager',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    runtime_tmpdir=None, console=False,  # windowed, no terminal
    icon='app_icon.ico',
)
