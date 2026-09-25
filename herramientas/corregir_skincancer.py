#!/usr/bin/env python3
"""Corrige el add-on de cáncer de piel de Automatic Sunburns (Flerb) para Los Sims 4.

Uso:
    python3 herramientas/corregir_skincancer.py ORIGINAL.package SALIDA.package

Cambios (el resto de recursos se copia sin tocar):

1. Los dos avisos del médico (DialogDramaNode) usaban las instancias de EA
   167175 y 167176 (dialogDramaNode_SP11_Intro2/Intro3, de Fitness Stuff), así
   que sobrescribían esos nodos del juego. Ahora tienen IDs propios y los
   loots que los programan apuntan a ellos.
2. Esos nodos tenían "scoring" activado (copiado de EA). Con eso el gestor de
   eventos del juego también los programa por su cuenta a cualquier Sim
   diagnosticado, y podía mandarle el aviso de muerte aunque le hubiera
   tocado sobrevivir (o al revés). Solo se programan desde el loot.
3. loot_test_to_start_skinCancer excluía un buff (9342144025305913298) y un
   rasgo (17880390607133040885, Flerb_UVskincancer_Trait_Q34mSf) que no
   existen en el mod: son IDs de una versión antigua. Ahora excluye el buff
   de diagnóstico y el rasgo de cáncer visible actuales, y también el buff de
   enfermedad terminal (para que un Sim al que le quedan 3-5 días no pueda
   volver a desarrollar cáncer y "sobrevivir").
4. La notificación de muerte repetía el mismo texto que el aviso del médico
   que sale justo antes; ahora usa el texto "{0.SimFirstName} will die from
   skin cancer" (0xD1C28321), que existía en el mod pero no se usaba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traducir import Resource, read_package, write_package  # noqa: E402

DRAMA_NODE = 0x2553F435
LOOT = 0x0C772E27

OLD_DEATH_NODE, OLD_SURVIVE_NODE = 167175, 167176
NEW_DEATH_NODE = 16504300624365318163     # Flerb:UVskincancer_DramaNode_DeathCall
NEW_SURVIVE_NODE = 17605809100702541165   # Flerb:UVskincancer_DramaNode_SurvivalCall

SCORING = """  <V n="scoring" t="enabled">
    <U n="enabled">
      <T n="base_score">100</T>
      <E n="bucket">DEFAULT</E>
    </U>
  </V>
"""

# (tipo, instancia) -> lista de (texto original, texto corregido)
EDITS = {
    (LOOT, 0x8359D2D55DAF4783): [  # Flerb:UVskincancer_cancerrandomtimer_scheduleDeathCall
        ('<T n="drama_node">167175<!--DialogDramaNode: dialogDramaNode_SP11_Intro2--></T>',
         '<T n="drama_node">%d<!--DialogDramaNode: Flerb:UVskincancer_DramaNode_DeathCall--></T>'
         % NEW_DEATH_NODE),
    ],
    (LOOT, 0xD285B99C4D99B9BD): [  # Flerb:UVskincancer_cancerrandomtimer_scheduleSurvivalCall
        ('<T n="drama_node">167176<!--DialogDramaNode: dialogDramaNode_SP11_Intro3--></T>',
         '<T n="drama_node">%d<!--DialogDramaNode: Flerb:UVskincancer_DramaNode_SurvivalCall--></T>'
         % NEW_SURVIVE_NODE),
    ],
    (LOOT, 0xC7543136008A8D4C): [  # Flerb:loot_test_to_start_skinCancer
        ('<T>9342144025305913298<!--Buff: Flerb_UVskincancer_CancerDiagnosisBuff--></T>',
         '<T>12653074233097929517<!--Buff: Flerb:UVskincancer_CancerDiagnosisBuff--></T>\n'
         '\t          <T>13163811220588367313<!--Buff: Flerb_UVskincancer_cancerrandomtimer_867M_death--></T>'),
        ('<T>17880390607133040885<!--Trait: Flerb_UVskincancer_Trait_Q34mSf--></T>',
         '<T>15400903259400657652<!--Trait: Flerb:Trait_SkinCancer_Active_visible--></T>'),
    ],
    (LOOT, 0xFAC33322F468F4BD): [  # Flerb_UVskincancer_cancerrandomtimer_lootdeath
        ('<T n="single">0xAA26075F</T>', '<T n="single">0xD1C28321</T>'),
    ],
    (DRAMA_NODE, OLD_DEATH_NODE): [
        ('n="dialogDramaNode_SP11_Intro2" s="167175"',
         'n="Flerb:UVskincancer_DramaNode_DeathCall" s="%d"' % NEW_DEATH_NODE),
        (SCORING, ''),
    ],
    (DRAMA_NODE, OLD_SURVIVE_NODE): [
        ('n="dialogDramaNode_SP11_Intro3" s="167176"',
         'n="Flerb:UVskincancer_DramaNode_SurvivalCall" s="%d"' % NEW_SURVIVE_NODE),
        (SCORING, ''),
    ],
}
NEW_INSTANCE = {(DRAMA_NODE, OLD_DEATH_NODE): NEW_DEATH_NODE,
                (DRAMA_NODE, OLD_SURVIVE_NODE): NEW_SURVIVE_NODE}


def fix(src, dst):
    header, resources = read_package(src)
    out = []
    pending = set(EDITS)
    for res in resources:
        key = (res.type, res.instance)
        if key not in EDITS:
            out.append(res)
            continue
        pending.discard(key)
        text = res.data().decode("utf-8")
        crlf = "\r\n" in text
        text = text.replace("\r\n", "\n")
        for old, new in EDITS[key]:
            if text.count(old) != 1:
                raise SystemExit("No encuentro el texto a corregir en %s:\n%s" % (res.tgi(), old))
            text = text.replace(old, new)
        if crlf:
            text = text.replace("\n", "\r\n")
        if key in NEW_INSTANCE:
            # Recurso nuevo con ID propio (grupo 0 como el resto de tuning del mod).
            res = Resource(res.type, 0, NEW_INSTANCE[key], b"", 0, 0, res.committed)
        res.set_data(text.encode("utf-8"))
        out.append(res)
        print("Corregido %s" % res.tgi())
    if pending:
        raise SystemExit("Faltan recursos en el .package: %s"
                         % ", ".join("%08X:%016X" % k for k in sorted(pending)))
    write_package(dst, header, out)
    print("Guardado %s (%d recursos)" % (dst, len(out)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    fix(sys.argv[1], sys.argv[2])
