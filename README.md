# Monitor de integridad de archivos

Proyecto de ciberseguridad defensiva para detectar si aparecieron, cambiaron o se
eliminaron archivos dentro de una carpeta.

La herramienta crea una **línea base** con la huella SHA-256 de cada archivo. Más
adelante vuelve a calcular las huellas y compara ambos estados.

## ¿Qué problema resuelve?

Un cambio inesperado en una configuración, página web o script puede ser una señal
de error o actividad no autorizada. Revisar muchos archivos manualmente no es
práctico; comparar sus huellas permite localizar qué cambió.

Este proyecto sólo **detecta diferencias**. No determina quién hizo el cambio ni
demuestra por sí solo que exista un ataque.

## Conceptos sencillos

- **Integridad:** confianza en que la información no cambió sin autorización.
- **Hash:** huella calculada a partir del contenido de un archivo.
- **SHA-256:** algoritmo utilizado para generar esa huella.
- **Línea base:** estado conocido que se guarda para compararlo después.
- **Falso positivo:** cambio esperado que produce un aviso, por ejemplo una
  actualización autorizada.

SHA-256 no cifra el archivo y no permite recuperar su contenido. Sólo ayuda a
detectar diferencias.

## Probarlo paso a paso

Necesitas Python 3.11 o posterior. Desde la carpeta del proyecto:

```bash
PYTHONPATH=src python -m integrity_monitor create sample-data/demo \
  --baseline baseline.json
```

Esto guarda las huellas actuales. Si verificas sin modificar nada:

```bash
PYTHONPATH=src python -m integrity_monitor check sample-data/demo \
  --baseline baseline.json
```

La salida será:

```text
Sin cambios: los archivos coinciden con la línea base.
```

`create` necesita un nombre de archivo nuevo: nunca reemplaza una línea base ni
otro archivo que ya exista. Para guardar otro estado, usa por ejemplo
`--baseline baseline-v2.json`. Conserva las líneas base fuera de la carpeta vigilada
para que sus nombres no aparezcan como cambios en futuras comparaciones.

Ahora puedes editar `sample-data/demo/config.txt` y repetir la verificación:

```text
Cambios detectados:
  [MODIFICADO] config.txt
```

El código de salida es `0` cuando todo coincide, `2` cuando hay diferencias y `1`
cuando existe un error. Esto permite utilizar la herramienta en automatizaciones.

## Reporte JSON

```bash
PYTHONPATH=src python -m integrity_monitor check sample-data/demo \
  --baseline baseline.json --json
```

Ejemplo reducido:

```json
{
  "changed": true,
  "summary": {
    "added": 0,
    "modified": 1,
    "deleted": 0
  }
}
```

## Cómo funciona

```text
carpeta
   ↓
recorrer archivos normales
   ↓
calcular SHA-256 por bloques
   ↓
comparar con baseline.json
   ↓
clasificar: nuevo / modificado / eliminado
```

Archivos principales:

- `core.py`: calcula hashes, guarda la línea base y compara estados.
- `models.py`: define cómo se representan un archivo y un reporte.
- `cli.py`: recibe los comandos y muestra errores comprensibles.
- `tests/`: verifica cambios, JSON, enlaces simbólicos y códigos de salida.

Los enlaces simbólicos se ignoran para no salir accidentalmente de la carpeta
observada. También se rechaza un enlace simbólico usado como carpeta raíz o como
línea base. Si una carpeta no puede leerse, la ejecución termina con un error en
lugar de presentar un recorrido incompleto como correcto.

La línea base se prepara en un archivo temporal y se publica completa mediante
un enlace duro (`os.link`), que falla si el destino ya existe. El sistema de
archivos debe admitir enlaces duros; si no los admite, se muestra un error.

## Pruebas automatizadas

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions repite las pruebas con Python 3.11 y 3.12 en cada cambio.

## Limitaciones

- Si un atacante puede modificar los archivos y la línea base, también podría
  reemplazar las huellas. En un entorno real la línea base debe protegerse aparte.
- Detecta que algo cambió, pero no identifica al responsable ni la causa.
- No vigila en tiempo real; compara estados cuando se ejecuta el comando.
- No conserva permisos, propietario ni fechas, sólo contenido y tamaño.
- No crea una instantánea del sistema de archivos. Úsalo sobre una carpeta estable:
  cambios durante la lectura pueden dar resultados incoherentes. La omisión de
  enlaces simbólicos no protege contra un atacante que cambie rutas durante el escaneo.
- Una carpeta muy grande puede tardar en procesarse.

## Ideas para seguir aprendiendo

1. Añadir patrones para ignorar archivos temporales.
2. Comparar también permisos de Linux.
3. Firmar la línea base para detectar su manipulación.
4. Ejecutar la verificación periódicamente y guardar un historial.
5. Crear una alerta local sin enviar información a servicios externos.

## Cómo explicarlo después de estudiarlo y personalizarlo

> Este proyecto guarda hashes SHA-256 de una carpeta y los compara después.
> Clasifica archivos nuevos, modificados y eliminados. Sus pruebas comprueban los
> cambios y que guardar una línea base no reemplace un archivo existente. La línea
> base debe protegerse fuera del alcance de un posible atacante.

Describe como aportación propia sólo las partes que hayas trabajado y entendido.

## Uso responsable

Analiza únicamente carpetas propias o que tengas autorización para revisar. Una
línea base puede revelar nombres de archivos sensibles, por lo que no debe subirse
a un repositorio público.

## Licencia

MIT © 2026 AVillegas118.
