# Nariño 360 — versión local funcional

## Ejecutar

Requiere Python 3.11 o superior. Desde la carpeta descomprimida:

**Windows**
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

**Linux / macOS**
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

El programa abre normalmente en http://localhost:8501. Los 27 PIN históricos se encuentran en `data/pendientes/` y NO vienen importados: hay que clasificarlos manualmente en **Importar PIN** y confirmar la carga.

## Funciones

- Inicio: indicadores calculados de la base de datos.
- Despliegues: registro, búsqueda, modificación, exportación CSV y adjuntos de evidencia vinculados al PIN.
- Importar PIN: clasificación manual y carga transaccional sin sobrescritura de los 27 PIN reales.
- Georreferenciación: mapa de intensidad de coordenadas y resumen exacto de actividades por municipio. **No incluye todavía polígonos oficiales para un coroplético municipal.**
- Evidencias: galería y descarga de fotografías registradas.
- Observatorio: visor de los cuatro PDF aportados. Categorías incluyen diario, semanal, temático e investigación. Mensual está disponible cuando se añada un documento.
- Presentación: visor con imágenes/miniaturas, selección directa, avance automático a intervalos y video por diapositiva. **Los recursos de la presentación original de 1,1 GB no se adjuntaron**, por lo que la interfaz está lista pero no puede mostrar aún esa presentación.
- Administración: bitácora y descarga de respaldo de base de datos y evidencias.

## Incorporar la presentación

Extraer las diapositivas como `001.png`, `002.png`, etc. y copiarlas a `assets/presentacion/diapositivas/`. Extraer los videos incrustados a MP4 y guardarlos con el mismo nombre base de su diapositiva, por ejemplo `assets/presentacion/videos/003.mp4` para `diapositivas/003.png`. Para un PPTX, los recursos multimedia se encuentran habitualmente en la carpeta interna `ppt/media`; **esa carpeta por sí sola no indica en qué diapositiva aparece cada video**, por lo que se debe verificar y asignar manualmente. La reproducción automática avanza imágenes; los videos se reproducen mediante un reproductor independiente.

## Datos y seguridad

**Uso local / red privada controlada únicamente.** Esta versión no implementa login multiusuario. No publicar en Internet ni cargar información sensible sin antes configurar autenticación, autorización por roles, almacenamiento persistente, HTTPS y respaldos programados. SQLite y archivos de evidencia están en `data/` y no deben versionarse. Las importaciones conservan su JSON histórico y el libro original. Los cambios se registran en `bitacora`.

Las cifras del mapa corresponden a actividades institucionales, **no** a delitos reportados en los PDF. La ausencia de registros no demuestra ausencia de intervenciones. Las fechas históricas se conservan textualmente para no reinterpretar datos.

## Acceso privado (versión actual)

Antes del primer inicio, crea un administrador desde terminal con el entorno virtual activo:

```
python manage_users.py create-admin
streamlit run app.py
```

El sistema no incluye credenciales predeterminadas. Las contraseñas se almacenan con PBKDF2-SHA256 (sal aleatoria y 600.000 iteraciones). Los roles son Administrador (todo, incluida importación y usuarios), Editor (registro/edición/evidencias) y Consulta (solo lectura). Todas las páginas requieren autenticación. Las sesiones expiran a las ocho horas de autenticación. **Mantener HTTPS y una base de datos externa para despliegues públicos o múltiples instancias.**

Para actualizar una instalación anterior, conserva tu carpeta `data/` al sustituir los archivos de código. No sobrescribas la base de datos SQLite con la del ZIP.
