#!/usr/bin/env python3
"""Traduce al español el mod "When Nature Calls" de Tinycoffee (Los Sims 4).

Uso:
    python3 herramientas/traducir.py ORIGINAL.package SALIDA.package

Toma la tabla de textos en inglés (STBL con prefijo de idioma 0x00) y escribe
su versión en español en la tabla con prefijo 0x13, que es la que carga el
juego cuando está en español. El resto de recursos del .package se copia sin
tocar. Si una versión nueva del mod añade textos que no están en TRADUCCIONES,
se dejan en inglés y se avisa por pantalla.
"""
import struct
import sys
import zlib

STBL_TYPE = 0x220557DA
LOCALE_EN = 0x00
LOCALE_ES = 0x13

# Clave del texto -> (inglés original, traducción al español)
TRADUCCIONES = {
    # Interacciones (menú circular)
    0xB36F7599: ("Pee On Tree", "Hacer pis en un árbol"),
    0x217FD8C6: ("Poo On Tree", "Hacer caca junto a un árbol"),
    0x777EC0A4: ("Heckle The Pooper", "Abuchear al que hace caca"),
    0x76488323: ("Heckle Sim Peeing On Tree", "Abuchear al Sim que hace pis en el árbol"),
    # Objeto
    0x411C75BD: ("Sim Turd", "Caca de Sim"),
    0xD19623C2: ("A Sim left this turd here. What an animal!",
                 "Un Sim dejó esta caca aquí. ¡Qué animal!"),
    # Estados de ánimo: nombre y descripción
    0x9F9D150D: ("Nature's Relief", "Alivio natural"),
    0xED229498: ("This sim couldn't stop what already started. Letting nature take its course was the only way. Good thing this tree was here!",
                 "Este Sim no pudo detener lo que ya había empezado. Dejar que la naturaleza siguiera su curso era la única opción. ¡Menos mal que este árbol estaba aquí!"),
    0xE8E469FD: ("Not So Fresh", "Frescura dudosa"),
    0x7AEF4EC8: ("This Sim isn't feeling so fresh after using this tree to relieve themselves. If only there was tissue....",
                 "A este Sim le falta frescura después de usar este árbol para hacer sus necesidades. Si al menos hubiera papel higiénico..."),
    0x1F79F2D9: ("Really? On a tree? ", "¿En serio? ¿En un árbol?"),
    0x3DE8CF44: ("Jeez, are you kidding? They really couldn't just wait? Where is the decorum?",
                 "¡Madre mía! ¿Es una broma? ¿De verdad no podía esperar? ¿Dónde está el decoro?"),
    0xF09F54DB: ("You Know What...", "Lo que hay que ver..."),
    0x00E0E2B2: ("Is this who we are? Is this what we represent??!",
                 "¿Esto es lo que somos? ¡¿Esto es lo que representamos?!"),
    0x072CBD54: ("Eeeyuck!", "¡Puaaaj!"),
    0xA5500CFB: ("Ewww, Why am I picking this up?! How did we get here?????",
                 "¡Qué asco! ¡¿Por qué estoy recogiendo esto?! ¿¿¿Cómo hemos llegado hasta aquí???"),
    0xA5804A73: ("Stepped On A Turd", "Pisó una caca"),
    0xEFB9A58A: ("That definitely wasn't mud....", "Está claro que eso no era barro..."),
    # Motivos de los estados de ánimo
    0x05EF47E9: ("(From Relieving Self Outside)", "(Por hacer sus necesidades al aire libre)"),
    0x768E4B79: ("(From Pooping Outside)", "(Por hacer caca al aire libre)"),
    0x0E87DAC5: ("(From Seeing A Sim Pee Outside)", "(Por ver a un Sim haciendo pis al aire libre)"),
    0xDC6723DB: ("(From Seeing A Sim Poop Outside)", "(Por ver a un Sim haciendo caca al aire libre)"),
    0xB368522A: ("(From Picking Up A Sim Turd)", "(Por recoger una caca de Sim)"),
    0xD7B41B23: ("(From Stepping On A Sim Turd)", "(Por pisar una caca de Sim)"),
}


# --- Formato DBPF 2.1 (.package) ---------------------------------------------

class Resource:
    def __init__(self, rtype, group, instance, raw, compression, mem_size, committed):
        self.type = rtype
        self.group = group
        self.instance = instance
        self.raw = raw  # bytes tal y como están guardados en el archivo
        self.compression = compression
        self.mem_size = mem_size
        self.committed = committed

    def data(self):
        if self.compression == 0x0000:
            return self.raw
        if self.compression == 0x5A42:
            return zlib.decompress(self.raw)
        raise ValueError("compresión no soportada %#06x en %s" % (self.compression, self.tgi()))

    def set_data(self, data):
        self.raw = zlib.compress(data, 9)
        self.compression = 0x5A42
        self.mem_size = len(data)

    def tgi(self):
        return "%08X:%08X:%016X" % (self.type, self.group, self.instance)


