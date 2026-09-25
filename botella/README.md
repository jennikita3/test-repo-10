# Juego de la botella

Mod para Los Sims 4 que convierte la botella de simsstories20 en un juego de la botella con las animaciones de Love4Sims.

## Instalación

Copia estos dos archivos en `Documentos/Electronic Arts/Los Sims 4/Mods`. Pueden ir en una subcarpeta, pero de un solo nivel:

- `Jennikita_JuegoBotella.package`
- `jennikita_botella.ts4script`

Activa los mods de script en las opciones del juego.

No hace falta ningún otro mod. Quita el `Bottle_MESH.package` original, porque este paquete ya lleva la botella y los dos chocarían. El pack de poses de Love4Sims para Pose Player puedes dejarlo o quitarlo: no choca con este mod.

## Cómo se juega

La botella está en el modo Comprar como «Botella para jugar a la botella». Ponla en el suelo, con sitio libre alrededor. Al hacer clic en ella salen dos opciones:

1. **Jugar a la botella**. Se abre un selector con los Sims del solar (de adolescente en adelante). El Sim que abre el selector ya sale marcado. Marca a los que quieras, hasta 8, y acepta. Todos van a sentarse en círculo alrededor de la botella, cada uno de rodillas o con las piernas cruzadas al azar.
2. **Girar la botella**. Un Sim se acerca, se agacha y hace girar la botella. La botella acaba señalando a uno de los Sims sentados, elegido al azar.

Después todo va solo: los dos se ponen frente a frente y se besan, y el resto de Sims sentados los animan. Al acabar, los que estaban sentados vuelven a su sitio en el círculo, y otro Sim puede girar la botella.

Los dos Sims que se besan consiguen el estado de ánimo «¡Me tocó la botella!» (Seguro, 3 horas) y suben 10 puntos de romance entre ellos.

## Qué animación hace cada Sim

No hay que vincular nada a mano. Cada animación va dentro de una interacción, y la interacción la hace un Sim concreto, así que la animación se le aplica a ese Sim. El script decide qué interacción recibe cada uno:

| Quién | Interacción | Animación de Love4Sims |
| --- | --- | --- |
| Cada Sim elegido en el selector | Sentarse a jugar | «sitted on knees» o «sitting cross legs» |
| El Sim que gira | Girar la botella | «Sim» (girar la botella) |
| La botella | Girar la botella (a la vez) | «bottle spining» |
| El Sim que gira | Beso de la botella | «Preparing to Kiss - Sims1» y después «kissing: giving the kiss» |
| El Sim señalado | Beso de la botella | «Preparing to be kissed - Sims2» y después «kissing: being kissed» |
| El resto de sentados | Animar a la pareja | «Cheering Sims» |

## Quién puede besarse

- Adolescentes solo con adolescentes.
- Jóvenes adultos, adultos y ancianos entre sí.
- Nunca familiares. Se usa la comprobación de parentesco del propio juego y el árbol genealógico.
- Los niños no pueden jugar.

Si no hay nadie sentado con quien se pueda besar el Sim que gira, «Girar la botella» sale en gris y explica por qué.

## Si algo se queda atascado

Abre la consola de trucos (Ctrl+Mayús+C) y escribe:

```
jennikita.botella_reiniciar
```

Olvida las partidas en curso y se puede volver a jugar.

## Qué hay que comprobar en el juego

El mod no se ha podido probar dentro del juego. Se ha comprobado que las referencias del paquete son correctas y se ha simulado una partida con el script. Lo que más conviene mirar al probarlo:

- Que el Sim que gira quede bien colocado frente a la botella. La distancia se puede ajustar en el tuning de `Jennikita:Botella_Girar`, que ahora está entre 0,55 y 0,8 m.
- Que los dos Sims del beso queden bien alineados.
- Que la botella acabe señalando al Sim elegido. Si señala al lado contrario o a otro sitio, hay que cambiar `ANGULO_FINAL_BOTELLA` en el script.
- Que las poses de sentado duren mientras el Sim está en el círculo.
- Que el selector de «Jugar a la botella» salga y que los elegidos vayan a sentarse.

Si algo falla, el archivo `lastException` de la carpeta de Los Sims 4 dice qué ha pasado.

## Cambios respecto a los archivos originales

**Animaciones.** En el pack de Love4Sims, cada animación colocaba al Sim en su sitio de la escena original (por ejemplo, la pareja del beso a ±0,38 m del centro). Las 5 animaciones de girar y besar se han centrado en el origen, y el script coloca a cada Sim. El resto de la animación no cambia. Estos clips llevan nombres nuevos para no chocar con el pack de poses original.

**Botella.** Se conservan la malla, las texturas, el catálogo y el estado de ánimo. La interacción que traía se ha sustituido por las del juego completo, y el icono del estado de ánimo ahora apunta a su imagen DST.

**Textos.** Están en español para el juego en español y en inglés para el resto de idiomas.

## Volver a construirlo

Las fuentes están en `botella/fuentes/`: ASM, tuning, textos y script. Para generar el mod de nuevo:

```
PYTHON37=/ruta/a/python3.7 python3 herramientas/construir_botella.py \
    Love4Sims_Spin_The_Bottle_Animation.package Bottle_MESH.package botella/
```

Necesita Python 3.7 para compilar el script, además de Pillow y numpy.

## Créditos

La botella es de simsstories20 y las animaciones son de Love4Sims. Si vas a compartir este mod públicamente, pide permiso antes a los dos.
