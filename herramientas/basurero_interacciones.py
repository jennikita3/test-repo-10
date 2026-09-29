#!/usr/bin/env python3
"""Añade al mod del camión de la basura las interacciones con el basurero.

Uso:
    python3 herramientas/basurero_interacciones.py

Modifica camion_basura/Jennikita_CamionBasura.package y añade (o sustituye si ya están):
- «Saludar al basurero» y «Preguntar por el reciclaje»: interacciones que salen al
  hacer clic en el basurero. Lo que hacen está en el script (clases SaludarBasurero y
  PreguntarReciclaje de camion_basura/jennikita_basura.py).
- El estado de ánimo «Basurero simpático» (Feliz +1), con su SimData.
- Los textos, en todas las tablas de idioma del mod.
- Los iconos, a partir de camion_basura/icono_saludar.png y icono_reciclaje.png.
  Para cambiar un icono, sustituye el PNG y vuelve a ejecutar esto.

La SimData del estado de ánimo se copia de uno que funciona (el de «Alivio natural»
del mod de Tinycoffee que hay en este repositorio) y se le cambian el nombre, la
descripción, el icono y la intensidad.
"""
import io
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traducir import Resource, build_stbl, parse_stbl, read_package, write_package  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PAQUETE = os.path.join(RAIZ, "camion_basura", "Jennikita_CamionBasura.package")
PLANTILLA = os.path.join(RAIZ, "Tinycoffee_WhenNatureCalls.package")
PLANTILLA_SIMDATA = (0x545AC67A, 0x0017E8F6, 0x9F244597324DB4A5)

T_PNG, T_XML_INTERACCION, T_XML_BUFF, T_SIMDATA, T_STBL = 0x2F7D0004, 0xE882D22F, 0x6017E896, 0x545AC67A, 0x220557DA
GRUPO_SIMDATA_BUFF = 0x0017E8F6
TABLA_TEXTOS = 0x000887A665BAE36A  # sin el byte de idioma

MOOD_FELIZ = 14640
ICONO_SALUDAR = 0xEDF6FE9BAF97BC28
ICONO_RECICLAJE = 0x8DBC49D8296FCD1D


def fnv64(texto):
    h = 0xCBF29CE484222325
    for b in texto.lower().encode("utf-8"):
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h ^= b
    return h | (1 << 63)


def fnv32(texto):
    h = 0x811C9DC5
    for b in texto.lower().encode("utf-8"):
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= b
    return h


SALUDAR = "Jennikita:interaccion_SaludarBasurero"
RECICLAJE = "Jennikita:interaccion_PreguntarReciclaje"
BUFF = "Jennikita:buff_BasureroSimpatico"

TEXTOS = {
    fnv32("Jennikita:texto_SaludarBasurero"): "Saludar al basurero",
    fnv32("Jennikita:texto_PreguntarReciclaje"): "Preguntar por el reciclaje",
    fnv32("Jennikita:texto_BuffBasureroNombre"): "Basurero simpático",
    fnv32("Jennikita:texto_BuffBasureroDescripcion"): "El basurero ha devuelto el saludo con una sonrisa enorme. ¡Qué majo!",
}
K_SALUDAR, K_RECICLAJE, K_BUFF_NOMBRE, K_BUFF_DESC = TEXTOS


def xml_interaccion(clase, nombre, texto, icono):
    return """<?xml version="1.0" encoding="utf-8"?>
<I c="{clase}" i="interaction" m="jennikita_basura" n="{nombre}" s="{guid}">
  <V n="_icon" t="resource_key">
    <U n="resource_key">
      <T n="key">2f7d0004:00000000:{icono:016x}</T>
    </U>
  </V>
  <T n="allow_autonomous">False</T>
  <T n="display_name">0x{texto:08X}<!--{desc}--></T>
  <L n="interaction_category_tags">
    <E>Interaction_All</E>
  </L>
  <E n="target_type">TARGET</E>
</I>
""".format(clase=clase, nombre=nombre, guid=fnv64(nombre), icono=icono, texto=texto, desc=TEXTOS[texto])


def xml_buff():
    return """<?xml version="1.0" encoding="utf-8"?>
<I c="Buff" i="buff" m="buffs.buff" n="{nombre}" s="{guid}">
  <V n="_temporary_commodity_info" t="enabled">
    <U n="enabled">
      <L n="categories">
        <E>Happy_Buffs</E>
      </L>
      <T n="max_duration">240</T>
      <T n="persists">True</T>
    </U>
  </V>
  <T n="audio_sting_on_add" p="InGame\\Audio\\Stings\\sting_buff_gain.propx">39b2aa4a:00000000:8af8b916cf64c646</T>
  <T n="audio_sting_on_remove" p="InGame\\Audio\\Stings\\sting_buff_loss.propx">39b2aa4a:00000000:3bf33216a25546ea</T>
  <T n="buff_description">0x{desc:08X}<!--{desc_txt}--></T>
  <T n="buff_name">0x{nom:08X}<!--{nom_txt}--></T>
  <T n="icon">2F7D0004:00000000:{icono:016X}</T>
  <T n="mood_type">{mood}<!--Mood: Mood_Happy--></T>
  <T n="mood_weight">1</T>
  <T n="refresh_on_add">True</T>
  <T n="visible">True</T>
  <T n="show_timeout">True</T>
</I>
""".format(nombre=BUFF, guid=fnv64(BUFF), desc=K_BUFF_DESC, desc_txt=TEXTOS[K_BUFF_DESC], nom=K_BUFF_NOMBRE,
           nom_txt=TEXTOS[K_BUFF_NOMBRE], icono=ICONO_SALUDAR, mood=MOOD_FELIZ)


