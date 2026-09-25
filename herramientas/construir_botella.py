"""Construye el mod del juego de la botella a partir de los dos paquetes originales.

Uso:
  python3 herramientas/construir_botella.py Love4Sims_Spin_The_Bottle_Animation.package \\
      Bottle_MESH.package botella/

Crea en la carpeta de salida:
  - Jennikita_JuegoBotella.package: botella, animaciones, tuning y textos.
  - jennikita_botella.ts4script: el script, compilado con Python 3.7.

Python 3.7 hace falta para compilar el script (es la versión del juego). Se busca
como "python3.7" o en la variable de entorno PYTHON37.
"""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iconos_dst import leer_paquete, escribir_paquete, png_a_dst5, ZLIB  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = os.path.join(RAIZ, 'botella', 'fuentes')

CLIP, CLIP_CABECERA, ASM, ANIMACION, INTERACCION = 0x6B20C4F3, 0xBC4A5044, 0x02D5DF13, 0xEE17C6AD, 0xE882D22F
LOOT, BUFF, OBJETO, STBL, SNIPPET_POSE, IMAGEN = 0x0C772E27, 0x6017E896, 0xB61DE6B4, 0x220557DA, 0x7DF2169C, 0x00B2D882
TIPO_TUNING = {'object': OBJETO, 'buff': BUFF, 'action': LOOT, 'interaction': INTERACCION, 'animation': ANIMACION}

# Tuning del paquete de la botella que se sustituye por el de botella/fuentes.
TIPOS_SUSTITUIDOS = {INTERACCION, ASM, ANIMACION, LOOT, STBL, OBJETO, BUFF}

PREFIJO_POSES = 'Love4Sims:PosePack_202501031433083408_'
# Clips con desplazamiento del hueso raíz: se centran y se renombran para no
# chocar con el pack de poses original si también está instalado.
CLIPS_CENTRADOS = {
    'set_1': 'Girar',
    'set_4': 'BesoA_Preparar',
    'set_7': 'BesoA_Besar',
    'set_5': 'BesoB_Preparar',
    'set_6': 'BesoB_Besar',
}
# Iconos del pack de Love4Sims que usan las interacciones de la cola del Sim.
ICONOS = {0x6D21261B31458EBB, 0x8685C4A352B0A407, 0x449152D865C905EF,
          0x69922336B8917F78, 0x2042072F05FB1C99}

# Textura principal de la botella (DST1 512x512); se sustituye por fuentes/texturas/Botella_Difusa.png.
DIFUSA = 0xA4056A7926B07DAE

ESPANOL = 0x13
ROOT_BIND = 0x57884BB9  # b__ROOT_bind__
MIRANDO_AL_FRENTE = (0.5, 0.5, 0.5, 0.5)


def fnv32(texto):
    h = 0x811C9DC5
    for c in texto.lower().encode('utf-8'):
        h = ((h * 0x01000193) & 0xFFFFFFFF) ^ c
    return h


