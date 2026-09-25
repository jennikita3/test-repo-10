# Automatic Sunburns (Flerb): revisión de los add-ons

## addon_Flerb_SkinCancer.package (corregido)

Sustituye el `addon_Flerb_SkinCancer.package` de tu carpeta Mods por el de esta carpeta.
Para volver a aplicar las correcciones sobre una versión nueva del add-on:

```
python3 herramientas/corregir_skincancer.py addon_Flerb_SkinCancer_original.package addon_Flerb_SkinCancer.package
```

Errores corregidos:

1. **Pisaba dos eventos de EA.** Los avisos del médico («se va a morir» / «se va a curar») usaban los IDs 167175 y 167176.
   Esos IDs son `dialogDramaNode_SP11_Intro2` y `Intro3` del juego, así que el mod los sobrescribía.
   Ahora tienen IDs propios: `Flerb:UVskincancer_DramaNode_DeathCall` y `Flerb:UVskincancer_DramaNode_SurvivalCall`.
2. **El juego podía mandar el aviso equivocado.** Esos avisos tenían la puntuación (`scoring`) activada, copiada del original de EA.
   Con eso, el juego también los programaba por su cuenta a cualquier Sim diagnosticado.
   Un Sim al que le había tocado curarse podía recibir el aviso de muerte, o al revés. Ahora solo los programa el mod.
3. **La comprobación de «ya tiene cáncer» no funcionaba.** `loot_test_to_start_skinCancer` excluía un buff y un rasgo que no existen: son IDs de una versión antigua del mod.
   Ahora excluye el buff de diagnóstico y el rasgo de cáncer visible actuales.
   También excluye el moodlet de enfermedad terminal, para que un Sim al que le quedan 3-5 días no pueda volver a enfermar y «curarse».
4. **Texto repetido.** La notificación de muerte repetía el mismo texto que el aviso del médico que sale justo antes.
   Ahora usa «{0.SimFirstName} will die from skin cancer». Ese texto ya estaba en el mod pero no se usaba.

Los otros 55 recursos del add-on son idénticos, byte a byte, al original.

## addon_Flerb_EASkins_Override.package (sin cambios)

Los 26 tonos de piel de EA que sustituye están bien formados y no tienen errores internos.
No los he podido comparar con los originales actuales del juego.

## addon_Flerb_more_traits.package (desactualizado, sin corregir)

Sustituye dos módulos enteros del juego (`sims.aging.aging_tuning` y `traits.traits`) para dar 4 rasgos de personalidad a adolescentes, jóvenes adultos, adultos y ancianos.
Esa copia es anterior a 2023: no tiene la edad **INFANT** (bebés de 0-1 años) ni la especie **HORSE** (Rancho de caballos).
Con el juego actual puede romper el crecimiento de bebés y caballos.
Para corregirlo hace falta partir de la versión actual de esos dos módulos del juego.
