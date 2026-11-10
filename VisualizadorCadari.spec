# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
datas += collect_data_files('openpyxl')
datas += [('assets', 'assets')]
# Regras de clash (YAML) são um arquivo de dados do próprio projeto, não
# de um pacote pip — collect_all() não o pega sozinho, então sem isso o
# app abre, mas trava (silenciosamente, sem traceback visível numa build
# --windowed) ao abrir o Visualizador IFC, porque a aba de Clash não
# consegue carregar as regras (FileNotFoundError dentro de um callback
# do Tkinter, que o Tkinter engole sem mostrar nada ao usuário).
datas += [('clash/regras_clash.yaml', 'clash')]
# dicionário português do corretor ortográfico (ui/corretor.py)
datas += collect_data_files('spellchecker')
tmp_ret = collect_all('vtkmodules')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ifcopenshell')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('fitz')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('matplotlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('trimesh')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('fcl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('manifold3d')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rtree')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yaml')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # PySide6/shiboken6 vêm como dependência opcional de ifcopenshell (não
    # são usados por este app, que é 100% Tkinter) e o .pth do shiboken6
    # instala um hook global no sistema de import que QUEBRA o app
    # congelado (AttributeError em '_SixMetaPathImporter') assim que
    # qualquer módulo (aqui, dateutil, puxado pelo matplotlib) é
    # inspecionado via `inspect.getsource`. pandas/pyarrow/psycopg2/
    # sqlalchemy/pygame também vêm de ifcopenshell e nunca são usados —
    # excluídos só para não inchar o executável à toa.
    excludes=[
        'PySide6', 'shiboken6',
        'pandas', 'pyarrow', 'psycopg2', 'sqlalchemy', 'pygame',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CadariVizzo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icone_cadari_vizzo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CadariVizzo',
)
