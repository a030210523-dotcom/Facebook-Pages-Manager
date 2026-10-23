# PyInstaller ONE-FILE spec — FPM Licensing Server
# Produces a SINGLE dist/FPMLicenseServer.exe (console) containing Python, FastAPI
# and uvicorn. The server runs on any Windows PC with NOTHING installed.
# Build:  pyinstaller LicenseServer.spec
a = Analysis(
    ['licensing_server/run_server.py'],
    pathex=[], binaries=[], datas=[],
    hiddenimports=['licensing_server.main', 'licensing_server.core', 'licensing_server.users',
                   'licensing_server.invites', 'licensing_server.meta_exchange',
                   'licensing_server.signing', 'uvicorn.logging', 'uvicorn.loops.auto',
                   'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto',
                   'uvicorn.lifespan.on'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['desktop', 'PySide6'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='FPMLicenseServer',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    runtime_tmpdir=None, console=True,  # console: the owner sees the server log window
    icon='app_icon.ico',
)
