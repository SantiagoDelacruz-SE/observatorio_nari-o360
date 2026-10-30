"""Pantalla de revisión, aprobación y carga selectiva de actividades externas."""
import re
import unicodedata
import pandas as pd
import streamlit as st
from src.database import store, importacion_externa as externo
from src.core.auth import require_roles


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '').lower())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).strip()


def render():
    require_roles('Administrador')
    store.init_db()
    st.title('Importar actividades de otros archivos')
    st.caption('Banco de Alimentos y Acción Unificada. Revisión obligatoria; no se importa nada automáticamente.')
    all_rows = externo.candidates()
    saved = externo.staged()
    existing = store.existing_ids()
    if not all_rows:
        st.warning('Copia actividades_revision.json en data/pendientes/.')
        return
    opciones = ['Todos', 'Banco de Alimentos', 'Acción Unificada']
    filtro = st.selectbox('Componente', opciones)
    visible = [x for x in all_rows if filtro == 'Todos' or x['componente'] == filtro]
    rows = []
    for x in visible:
        p = x['id_pin']
        s = saved.get(p, {})
        rows.append({'Seleccionar': False, 'ID': p, 'Componente': x['componente'],
                     'Estado': 'Importada' if p in existing else s.get('estado','Pendiente'),
                     'Municipio': s.get('municipio',x['municipio']),
                     'Fecha AAAA-MM-DD': s.get('fecha',x['fecha']),
                     'Actividad': s.get('actividad',x['actividad']),
                     'Población': s.get('poblacion',str(x.get('poblacion') or ''))})
    df = pd.DataFrame(rows)
    st.metric('Registros candidatos',len(all_rows))
    edited = st.data_editor(df, hide_index=True, width='stretch', num_rows='fixed',
        disabled=['ID','Componente'],
        column_config={
            'Seleccionar':st.column_config.CheckboxColumn('Importar',default=False),
            'Estado':st.column_config.SelectboxColumn('Estado',options=['Pendiente','En revisión','Aprobada','Importada']),
            'Actividad':st.column_config.TextColumn('Actividad',width='large')},
        key='revisor_externo')
    ids = edited.loc[edited['Seleccionar']==True,'ID'].astype(str).tolist()
    new_ids = [p for p in ids if p not in existing]
    original = {x['id_pin']:x for x in all_rows}
    current = {x['id_pin']:x for x in store.list_activities()}
    # Señalar coincidencias potenciales, nunca fusionar automáticamente.
    similar = []
    for p in new_ids:
        row = edited.loc[edited['ID']==p].iloc[0]
        for old in current.values():
            if norm(row['Actividad']) and norm(row['Actividad']) == norm(old['actividad']) and norm(row['Municipio']) == norm(old['municipio']):
                similar.append(f'{p} ≈ {old["id_pin"]}')
    if similar:
        st.warning('Posibles duplicados que debes revisar: '+', '.join(similar[:20]))
    st.caption(f'Seleccionadas para importar: {len(new_ids)} · Ya existentes: {len(ids)-len(new_ids)}')
    if st.button('Guardar revisión',type='secondary'):
        externo.save_review([{'id_pin':str(r['ID']), 'municipio':str(r['Municipio'] or ''),
             'fecha':str(r['Fecha AAAA-MM-DD'] or ''), 'actividad':str(r['Actividad'] or ''),
             'poblacion':str(r['Población'] or ''),
             'estado':'Aprobada' if str(r['Estado'])=='Importada' and str(r['ID']) not in existing else
                     ('Pendiente' if str(r['Estado'])=='Importada' else str(r['Estado']))}
             for _,r in edited.iterrows() if str(r['ID']) not in existing])
        st.success('Revisión guardada. Ninguna actividad fue importada.')
    confirmar = st.checkbox('He revisado y deseo importar únicamente las actividades seleccionadas.')
    if st.button('Importar seleccionadas',type='primary',disabled=not confirmar or not new_ids):
        try:
            externo.save_review([{'id_pin':str(r['ID']), 'municipio':str(r['Municipio'] or ''),
                'fecha':str(r['Fecha AAAA-MM-DD'] or ''), 'actividad':str(r['Actividad'] or ''),
                'poblacion':str(r['Población'] or ''),
                'estado':str(r['Estado'])} for _,r in edited.iterrows()
                if str(r['ID']) in new_ids])
            n, omitted = externo.import_selected(new_ids)
            st.success(f'{n} actividades importadas; {omitted} ya existían.')
            st.rerun()
        except (ValueError,Exception) as exc:
            st.error(f'Importación cancelada: {exc}')
    st.caption('La selección es temporal. Usa Guardar revisión para conservar fechas, municipios, población y estados.')
