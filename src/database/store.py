"""Almacenamiento local transaccional. Los PIN históricos conservan su JSON original."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from src.core.config import ROOT

DB_PATH = ROOT / 'data' / 'narino360.sqlite3'
SOURCE_PATH = ROOT / 'data' / 'pendientes' / 'consolidado_fuente.json'
EVIDENCE_DIR = ROOT / 'data' / 'evidencias'
COMPONENTES_HISTORICOS = ['Acción Unificada','Banco de Alimentos','Cultivos para la Paz','Observatorio']
FIELD_NAMES = ('municipio','fecha','hora','lugar','comuna','meta','poblacion','actividad','resultados','objetivo','novedades','participantes','armas_blancas','asistentes','latitud','longitud','rutas_fotos','fecha_registro')

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def init_db():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS actividades (
           id_pin TEXT PRIMARY KEY NOT NULL,
           componente TEXT NOT NULL CHECK(componente IN ('Acción Unificada','Banco de Alimentos','Cultivos para la Paz','Observatorio')),
           municipio TEXT, fecha_original TEXT, actividad TEXT,
           contenido_original TEXT NOT NULL,
           fecha_importacion TEXT NOT NULL,
           origen TEXT NOT NULL DEFAULT 'consolidado'
        );
        CREATE TABLE IF NOT EXISTS clasificaciones (
           id_pin TEXT PRIMARY KEY NOT NULL,
           componente TEXT NOT NULL CHECK(componente IN ('Acción Unificada','Banco de Alimentos','Cultivos para la Paz','Observatorio'))
        );
        CREATE TABLE IF NOT EXISTS importaciones (
           id INTEGER PRIMARY KEY AUTOINCREMENT,fecha TEXT NOT NULL,origen TEXT NOT NULL,total INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidencias (
           id TEXT PRIMARY KEY, id_pin TEXT NOT NULL REFERENCES actividades(id_pin) ON DELETE CASCADE,
           archivo TEXT NOT NULL, nombre_original TEXT NOT NULL, fecha TEXT NOT NULL,
           descripcion TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS bitacora (
           id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, accion TEXT NOT NULL,
           id_pin TEXT, detalle TEXT
        );
        ''')

def source_records():
    if not SOURCE_PATH.exists(): return []
    return json.loads(SOURCE_PATH.read_text(encoding='utf-8'))

def get_classifications():
    with connect() as con: return dict(con.execute('SELECT id_pin, componente FROM clasificaciones').fetchall())

def save_classifications(mapping):
    valid={r['id_pin'] for r in source_records()}
    if any(k not in valid or v not in COMPONENTES_HISTORICOS for k,v in mapping.items()): raise ValueError('Clasificación inválida.')
    with connect() as con:
        con.executemany('INSERT INTO clasificaciones(id_pin,componente) VALUES(?,?) ON CONFLICT(id_pin) DO UPDATE SET componente=excluded.componente',list(mapping.items()))

def existing_ids():
    with connect() as con: return {r[0] for r in con.execute('SELECT id_pin FROM actividades')}

def import_records(selected_ids):
    records = source_records()
    classifications = get_classifications()

    selected_ids = list(dict.fromkeys(str(x) for x in selected_ids))

    if not selected_ids:
        raise ValueError("Selecciona al menos un PIN.")

    source_by_id = {str(r["id_pin"]): r for r in records}

    unknown = set(selected_ids) - set(source_by_id)
    if unknown:
        raise ValueError(f"PIN inexistentes en el consolidado: {unknown}")

    missing = [
        pin for pin in selected_ids
        if classifications.get(pin) not in COMPONENTES_HISTORICOS
    ]
    if missing:
        raise ValueError(
            "Los PIN seleccionados necesitan un componente: "
            + ", ".join(missing)
        )

    timestamp = now()

    with connect() as con:
        con.execute("BEGIN IMMEDIATE")

        existing = {
            row[0]
            for row in con.execute(
                "SELECT id_pin FROM actividades"
            )
        }

        pending = [
            source_by_id[pin]
            for pin in selected_ids
            if pin not in existing
        ]

        for r in pending:
            pin = str(r["id_pin"])

            con.execute(
                """
                INSERT INTO actividades(
                    id_pin, componente, municipio,
                    fecha_original, actividad,
                    contenido_original, fecha_importacion, origen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pin,
                    classifications[pin],
                    str(r.get("municipio") or ""),
                    str(r.get("fecha") or ""),
                    str(r.get("actividad") or ""),
                    json.dumps(r, ensure_ascii=False),
                    timestamp,
                    "consolidado",
                )
            )

        if pending:
            con.execute(
                """
                INSERT INTO importaciones(fecha, origen, total)
                VALUES (?, ?, ?)
                """,
                (
                    timestamp,
                    "consolidado_original.xlsx",
                    len(pending),
                )
            )

            con.execute(
                """
                INSERT INTO bitacora(fecha, accion, detalle)
                VALUES (?, ?, ?)
                """,
                (
                    timestamp,
                    "importación selectiva",
                    f"{len(pending)} PIN",
                )
            )

    return len(pending)

