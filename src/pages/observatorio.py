import streamlit as st
from src.core.config import PUBLICACIONES, BOLETINES_DIR

def render():
    st.title("Observatorio")
    st.caption("Biblioteca de boletines y documentos institucionales")
    tipos = ["Todos", "Diario", "Semanal", "Mensual", "Temático", "Investigación"]
    tipo = st.segmented_control("Categoría", tipos, default="Todos")
    visibles = [p for p in PUBLICACIONES if tipo == "Todos" or p["tipo"] == tipo]
    if not visibles:
        st.info("Todavía no hay documentos en esta categoría.")
        return
    etiquetas = [f'{p["fecha"]} · {p["titulo"]}' for p in visibles]
    seleccionado = st.selectbox("Publicación", range(len(etiquetas)), format_func=lambda i: etiquetas[i])
    publicacion = visibles[seleccionado]
    ruta = BOLETINES_DIR / publicacion["archivo"]
    if not ruta.is_file():
        st.error("No se encontró el archivo de esta publicación.")
        return
    st.subheader(publicacion["titulo"])
    st.caption(f'{publicacion["tipo"]} · {publicacion["fecha"]}')
    contenido = ruta.read_bytes()
    st.download_button("Descargar PDF", data=contenido, file_name=publicacion["archivo"], mime="application/pdf")
    if hasattr(st, "pdf"):
        st.pdf(contenido, height=680)
    else:
        import base64
        from streamlit.components.v1 import html
        data_url = "data:application/pdf;base64," + base64.b64encode(contenido).decode("ascii")
        html(f'<iframe src="{data_url}" style="width:100%;height:680px;border:0" title="Visor PDF"></iframe>', height=690)
        st.caption("Si el navegador bloquea la vista integrada, utiliza Descargar PDF.")
