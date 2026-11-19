# CompatiCheck Pipeline · Demo

Repositorio de demostración del pipeline CI/CD **CompatiCheck**, creado para la
Evaluación Sumativa 4 de *Funciones y Matrices* (Ingeniería Informática).

El workflow se ejecuta en una matriz de **Windows** y **Linux** y revisa cinco
categorías de compatibilidad:

| Check | Qué detecta |
|---|---|
| Rutas | Rutas absolutas de Windows o separadores `\` en configuración |
| Mayúsculas | Imports cuyo nombre no coincide exactamente con el archivo |
| Saltos de línea | Archivos de texto con CRLF cuando se espera LF |
| Permisos | Scripts `.sh` sin bit de ejecución |
| Dependencias | Imports de terceros que no están en `requirements.txt` |

## Ejecución local

```bash
python scripts/compatcheck.py --report reports/report-local.json
```

El comando imprime los hallazgos y genera `reports/summary.md`. En GitHub Actions,
el resumen se publica en la página del run y los reportes quedan como artefactos.

## Resultado esperado

El repositorio incluye **cinco hallazgos de ejemplo**, uno por categoría. El
pipeline no falla: reporta los hallazgos para que el equipo los priorice y corrija.
