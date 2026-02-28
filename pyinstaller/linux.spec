# pyinstaller/linux.spec
# Usage: pyinstaller pyinstaller/linux.spec

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

def safe_collect(package):
    try:
        d, b, h = collect_all(package)
        return d, b, h
    except Exception as e:
        print(f"[WARN] collect_all('{package}') failed: {e}")
        return [], [], []

uv_d, uv_b, uv_h = safe_collect('uvicorn')
st_d, st_b, st_h = safe_collect('starlette')
fa_d, fa_b, fa_h = safe_collect('fastapi')
ws_d, ws_b, ws_h = safe_collect('websockets')
wv_d, wv_b, wv_h = safe_collect('webview')

all_datas = (
    [('ui', 'ui')]
    + uv_d + st_d + fa_d + ws_d + wv_d
)

all_binaries = uv_b + st_b + fa_b + ws_b + wv_b

all_hidden = (
    uv_h + st_h + fa_h + ws_h + wv_h
    + collect_submodules('uvicorn')
    + collect_submodules('starlette')
    + collect_submodules('fastapi')
    + collect_submodules('websockets')
    + collect_submodules('webview')
    + [
        'webview.platforms.gtk',
        'multiprocessing',
        'asyncio',
        'h11',
        'anyio',
        'anyio._backends._asyncio',
        'anyio._backends._trio',
    ]
)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='asterix_decoder',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    runtime_tmpdir=None,
)
