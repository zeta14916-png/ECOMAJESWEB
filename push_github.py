#!/usr/bin/env python3
"""Script para hacer push a GitHub usando el token guardado como secreto."""
import os
import subprocess

token = os.environ.get("GITHUB_TOKEN", "").strip()
if not token:
    print("❌ GITHUB_TOKEN no encontrado. Agrega el token como secreto de Replit primero.")
    raise SystemExit(1)

url = f"https://zeta14916-png:{token}@github.com/zeta14916-png/ECOMAJESWEB.git"
result = subprocess.run(
    ["git", "push", url, "main"],
    cwd="/home/runner/workspace",
    capture_output=True,
    text=True,
)
if result.returncode == 0:
    print("✅ Push exitoso a GitHub. Railway redesplegará automáticamente.")
    print(result.stdout)
else:
    print("❌ Error en el push:")
    print(result.stderr)
