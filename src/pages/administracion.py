import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from src.core.config import ROOT
from src.database import store
from src.core import auth

def render():
    user=auth.require_roles('Administrador')
    st.title('Administración')
    st.caption('Usuarios, permisos, respaldos y bitácora.')
    st.subheader('Crear usuario')
    with st.form('nuevo_usuario'):
        a,b=st.columns(2)
        username=a.text_input('Usuario (identificador)')
        nombre=b.text_input('Nombre completo')
        rol=st.selectbox('Rol',auth.ROLES,index=1)
        pw=st.text_input('Contraseña inicial (mínimo 12 caracteres)',type='password')
        if st.form_submit_button('Crear usuario',type='primary'):
            try:auth.create_user(username,nombre,rol,pw);st.success('Usuario creado.');st.rerun()
            except Exception as exc:st.error(str(exc))
    st.subheader('Cuentas existentes')
    for account in auth.list_users():
        with st.expander(f"{account['username']} · {account['rol']} · {'Activo' if account['activo'] else 'Inactivo'}"):
            with st.form('user_'+str(account['id'])):
                role=st.selectbox('Rol',auth.ROLES,index=auth.ROLES.index(account['rol']))
                active=st.checkbox('Cuenta activa',value=bool(account['activo']))
                newpw=st.text_input('Nueva contraseña (dejar vacío para no cambiar)',type='password')
                if st.form_submit_button('Guardar cambios'):
                    try:
                        auth.set_user(account['id'],role,active,user['id'])
                        if newpw:auth.change_password(account['id'],newpw)
                        st.success('Cuenta actualizada.');st.rerun()
                    except Exception as exc:st.error(str(exc))
    st.subheader('Copia de seguridad')
    if st.button('Preparar respaldo ZIP'):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            # Use SQLite consistent backup to avoid incomplete WAL copies.
            import sqlite3
            mem=sqlite3.connect(':memory:')
            with store.connect() as con:con.backup(mem)
            dump='\n'.join(mem.iterdump())
            z.writestr('respaldo_sqlite.sql',dump)
            mem.close()
            for base in [ROOT/'data'/'evidencias',ROOT/'data'/'pendientes']:
                if base.exists():
                    for file in base.rglob('*'):
                        if file.is_file():z.write(file,file.relative_to(ROOT))
        st.download_button('Descargar respaldo',buffer.getvalue(),file_name='respaldo_narino360_'+datetime.now().strftime('%Y%m%d_%H%M')+'.zip',mime='application/zip')
    st.subheader('Auditoría de cambios')
    log=store.list_log()
    if log:st.dataframe(pd.DataFrame(log),hide_index=True,use_container_width=True)
    else:st.info('No hay operaciones registradas.')
    st.caption('FONSET permanece desactivado. Ingesta de WhatsApp eliminada.')
