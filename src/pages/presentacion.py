"""Visor local: diapositivas numeradas y videos con nombre equivalente."""
from pathlib import Path
import streamlit as st
from src.core.config import ROOT

ROOT_SLIDES=ROOT/'assets'/'presentacion'/'diapositivas'
ROOT_VIDEOS=ROOT/'assets'/'presentacion'/'videos'

def catalog():
    images=sorted([p for p in ROOT_SLIDES.iterdir() if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp')])
    return images

@st.fragment(run_every='5s')
def reproductor(images):
    if st.session_state.get('present_auto') and len(images)>1:
        st.session_state.present_idx=(st.session_state.get('present_idx',-1)+1)%len(images)
    idx=st.session_state.get('present_idx',0)%len(images)
    slide=images[idx]
    st.image(str(slide),use_container_width=True)
    st.caption(f'Diapositiva {idx+1} de {len(images)} · {slide.stem}')
    videos=[p for p in ROOT_VIDEOS.iterdir() if p.suffix.lower() in ('.mp4','.webm','.mov') and p.stem==slide.stem]
    if videos:
        st.video(str(videos[0]))
        st.caption('El video se reproduce manualmente. La reproducción automática avanza las diapositivas cada 5 segundos.')

def render():
    st.title('Presentación Nariño 360')
    st.caption('Visor de diapositivas con miniaturas, selección directa y videos asociados.')
    images=catalog()
    if not images:
        st.info('Aún no se ha incorporado el PowerPoint original. Para activar la presentación, coloca imágenes numeradas en assets/presentacion/diapositivas/ y los videos extraídos con el mismo nombre base en assets/presentacion/videos/.')
        st.code('diapositivas/001.png\nvideos/001.mp4\ndiapositivas/002.png')
        return
    if 'present_idx' not in st.session_state:st.session_state.present_idx=0
    if 'present_auto' not in st.session_state:st.session_state.present_auto=False
    a,b,c,d=st.columns([1,1,1,1])
    if a.button('◀ Anterior',use_container_width=True):st.session_state.present_idx=(st.session_state.present_idx-1)%len(images);st.session_state.present_auto=False
    if b.button('▶ Siguiente',use_container_width=True):st.session_state.present_idx=(st.session_state.present_idx+1)%len(images);st.session_state.present_auto=False
    if c.button('▶ Automático' if not st.session_state.present_auto else '⏸ Pausar',use_container_width=True):st.session_state.present_auto=not st.session_state.present_auto
    if d.button('↺ Reiniciar',use_container_width=True):st.session_state.present_idx=0;st.session_state.present_auto=False
    left,right=st.columns([3,1])
    with right:
        st.markdown('**Todas las diapositivas**')
        options=list(range(len(images)))
        choice=st.selectbox('Ir directamente a',options,index=st.session_state.present_idx,format_func=lambda i:f'{i+1:03d} · {images[i].stem}',key='selector_diapositiva')
        if st.button('Abrir diapositiva',use_container_width=True):st.session_state.present_idx=choice;st.session_state.present_auto=False;st.rerun()
        with st.container(height=420):
            for i,path in enumerate(images):
                st.image(str(path),width=145)
                if st.button(f'{i+1:03d} · {path.stem}',key=f'thumb_{i}',use_container_width=True):
                    st.session_state.present_idx=i;st.session_state.present_auto=False;st.rerun()
    with left:reproductor(images)