def fnv64(texto):
    h = 0xCBF29CE484222325
    for c in texto.lower().encode('utf-8'):
        h = ((h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF) ^ c
    return h


def id_tuning(nombre):
    return fnv64(nombre) | (1 << 63)


def nombre_clip(etiqueta):
    """Nombre nuevo con la misma longitud que el original, para no mover offsets."""
    return ('Jennikita:Botella_L4S_' + etiqueta).ljust(len(PREFIJO_POSES + 'set_1'), '_')


# --- Clips -------------------------------------------------------------------

def centrar_raiz(d):
    """Deja b__ROOT_bind__ en el origen y mirando al frente, conservando la altura."""
    d = bytearray(d)
    base = d.find(b'_pilC3S_')
    canales, = struct.unpack_from('<I', d, base + 24)
    tabla, = struct.unpack_from('<I', d, base + 32)
    for k in range(canales):
        h = base + tabla + 20 * k
        off, hueso, o, s, fotogramas, tipo, _ = struct.unpack_from('<IIffHBB', d, h)
        if hueso != ROOT_BIND:
            continue
        p = base + off
        if tipo == 20:  # rotación, 4 x 12 bits
            struct.pack_into('<ff', d, h + 8, 0.0, 1.0)
            for _ in range(fotogramas):
                banderas, = struct.unpack_from('<H', d, p + 2)
                struct.pack_into('<H4H', d, p + 2, banderas & ~0xF,
                                 *[round(c * 4095) for c in MIRANDO_AL_FRENTE])
                p += 12
        elif tipo == 18:  # posición, 3 x 10 bits
            valores = []
            q = p
            for _ in range(fotogramas):
                banderas, u = struct.unpack_from('<HI', d, q + 2)
                valores.append([o + s * ((-1 if banderas >> j & 1 else 1) * ((u >> (10 * j)) & 0x3FF) / 1023)
                                for j in range(3)])
                q += 8
            x0, z0 = valores[0][0], valores[0][2]
            valores = [[x - x0, y, z - z0] for x, y, z in valores]
            todos = [c for v in valores for c in v]
            no, ns = (max(todos) + min(todos)) / 2, max((max(todos) - min(todos)) / 2, 1e-4)
            struct.pack_into('<ff', d, h + 8, no, ns)
            q = p
            for v in valores:
                banderas, = struct.unpack_from('<H', d, q + 2)
                banderas &= ~0x7
                u = 0
                for j, c in enumerate(v):
                    n = max(-1.0, min(1.0, (c - no) / ns))
                    if n < 0:
                        banderas |= 1 << j
                    u |= round(abs(n) * 1023) << (10 * j)
                struct.pack_into('<HI', d, q + 2, banderas, u)
                q += 8
        else:
            raise ValueError('Canal del hueso raíz con formato inesperado: %d' % tipo)
    return bytes(d)


def recurso(t, g, instancia, datos):
    return dict(t=t, g=g, ih=instancia >> 32, il=instancia & 0xFFFFFFFF,
                raw=zlib.compress(datos, 9), ms=len(datos), comp=ZLIB)


def clips(recursos):
    salida = []
    for r in recursos:
        if r['t'] not in (CLIP, CLIP_CABECERA):
            continue
        datos = r['data']
        viejo = re.search(rb'Love4Sims:PosePack_202501031433083408_(set_\d)', datos)
        etiqueta = CLIPS_CENTRADOS.get(viejo.group(1).decode())
        if etiqueta is None:
            salida.append(r)
            continue
        nuevo = nombre_clip(etiqueta)
        if r['t'] == CLIP:
            datos = centrar_raiz(datos)
        datos = datos.replace(viejo.group(0), nuevo.encode())
        salida.append(recurso(r['t'], r['g'], fnv64(nuevo), datos))
    return salida


# --- Tuning y textos ---------------------------------------------------------

def cargar_textos():
    textos = json.load(open(os.path.join(FUENTES, 'textos.json'), encoding='utf-8'))
    claves = {}
    for clave, valor in textos.items():
        if clave.startswith('_'):
            continue
        fija = int(valor[2], 16) if len(valor) > 2 else fnv32('Jennikita:Botella:' + clave)
        claves[clave] = (fija, valor[0], valor[1])
    return claves


def rellenar(xml, textos):
    def sustituir(m):
        tipo, valor = m.group(1), m.group(2)
        if tipo == 'id':
            return str(id_tuning(valor))
        if tipo == 'asm':
            return '02d5df13:00000000:%016x' % id_tuning(valor)
        if tipo == 'str':
            return '0x%08X' % textos[valor][0]
        if tipo == 'clip':
            return nombre_clip(valor)
        if tipo == 'icono':
            return '00b2d882:00000000:%016x' % id_tuning(valor)
        raise ValueError(m.group(0))
    xml = re.sub(r'\{\{(\w+):([^}]+)\}\}', sustituir, xml)
    if '{{' in xml:
        raise ValueError('Quedan marcas sin sustituir')
    return xml


def tuning(textos):
    salida = []
    for carpeta in ('asm', 'animaciones', 'interacciones', 'otros'):
        for nombre in sorted(os.listdir(os.path.join(FUENTES, carpeta))):
            xml = rellenar(open(os.path.join(FUENTES, carpeta, nombre), encoding='utf-8').read(), textos)
            if carpeta == 'asm':
                tipo = ASM
                instancia = id_tuning(re.search(r'<ASM name="([^"]+)"', xml).group(1))
            else:
                cab = re.search(r'<I c="[^"]+" i="([^"]+)" m="[^"]+" n="[^"]+" s="(\d+)"', xml)
                tipo, instancia = TIPO_TUNING[cab.group(1)], int(cab.group(2))
            salida.append(recurso(tipo, 0, instancia, xml.encode('utf-8')))
    return salida


def iconos_propios():
    """Iconos del menú dibujados para el mod (PNG en fuentes/iconos, se pasan a DST)."""
    carpeta = os.path.join(FUENTES, 'iconos')
    salida = []
    for archivo in sorted(os.listdir(carpeta)):
        nombre = os.path.splitext(archivo)[0].replace('_Botella_', ':Botella_', 1)
        png = open(os.path.join(carpeta, archivo), 'rb').read()
        salida.append(recurso(IMAGEN, 0, id_tuning(nombre), png_a_dst5(png)))
    return salida


def textura_botella(originales):
    """La textura de la botella con la foto pintada encima (ver texturizar_botella.py)."""
    ruta = os.path.join(FUENTES, 'texturas', 'Botella_Difusa.png')
    original = next(r for r in originales if r['t'] == IMAGEN and ((r['ih'] << 32) | r['il']) == DIFUSA)
    return recurso(IMAGEN, original['g'], DIFUSA, png_a_dst5(open(ruta, 'rb').read(), b'DST1'))


def tabla_textos(entradas):
    cuerpo = bytearray()
    total = 0
    for clave, texto in entradas:
        b = texto.encode('utf-8')
        cuerpo += struct.pack('<IBH', clave, 0, len(b)) + b
        total += len(b) + 1
    return b'STBL' + struct.pack('<HBQHI', 5, 0, len(entradas), 0, total) + bytes(cuerpo)


def tablas_textos(textos, originales):
    salida = []
    for r in originales:
        idioma = r['ih'] >> 24
        entradas = [(c, es if idioma == ESPANOL else en) for c, es, en in textos.values()]
        salida.append(recurso(STBL, r['g'], (r['ih'] << 32) | r['il'], tabla_textos(entradas)))
    return salida


# --- Script ------------------------------------------------------------------

def compilar_script(salida):
    python37 = os.environ.get('PYTHON37', 'python3.7')
    fuente = os.path.join(FUENTES, 'jennikita_botella.py')
    with tempfile.TemporaryDirectory() as tmp:
        pyc = os.path.join(tmp, 'jennikita_botella.pyc')
        subprocess.run([python37, '-c', 'import py_compile, sys; py_compile.compile(sys.argv[1], sys.argv[2], '
                        'dfile="jennikita_botella.py", doraise=True)', fuente, pyc], check=True)
        with zipfile.ZipFile(os.path.join(salida, 'jennikita_botella.ts4script'), 'w', zipfile.ZIP_STORED) as z:
            z.write(pyc, 'jennikita_botella.pyc')


def main(animaciones, botella, salida):
    _, rec_anim = leer_paquete(animaciones)
    cabecera, rec_botella = leer_paquete(botella)
    textos = cargar_textos()

    recursos = [r for r in rec_botella if r['t'] not in TIPOS_SUSTITUIDOS
                and not (r['t'] == IMAGEN and ((r['ih'] << 32) | r['il']) == DIFUSA)]
    recursos.append(textura_botella(rec_botella))
    recursos += clips(rec_anim)
    recursos += [r for r in rec_anim if r['t'] == IMAGEN and ((r['ih'] << 32) | r['il']) in ICONOS]
    recursos += iconos_propios()
    recursos += tuning(textos)
    recursos += tablas_textos(textos, [r for r in rec_botella if r['t'] == STBL])

    claves = [(r['t'], r['g'], r['ih'], r['il']) for r in recursos]
    if len(claves) != len(set(claves)):
        raise ValueError('Hay recursos repetidos')
    os.makedirs(salida, exist_ok=True)
    escribir_paquete(os.path.join(salida, 'Jennikita_JuegoBotella.package'), cabecera, recursos)
    compilar_script(salida)
    print('%d recursos en Jennikita_JuegoBotella.package' % len(recursos))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
