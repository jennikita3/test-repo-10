#!/usr/bin/env python3
"""Monta el mod "Juego de la botella" de Jennikita (Los Sims 4).

Uso:
    python3 herramientas/construir_botella.py BASE.package [PYTHON37]

Toma BASE.package (la botella, la alfombra, los iconos, los textos...) y:
  - sustituye o añade el tuning de botella/fuente/tuning/ (un archivo por
    recurso, con el nombre TIPO_GRUPO_INSTANCIA.xml);
  - quita los recursos de la versión 1 que ya no se usan (las animaciones
    personalizadas de los Sims y sus interacciones);
  - escribe botella/Jennikita_JuegoBotella.package.

Si se indica PYTHON37 (la ruta a un Python 3.7, la versión del juego), también
compila botella/fuente/jennikita_botella.py y escribe
botella/jennikita_botella.ts4script.
"""
import os
import subprocess
import sys
import tempfile
import zipfile

from traducir import Resource, read_package, write_package

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, 'botella')
TUNING = os.path.join(CARPETA, 'fuente', 'tuning')
SCRIPT = os.path.join(CARPETA, 'fuente', 'jennikita_botella.py')
PAQUETE = os.path.join(CARPETA, 'Jennikita_JuegoBotella.package')
TS4SCRIPT = os.path.join(CARPETA, 'jennikita_botella.ts4script')

CLIP, CABECERA_CLIP, ASM, ANIMACION, INTERACCION = 0x6B20C4F3, 0xBC4A5044, 0x02D5DF13, 0xEE17C6AD, 0xE882D22F

# Recursos de la versión 1 que ya no se usan: animaciones de Love4Sims (los
# Sims usan ahora las del juego) y las interacciones que las ponían.
OBSOLETOS = {
    (CLIP, 0x1AFED2115FB9A8CF), (CABECERA_CLIP, 0x1AFED2115FB9A8CF),  # Botella_GirarSim
    (CLIP, 0x5E8AD1107922403F), (CABECERA_CLIP, 0x5E8AD1107922403F),  # Botella_Animar
    (CLIP, 0x91C8F12282B1CC09), (CABECERA_CLIP, 0x91C8F12282B1CC09),  # Botella_BesoA_Preparar
    (CLIP, 0x65035A115CFE906A), (CABECERA_CLIP, 0x65035A115CFE906A),  # Botella_BesoA_Besar
    (CLIP, 0x4860847B01DE51E6), (CABECERA_CLIP, 0x4860847B01DE51E6),  # Botella_BesoB_Preparar
    (CLIP, 0x251095CC950DAB81), (CABECERA_CLIP, 0x251095CC950DAB81),  # Botella_BesoB_Besar
    (CLIP, 0xE902E10FBDE300BB), (CABECERA_CLIP, 0xE902E10FBDE300BB),  # Botella_Rodillas
    (CLIP, 0xB29979BCB1101F1A), (CABECERA_CLIP, 0xB29979BCB1101F1A),  # Botella_Cruzado
    (ASM, 0xC04EDEE4E9DE2375),          # Botella_ASM_Sim
    (ANIMACION, 0xA10336E796A62240),    # Botella_Anim_Animar
    (ANIMACION, 0xB9861EDF792C386C),    # Botella_Anim_BesoA
    (ANIMACION, 0xB9861EDF792C386F),    # Botella_Anim_BesoB
    (ANIMACION, 0xB9AA2E71CAD3EA2A),    # Botella_Anim_Rodillas
    (ANIMACION, 0xF684364ACD7866B6),    # Botella_Anim_Cruzado
    (INTERACCION, 0xD9C2821AFD8DF887),  # Botella_Besar_A
    (INTERACCION, 0xD9C2821AFD8DF884),  # Botella_Besar_B
    (INTERACCION, 0xC1EBEE037488FE10),  # Botella_Esperar_A
    (INTERACCION, 0xC1EBEE037488FE13),  # Botella_Esperar_B
    (INTERACCION, 0xCDEF5A4939752B9B),  # Botella_Girar (menú)
    (INTERACCION, 0xD1C70DA42FE42ABA),  # Botella_Mixer_Cruzado
    (INTERACCION, 0xDEFB4F5B239A5A6E),  # Botella_Mixer_Rodillas
}


def construir_paquete(base):
    cabecera, recursos = read_package(base)
    quitados = [r for r in recursos if (r.type, r.instance) in OBSOLETOS]
    recursos = [r for r in recursos if (r.type, r.instance) not in OBSOLETOS]
    por_tgi = {(r.type, r.group, r.instance): r for r in recursos}
    nuevos, cambiados = 0, 0
    for nombre in sorted(os.listdir(TUNING)):
        if not nombre.endswith('.xml'):
            continue
        tipo, grupo, instancia = (int(parte, 16) for parte in nombre[:-4].split('_'))
        with open(os.path.join(TUNING, nombre), 'rb') as f:
            datos = f.read()
        recurso = por_tgi.get((tipo, grupo, instancia))
        if recurso is None:
            recurso = Resource(tipo, grupo, instancia, b'', 0, 0, 1)
            recursos.append(recurso)
            nuevos += 1
        elif recurso.data() == datos:
            continue
        else:
            cambiados += 1
        recurso.set_data(datos)
    write_package(PAQUETE, cabecera, recursos)
    print('%s: %d recursos (%d quitados, %d cambiados, %d nuevos)'
          % (os.path.relpath(PAQUETE, RAIZ), len(recursos), len(quitados), cambiados, nuevos))


def construir_script(python37):
    version = subprocess.check_output([python37, '-c', 'import sys; print(sys.version_info[:2])']).decode().strip()
    if version != '(3, 7)':
        raise SystemExit('%s no es Python 3.7 (es %s); el juego solo carga .pyc de Python 3.7.' % (python37, version))
    with tempfile.TemporaryDirectory() as carpeta:
        pyc = os.path.join(carpeta, 'jennikita_botella.pyc')
        subprocess.check_call([python37, '-c',
                               'import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], '
                               'dfile="jennikita_botella.py", doraise=True)', SCRIPT, pyc])
        with zipfile.ZipFile(TS4SCRIPT, 'w', zipfile.ZIP_STORED) as z:
            z.write(pyc, 'jennikita_botella.pyc')
    print('%s: compilado con Python 3.7' % os.path.relpath(TS4SCRIPT, RAIZ))


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    with open(SCRIPT, encoding='utf-8') as f:
        compile(f.read(), SCRIPT, 'exec')  # falla aquí si hay errores de sintaxis
    construir_paquete(sys.argv[1])
    if len(sys.argv) == 3:
        construir_script(sys.argv[2])
