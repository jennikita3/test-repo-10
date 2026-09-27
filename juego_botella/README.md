# Juego de la botella (Jennikita): versión 8

Arreglo del mod del juego de la botella. En la v7 algunos Sims se volvían invisibles (solo se veían sus bocadillos) y las animaciones no se veían.

## Instalación

1. En `Documentos/Electronic Arts/Los Sims 4/Mods`, borra los archivos de la versión anterior:
   `Jennikita_JuegoBotella.package`, `jennikita_botella.ts4script` y `jennikita_botella_log.txt`.
2. Copia en su lugar los dos archivos de esta carpeta:
   - `Jennikita_JuegoBotella.package`
   - `jennikita_botella.ts4script`

   El `.ts4script` puede estar como mucho una carpeta por debajo de `Mods`.
3. Borra `localthumbcache.package` de `Documentos/Electronic Arts/Los Sims 4`.
   Así el juego no usa animaciones antiguas guardadas en caché.
4. En Opciones del juego > Otros, activa «Contenido personalizado y mods» y «Mods de script».
5. Si al cargar la partida hay algún Sim invisible o atascado de la versión anterior, usa en la consola de trucos (Ctrl+Mayús+C):
   - `jennikita.botella_reiniciar`
   - `resetSim Nombre Apellido`

Para comprobar que el script está cargado, escribe `jennikita.botella_estado`. Debe decir «v8» y «10 de 10».

## Qué se ha cambiado

### Animaciones (`.package`)

Un Sim se vuelve invisible (y se le siguen viendo los bocadillos) cuando el juego no consigue reproducir su animación. La v7 tenía varias cosas distintas de los mods de animación que sí funcionan. Se han cambiado todas:

- **Sentarse ya no usa mixers.** Sentarse de rodillas o con las piernas cruzadas usa ahora `looping_content`, el mismo sistema que usa *When Nature Calls* para sus animaciones en bucle.
  Antes, un mixer reproducía la animación de sentado 30 veces seguidas (unos 4 minutos) y no se podía interrumpir. Si al Sim le tocaba girar mientras tanto, se quedaba bloqueado.
  Ahora el Sim está sentado mientras dura la interacción. Cuando le toca girar, se levanta en el momento. Los dos mixers se han quitado.
- **ASM reescritos** con la misma estructura que los ASM que funcionan:
  - Se quitan el `PostureManifest` vacío y la variante `UpperBody` con `<Reference>`.
  - Se añade el selector por edad.
  - Los estados de sentarse se pueden interrumpir.
- **Las animaciones terminan en `exit`.** Al acabar de sentarse, animar o besarse, el Sim sale bien de la animación y vuelve a estar de pie.
  El giro no termina en `exit`, para que la botella se quede apuntando al Sim elegido.
- **Clips:**
  - Nombres sin dos puntos ni relleno de guiones bajos (por ejemplo, `Jennikita_Botella_Rodillas_x`).
  - Se quitan dos eventos de plantilla que traían todos los clips: un sonido en el segundo 1000 y un evento tipo 19 con valores extraños en el segundo 0.
  - Los datos de las animaciones (huesos y fotogramas) son idénticos a los de antes.

### Script (`.ts4script`)

- Al colocar a un Sim en su asiento se usa su propia altura y superficie. Antes se usaban las de la botella, y si la botella estaba encima de la alfombra el Sim quedaba a otra altura.
- Los tiempos de espera usan el reloj del juego y no el reloj real. Antes, con el juego en pausa o a velocidad 3, los turnos se saltaban o no avanzaban.
- Se quita la lectura del árbol genealógico. Fallaba en cada comprobación (era el aviso `GenealogyTracker ... get_family_sim_ids` del registro). Para saber si dos Sims son familia se usa ahora la prueba de incesto del propio juego.

El código fuente está en `src/jennikita_botella.py`. Se compila con Python 3.7, la versión que usa Los Sims 4.

## Si algo sigue fallando

Pásame el `jennikita_botella_log.txt` que se crea en la carpeta `Mods`. Si aparece un `lastException.txt` o `lastUIException.txt` en `Documentos/Electronic Arts/Los Sims 4`, pásamelo también.

## Rehacer el `.package`

`herramientas/arreglar_paquete.py` aplica todos los cambios del `.package` sobre el paquete de la v7:

```
python3 juego_botella/herramientas/arreglar_paquete.py Jennikita_JuegoBotella_v7.package juego_botella/Jennikita_JuegoBotella.package
```

La botella y la alfombra son de SIXAMcc. Las animaciones son de Love4Sims.
