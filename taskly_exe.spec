# -*- mode: python ; coding: utf-8 -*-
"""
Сборка Taskly в единый EXE-файл (PyInstaller onefile).

Запуск:
  .venv-build\Scripts\python -m PyInstaller --clean taskly_exe.spec
"""
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_root = Path(os.getcwd())

# Все подмодули проекта — Django подгружает их динамически по INSTALLED_APPS
hiddenimports = []
hiddenimports += collect_submodules("apps")
hiddenimports += collect_submodules("config")
# Django подключает их по строкам из settings, PyInstaller их не «видит»
hiddenimports += collect_submodules("whitenoise")
hiddenimports += collect_submodules("waitress")

# ДАННЫЕ: шаблоны, статика, миграции (модули уже в PYZ через collect_submodules)
datas = [
    (str(project_root / "templates"), "templates"),
    (str(project_root / "static"), "static"),
]

a = Analysis(
    ["taskly_entry.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "psycopg",
        "psycopg_pool",
        "psycopg_types",
        "gunicorn",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Taskly",
    icon=str(project_root / "Taskly.ico"),  # сгенерирован из static/images/favicon.svg
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
