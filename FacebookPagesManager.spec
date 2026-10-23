# PyInstaller spec — Facebook Pages Manager (Phase 6)
# Build on Windows:  pyinstaller FacebookPagesManager.spec
# Output: dist/FacebookPagesManager/FacebookPagesManager.exe
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['desktop.ui.main_window'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['licensing_server'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='FacebookPagesManager', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, icon='app_icon.ico',  # windowed: customers never see a terminal
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='FacebookPagesManager')
