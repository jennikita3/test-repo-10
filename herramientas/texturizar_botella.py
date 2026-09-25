"""Pinta la foto de una botella sobre la zona de la textura que usa el modelo de la botella.

Uso:
  python3 herramientas/texturizar_botella.py Bottle_MESH.package foto.png botella/fuentes/texturas/Botella_Difusa.png

La foto tiene que ser una botella de frente, derecha y sobre fondo blanco o transparente.
Se reparte por tramos para que no se deforme: el cuello de la foto va al cuello del
modelo, los hombros a los hombros y el cuerpo (con la etiqueta) al cuerpo. El resto
de la textura se queda como estaba. construir_botella.py convierte el PNG a DST.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iconos_dst import leer_paquete  # noqa: E402

MODELO = 0x01D10F34
IMAGEN = 0x00B2D882
DIFUSA = 0xA4056A7926B07DAE
# Alturas del modelo (metros) donde empiezan el cuerpo, los hombros y el cuello, y la punta.
ALTURAS_MODELO = (0.0, 0.222, 0.264, 0.368)
MARGEN = 2  # píxeles de más alrededor de la zona usada, para que no se vean costuras
BORDE_FOTO = 2  # píxeles que se ignoran en los bordes de la botella de la foto (antialias con el fondo)


def decodificar_dst(d):
    """Decodifica la primera imagen de un DST1 o DST5 (solo lo que hace falta aquí)."""
    alto, ancho = int.from_bytes(d[12:16], 'little'), int.from_bytes(d[16:20], 'little')
    cuerpo, bloques = d[128:], (ancho // 4) * (alto // 4)
    if d[84:88] != b'DST1':
        raise ValueError('Se esperaba una textura DST1')
    n = len(cuerpo) // 8
    ext = np.frombuffer(cuerpo[:bloques * 4], np.uint8).reshape(-1, 4).astype(np.int32)
    ind = np.frombuffer(cuerpo[n * 4:n * 4 + bloques * 4], np.uint8).reshape(-1, 4).astype(np.int64)
    c0, c1 = ext[:, 0] | ext[:, 1] << 8, ext[:, 2] | ext[:, 3] << 8
    idx = ind[:, 0] | ind[:, 1] << 8 | ind[:, 2] << 16 | ind[:, 3] << 24

    def rgb(c):
        return np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], -1)
    p0, p1 = rgb(c0), rgb(c1)
    cuatro = (c0 > c1)[:, None]
    pal = np.stack([p0, p1, np.where(cuatro, (2 * p0 + p1) // 3, (p0 + p1) // 2),
                    np.where(cuatro, (p0 + 2 * p1) // 3, 0)], 1)
    px = np.stack([pal[np.arange(len(idx)), idx >> (2 * k) & 3] for k in range(16)], 1)
    return px.reshape(alto // 4, ancho // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(alto, ancho, 3).astype(np.uint8)


def malla(d):
    """Posiciones y UV del modelo principal (primer VBUF con formato VRTF de 32 bytes)."""
    vb = d.find(b'VBUF', d.find(b'VRTF'))
    ib = d.find(b'IBUF', vb)
    n = (ib - vb - 16) // 32
    v = np.frombuffer(d[vb + 16:vb + 16 + n * 32], np.uint8).reshape(n, 32)
    pos = v[:, 0:8].copy().view('<i2').reshape(n, 4)[:, :3] / 32767.0
    uv = v[:, 12:16].copy().view('<i2').reshape(n, 2) / 32767.0
    fin = d.find(b'SKIN', ib)
    indices = np.cumsum(np.frombuffer(d[ib + 16:fin], '<i2').astype(int))  # índices diferenciales
    return pos, uv, indices.reshape(-1, 3)


def perfil_foto(foto):
    a = np.asarray(foto.convert('RGBA')).astype(int)
    botella = (a[:, :, :3].min(2) <= 235) & (a[:, :, 3] >= 20)
    filas = np.nonzero(botella.sum(1) > 2)[0]
    izq = np.full(a.shape[0], -1)
    der = np.full(a.shape[0], -1)
    for y in filas:
        xs = np.nonzero(botella[y])[0]
        izq[y], der[y] = xs.min(), xs.max()
    arriba = filas.min() + BORDE_FOTO
    ancho = der - izq + 1
    maximo = ancho[filas].max()
    # La base: última fila ancha que todavía es oscura (debajo suele haber un reflejo claro).
    brillo = [a[y, izq[y]:der[y] + 1, :3].mean() if der[y] >= 0 else 255 for y in range(a.shape[0])]
    anchas = [y for y in filas if ancho[y] >= 0.9 * maximo and brillo[y] < 120]
    abajo = max(anchas) if anchas else filas.max()
    hay = der >= 0
    izq[hay] += BORDE_FOTO
    der[hay] -= BORDE_FOTO
    ancho = der - izq + 1
    maximo = ancho[filas].max()
    cuello = np.median(ancho[arriba:arriba + (abajo - arriba) // 5])
    fin_cuello = next(y for y in range(arriba, abajo) if ancho[y] > 1.25 * cuello)
    inicio_cuerpo = next(y for y in range(fin_cuello, abajo) if ancho[y] >= 0.97 * maximo)
    return a, izq, der, (abajo, inicio_cuerpo, fin_cuello, arriba)


def main(paquete, foto_ruta, salida):
    _, recursos = leer_paquete(paquete)
    modelo = next(r for r in recursos if r['t'] == MODELO and r['g'] == 0)['data']
    difusa = next(r for r in recursos if r['t'] == IMAGEN and (r['ih'] << 32 | r['il']) == DIFUSA)['data']
    textura = decodificar_dst(difusa)
    alto, ancho = textura.shape[:2]
    pos, uv, tris = malla(modelo)

    # Zona de la textura que usa el modelo.
    zona = Image.new('L', (ancho, alto), 0)
    dibujo = ImageDraw.Draw(zona)
    for t in tris:
        dibujo.polygon([(uv[k, 0] * ancho, uv[k, 1] * alto) for k in t], fill=255)
    zona = np.asarray(zona) > 0
    filas_zona = np.nonzero(zona.any(1))[0]

    # Fila de la textura -> altura en el modelo (v baja cuando la altura sube).
    orden = np.argsort(uv[:, 1])
    v_px, altura = uv[orden, 1] * alto, pos[orden, 1]
    foto = Image.open(foto_ruta)
    a, izq, der, filas_foto = perfil_foto(foto)

    nueva = textura.copy()
    for y in range(max(0, filas_zona.min() - MARGEN), min(alto, filas_zona.max() + MARGEN + 1)):
        cerca = zona[max(0, y - MARGEN):y + MARGEN + 1].any(0)
        xs = np.nonzero(cerca)[0]
        if len(xs) == 0:
            continue
        h = np.interp(y + 0.5, v_px, altura)
        fy = int(round(np.interp(h, ALTURAS_MODELO, filas_foto)))
        if izq[fy] < 0:
            continue
        x0, x1 = xs.min(), xs.max()
        fx = izq[fy] + (xs - x0 + 0.5) / max(1, x1 - x0 + 1) * (der[fy] - izq[fy] + 1)
        fx = np.clip(fx.astype(int), izq[fy], der[fy])
        nueva[y, xs] = a[fy, fx, :3]

    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    Image.fromarray(nueva).save(salida)
    print('Textura guardada en %s (filas de la foto: base %d, cuerpo %d, cuello %d, punta %d)'
          % ((salida,) + tuple(int(f) for f in filas_foto)))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
