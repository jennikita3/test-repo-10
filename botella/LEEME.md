# Juego de la botella (versión 4)

Mod de Jennikita para Los Sims 4. La botella y la alfombra son de SIXAMcc.

Desde la versión 2 está rehecho desde cero para que los Sims usen las animaciones del juego en vez de las personalizadas.
La botella, la alfombra, los iconos y los textos son los mismos que antes.

La versión 4 arregla lo que fallaba en la 3: los Sims no encontraban el camino hasta su hueco (hacían el gesto de error), la botella no giraba y no se besaban.

## Instalación

1. En tu carpeta `Documentos/Electronic Arts/Los Sims 4/Mods`, borra los archivos de la versión anterior:
   `Jennikita_JuegoBotella.package` y `jennikita_botella.ts4script`.
2. Copia en `Mods` los dos archivos de esta carpeta: `Jennikita_JuegoBotella.package` y `jennikita_botella.ts4script`.
   El `.ts4script` puede ir dentro de una carpeta, pero de una sola: `Mods/Jennikita/` sirve, `Mods/Jennikita/Botella/` no.
3. En el juego, activa **Opciones → Opciones del juego → Otros → Mods de script**.
4. Borra `localthumbcache.package` de la carpeta `Los Sims 4`. El juego lo vuelve a crear.

## Cómo se juega

1. Pulsa en la botella y elige **Jugar a la botella**. Se abre una lista de Sims: marca a quién quieres que juegue.
2. Los elegidos van hasta el círculo alrededor de la botella, se colocan en su hueco mirando a la botella y se sientan en el suelo.
   Cada uno se sienta de rodillas o con las piernas cruzadas, al azar.
3. Cuando están todos sentados, cada uno gira la botella por turnos: se pone de pie y la botella gira sola.
4. La botella señala a alguien con quien se pueda besar. Los dos se levantan y se besan, el resto anima y todos vuelven a su sitio.
5. Cuando todos han girado, se acaba el juego.

Si un Sim se levanta por su cuenta, porque le mandas otra cosa o porque tiene una necesidad urgente, sale del juego y el resto sigue.
Si un Sim no consigue llegar al círculo después de tres intentos, se queda fuera.

Quién puede besarse: adolescentes con adolescentes, y jóvenes adultos, adultos y ancianos entre sí. Nunca familiares.
Si alguien no tiene con quién besarse, sale un aviso y se salta su turno.

Después del beso, los dos Sims reciben el estado de ánimo «¡Me tocó la botella!» y ganan relación y romance.

## Qué animaciones son del juego

| Momento | Animación |
| --- | --- |
| Sentarse | Posturas del juego «de rodillas» y «piernas cruzadas», las mismas de «Sentarse en el suelo» |
| Girar | El Sim se pone de pie y solo se anima la botella; el Sim no la toca |
| Beso | Los dos se ponen de pie y se besan con el beso normal del juego, dentro de una charla y sin las pruebas de romance del juego |
| Animar | La animación del público del juego (`reactionlets_Audience_CheerRandom`), de pie. Luego vuelven a sentarse |

## Si algo falla

- El mod apunta todo lo que pasa en cada partida en `Mods/jennikita_botella_log.txt`.
  Si algo no va bien, ese archivo dice en qué paso se ha quedado.
  Por ejemplo, apunta cuándo se coloca cada Sim en su hueco, y en qué postura están los dos Sims mientras se espera el beso.
  El archivo se vuelve a crear cada vez que se carga el juego: cópialo antes de cerrar.
- Trucos (abre la consola con Ctrl+Mayús+C):
  - `jennikita.botella_estado`: dice si el script está cargado y en qué punto está la partida.
    Tienen que salir 8 de 8 interacciones enganchadas.
  - `jennikita.botella_reiniciar`: termina las partidas en curso si algo se queda atascado.

## Para modificarlo

- El script está en `fuente/jennikita_botella.py`.
- El tuning que cambia respecto a la versión 1 está en `fuente/tuning/`: un archivo por recurso, con el nombre `TIPO_GRUPO_INSTANCIA.xml`.
- Para volver a montar el `.package` y el `.ts4script` después de un cambio:

  ```
  python3 herramientas/construir_botella.py botella/Jennikita_JuegoBotella.package /ruta/a/python3.7
  ```

  Hace falta Python 3.7 porque el juego solo carga scripts compilados con esa versión.
