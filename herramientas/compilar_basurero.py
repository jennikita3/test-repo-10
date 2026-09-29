#!/usr/bin/env python3.7
"""Compila el script del camión de la basura y crea el .ts4script.

Uso (con Python 3.7, que es la versión que usa Los Sims 4):
    python3.7 herramientas/compilar_basurero.py

Lee camion_basura/jennikita_basura.py y escribe
camion_basura/Jennikita_CamionBasura.ts4script con el .pyc dentro.
"""
import os
import py_compile
import sys
import tempfile
import zipfile

if sys.version_info[:2] != (3, 7):
    raise SystemExit("Hay que compilarlo con Python 3.7 (el juego no carga .pyc de otras versiones).")

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "camion_basura")
FUENTE = os.path.join(CARPETA, "jennikita_basura.py")
SALIDA = os.path.join(CARPETA, "Jennikita_CamionBasura.ts4script")

with tempfile.TemporaryDirectory() as tmp:
    pyc = os.path.join(tmp, "jennikita_basura.pyc")
    py_compile.compile(FUENTE, cfile=pyc, dfile="jennikita_basura.py", doraise=True)
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_STORED) as z:
        z.write(pyc, "jennikita_basura.pyc")

print("Creado", os.path.normpath(SALIDA))
