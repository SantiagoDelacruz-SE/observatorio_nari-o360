# Nariño 360 — acceso privado obligatorio
import streamlit as st
from src.database.store import init_db
from src.core.auth import init_auth, user_count, current_user, login, logout
from src.pages import inicio, despliegues, observatorio, georreferenciacion, evidencias, presentacion, clasificacion, administracion, importacion_actividades


st.set_page_config(page_title='Nariño 360 | Gobernación de Nariño', page_icon='🧭', layout='wide', initial_sidebar_state='collapsed')

st.markdown("""
<style>
.version-label {
    position: fixed;
    bottom: 12px;
    left: 15px;
    z-index: 9999;
    background: #0871AC;
    color: white;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    pointer-events: none;
}
</style>

<div class="version-label">
    Version: Alpha 2.0
</div>
""", unsafe_allow_html=True)

from pathlib import Path
import base64

IDENTIDAD_DIR = Path(__file__).resolve().parent / 'assets' / 'identidad'

def _logo_data(nombre):
    archivo = IDENTIDAD_DIR / nombre
    if not archivo.exists():
        return ''
    return base64.b64encode(archivo.read_bytes()).decode('ascii')

def mostrar_encabezado():
    """Encabezado compartido de acceso y páginas internas."""
    izquierda = _logo_data('gobernacion_subsecretaria_referencia.png')
    derecha = _logo_data('observatorio_referencia.png')
    logo_izq = f'<img src="data:image/png;base64,{izquierda}" alt="Gobernación de Nariño y Subsecretaría de Seguridad Ciudadana" />' if izquierda else '<span>Gobernación de Nariño</span>'
    logo_der = f'<img src="data:image/png;base64,{derecha}" alt="Observatorio de Paz, Seguridad y Convivencia" />' if derecha else '<span>Observatorio</span>'
    st.markdown(f"""
    <section class="n360-header" aria-label="Encabezado institucional">
        <div class="n360-logo n360-logo-left">{logo_izq}</div>
        <div class="n360-heading">
            <div class="n360-name">Subsecretaría de<br>Seguridad Ciudadana</div>
            <div class="n360-subtitle">Observatorio de Paz, Seguridad y Convivencia · Estrategia Nariño 360</div>
        </div>
        <div class="n360-logo n360-logo-right">{logo_der}</div>
    </section>
    """, unsafe_allow_html=True)

st.markdown("""<style>
:root {--verde:#10A13B;--amarillo:#FFD500;--azul:#0871AC;}
[data-testid="stAppViewContainer"] {background:#f4f6f8;}
[data-testid="stHeader"] {background:#f4f6f8;}
.block-container {padding-top:3.3rem!important;padding-bottom:2.5rem;max-width:1500px;}
[data-testid="stMetric"] {border:1px solid #dce7e5;border-top:4px solid var(--verde);border-radius:10px;padding:13px;}
h1,h2,h3 {color:#273341;} h1 {font-size:1.9rem!important;}
.stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"] {background:var(--verde);border-color:var(--verde);color:white;border-radius:9px;}
.stButton button[kind="primary"]:hover,.stFormSubmitButton button[kind="primary"]:hover {background:#087a2d;border-color:#087a2d;color:white;}
[data-testid="stNavigation"] [aria-current="page"] {border-bottom:3px solid var(--verde);}
.n360-header {background:#fff;display:grid;grid-template-columns:minmax(205px,1fr) minmax(350px,2fr) minmax(190px,1fr);align-items:center;gap:16px;min-height:230px;padding:27px 36px 17px;border-radius:17px;border-bottom:5px solid var(--verde);box-shadow:0 9px 26px rgba(22,40,50,.07);margin-bottom:30px;}
.n360-logo {display:flex;align-items:center;justify-content:center;}
.n360-logo img {max-width:100%;max-height:95px;object-fit:contain;}
.n360-logo-left img {max-height:92px;}
.n360-heading {text-align:center;align-self:center;}
.n360-name {font-weight:800;color:#343434;line-height:1.12;font-size:clamp(1.65rem,3.1vw,3rem);letter-spacing:-.025em;}
.n360-subtitle {font-size:clamp(.73rem,1.1vw,.97rem);color:#344454;margin-top:30px;line-height:1.4;}
.n360-login-title {text-align:center;font-size:1.7rem;font-weight:750;color:#283747;margin-bottom:2px;}
.n360-login-subtitle {text-align:center;color:#697685;margin-bottom:20px;}
.n360-session {border-top:1px solid #e2e6eb;padding-top:4px;margin-bottom:12px;}
@media(max-width:850px){.n360-header{grid-template-columns:1fr 1fr;min-height:unset;padding:20px 14px;gap:12px}.n360-heading{grid-column:1/-1;grid-row:2}.n360-logo img{max-height:72px}.n360-name{font-size:1.85rem}.n360-subtitle{margin-top:14px}.block-container{padding-top:2.1rem!important}}
</style>""",unsafe_allow_html=True)
init_db()
init_auth()
mostrar_encabezado()

