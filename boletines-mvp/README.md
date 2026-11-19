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
