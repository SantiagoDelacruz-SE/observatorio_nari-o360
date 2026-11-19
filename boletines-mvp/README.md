# Observatorio de Nariño — MVP de automatización de boletines

Proyecto aislado en `boletines-mvp/`. No modifica los servicios existentes de Nariño 360.

## Flujo implementado
- Login con cuenta administradora y cuentas locales (estas últimas solo con almacenamiento persistente)
- Consulta de Google Sheets 01 y 03 por cuenta de servicio
- Mapeo explícito de celdas a etiquetas numéricas de Canva mediante FIELD_MAPPING_JSON
- Vista previa y CSV con estructura normalizada que **no reproduce** íntegramente el Excel 07
- Envío de campos exclusivamente de tipo `text` a un diseño de Canva cuya denominación indique COPIA o PRUEBA
- Bitácora elemental de envíos y bloqueo por contenido repetido

## Variables de Render
- `ADMIN_PASSWORD`: contraseña robusta de al menos 12 caracteres
- `SESSION_SECRET`: secreto aleatorio de al menos 32 caracteres
- `GOOGLE_SERVICE_ACCOUNT_JSON`: JSON de cuenta de servicio (dar acceso de lectura a los dos Google Sheets)
- `FIELD_MAPPING_JSON`: array validado que mapea etiquetas reales de Canva a celdas de origen
- `CANVA_ACCESS_TOKEN`: token Canva vigente (para pruebas; falta OAuth con renovación automática)
- `CANVA_TEST_DESIGN_ID`: ID de la COPIA autorizada, nunca el original
- `ENABLE_CANVA_WRITES`: solo `true` después de aprobar el mapeo y las credenciales
- `MONTH_SHEETS_JSON`: opcional, estructura de IDs por otros meses
- `DATA_DIR`: solo si se adjuntó disco persistente en Render; necesario para crear usuarios locales durables

Ejemplo conceptual de FIELD_MAPPING_JSON (sustituir únicamente con etiquetas/hojas/celdas verificadas):

```json
[
  {"key":"ETIQUETA_NUMERICA_VERIFICADA","source":"01","range":"HOJA_VERIFICADA!C12"}
]
```

## Límites del MVP
No se ha certificado el mapeo real entre 01 + 03 y 07; los archivos Google Sheets enlazados deben ser accesibles a la cuenta de servicio. No activa envíos hasta configurar fuentes, etiquetas y Canva. No publica ni modifica análisis o gráficos. Esta versión no incluye OAuth de renovación Canva, programador automático, base de datos externa ni persistencia fiable en Render Free. Para producción institucional se requiere corregir estas limitaciones y validar el acceso multiusuario.

## Estado operativo después de la segunda iteración

Se agregó:
- Diagnóstico administrativo de nombres de hojas de los libros 01, 03 y 07 (`GET /api/inspect`).
- Control previo de `00_INDICE_PAGINAS!L2`, `QA_PUBLICACION!L2:L5`, y etiquetas de `CAMPOS_CANVA` en el libro 07 antes de generar una vista previa.
- Revisión antes del envío para impedir actualizar cifras que cambiaron después de la vista previa.
- Consulta y confirmación independiente de trabajos de Canva (`POST /api/reconcile`, `GET /api/jobs`).
- Motor de revisión programada, **apagado por defecto**.

### Activación de sincronización programada

Después de validar las cuentas, permisos, fuentes, QA y Canva:
- `AUTO_SYNC_ENABLED=true` activa el planificador en el proceso Node.
- `AUTO_SYNC_MINUTES=15` establece el intervalo de revisión.
- `AUTO_SYNC_MONTHS=SEPTIEMBRE` y `AUTO_SYNC_YEAR=2026` seleccionan los periodos.
- `ENABLE_CANVA_WRITES=true` permite operaciones de escritura, exclusivamente sobre la copia autorizada.
- `REQUIRE_07_QA=true` (recomendado y predeterminado) obliga a pasar la compuerta de controles.

**Limitaciones críticas:** el programador en el proceso no garantiza ejecución continua si Render suspende la instancia. El sistema solo ejecutará ciclos automáticos si existe almacenamiento persistente (`DATA_DIR`) y credenciales válidas. No active el programador en un servicio gratuito sin procesos persistentes. La contraseña inicial de admin debe reemplazarse en Render por una que solo conozca el administrador; el código no muestra credenciales.

