"""Convierte a DST5 los iconos PNG de un .package de Los Sims 4.

Cada imagen PNG (2F7D0004) pasa a imagen DST5 (00B2D882, grupo 0, misma
instancia) con todos sus mipmaps, y las referencias a ella en el XML de
tuning se cambian para que apunten al DST. El resto de recursos se copia
tal cual.

Uso: python3 herramientas/iconos_dst.py entrada.package salida.package
Necesita Pillow y numpy (pip install pillow numpy).
"""
import io
import struct
import sys
import zlib

import numpy as np
from PIL import Image

TIPO_PNG = 0x2F7D0004
TIPO_DST = 0x00B2D882
ZLIB = 0x5A42


# --- Paquete DBPF ----------------------------------------------------------

def leer_paquete(ruta):
    d = open(ruta, 'rb').read()
    if d[:4] != b'DBPF':
        raise ValueError('%s no es un .package' % ruta)
    total = struct.unpack_from('<I', d, 36)[0]
    pos = struct.unpack_from('<I', d, 64)[0]
    flags = struct.unpack_from('<I', d, pos)[0]
    pos += 4
    fijos = {}
    for i, campo in enumerate(('t', 'g', 'ih')):
        if flags & (1 << i):
            fijos[campo] = struct.unpack_from('<I', d, pos)[0]
            pos += 4
    recursos = []
    for _ in range(total):
        r = {}
        for campo in ('t', 'g', 'ih'):
            if campo in fijos:
                r[campo] = fijos[campo]
            else:
                r[campo] = struct.unpack_from('<I', d, pos)[0]
                pos += 4
        r['il'], off, tam, r['ms'] = struct.unpack_from('<IIII', d, pos)
        pos += 16
        r['comp'] = 0
        if tam >> 31:
            r['comp'] = struct.unpack_from('<H', d, pos)[0]
            pos += 4
        r['raw'] = d[off:off + (tam & 0x7FFFFFFF)]
        if r['comp'] == ZLIB:
            r['data'] = zlib.decompress(r['raw'])
        elif r['comp'] == 0:
            r['data'] = r['raw']
        else:
            r['data'] = None
        recursos.append(r)
    return d[:96], recursos


def escribir_paquete(ruta, cabecera, recursos):
    out = bytearray(cabecera)
    offsets = []
    for r in recursos:
        offsets.append(len(out))
        out += r['raw']
    pos_indice = len(out)
    indice = bytearray(struct.pack('<I', 0))
    for r, off in zip(recursos, offsets):
        indice += struct.pack('<IIIIIIIHH', r['t'], r['g'], r['ih'], r['il'], off,
                              len(r['raw']) | 0x80000000, r['ms'], r['comp'], 1)
    out += indice
    struct.pack_into('<I', out, 36, len(recursos))
    struct.pack_into('<I', out, 44, len(indice))
    struct.pack_into('<I', out, 64, pos_indice)
    open(ruta, 'wb').write(out)


# --- DXT5 / DST5 ------------------------------------------------------------