def read_package(path):
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != b"DBPF" or struct.unpack_from("<II", buf, 4) != (2, 1):
        raise ValueError("%s no es un .package de Los Sims 4" % path)
    count = struct.unpack_from("<I", buf, 0x24)[0]
    pos = struct.unpack_from("<Q", buf, 0x40)[0] or struct.unpack_from("<I", buf, 0x28)[0]
    flags = struct.unpack_from("<I", buf, pos)[0]
    pos += 4
    constants = []
    for bit in (1, 2, 4):  # tipo, grupo e instancia alta pueden ser constantes
        if flags & bit:
            constants.append(struct.unpack_from("<I", buf, pos)[0])
            pos += 4
        else:
            constants.append(None)
    resources = []
    for _ in range(count):
        tgi = []
        for const in constants:
            if const is None:
                tgi.append(struct.unpack_from("<I", buf, pos)[0])
                pos += 4
            else:
                tgi.append(const)
        instance_lo, offset, file_size, mem_size = struct.unpack_from("<IIII", buf, pos)
        pos += 16
        compression, committed = 0, 1
        if file_size & 0x80000000:
            compression, committed = struct.unpack_from("<HH", buf, pos)
            pos += 4
        file_size &= 0x7FFFFFFF
        resources.append(Resource(tgi[0], tgi[1], (tgi[2] << 32) | instance_lo,
                                  buf[offset:offset + file_size], compression, mem_size, committed))
    return buf[:96], resources


def write_package(path, header, resources):
    out = bytearray(header)
    index = bytearray(struct.pack("<I", 0))
    for res in resources:
        index += struct.pack("<IIIIIIIHH", res.type, res.group, res.instance >> 32,
                             res.instance & 0xFFFFFFFF, len(out), len(res.raw) | 0x80000000,
                             res.mem_size, res.compression, res.committed)
        out += res.raw
    struct.pack_into("<IIII", out, 0x24, len(resources), 0, len(index), 0)
    struct.pack_into("<IQ", out, 0x3C, 3, len(out))
    out += index
    with open(path, "wb") as f:
        f.write(out)


# --- Tablas de textos (STBL) -------------------------------------------------

def parse_stbl(data):
    if data[:4] != b"STBL":
        raise ValueError("no es una tabla STBL")
    version, compressed, count = struct.unpack_from("<HBQ", data, 4)
    pos = 21
    entries = []
    for _ in range(count):
        key, flags, length = struct.unpack_from("<IBH", data, pos)
        pos += 7
        entries.append((key, flags, data[pos:pos + length].decode("utf-8")))
        pos += length
    return version, compressed, data[15:17], entries


def build_stbl(version, compressed, reserved, entries):
    body = bytearray()
    for key, flags, text in entries:
        encoded = text.encode("utf-8")
        body += struct.pack("<IBH", key, flags, len(encoded)) + encoded
    total = sum(len(text.encode("utf-8")) + 1 for _, _, text in entries)
    return (b"STBL" + struct.pack("<HBQ", version, compressed, len(entries))
            + reserved + struct.pack("<I", total) + bytes(body))


def translate(src, dst):
    header, resources = read_package(src)
    by_tgi = {(r.type, r.group, r.instance): r for r in resources}
    english = [r for r in resources if r.type == STBL_TYPE and r.instance >> 56 == LOCALE_EN]
    if not english:
        raise SystemExit("El mod no tiene textos en inglés que traducir.")

    missing, outdated, used = [], [], set()
    for en in english:
        version, compressed, reserved, entries = parse_stbl(en.data())
        spanish_entries = []
        for key, flags, text in entries:
            if key in TRADUCCIONES:
                original, translation = TRADUCCIONES[key]
                if original != text:
                    outdated.append((key, original, text))
                spanish_entries.append((key, flags, translation))
                used.add(key)
            else:
                missing.append((key, text))
                spanish_entries.append((key, flags, text))

        es_instance = (LOCALE_ES << 56) | (en.instance & 0x00FFFFFFFFFFFFFF)
        es = by_tgi.get((STBL_TYPE, en.group, es_instance))
        if es is None:
            es = Resource(STBL_TYPE, en.group, es_instance, b"", 0, 0, en.committed)
            resources.append(es)
        es.set_data(build_stbl(version, compressed, reserved, spanish_entries))

    write_package(dst, header, resources)

    print("Traducidos %d textos -> %s" % (len(used), dst))
    for key, original, text in outdated:
        print("AVISO: el texto %08X ha cambiado en el mod (antes %r, ahora %r); revisa la traducción."
              % (key, original, text))
    for key, text in missing:
        print("AVISO: texto nuevo sin traducir %08X, queda en inglés: %r" % (key, text))
    for key in sorted(set(TRADUCCIONES) - used):
        print("AVISO: el mod ya no usa el texto %08X (%r)." % (key, TRADUCCIONES[key][0]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    translate(sys.argv[1], sys.argv[2])