### Por qué no hay un mapeo final todavía

No se han podido inspeccionar directamente las celdas de los tres Google Sheets mediante el acceso institucional. Los ID de septiembre están configurados, pero todavía es imprescindible conceder acceso a la cuenta de servicio a los tres libros, ejecutar el diagnóstico de hojas y contrastar las referencias con la salida real del archivo 07.

No introduzca nombres de campo ni coordenadas de celda especulativas. La interfaz ofrece diagnóstico de hojas; el paso siguiente es validar las referencias y configurar `FIELD_MAPPING_JSON`. Hasta entonces la aplicación muestra un error informativo y **no envía cambios**.

### Producción multiusuario

La creación de usuarios secundarios exige directorio de datos persistente; una ruta temporal no lo satisface. La funcionalidad actual es un MVP experimental para entornos controlados. Antes de uso institucional real debe incorporarse almacenamiento seguro y resistente a concurrencia, renovación de credenciales Canva, rotación de secretos y controles de sesión adicionales.

## Prueba operativa más rápida: archivo 07 de septiembre
La interfaz ofrece dos caminos:
1. **Generar vista previa desde 01 + 03:** requiere `FIELD_MAPPING_JSON` con referencias de celdas confirmadas. Esta ruta todavía no construye todas las pestañas de 07.
2. **Leer 16 campos verificados del archivo 07:** consulta `SYNC_CANVA_INTERNO!A2:E17`, usa la etiqueta de la columna A y el valor de la columna E. Comprueba que las 16 etiquetas existan en `CAMPOS_CANVA!D2:D500` y que el control QA y `00_INDICE_PAGINAS!L2` permitan la operación.

Ambas rutas exigen `GOOGLE_SERVICE_ACCOUNT_JSON`. El archivo 07 se consulta en modo de solo lectura y no se sobrescribe.

La automatización programada acepta `AUTO_SYNC_SOURCE_MODE=07` (predeterminado) o `AUTO_SYNC_SOURCE_MODE=01_03` (requiere mapeo configurado). La condición `ENABLE_CANVA_WRITES=true` continúa siendo indispensable para cualquier envío.

### Acciones indispensables antes de declarar el sistema listo
- Obtener una cuenta de servicio Google desde un proyecto institucional y compartir con ella los tres libros 01, 03 y 07.
- Introducir el JSON de esa cuenta en la variable segura `GOOGLE_SERVICE_ACCOUNT_JSON` en Render.
- Abrir la aplicación como administrador y utilizar **Comprobar hojas de septiembre**.
- Activar y validar los controles QA/etiquetas en el 07 sin quitar bloqueos de un libro que aún esté pendiente de aprobación.
- Configurar el acceso autorizado a Canva y la ID de la copia de prueba, sin utilizar un diseño institucional original.
- Verificar la primera sincronización manual y la confirmación del job antes de activar la ejecución programada.
- Sustituir la contraseña inicial del administrador y habilitar almacenamiento persistente para cuentas de integrantes.

**No existe todavía una prueba de punta a punta con Google Sheets y Canva.** La compilación correcta de Render no garantiza el funcionamiento de las integraciones sin dichas credenciales.

## Renovación de credenciales Canva

Para permitir sincronizaciones sostenidas sin introducir manualmente nuevos tokens:

- Modalidad OAuth de usuario: configurar `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_REFRESH_TOKEN` y un `DATA_DIR` montado en almacenamiento persistente. La aplicación guarda de forma restringida el refresh token rotado; requiere autorización previa del usuario de Canva.
- Modalidad app de servicio: configurar `CANVA_AUTH_MODE=client_credentials`, `CANVA_CLIENT_ID` y `CANVA_CLIENT_SECRET`. Requiere una app de servicio de Canva con permisos para las operaciones y diseños. No asumir que una cuenta o diseño concreto permite esta modalidad.
- Modalidad temporal para pruebas: `CANVA_ACCESS_TOKEN`. Caduca y no es suficiente para una automatización de producción.

El token nunca debe guardarse en el repositorio ni enviarse por chat. Aunque la gestión de tokens está implementada, no se ha probado todavía con una cuenta Canva real. `ENABLE_CANVA_WRITES` se mantiene en `false` hasta el ensayo supervisado.
