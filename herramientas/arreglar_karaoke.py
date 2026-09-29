"""Arregla el mod de karaoke (KaraokeMod.package).

- "Unirse al karaoke" pasa a ser una SuperInteraction, como "Aplaudir al
  cantante", "Abuchear al cantante" y "Grabar la actuacion", que tienen los
  mismos tests. Con PlayAudioSuperInteraction no aparecía en el menú. Se
  quitan los campos que solo usa esa clase (pista de voz del corista).
- "Dedicar una cancion..." tenía la lista de especies vacía en test_globals
  (<E />), así que el test del Sim fallaba siempre. Se indica HUMAN.
- Los 5 iconos propios pasan de PNG a DST5 y el tuning apunta a ellos. Los
  DST5 que ya traía el mod tenían los bloques en otro orden y se veían como
  ruido, así que se rehacen a partir de los PNG.

Uso: python3 herramientas/arreglar_karaoke.py KaraokeMod_original.package karaoke/KaraokeMod.package
Necesita Pillow y numpy (pip install pillow numpy).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iconos_dst  # noqa: E402

TIPO_INTERACCION = 0xE882D22F
UNIRSE = 0xBBB14B010D6CF2D9    # Jennikita:karaokeUnirseCoro
DEDICAR = 0x9C23531FDF69876D   # Jennikita:karaokeDedicarCancion

CAMBIOS = {
    UNIRSE: [
        ('<I c="PlayAudioSuperInteraction" i="interaction" m="crafting.music_interactions" '
         'n="Jennikita:karaokeUnirseCoro" s="13524673623862604505">\n',
         '<I c="SuperInteraction" i="interaction" m="interactions.base.super_interaction" '
         'n="Jennikita:karaokeUnirseCoro" s="13524673623862604505">\n'
         '  <!-- SuperInteraction, como Aplaudir, Abuchear y Grabar: con PlayAudioSuperInteraction'
         ' no salia en el menu -->\n'),
        ('  <!-- Voz de los coristas: la misma pista de voz de Practicar canto (sin microfono) -->\n'
         '  <E n="instrument_participant">Actor</E>\n', ''),
        ('  <!-- Siempre de pie: sentarse y nadar quedan descartados -->\n'
         '  <L n="music_styles">\n'
         '    <T>139277<!--MusicStyle: musicStyle_SingingSkill_MicrophoneSelf_Practice--></T>\n'
         '  </L>\n', ''),
        ('  <T n="play_multiple_clips">True</T>\n', ''),
        ('  <U n="posture_preferences">\n',
         '  <!-- Siempre de pie: sentarse y nadar quedan descartados -->\n'
         '  <U n="posture_preferences">\n'),
    ],
    DEDICAR: [
        ('            <L n="species">\n'
         '              <E />\n'
         '            </L>\n',
         '            <L n="species">\n'
         '              <E>HUMAN</E>\n'
         '            </L>\n'),
    ],
}


def arreglar_tuning(recursos):
    pendientes = dict(CAMBIOS)
    nuevos = []
    for r in recursos:
        inst = (r['ih'] << 32) | r['il']
        if r['t'] == TIPO_INTERACCION and inst in pendientes:
            xml = r['data'].decode('utf-8')
            for viejo, nuevo in pendientes.pop(inst):
                if xml.count(viejo) != 1:
                    sys.exit('%016X: no encuentro exactamente una vez:\n%s' % (inst, viejo))
                xml = xml.replace(viejo, nuevo)
            r = iconos_dst.con_datos(r, xml.encode('utf-8'))
            print('Tuning %016X arreglado' % inst)
        nuevos.append(r)
    if pendientes:
        sys.exit('No están en el paquete: ' + ', '.join('%016X' % i for i in pendientes))
    return nuevos


def main(entrada, salida):
    cabecera, recursos = iconos_dst.leer_paquete(entrada)
    recursos = iconos_dst.convertir_iconos(arreglar_tuning(recursos))
    iconos_dst.escribir_paquete(salida, cabecera, recursos)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
