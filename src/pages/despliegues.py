import json
from datetime import date
import pandas as pd
import streamlit as st
from src.database import store
from src.core.config import COMPONENTES
from src.core.auth import current_user, require_roles

def form_fields(prefix,initial=None):
    d=initial or {}
    def val(k): return str(d.get(k) or '')
    with st.form(prefix):
        st.markdown('#### Identificación')
        a,b,c=st.columns([1,1,1])
        comp=a.selectbox('Componente',store.COMPONENTES_HISTORICOS,index=store.COMPONENTES_HISTORICOS.index(d.get('_componente')) if d.get('_componente') in store.COMPONENTES_HISTORICOS else 0)
        municipio=b.text_input('Municipio *',value=val('municipio'))
        fecha=c.text_input('Fecha de actividad *',value=val('fecha') or date.today().isoformat(),help='Conserva el formato histórico cuando edites un PIN.')
        a,b,c=st.columns(3)
        hora=a.text_input('Hora',value=val('hora'))
        lugar=b.text_input('Lugar',value=val('lugar'))
        comuna=c.text_input('Comuna',value=val('comuna'))
        st.markdown('#### Actividad')
        a,b=st.columns(2)
        meta=a.text_input('Meta PISCC',value=val('meta'))
        poblacion=b.text_input('Población impactada',value=val('poblacion'),help='Texto original; no se presume que represente una cifra.')
        actividad=st.text_area('Actividad *',value=val('actividad'),height=85)
        objetivo=st.text_area('Objetivo',value=val('objetivo'),height=70)
        st.markdown('#### Resultados')
        resultados=st.text_area('Resultados',value=val('resultados'),height=65)
        novedades=st.text_area('Novedades',value=val('novedades'),height=65)
        participantes=st.text_area('Participantes / instituciones',value=val('participantes'),height=65)
        a,b=st.columns(2)
        asistentes=a.number_input('Asistentes',min_value=0,value=int(d.get('asistentes') or 0),step=1)
        armas=b.number_input('Armas blancas',min_value=0,value=int(d.get('armas_blancas') or 0),step=1)
        st.markdown('#### Ubicación')
        a,b=st.columns(2)
        lat=a.text_input('Latitud (opcional)',value=val('latitud'))
        lon=b.text_input('Longitud (opcional)',value=val('longitud'))
        submitted=st.form_submit_button('Guardar actividad',type='primary',use_container_width=True)
    if not submitted: return None
    try:
        lati=float(lat.replace(',','.')) if lat.strip() else None
        longi=float(lon.replace(',','.')) if lon.strip() else None
        if lati is not None and not -90<=lati<=90: raise ValueError('Latitud fuera de rango.')
        if longi is not None and not -180<=longi<=180: raise ValueError('Longitud fuera de rango.')
        if not fecha.strip(): raise ValueError('La fecha es obligatoria.')
        return comp,dict(municipio=municipio,fecha=fecha.strip(),hora=hora,lugar=lugar,comuna=comuna,meta=meta,poblacion=poblacion,actividad=actividad,objetivo=objetivo,resultados=resultados,novedades=novedades,participantes=participantes,asistentes=asistentes,armas_blancas=armas,latitud=lati,longitud=longi)
    except ValueError as e:
        st.error(str(e));return None

def render():
    st.title('Despliegues')
    st.caption('Registro único, consulta y edición de actividades de campo y del Observatorio.')
    registros=store.list_activities()
    writable=current_user()['rol'] in ('Administrador','Editor')
    tabs=st.tabs(['➕ Nueva actividad','📋 Consultar actividades','✏️ Editar / evidencias']) if writable else [None,st.container(),None]
    crear, consultar, editar=tabs
    if writable:
      with crear:
          result=form_fields('crear_pin')
          if result:
              try:
                  pin=store.create_activity(*result)
                  st.success(f'Actividad guardada: {pin}')
                  st.info('Para adjuntar fotografías, abre la pestaña «Editar / evidencias» y selecciona el PIN.')
              except Exception as e: st.error(f'No se guardó: {e}')
    with consultar:
        if not registros: st.info('Sin actividades. Registra una o importa el consolidado.');return
        a,b,c=st.columns([1,1,2])
        opciones=['Todos']+store.COMPONENTES_HISTORICOS
        filtro=a.selectbox('Componente',opciones)
        municipio=b.selectbox('Municipio',['Todos']+sorted(set(r['municipio'] for r in registros if r['municipio'])))
        buscar=c.text_input('Buscar texto o ID')
        filtrados=[r for r in registros if (filtro=='Todos' or r['componente']==filtro) and (municipio=='Todos' or r['municipio']==municipio) and (not buscar or buscar.casefold() in (' '.join(str(r.get(k) or '') for k in ('id_pin','actividad','municipio','componente'))).casefold())]
        st.caption(f'{len(filtrados)} registros')
        st.dataframe(pd.DataFrame([{k:r[k] for k in ('id_pin','componente','municipio','fecha_original','actividad','origen')} for r in filtrados]),hide_index=True,use_container_width=True)
        if filtrados:
            selected=st.selectbox('Ver ficha completa',filtrados,format_func=lambda r:f"{r['id_pin']} — {r['actividad'][:85]}")
            st.json(json.loads(selected['contenido_original']),expanded=False)
            st.download_button('Exportar consulta CSV',pd.DataFrame([{k:r[k] for k in ('id_pin','componente','municipio','fecha_original','actividad','origen')} for r in filtrados]).to_csv(index=False).encode('utf-8-sig'),'actividades_filtradas.csv','text/csv')
    if writable:
      with editar:
          if not registros: st.info('No hay PIN para editar.');return
          pin=st.selectbox('PIN a editar', [r['id_pin'] for r in registros],key='edit_pin')
          actual=store.get_activity(pin)
          d=json.loads(actual['contenido_original']);d['_componente']=actual['componente']
          st.caption(f"ID permanente: {pin} · Origen: {actual['origen']}")
          result=form_fields('edicion_'+pin,d)
          if result:
              try:store.update_activity(pin,*result);st.success('Cambios guardados.');st.rerun()
              except Exception as e:st.error(str(e))
          st.divider()
          st.subheader('Adjuntar evidencias')
          fotos=st.file_uploader('Fotografías (máximo 15 MB cada una)',type=['jpg','jpeg','png','webp'],accept_multiple_files=True,key='fotos_'+pin)
          desc=st.text_input('Descripción (opcional)',key='desc_'+pin)
          if st.button('Guardar fotografías',disabled=not bool(fotos)):
              ok=0
              for foto in fotos:
                  try:store.add_evidence(pin,foto.name,foto.getvalue(),desc);ok+=1
                  except Exception as e:st.error(f'{foto.name}: {e}')
              if ok:st.success(f'{ok} fotografía(s) guardada(s).')
