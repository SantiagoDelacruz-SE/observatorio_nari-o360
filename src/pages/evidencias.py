"""Mural: fotos de actividades y anexos fotográficos pendientes de vinculación."""
import json
from pathlib import Path
import streamlit as st
from src.core.config import ROOT
from src.database import store

FOLDER = ROOT / 'assets' / 'evidencias_informe'
CATALOG = FOLDER / 'catalogo.json'


imagenes = sorted(
    p for p in FOLDER.rglob("*")
    if p.is_file()
    and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
)

def anexos_informe():
    catalogo = {}

    # Leer información de las imágenes originales.
    if CATALOG.is_file():
        try:
            rows = json.loads(CATALOG.read_text(encoding="utf-8"))

            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("archivo"):
                        catalogo[str(row["archivo"])] = row

        except (OSError, ValueError, TypeError):
            pass

    # Detectar automáticamente todas las imágenes de la carpeta.
    # Identificar imágenes originales del informe
    archivos_informe = set(catalogo.keys())

    # Buscar todas las fotografías
    imagenes = [
        p for p in FOLDER.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]

    # Primero manuales, después originales del Word
    imagenes.sort(
        key=lambda p: (
            p.relative_to(FOLDER).as_posix() in archivos_informe,
            -p.stat().st_mtime
        )
    )
    anexos = []

    for numero, imagen in enumerate(imagenes, start=1):
        ruta = imagen.relative_to(FOLDER).as_posix()
        datos = catalogo.get(ruta, {})

        anexos.append({
            "archivo": ruta,
            "orden": numero,
            "imagen_origen": datos.get(
                "imagen_origen",
                "Fotografía agregada manualmente"
            )
        })

    return anexos


def mostrar_fotos_registradas():
    fotos = store.list_evidence()
    if not fotos:
        st.info('Todavía no hay fotografías vinculadas a PIN en la base de datos.')
        return
    a, b = st.columns(2)
    componentes = sorted({str(f.get('componente') or '') for f in fotos if f.get('componente')})
    municipios = sorted({str(f.get('municipio') or '') for f in fotos if f.get('municipio')})
    comp = a.selectbox('Componente', ['Todos'] + componentes, key='ev_comp')
    mun = b.selectbox('Municipio', ['Todos'] + municipios, key='ev_mun')
    fotos = [f for f in fotos if (comp == 'Todos' or f.get('componente') == comp)
             and (mun == 'Todos' or f.get('municipio') == mun)]
    st.caption(f'{len(fotos)} fotografías vinculadas a actividades')
    for index in range(0, len(fotos), 3):
        cols = st.columns(3)
        for col, item in zip(cols, fotos[index:index+3]):
            with col:
                path = ROOT / str(item.get('archivo') or '')
                if path.is_file():
                    st.image(str(path), width='stretch')
                    st.download_button('Descargar fotografía', path.read_bytes(),
                                       file_name=item.get('nombre_original') or path.name,
                                       key='ev_dl_' + str(item.get('id')))
                else:
                    st.warning('Imagen no disponible')
                st.markdown(f"**PIN {item.get('id_pin', '')}** · {item.get('municipio') or 'Sin municipio'}")
                st.caption(str(item.get('componente') or ''))
                if item.get('descripcion'):
                    st.write(str(item['descripcion']))


def mostrar_anexos():
    anexos = anexos_informe()
    if not anexos:
        st.info('No se han añadido imágenes extraídas del informe todavía.')
        return
    st.caption(f"{len(anexos)} evidencias fotográficas disponibles · Sin vínculo a PIN")
    # st.info('Estas imágenes proceden del Word. Aún no se ha verificado a qué actividad corresponde cada una; algunas pueden ser gráficos o logos del informe.')
    for index in range(0, len(anexos), 3):
        cols = st.columns(3)
        for col, item in zip(cols, anexos[index:index+3]):
            with col:
                path = FOLDER / item['archivo']
                st.image(str(path), width='stretch')
                st.caption(f"Imagen {item['orden']:03d} · {item['imagen_origen']}")
                st.download_button('Descargar', path.read_bytes(),
                                   file_name=item['archivo'], key='anexo_dl_' + str(item['orden']))


def render():
    st.title('Mural de evidencias')
    st.caption('Galería de registros fotográficos institucionales')
    tabs = st.tabs(['Evidencias del informe', 'Evidencias vinculadas a PIN'])
    with tabs[0]:
        mostrar_anexos()
    with tabs[1]:
        mostrar_fotos_registradas()