def _a_565(c):
    c = np.clip(np.rint(c), 0, 255).astype(np.int32)
    return (((c[..., 0] * 31 + 127) // 255) << 11) | (((c[..., 1] * 63 + 127) // 255) << 5) \
        | ((c[..., 2] * 31 + 127) // 255)


def _de_565(v):
    return np.stack([((v >> 11) & 31) * 255 / 31, ((v >> 5) & 63) * 255 / 63,
                     (v & 31) * 255 / 31], -1)


def _empaquetar(indices, bits, nbytes):
    v = np.zeros(indices.shape[0], np.uint64)
    for p in range(16):
        v |= indices[:, p].astype(np.uint64) << np.uint64(bits * p)
    return np.stack([(v >> np.uint64(8 * k)) & np.uint64(255) for k in range(nbytes)], 1).astype(np.uint8)


def codificar_dxt5(img):
    """Devuelve las 4 partes de los bloques DXT5 por separado:
    extremos alfa, índices alfa, extremos color, índices color."""
    h, w, _ = img.shape
    bh, bw = (h + 3) // 4, (w + 3) // 4
    lienzo = np.zeros((bh * 4, bw * 4, 4))
    for y in range(bh * 4):  # mipmaps de menos de 4 px: se repite la imagen
        lienzo[y] = img[y % h][np.arange(bw * 4) % w]
    bloques = lienzo.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    n = bloques.shape[0]
    rgb, alfa = bloques[:, :, :3], bloques[:, :, 3]

    # Color: extremos sobre el eje principal de cada bloque.
    media = rgb.mean(1, keepdims=True)
    centrado = rgb - media
    cov = np.einsum('npi,npj->nij', centrado, centrado)
    eje = np.full((n, 3), 1 / np.sqrt(3))
    for _ in range(8):
        eje = np.einsum('nij,nj->ni', cov, eje)
        norma = np.linalg.norm(eje, axis=1, keepdims=True)
        eje = np.where(norma > 1e-9, eje / np.maximum(norma, 1e-9), 1 / np.sqrt(3))
    proy = np.einsum('npi,ni->np', centrado, eje)
    c0 = _a_565(media[:, 0] + eje * proy.max(1, keepdims=True))
    c1 = _a_565(media[:, 0] + eje * proy.min(1, keepdims=True))
    c0, c1 = np.maximum(c0, c1), np.minimum(c0, c1)  # c0 > c1: modo de 4 colores
    p0, p1 = _de_565(c0), _de_565(c1)
    paleta = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)
    ic = ((rgb[:, :, None] - paleta[:, None]) ** 2).sum(-1).argmin(-1)
    ic[c0 == c1] = 0

    # Alfa: modo de 8 niveles (a0 > a1).
    a0 = np.rint(alfa.max(1)).astype(np.int32)
    a1 = np.rint(alfa.min(1)).astype(np.int32)
    iguales = a0 == a1
    a0 = np.where(iguales & (a0 < 255), a0 + 1, a0)
    a1 = np.where(iguales & (a0 == a1), a1 - 1, a1)
    niveles = np.zeros((n, 8))
    niveles[:, 0], niveles[:, 1] = a0, a1
    for i in range(1, 7):
        niveles[:, 1 + i] = ((7 - i) * a0 + i * a1) // 7
    ia = np.abs(alfa[:, :, None] - niveles[:, None]).argmin(-1)

    return (np.stack([a0, a1], 1).astype(np.uint8),
            _empaquetar(ia, 3, 6),
            np.stack([c0 & 255, c0 >> 8, c1 & 255, c1 >> 8], 1).astype(np.uint8),
            _empaquetar(ic, 2, 4))


def png_a_dst5(png, formato=b'DST5'):
    """PNG -> DST5 (con alfa) o DST1 (sin alfa, la mitad de tamaño), con mipmaps."""
    im = Image.open(io.BytesIO(png)).convert('RGBA')
    w, h = im.size
    niveles, cw, ch = [], w, h
    while True:
        nivel = im if (cw, ch) == (w, h) else im.resize((cw, ch), Image.LANCZOS)
        niveles.append(codificar_dxt5(np.asarray(nivel, dtype=np.float64)))
        if cw == 1 and ch == 1:
            break
        cw, ch = max(1, cw // 2), max(1, ch // 2)
    # Los bloques de toda la cadena de mipmaps van separados en tiras.
    # DST5: extremos alfa, extremos color, índices alfa, índices color.
    # DST1: extremos color, índices color.
    tiras = (2, 3) if formato == b'DST1' else (0, 2, 1, 3)
    cuerpo = b''.join(np.concatenate([n[k] for n in niveles]).tobytes() for k in tiras)
    cab = bytearray(128)
    struct.pack_into('<4sIIIIIII', cab, 0, b'DDS ', 124, 0x21007, h, w, 0, 1, len(niveles))
    struct.pack_into('<II4s', cab, 76, 32, 4, formato)
    struct.pack_into('<I', cab, 108, 0x401008)
    return bytes(cab) + cuerpo


# --- Programa ---------------------------------------------------------------

def main(entrada, salida):
    cabecera, recursos = leer_paquete(entrada)
    nuevos = []
    for r in recursos:
        if r['t'] == TIPO_PNG:
            dst = png_a_dst5(r['data'])
            nuevos.append(dict(t=TIPO_DST, g=0, ih=r['ih'], il=r['il'],
                               raw=zlib.compress(dst, 9), ms=len(dst), comp=ZLIB))
            print('Icono %08X%08X: PNG -> DST5' % (r['ih'], r['il']))
            continue
        if r['data'] and r['data'].startswith(b'<?xml'):
            xml = r['data'].decode('utf-8')
            nuevo = xml.replace('2f7d0004:00000000:', '00b2d882:00000000:')
            if nuevo != xml:
                datos = nuevo.encode('utf-8')
                r = dict(r, raw=zlib.compress(datos, 9), ms=len(datos), comp=ZLIB)
                print('Referencias al icono actualizadas en %08X:%08X%08X' % (r['t'], r['ih'], r['il']))
        nuevos.append(r)
    escribir_paquete(salida, cabecera, nuevos)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
