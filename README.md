# When Nature Calls (Tinycoffee): traducción al español

Traducción al español del mod *When Nature Calls* de Tinycoffee para Los Sims 4.
Traduce los 24 textos del mod: interacciones, estados de ánimo con su motivo y el objeto «Caca de Sim».

## Instalación

1. Borra el `Tinycoffee_WhenNatureCalls.package` original de tu carpeta
   `Documentos/Electronic Arts/Los Sims 4/Mods`.
2. Copia en su lugar el `Tinycoffee_WhenNatureCalls.package` de este repositorio.
   Es el mod completo con los textos en español. No dejes los dos, porque entrarían en conflicto.
3. Mantén las dependencias del mod original. Por ejemplo, el mod usa Lot 51 Core Library.

Los textos salen en español cuando el juego está en español.

## Qué se ha cambiado

Solo la tabla de textos en español (STBL `220557DA:80000000:13F289CA72EDB5F8`).
Los otros 142 recursos del mod son idénticos, byte a byte, a los del original.

En el mod original, la tabla en español era una copia antigua del texto en inglés.
Cinco textos estaban desfasados y en el sitio equivocado. Por ejemplo, el estado de ánimo «Eeeyuck!» mostraba «Picked Up A Sim's Turd».
Esta traducción se hizo a partir del texto en inglés actual.

## Si el mod se actualiza

Vuelve a aplicar la traducción sobre la versión nueva:

```
python3 herramientas/traducir.py Tinycoffee_WhenNatureCalls_nuevo.package Tinycoffee_WhenNatureCalls.package
```

El script avisa si hay textos nuevos o cambiados. Los textos nuevos se quedan en inglés hasta que se añadan a `TRADUCCIONES` en `herramientas/traducir.py`.

## Textos

| Inglés | Español |
| --- | --- |
| **Interacciones** | |
| Pee On Tree | Hacer pis en un árbol |
| Poo On Tree | Hacer caca junto a un árbol |
| Heckle The Pooper | Abuchear al que hace caca |
| Heckle Sim Peeing On Tree | Abuchear al Sim que hace pis en el árbol |
| **Objeto** | |
| Sim Turd | Caca de Sim |
| A Sim left this turd here. What an animal! | Un Sim dejó esta caca aquí. ¡Qué animal! |
| **Estados de ánimo** | |
| Nature's Relief | Alivio natural |
| This sim couldn't stop what already started. Letting nature take its course was the only way. Good thing this tree was here! | Este Sim no pudo detener lo que ya había empezado. Dejar que la naturaleza siguiera su curso era la única opción. ¡Menos mal que este árbol estaba aquí! |
| Not So Fresh | Frescura dudosa |
| This Sim isn't feeling so fresh after using this tree to relieve themselves. If only there was tissue.... | A este Sim le falta frescura después de usar este árbol para hacer sus necesidades. Si al menos hubiera papel higiénico... |
| Really? On a tree? | ¿En serio? ¿En un árbol? |
| Jeez, are you kidding? They really couldn't just wait? Where is the decorum? | ¡Madre mía! ¿Es una broma? ¿De verdad no podía esperar? ¿Dónde está el decoro? |
| You Know What... | Lo que hay que ver... |
| Is this who we are? Is this what we represent??! | ¿Esto es lo que somos? ¡¿Esto es lo que representamos?! |
| Eeeyuck! | ¡Puaaaj! |
| Ewww, Why am I picking this up?! How did we get here????? | ¡Qué asco! ¡¿Por qué estoy recogiendo esto?! ¿¿¿Cómo hemos llegado hasta aquí??? |
| Stepped On A Turd | Pisó una caca |
| That definitely wasn't mud.... | Está claro que eso no era barro... |
| **Motivos de los estados de ánimo** | |
| (From Relieving Self Outside) | (Por hacer sus necesidades al aire libre) |
| (From Pooping Outside) | (Por hacer caca al aire libre) |
| (From Seeing A Sim Pee Outside) | (Por ver a un Sim haciendo pis al aire libre) |
| (From Seeing A Sim Poop Outside) | (Por ver a un Sim haciendo caca al aire libre) |
| (From Picking Up A Sim Turd) | (Por recoger una caca de Sim) |
| (From Stepping On A Sim Turd) | (Por pisar una caca de Sim) |

El mod es obra de Tinycoffee. Si vas a compartir esta traducción públicamente, pide permiso antes a su creador.

# Camión de la basura funcional (Jennikita)

Está en la carpeta `camion_basura/`. Copia los dos archivos a tu carpeta `Mods`, sustituyendo los antiguos:

- `Jennikita_CamionBasura.package`
- `Jennikita_CamionBasura.ts4script`

El código del script es `camion_basura/jennikita_basura.py`. Si lo cambias, vuelve a crear el `.ts4script` con Python 3.7, que es la versión que usa el juego:

```
python3.7 herramientas/compilar_basurero.py
```

## Qué hace el basurero

El basurero llega ya con el mono amarillo puesto: se le pone en cuanto entra en la visita, antes de aparecer.
Va al cubo de fuera, lo vacía, coge la bolsa de basura y, cuando termina la animación de cogerla, se va andando del solar con la bolsa en la mano.

- Si suelta la bolsa en el suelo, la bolsa desaparece.
- Si pasan 20 minutos y no ha terminado, se va igualmente.
- El camión se quita 5 minutos después de que se vaya el basurero.

Solo se quitan las bolsas que saca el basurero. La basura que ya estaba en el suelo cuando llegó se queda, y es la que cuenta para la multa.

## Hablar con el basurero

Al hacer clic en el basurero mientras está en tu solar, tus sims tienen dos opciones:

- **Saludar al basurero**: sube un poco la amistad y el sim se pone de buen humor con «Basurero simpático» (Feliz +1, 4 horas).
- **Preguntar por el reciclaje**: sube un poco la amistad y sale una notificación con un consejo de reciclaje al azar.

El basurero no se entretiene: sigue con lo suyo y se va igual.

Las interacciones, el estado de ánimo, los textos y los iconos los añade al `.package` `herramientas/basurero_interacciones.py`. Lo que hace cada interacción está en el script.
Los iconos salen de `camion_basura/icono_saludar.png` e `icono_reciclaje.png`: para cambiarlos, sustituye el PNG y ejecuta

```
python3 herramientas/basurero_interacciones.py
```

## Sim blanco

La textura del mono amarillo era opaca en todo el mapa de textura del sim, con fondo blanco. Como se pinta encima de la piel, el pelo y los zapatos, el basurero salía blanco como un maniquí.
En el `.package` se ha dejado transparente todo lo que no es el mono: el fondo, las manos y el borde del cuello. El dibujo del mono no cambia.
Si vuelves a exportar el mono desde Sims 4 Studio, deja transparente el fondo de la textura.

## Icono del aviso

El icono del aviso de las 21:00 es un PNG de 128×128 (`2F7D0004:00000000:D4961EED372508C7`), sacado de `camion_basura/icono_aviso_original.png` con el fondo blanco quitado.
El juego busca los iconos como PNG. La versión antigua en DST (`00B2D882`) sigue en el `.package`, pero no se usa.