def list_activities():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT id_pin,componente,municipio,fecha_original,actividad,origen,contenido_original,fecha_importacion FROM actividades ORDER BY fecha_importacion DESC,id_pin')]

def get_activity(pin):
    with connect() as con:
        row=con.execute('SELECT * FROM actividades WHERE id_pin=?',(pin,)).fetchone()
        return dict(row) if row else None

def new_pin(): return 'PIN-' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:8].upper()

def create_activity(componente,data):
    if componente not in COMPONENTES_HISTORICOS: raise ValueError('Componente inválido.')
    if not str(data.get('municipio') or '').strip() or not str(data.get('actividad') or '').strip() or not str(data.get('fecha') or '').strip():
        raise ValueError('Municipio, fecha y actividad son obligatorios.')
    if (data.get('latitud') is None) != (data.get('longitud') is None): raise ValueError('Indica ambas coordenadas o ninguna.')
    pin=new_pin(); timestamp=now(); payload={key:data.get(key) for key in FIELD_NAMES}
    payload['id_pin']=pin;payload['fecha_registro']=timestamp
    with connect() as con:
        con.execute('''INSERT INTO actividades(id_pin,componente,municipio,fecha_original,actividad,contenido_original,fecha_importacion,origen)
        VALUES(?,?,?,?,?,?,?,?)''',(pin,componente,data['municipio'].strip(),data['fecha'],data['actividad'].strip(),json.dumps(payload,ensure_ascii=False),timestamp,'manual'))
        con.execute('INSERT INTO bitacora(fecha,accion,id_pin) VALUES(?,?,?)',(timestamp,'creación',pin))
    return pin

def update_activity(pin,componente,data):
    if componente not in COMPONENTES_HISTORICOS: raise ValueError('Componente inválido.')
    if not str(data.get('municipio') or '').strip() or not str(data.get('actividad') or '').strip(): raise ValueError('Municipio y actividad son obligatorios.')
    if (data.get('latitud') is None) != (data.get('longitud') is None): raise ValueError('Indica ambas coordenadas o ninguna.')
    with connect() as con:
        old=con.execute('SELECT * FROM actividades WHERE id_pin=?',(pin,)).fetchone()
        if old is None: raise ValueError('PIN no encontrado.')
        previous=json.loads(old['contenido_original']); previous.update({k:data.get(k) for k in FIELD_NAMES if k in data})
        previous['id_pin']=pin
        con.execute('UPDATE actividades SET componente=?, municipio=?, fecha_original=?, actividad=?, contenido_original=? WHERE id_pin=?',
            (componente,str(previous.get('municipio') or ''),str(previous.get('fecha') or ''),str(previous.get('actividad') or ''),json.dumps(previous,ensure_ascii=False),pin))
        con.execute('INSERT INTO bitacora(fecha,accion,id_pin,detalle) VALUES(?,?,?,?)',(now(),'edición',pin,'Contenido anterior: '+old['contenido_original']))

def add_evidence(pin,original,content,description=''):
    if not get_activity(pin): raise ValueError('El PIN no existe.')
    if not content or len(content)>15*1024*1024: raise ValueError('Imagen vacía o superior a 15 MB.')
    from PIL import Image,UnidentifiedImageError
    import io
    try:
        image=Image.open(io.BytesIO(content)); image.verify()
        image=Image.open(io.BytesIO(content)); image.load()
        if image.format not in ('JPEG','PNG','WEBP'): raise ValueError('Formato no admitido.')
    except (UnidentifiedImageError,OSError) as e: raise ValueError('Imagen inválida.') from e
    ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[image.format]
    ident=uuid.uuid4().hex
    folder=EVIDENCE_DIR / uuid.uuid5(uuid.NAMESPACE_URL,pin).hex
    folder.mkdir(parents=True,exist_ok=True)
    destination=folder/(ident+ext)
    destination.write_bytes(content)
    try:
        with connect() as con:
            con.execute('INSERT INTO evidencias(id,id_pin,archivo,nombre_original,fecha,descripcion) VALUES(?,?,?,?,?,?)',
                (ident,pin,str(destination.relative_to(ROOT)),Path(original).name,now(),description.strip()))
            con.execute('INSERT INTO bitacora(fecha,accion,id_pin,detalle) VALUES(?,?,?,?)',(now(),'evidencia',pin,Path(original).name))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return ident

def list_evidence(pin=None):
    with connect() as con:
        sql='''SELECT e.*,a.componente,a.municipio,a.actividad FROM evidencias e JOIN actividades a ON a.id_pin=e.id_pin'''
        if pin: return [dict(r) for r in con.execute(sql+' WHERE e.id_pin=? ORDER BY e.fecha DESC',(pin,))]
        return [dict(r) for r in con.execute(sql+' ORDER BY e.fecha DESC')]

def list_log():
    with connect() as con: return [dict(r) for r in con.execute('SELECT * FROM bitacora ORDER BY id DESC LIMIT 200')]
