"""Usuarios locales: contraseñas PBKDF2-SHA256 y sesiones Streamlit."""
import hashlib, hmac, secrets, sqlite3, time
import streamlit as st
from src.database.store import connect, now

ROLES = ('Administrador', 'Editor', 'Consulta')
ITERATIONS = 600_000

def init_auth():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS usuarios (
           id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
           nombre TEXT NOT NULL, rol TEXT NOT NULL CHECK(rol IN ('Administrador','Editor','Consulta')),
           password_hash TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1,
           creado TEXT NOT NULL, ultimo_acceso TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS accesos (
           id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL,
           username TEXT NOT NULL, evento TEXT NOT NULL)""")

def _hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'

def _verify(password, stored):
    try:
        algo, rounds, salt, digest=stored.split('$')
        if algo!='pbkdf2_sha256':return False
        current=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(current,bytes.fromhex(digest))
    except (ValueError,TypeError):return False

def _validate_password(password):
    if len(password)<12:raise ValueError('La contraseña debe contener al menos 12 caracteres.')

def user_count():
    with connect() as db:return db.execute('SELECT count(*) FROM usuarios').fetchone()[0]

def create_user(username,nombre,rol,password):
    username=username.strip().lower();nombre=nombre.strip()
    if len(username)<3 or not all(c.isascii() and (c.isalnum() or c in '._-') for c in username):raise ValueError('Usuario inválido: usa letras, números, punto, guion o guion bajo (mínimo 3 caracteres).')
    if not nombre:raise ValueError('El nombre es obligatorio.')
    if rol not in ROLES:raise ValueError('Rol inválido.')
    _validate_password(password)
    with connect() as db:
        db.execute('INSERT INTO usuarios(username,nombre,rol,password_hash,creado) VALUES (?,?,?,?,?)',(username,nombre,rol,_hash(password),now()))
        db.execute('INSERT INTO accesos(fecha,username,evento) VALUES (?,?,?)',(now(),username,'creación de usuario'))

def login(username,password):
    username=username.strip().lower()
    with connect() as db:
        user=db.execute('SELECT * FROM usuarios WHERE username=? AND activo=1',(username,)).fetchone()
        if user is None or not _verify(password,user['password_hash']):
            db.execute('INSERT INTO accesos(fecha,username,evento) VALUES(?,?,?)',(now(),username,'acceso rechazado'))
            return False
        db.execute('UPDATE usuarios SET ultimo_acceso=? WHERE id=?',(now(),user['id']))
        db.execute('INSERT INTO accesos(fecha,username,evento) VALUES(?,?,?)',(now(),username,'inicio de sesión'))
    st.session_state['user_id']=user['id']
    st.session_state['auth_at']=time.monotonic()
    return True

def current_user():
    uid=st.session_state.get('user_id')
    if not uid:return None
    # Caducidad por duración de sesión, sin confiar en cachés de roles.
    if time.monotonic()-st.session_state.get('auth_at',0)>8*3600:
        logout();return None
    with connect() as db:
        row=db.execute('SELECT id,username,nombre,rol,activo FROM usuarios WHERE id=?',(uid,)).fetchone()
    if not row or not row['activo']:
        logout();return None
    return dict(row)

def logout():
    for k in ('user_id','auth_at'):st.session_state.pop(k,None)

def require_roles(*roles):
    user=current_user()
    if user is None or user['rol'] not in roles:
        st.error('No tienes permisos para acceder a esta sección.')
        st.stop()
    return user

def list_users():
    with connect() as db:return [dict(r) for r in db.execute('SELECT id,username,nombre,rol,activo,creado,ultimo_acceso FROM usuarios ORDER BY username')]

def set_user(uid,rol,activo,actor_id):
    if rol not in ROLES:raise ValueError('Rol inválido.')
    if uid==actor_id and (not activo or rol!='Administrador'):raise ValueError('No puedes desactivar tu propia cuenta ni quitarte el rol de administrador.')
    with connect() as db:
        if not activo or rol!='Administrador':
            count=db.execute("SELECT count(*) FROM usuarios WHERE rol='Administrador' AND activo=1 AND id<>?",(uid,)).fetchone()[0]
            target=db.execute('SELECT rol,activo FROM usuarios WHERE id=?',(uid,)).fetchone()
            if target and target['rol']=='Administrador' and target['activo'] and count==0:raise ValueError('Debe mantenerse al menos un administrador activo.')
        db.execute('UPDATE usuarios SET rol=?,activo=? WHERE id=?',(rol,int(activo),uid))

def change_password(uid,password):
    _validate_password(password)
    with connect() as db:db.execute('UPDATE usuarios SET password_hash=? WHERE id=?',(_hash(password),uid))