def crear_administrador_inicial():
    import sqlite3
    import streamlit as st

    from src.database.store import init_db
    from src.core.auth import init_auth, user_count, create_user

    init_db()
    init_auth()

    if user_count() > 0:
        return

    bootstrap = st.secrets.get("bootstrap")

    if not bootstrap:
        return

    try:
        create_user(
            username=bootstrap["username"],
            nombre=bootstrap["nombre"],
            rol="Administrador",
            password=bootstrap["password"],
        )

    except sqlite3.IntegrityError:
        # Otra ejecución pudo haber creado el usuario al mismo tiempo.
        if user_count() > 0:
            return

        # Si no existe ningún usuario, hay otro problema de integridad.
        raise
    

crear_administrador_inicial()


if not user_count():
    st.warning('No hay cuentas de administrador configuradas. El acceso permanece bloqueado.')
    st.code('python manage_users.py create-admin', language='powershell')
    st.stop()

user = current_user()
if user is None:
    st.markdown('<div class="n360-login-title">Acceso al Sistema Institucional</div><div class="n360-login-subtitle">Ingresa con tu cuenta institucional autorizada</div>',unsafe_allow_html=True)
    espacio_izq, central, espacio_der = st.columns([1,1.15,1])
    with central:
        with st.container(border=True):
            with st.form('login'):
                username = st.text_input('Usuario',placeholder='Nombre de usuario',autocomplete='username')
                password = st.text_input('Contraseña',type='password',placeholder='Contraseña',autocomplete='current-password')
                submitted = st.form_submit_button('Iniciar sesión',type='primary',use_container_width=True)
            if submitted:
                if login(username,password):
                    st.rerun()
                else:
                    st.error('Usuario o contraseña incorrectos.')
        st.caption('Acceso exclusivo para personal y usuarios autorizados.')
    st.stop()

st.markdown('<div class="n360-session"></div>',unsafe_allow_html=True)
left,right=st.columns([6,2])
with left:
    st.caption('GOBERNACIÓN DE NARIÑO · NARIÑO 360')
with right:
    st.caption(f"{user['nombre']} · {user['rol']}")
    if st.button('Cerrar sesión',key='logout'):
        logout()
        st.rerun()

pages=[st.Page(inicio.render,title='Inicio',icon='🏠',url_path='inicio',default=True),
       st.Page(georreferenciacion.render,title='Georreferenciación',icon='🗺️',url_path='georreferenciacion'),
       st.Page(evidencias.render,title='Evidencias',icon='🖼️',url_path='evidencias'),
       st.Page(observatorio.render,title='Observatorio',icon='📄',url_path='observatorio'),
       st.Page(presentacion.render,title='Presentación',icon='▶️',url_path='presentacion')]
if user['rol'] in ('Administrador','Editor'):
    pages.insert(1,st.Page(despliegues.render,title='Despliegues',icon='📋',url_path='despliegues'))
else:
    # Consulta puede ver actividades sin usar el editor.
    pages.insert(1,st.Page(despliegues.render,title='Consultar despliegues',icon='📋',url_path='despliegues'))
if user['rol']=='Administrador':
    pages.insert(2,st.Page(clasificacion.render,title='Importar PIN',icon='📥',url_path='importar-pin'))
    pages.append(st.Page(administracion.render,title='Administración',icon='⚙️',url_path='administracion'))
    pages.insert(3, st.Page(importacion_actividades.render, title='Importar actividades', icon='📥', url_path='importar-actividades'))
st.navigation(pages,position='top').run()
