"""Revisión y carga idempotente de actividades desde Excel/Word; no altera PIN históricos."""
import json
from datetime import date, datetime
from src.database import store

SOURCE_FILE = store.ROOT / 'data' / 'pendientes' / 'actividades_revision.json'


def candidates():
    if not SOURCE_FILE.exists():
        return []
    raw = json.loads(SOURCE_FILE.read_text(encoding='utf-8'))
    results = []
    for values, headers in ((raw.get('accion_unificada', []), raw.get('headers_accion', [])),
                            (raw.get('banco_alimentos', []), raw.get('headers_banco', []))):
        for row in values:
            item = dict(zip(headers, row))
            pin = str(item['ID provisional']).strip()
            comp = str(item['Componente']).strip()
            if comp == 'Acción Unificada':
                record = dict(id_pin=pin, componente=comp, municipio=str(item.get('Municipio (revisar)') or ''),
                              fecha=str(item.get('Fecha original') or ''), actividad=str(item.get('Actividad') or ''),
                              lugar=str(item.get('Lugar') or ''), resultados=str(item.get('Resultados originales') or ''),
                              poblacion=item.get('Población reportada'), participantes=str(item.get('Entidades articuladas') or ''),
                              observaciones_revision=str(item.get('Observaciones') or ''),
                              fuente='ACCIONES COMPONENTE ACCION UNIFICADA.xlsx')
            else:
                record = dict(id_pin=pin, componente=comp, municipio=str(item.get('Municipio (revisar)') or ''),
                              fecha=str(item.get('Fecha ISO (propuesta)') or item.get('Fecha original') or ''),
                              fecha_original_fuente=str(item.get('Fecha original') or ''),
                              actividad=str(item.get('Actividad / entrega') or ''),
                              resultados=str(item.get('Descripción original y contexto') or ''),
                              poblacion=item.get('Población específica'),
                              seccion_informe=str(item.get('Sección de informe') or ''),
                              observaciones_revision=str(item.get('Observaciones') or ''),
                              fuente='INFORME BANCO DE ALIMENTOS.docx')
            record['registro_fuente'] = item
            results.append(record)
    ids = [r['id_pin'] for r in results]
    if len(set(ids)) != len(ids):
        raise ValueError('Existen identificadores duplicados en el archivo de revisión.')
    return results


def init_staging():
    with store.connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS revision_actividades (
            id_pin TEXT PRIMARY KEY, municipio TEXT NOT NULL DEFAULT '',
            fecha TEXT NOT NULL DEFAULT '', actividad TEXT NOT NULL DEFAULT '',
            poblacion TEXT NOT NULL DEFAULT '', estado TEXT NOT NULL DEFAULT 'Pendiente',
            actualizado TEXT NOT NULL)''')


def staged():
    init_staging()
    with store.connect() as con:
        return {r['id_pin']: dict(r) for r in con.execute('SELECT * FROM revision_actividades')}


def save_review(rows):
    init_staging()
    valid = {r['id_pin'] for r in candidates()}
    for r in rows:
        if r['id_pin'] not in valid or r['estado'] not in ('Pendiente', 'En revisión', 'Aprobada'):
            raise ValueError('Identificador o estado de revisión inválido.')
    with store.connect() as con:
        con.executemany('''INSERT INTO revision_actividades
            (id_pin,municipio,fecha,actividad,poblacion,estado,actualizado)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(id_pin) DO UPDATE SET
            municipio=excluded.municipio,fecha=excluded.fecha,
            actividad=excluded.actividad,poblacion=excluded.poblacion,
            estado=excluded.estado,actualizado=excluded.actualizado''',
            [(r['id_pin'],r['municipio'],r['fecha'],r['actividad'],r['poblacion'],r['estado'],store.now()) for r in rows])


def import_selected(ids):
    init_staging()
    ids = list(dict.fromkeys(str(x) for x in ids))
    if not ids:
        raise ValueError('Marca al menos una actividad.')
    by_id = {r['id_pin']: r for r in candidates()}
    review = staged()
    if any(i not in by_id for i in ids):
        raise ValueError('La selección contiene identificadores desconocidos.')
    payloads = []
    for pin in ids:
        source = by_id[pin]
        r = review.get(pin)
        if not r or r['estado'] != 'Aprobada':
            raise ValueError(f'{pin}: guarda primero el estado Aprobada.')
        # if not r['municipio'].strip() or not r['fecha'].strip() or not r['actividad'].strip():
        #     raise ValueError(f'{pin}: municipio, fecha y actividad son obligatorios.')
        # Fechas ambiguas o fuera del calendario deben corregirse manualmente.
        # try:
        #     actual_date = date.fromisoformat(r['fecha'])
        # except ValueError:
        #     raise ValueError(f'{pin}: la fecha debe tener formato AAAA-MM-DD.')
        # if actual_date > date.today():
        #     raise ValueError(f'{pin}: revisa la fecha futura {r["fecha"]}.')
        data = {key: source.get(key) for key in store.FIELD_NAMES}
        data.update(id_pin=pin, municipio=r['municipio'].strip(), fecha=r['fecha'],
                    actividad=r['actividad'].strip(), poblacion=r['poblacion'].strip() or None,
                    fuente=source['fuente'], registro_fuente=source['registro_fuente'],
                    seccion_informe=source.get('seccion_informe'),
                    fecha_original_fuente=source.get('fecha_original_fuente'))
        payloads.append((pin,source['componente'],r['municipio'].strip(),r['fecha'],
                         r['actividad'].strip(),json.dumps(data,ensure_ascii=False)))
    timestamp = store.now()
    with store.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        existing = {row[0] for row in con.execute('SELECT id_pin FROM actividades')}
        new = [p for p in payloads if p[0] not in existing]
        if new:
            con.executemany('''INSERT INTO actividades
                (id_pin,componente,municipio,fecha_original,actividad,contenido_original,fecha_importacion,origen)
                VALUES (?,?,?,?,?,?,?,?)''', [(*p,timestamp,'revision_externa') for p in new])
            con.execute('INSERT INTO importaciones(fecha,origen,total) VALUES(?,?,?)',
                        (timestamp,'actividades_revision',len(new)))
            con.executemany('INSERT INTO bitacora(fecha,accion,id_pin,detalle) VALUES(?,?,?,?)',
                            [(timestamp,'importación externa',p[0],p[1]) for p in new])
    return len(new), len(ids)-len(new)
