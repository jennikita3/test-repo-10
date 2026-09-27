#!/usr/bin/env python3
"""Arregla las animaciones del Juego de la botella de Jennikita (Los Sims 4).

Uso:
    python3 juego_botella/herramientas/arreglar_paquete.py ORIGINAL.package SALIDA.package

ORIGINAL.package es el Jennikita_JuegoBotella.package de la v7 (el que dejaba
a los Sims invisibles). El script escribe una copia con estos cambios:

1. Clips (0x6B20C4F3 y sus cabeceras 0xBC4A5044):
   - Nombres sin dos puntos ni relleno de guiones bajos, al estilo de los
     clips que funcionan (Jennikita_Botella_Rodillas_x...). La instancia de
     cada clip es el FNV64 del nombre en minúsculas, como espera el juego.
   - Se quitan los dos eventos de plantilla que traían todos los clips (un
     sonido "vo_cas_trait_artlover" en el segundo 1000 y un evento tipo 19
     con banderas raras en el segundo 0).
   - El clip de la botella pierde las asignaciones de IK de Sim que tenía
     copiadas de la plantilla.
   Los datos de animación (huesos y fotogramas) no se tocan.
2. ASM (0x02D5DF13): reescritos con la misma estructura que los ASM que
   funcionan (sin el PostureManifest vacío, sin la variante UpperBody con
   <Reference>, selector por edad, estados de sentarse interrumpibles).
3. AnimationElement (0xEE17C6AD): sentarse, animar y besar terminan en el
   estado "exit", así la animación se cierra y el Sim vuelve a estar de pie
   cuando acaba. El giro no, para que la botella se quede apuntando al Sim
   elegido (si saliera del ASM volvería a su postura inicial).
4. Sentarse de rodillas / con las piernas cruzadas: pasan de "staging" con
   mixers a "looping_content", que repite la animación de sentado mientras
   dura la interacción. Los dos mixers dejan de usarse y se quitan.

El resto de recursos se copia sin tocar.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'herramientas'))
from traducir import read_package, write_package  # noqa: E402

CLIP = 0x6B20C4F3
CLIP_HEADER = 0xBC4A5044
ASM = 0x02D5DF13
ANIMATION = 0xEE17C6AD
INTERACTION = 0xE882D22F

# Nombre antiguo -> nombre nuevo de cada clip
CLIPS = {
    'Jennikita:Botella_Rodillas_________________': 'Jennikita_Botella_Rodillas_x',
    'Jennikita:Botella_Cruzado__________________': 'Jennikita_Botella_Cruzado_x',
    'Jennikita:Botella_Animar___________________': 'Jennikita_Botella_Animar_x',
    'Jennikita:Botella_BesoA_Preparar___________': 'Jennikita_Botella_BesoA_Preparar_x',
    'Jennikita:Botella_BesoA_Besar______________': 'Jennikita_Botella_BesoA_Besar_x',
    'Jennikita:Botella_BesoB_Preparar___________': 'Jennikita_Botella_BesoB_Preparar_x',
    'Jennikita:Botella_BesoB_Besar______________': 'Jennikita_Botella_BesoB_Besar_x',
    'Jennikita:Botella_GirarSim_________________': 'Jennikita_Botella_GirarSim_x',
    'Jennikita:Botella_GirarBotella_____________': 'Jennikita_Botella_GirarBotella_spinbottle',
}
CLIP_BOTELLA = 'Jennikita_Botella_GirarBotella_spinbottle'

ASM_SIM = 0xC04EDEE4E9DE2375
ASM_GIRAR = 0xD9865E61599F5563
ANIM_GIRAR = 0xA61750C2AAC203E5

# Estados del ASM de los Sims: (estado, clip, repeticiones, interrumpible)
ESTADOS_SIM = [
    ('Rodillas', 'Jennikita_Botella_Rodillas_x', 1, True),
    ('Cruzado', 'Jennikita_Botella_Cruzado_x', 1, True),
    ('Animar', 'Jennikita_Botella_Animar_x', 2, False),
    ('BesoA_Preparar', 'Jennikita_Botella_BesoA_Preparar_x', 1, False),
    ('BesoA_Besar', 'Jennikita_Botella_BesoA_Besar_x', 1, False),
    ('BesoB_Preparar', 'Jennikita_Botella_BesoB_Preparar_x', 1, False),
    ('BesoB_Besar', 'Jennikita_Botella_BesoB_Besar_x', 1, False),
]
CONEXIONES_SIM = [
    ('entry', 'Rodillas'), ('Rodillas', 'exit'),
    ('entry', 'Cruzado'), ('Cruzado', 'exit'),
    ('entry', 'Animar'), ('Animar', 'exit'),
    ('entry', 'BesoA_Preparar'), ('BesoA_Preparar', 'BesoA_Besar'), ('BesoA_Besar', 'exit'),
    ('entry', 'BesoB_Preparar'), ('BesoB_Preparar', 'BesoB_Besar'), ('BesoB_Besar', 'exit'),
]
EDADES = ('teen', 'youngadult', 'adult', 'elder')

# Interacciones de sentarse -> AnimationElement que repiten en bucle
SENTARSE = {
    0x918EF6B8055549C2: 13378556709326547498,  # Sentarse_Rodillas -> Anim_Rodillas
    0xED502CE067D2F23E: 17763382525158778550,  # Sentarse_Cruzado -> Anim_Cruzado
}
MIXERS = {0xD1C70DA42FE42ABA, 0xDEFB4F5B239A5A6E}


def fnv64(texto):
    h = 0xCBF29CE484222325
    for c in texto.lower().encode('utf-8'):
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h ^= c
    return h


# --- Clips -------------------------------------------------------------------

def _string(data, pos):
    n = struct.unpack_from('<I', data, pos)[0]
    return data[pos + 4:pos + 4 + n].decode('ascii'), pos + 4 + n


def _pack_string(texto):
    raw = texto.encode('ascii')
    return struct.pack('<I', len(raw)) + raw


def parse_clip(data):
    """Separa la cabecera de un clip (versión 14) de sus datos S3Clip."""
    version = struct.unpack_from('<I', data, 0)[0]
    if version != 14:
        raise ValueError('versión de clip no soportada: %d' % version)
    pos = 56  # versión, flags, duración, rotación, traslación y 4 hashes
    fixed = data[:pos]
    name, pos = _string(data, pos)
    namespace, pos = _string(data, pos)
    count = struct.unpack_from('<I', data, pos)[0]
    pos += 4
    namespaces = []
    for _ in range(count):
        ns, pos = _string(data, pos)
        namespaces.append(ns)
    slots = []
    count = struct.unpack_from('<I', data, pos)[0]
    pos += 4
    for _ in range(count):
        chain, slot = struct.unpack_from('<HH', data, pos)
        pos += 4
        target_ns, pos = _string(data, pos)
        target, pos = _string(data, pos)
        slots.append((chain, slot, target_ns, target))
    events = []
    count = struct.unpack_from('<I', data, pos)[0]
    pos += 4
    for _ in range(count):
        kind, size = struct.unpack_from('<II', data, pos)
        events.append((kind, data[pos + 8:pos + 8 + size]))
        pos += 8 + size
    codec_len = struct.unpack_from('<I', data, pos)[0]
    codec = data[pos + 4:pos + 4 + codec_len]
    if pos + 4 + codec_len != len(data) or codec[:8] != b'_pilC3S_':
        raise ValueError('clip %s: los datos S3Clip no cuadran' % name)
    return dict(fixed=fixed, name=name, namespace=namespace, namespaces=namespaces,
                slots=slots, events=events, codec=codec)


def build_clip(clip):
    out = bytearray(clip['fixed'])
    out += _pack_string(clip['name']) + _pack_string(clip['namespace'])
    out += struct.pack('<I', len(clip['namespaces']))
    for ns in clip['namespaces']:
        out += _pack_string(ns)
    out += struct.pack('<I', len(clip['slots']))
    for chain, slot, target_ns, target in clip['slots']:
        out += struct.pack('<HH', chain, slot) + _pack_string(target_ns) + _pack_string(target)
    out += struct.pack('<I', len(clip['events']))
    for kind, payload in clip['events']:
        out += struct.pack('<II', kind, len(payload)) + payload
    out += struct.pack('<I', len(clip['codec'])) + clip['codec']
    return bytes(out)


def fix_clip(res):
    clip = parse_clip(res.data())
    new_name = CLIPS.get(clip['name'])
    if new_name is None:
        raise ValueError('clip desconocido: %s' % clip['name'])
    if res.instance != fnv64(clip['name']):
        raise ValueError('la instancia de %s no es el hash de su nombre' % clip['name'])
    clip['name'] = new_name
    clip['events'] = []
    if new_name == CLIP_BOTELLA:
        clip['slots'] = []
    data = build_clip(clip)
    check = parse_clip(data)
    assert check['name'] == new_name and check['codec'] == clip['codec']
    res.set_data(data)
    res.instance = fnv64(new_name)


# --- ASM ---------------------------------------------------------------------

TRANSICION = ('<TransitionClassList>\n'
              '{i}  <Transition transition_class_name="Default" transition_duration_in="0.2666667" '
              'use_custom_transition_in="true" transition_type_in="linear" transition_mask_in="" '
              'transition_duration_out="0.2666667" use_custom_transition_out="true" '
              'transition_type_out="linear" transition_mask_out="" />\n'
              '{i}</TransitionClassList>')


class _Ids:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return self.n


def _controller(target, clip, loops, indent, ids):
    return ('{i}<Controller target="{t}" controller="@ClipController(clip={c}, loop_count=#{n})" '
            'overridePosture="false" mask="" track="normal" mirror_conditional="False" '
            'suppress_footsteps="False" transition_class_in="Default" transition_class_out="Default" '
            'ik_configuration="" focus="undefined" start_frame_offset="0" end_frame_offset="0" '
            'timescale="1" unique_id="{u}">\n'
            '{i}  {tr}\n'
            '{i}</Controller>\n').format(i=indent, t=target, c=clip, n=loops, u=ids(),
                                          tr=TRANSICION.format(i=indent + '  '))


def _state_attrs(name, interrupt):
    return ('name="{}" type="public" countlooptime="false" disableautostop="false" skippable="false" '
            'interrupt_this="{}" focus="none" facialoverlays="false" tailoverlays="true" '
            'wingsoverlays="true"').format(name, 'true' if interrupt else 'false')


def _state(name, interrupt, controllers, ids):
    """controllers: lista de (actor, clip, repeticiones)."""
    out = '  <State {}>\n    <description />\n    <ParameterSelector parameter="x:age">\n'.format(
        _state_attrs(name, interrupt))
    for edad in EDADES:
        out += ('      <Choice value="{}">\n        <MakeController>\n'
                '          <PostureSelector parameter="x:posture" unique_id="{}">\n'
                '            <Choice value="-stand-FullBody" track="normal" mask="">\n').format(edad, ids())
        for actor, clip, loops in controllers:
            out += _controller(actor, clip, loops, '              ', ids)
        out += ('            </Choice>\n          </PostureSelector>\n'
                '        </MakeController>\n      </Choice>\n')
    out += '    </ParameterSelector>\n  </State>\n'
    return out


def _asm(name, actors, states, connections):
    ids = _Ids()
    out = '<?xml version="1.0" encoding="utf-8"?>\n<ASM name="{}" dcc="sage">\n'.format(name)
    for actor, kind in actors:
        out += '  <Actor name="{}" type="{}"{} virtual="false" />\n'.format(
            actor, kind, ' master="true"' if kind == 'Sim' else '')
    out += ('  <Parameter name="x:age" type="enum" labels="baby,toddler,child,teen,youngadult,adult,elder" '
            'default="adult" />\n'
            '  <Parameter name="x:sex" type="enum" labels="male,female" default="male" />\n'
            '  <PostureManifest actors="x">\n'
            '    <Support family="stand" compatibility="FullBody" carry_left="-" carry_right="-" '
            'carry_back="-" surface="*" />\n'
            '  </PostureManifest>\n')
    for state, interrupt, _ in states:
        out += '  <State {} />\n'.format(_state_attrs(state, interrupt))
    for a, b in connections:
        out += '  <Connection from="{}" to="{}" />\n'.format(a, b)
    for state, interrupt, controllers in states:
        out += _state(state, interrupt, controllers, ids)
    out += '</ASM>\n'
    return out.encode('utf-8')


def asm_sim():
    states = [(s, interrupt, [('x', clip, loops)]) for s, clip, loops, interrupt in ESTADOS_SIM]
    return _asm('Jennikita:Botella_ASM_Sim', [('x', 'Sim')], states, CONEXIONES_SIM)


def asm_girar():
    states = [('Girar', False, [('x', 'Jennikita_Botella_GirarSim_x', 1),
                                ('spinbottle', CLIP_BOTELLA, 1)])]
    return _asm('Jennikita:Botella_ASM_Girar', [('x', 'Sim'), ('spinbottle', 'Object')], states,
                [('entry', 'Girar'), ('Girar', 'exit')])


# --- Tuning ------------------------------------------------------------------

def fix_animation_element(res):
    xml = res.data().decode('utf-8')
    if 'n="end_states"' in xml:
        return
    new = re.sub(r'(  </L>\n)', r'\1  <L n="end_states">\n    <T>exit</T>\n  </L>\n', xml, count=1)
    if new == xml:
        raise ValueError('AnimationElement sin begin_states: %s' % res.tgi())
    res.set_data(new.encode('utf-8'))


def fix_sentarse(res, animation):
    xml = res.data().decode('utf-8')
    new, n = re.subn(r'<V n="content" t="staging_content">.*?</V>\n',
                     '<V n="content" t="looping_content">\n'
                     '        <U n="looping_content">\n'
                     '          <U n="animation_ref">\n'
                     '            <T n="factory">%d</T>\n'
                     '          </U>\n'
                     '        </U>\n'
                     '      </V>\n' % animation,
                     xml, flags=re.S)
    if n != 1:
        raise ValueError('no se encontró el contenido de %s' % res.tgi())
    res.set_data(new.encode('utf-8'))


def arreglar(src, dst):
    header, resources = read_package(src)
    out = []
    clips = 0
    for res in resources:
        if res.type == INTERACTION and res.instance in MIXERS:
            continue
        if res.type in (CLIP, CLIP_HEADER):
            fix_clip(res)
            clips += 1
        elif res.type == ASM and res.instance == ASM_SIM:
            res.set_data(asm_sim())
        elif res.type == ASM and res.instance == ASM_GIRAR:
            res.set_data(asm_girar())
        elif res.type == ANIMATION and res.instance != ANIM_GIRAR:
            fix_animation_element(res)
        elif res.type == INTERACTION and res.instance in SENTARSE:
            fix_sentarse(res, SENTARSE[res.instance])
        out.append(res)
    if clips != 2 * len(CLIPS):
        raise SystemExit('Se esperaban %d clips y cabeceras, hay %d' % (2 * len(CLIPS), clips))
    keys = [(r.type, r.group, r.instance) for r in out]
    if len(keys) != len(set(keys)):
        raise SystemExit('Hay recursos repetidos en la salida')
    write_package(dst, header, out)
    print('Paquete arreglado -> %s (%d recursos)' % (dst, len(out)))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    arreglar(sys.argv[1], sys.argv[2])
