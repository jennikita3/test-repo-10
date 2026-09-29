# Mod de karaoke: arreglos

## Instalación

1. Borra el `KaraokeMod.package` antiguo de `Documentos/Electronic Arts/Los Sims 4/Mods`.
2. Copia en su lugar el `KaraokeMod.package` de esta carpeta. No dejes los dos, porque entrarían en conflicto.
3. El mod necesita XML Injector (añade las interacciones a los Sims y a la máquina de karaoke) y la máquina de karaoke de *Urbanitas*.

## Qué se ha cambiado

- **«Unirse al karaoke» no aparecía.** Era una `PlayAudioSuperInteraction`. «Aplaudir al cantante», «Abuchear al cantante» y «Grabar la actuación» tienen los mismos tests pero son `SuperInteraction`.
  Ahora «Unirse» también lo es. Se han quitado los campos que solo usa esa clase: la pista de voz de los coristas (`music_styles`, `instrument_participant` y `play_multiple_clips`).
  Los coristas siguen con las animaciones de «Practicar canto», sin voz propia. Se oye la canción del cantante principal.
- **«Dedicar una canción...» tampoco podía aparecer.** La lista de especies de `test_globals` estaba vacía (`<E />`), así que el test del Sim fallaba siempre, igual que en el mod de postales. Ahora es `HUMAN`.
- **Iconos en DST.** El tuning apuntaba a los 5 iconos en PNG (`2f7d0004`). El mod ya traía una versión DST5 de cada uno, pero con los bloques en otro orden que el del juego, así que se verían como ruido.
  Ahora los 5 iconos son DST5 hechos a partir de los PNG, con el mismo formato que Sims 4 Studio (cabecera idéntica y mipmaps). El tuning apunta a ellos (`00b2d882`) y los PNG se han quitado del paquete.
  Los globos del juego (micrófono, prohibido, etc.) siguen como `2f7d0004`, porque en el juego solo existen en PNG.

El resto de recursos (textos, loot, XML Injector y las otras interacciones, salvo la referencia al icono) no ha cambiado.

## Si cambias el mod

Para aplicar los mismos arreglos a otra versión del mod:

```
python3 herramientas/arreglar_karaoke.py KaraokeMod_original.package karaoke/KaraokeMod.package
```

Solo la conversión de iconos, para cualquier mod:

```
python3 herramientas/iconos_dst.py entrada.package salida.package
```

Necesitan Pillow y numpy (`pip install pillow numpy`).
