import SimConnect
import os

simconnect_dir = os.path.dirname(SimConnect.__file__)
simconnect_dll = os.path.join(simconnect_dir, 'SimConnect.dll')
simconnect_json = os.path.join(simconnect_dir, 'scvars.json')

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src\\icon.png', '.'),
        ('src\\icon.ico', '.'),
        ('default_airports_db.bin', '.'),
        ('airlines_terminals.json', '.'),
        ('MSFS_Package\\wildbill75-gatefinder', 'MSFS_Package\\wildbill75-gatefinder'),
        (simconnect_dll, 'SimConnect'),
        (simconnect_json, 'SimConnect'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GateFinder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src\\icon.ico',
)
