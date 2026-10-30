import streamlit as st
from src.database import store
from src.core.config import PUBLICACIONES

def render():
    st.title('Nariño 360')
    st.caption('Despliegues territoriales')
    registros=store.list_activities()
    a,b,c,d=st.columns(4)
    a.metric('PIN registrados',len(registros))
    b.metric('Municipios con PIN',len(set(r['municipio'] for r in registros if r['municipio'])))
    c.metric('Boletines disponibles',len(PUBLICACIONES))
    d.metric('Evidencias cargadas',len(store.list_evidence()))
    st.subheader('Componentes de campo')
    cols=st.columns(3)
    for col,name in zip(cols,store.COMPONENTES_HISTORICOS[:3]):
        with col:st.metric(name,sum(r['componente']==name for r in registros))
    st.info('Usa **Despliegues** para registrar actividades, **Importar PIN** para revisar el consolidado y **Observatorio** para consultar boletines.')
    if not registros:st.warning('Los PIN históricos aún requieren clasificación manual antes de importarse.')
