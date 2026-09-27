# Camión de la basura (Jennikita)

## Instalación

Copia estos dos archivos a `Documentos/Electronic Arts/Los Sims 4/Mods`, en lugar de los antiguos:

- `Jennikita_CamionBasura.package`
- `Jennikita_CamionBasura.ts4script`

`jennikita_basura.py` es el código fuente del script. El juego no lo necesita.

## Trucos

| Truco | Qué hace |
| --- | --- |
| `jennikita.basurero` | Hace venir al basurero ahora. El camión aparece cuando llega él. |
| `jennikita.estado` | Dice qué partes del mod encuentra el juego, dónde está el basurero y los últimos mensajes o errores. |
| `jennikita.camion` | Pone o quita solo el camión, sin basurero, para ver dónde queda. |
| `jennikita.camion_calle 5.5` / `jennikita.camion_largo 8` / `jennikita.camion_giro 0` | Recolocan el camión. |

## Volver a compilar el script

El juego usa Python 3.7:

```
python3.7 -c "import py_compile; py_compile.compile('jennikita_basura.py', cfile='jennikita_basura.pyc')"
```

Mete el `jennikita_basura.pyc` resultante, sin carpetas, en un zip sin compresión llamado `Jennikita_CamionBasura.ts4script`.