# --- SimData ----------------------------------------------------------------

def _rel(d, pos):
    v = struct.unpack_from("<i", d, pos)[0]
    return None if (v & 0xFFFFFFFF) == 0x80000000 else pos + v


def _columnas(d):
    """Devuelve (posición del nombre de la tabla, posición de su hash, {columna: posición del valor})."""
    th = _rel(d, 8)
    esquema = _rel(d, th + 8)
    fila = _rel(d, th + 20)
    cols = _rel(d, esquema + 16)
    n = struct.unpack_from("<I", d, esquema + 20)[0]
    res = {}
    for j in range(n):
        q = cols + 20 * j
        p = _rel(d, q)
        nombre = d[p:d.index(b"\0", p)].decode()
        res[nombre] = fila + struct.unpack_from("<I", d, q + 12)[0]
    return _rel(d, th), th + 4, res


def simdata_buff(plantilla):
    d = bytearray(plantilla)
    pos_nombre, pos_hash, col = _columnas(d)
    viejo = d[pos_nombre:d.index(b"\0", pos_nombre)].decode()
    nuevo = BUFF.split(":")[-1]
    assert len(nuevo) <= len(viejo)
    d[pos_nombre:pos_nombre + len(viejo)] = nuevo.encode().ljust(len(viejo), b"\0")
    h = struct.unpack_from("<I", d, pos_hash)[0]
    if h and h == fnv32(viejo):
        struct.pack_into("<I", d, pos_hash, fnv32(nuevo))
    struct.pack_into("<I", d, col["buff_name"], K_BUFF_NOMBRE)
    struct.pack_into("<I", d, col["buff_description"], K_BUFF_DESC)
    struct.pack_into("<QII", d, col["icon"], ICONO_SALUDAR, T_PNG, 0)
    struct.pack_into("<Q", d, col["mood_type"], MOOD_FELIZ)
    struct.pack_into("<i", d, col["mood_weight"], 1)
    return bytes(d)


def png(ruta):
    im = Image.open(ruta).convert("RGBA")
    if im.size != (128, 128):
        im = im.resize((128, 128), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main():
    cabecera, recursos = read_package(PAQUETE)
    por_tgi = {(r.type, r.group, r.instance): r for r in recursos}

    def poner(tipo, grupo, instancia, datos):
        r = por_tgi.get((tipo, grupo, instancia))
        if r is None:
            r = Resource(tipo, grupo, instancia, b"", 0, 0, 1)
            recursos.append(r)
            por_tgi[(tipo, grupo, instancia)] = r
        r.set_data(datos)

    _, plantilla = read_package(PLANTILLA)
    simdata = [r for r in plantilla if (r.type, r.group, r.instance) == PLANTILLA_SIMDATA][0].data()

    poner(T_XML_INTERACCION, 0, fnv64(SALUDAR),
          xml_interaccion("SaludarBasurero", SALUDAR, K_SALUDAR, ICONO_SALUDAR).encode())
    poner(T_XML_INTERACCION, 0, fnv64(RECICLAJE),
          xml_interaccion("PreguntarReciclaje", RECICLAJE, K_RECICLAJE, ICONO_RECICLAJE).encode())
    poner(T_XML_BUFF, 0, fnv64(BUFF), xml_buff().encode())
    poner(T_SIMDATA, GRUPO_SIMDATA_BUFF, fnv64(BUFF), simdata_buff(simdata))
    poner(T_PNG, 0, ICONO_SALUDAR, png(os.path.join(RAIZ, "camion_basura", "icono_saludar.png")))
    poner(T_PNG, 0, ICONO_RECICLAJE, png(os.path.join(RAIZ, "camion_basura", "icono_reciclaje.png")))

    tablas = [r for r in recursos if r.type == T_STBL and r.instance & 0x00FFFFFFFFFFFFFF == TABLA_TEXTOS]
    assert tablas, "no encuentro la tabla de textos del basurero"
    for r in tablas:
        version, comprimido, reservado, entradas = parse_stbl(r.data())
        entradas = [e for e in entradas if e[0] not in TEXTOS]
        entradas += [(k, 0, v) for k, v in TEXTOS.items()]
        r.set_data(build_stbl(version, comprimido, reservado, entradas))

    write_package(PAQUETE, cabecera, recursos)
    print("Interacciones añadidas a", os.path.normpath(PAQUETE))
    print("  INTERACCION_SALUDAR =", fnv64(SALUDAR))
    print("  INTERACCION_RECICLAJE =", fnv64(RECICLAJE))
    print("  BUFF_BASURERO_SIMPATICO =", fnv64(BUFF))
    print("  ICONO_RECICLAJE =", ICONO_RECICLAJE)


if __name__ == "__main__":
    main()
