
import json
import math
import re
from html import escape

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from src.database import store

IMPACTO_BANCO = {
    "Cultivos para la Paz": 1800,
    "Gestión Social": 9800,
    "Apoyo a Fuerza Pública": 5150,
    "Sensibilización y Prevención": 6270,
}

TOTAL_BANCO = sum(IMPACTO_BANCO.values())  # 23020

def numero(valor):
    """Convierte cantidades inequívocas; no inventa valores."""
    if isinstance(valor, bool) or valor is None:
        return None

    if isinstance(valor, (int, float)):
        return int(valor) if math.isfinite(valor) and valor >= 0 and valor == int(valor) else None

    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return None

    # Permitir separadores de miles: 1.250 o 1,250
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", texto):
        return int(re.sub(r"[.,]", "", texto))

    if texto.isdigit():
        return int(texto)

    return None


def original(registro):
    try:
        return json.loads(registro.get("contenido_original") or "{}")
    except (TypeError, ValueError):
        return {}


def coordenada(valor, minimo, maximo):
    try:
        n = float(str(valor).strip().replace(",", "."))
        if math.isfinite(n) and minimo <= n <= maximo and n != 0:
            return n
    except (TypeError, ValueError):
        pass
    return None


def tarjeta(titulo, valor, descripcion, color):
    st.markdown(
        f"""
        <div style="
            background:white;
            border-radius:15px;
            border-top:6px solid {color};
            padding:15px 17px;
            min-height:142px;
            box-shadow:0 3px 14px rgba(0,0,0,.07);
            margin-bottom:10px;
        ">
            <div style="font-size:12px;font-weight:750;
                        color:#555;letter-spacing:.5px;">
                {escape(titulo.upper())}
            </div>
            <div style="font-size:30px;font-weight:800;
                        color:{color};margin:9px 0 4px;">
                {escape(str(valor))}
            </div>
            <div style="font-size:11px;color:#777;">
                {escape(descripcion)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    st.title("Georreferenciación")
    st.caption("Impacto territorial de las actividades institucionales · Nariño 360")

    records = store.list_activities()

    if not records:
        st.info("Primero importa o registra actividades.")
        return

    municipios = sorted({
        str(r.get("municipio") or "").strip()
        for r in records
        if str(r.get("municipio") or "").strip()
    })

    filtro1, filtro2, filtro3 = st.columns([1, 1, 1])

    componente = filtro1.selectbox(
        "Componente",
        ["Todos"] + list(store.COMPONENTES_HISTORICOS),
        key="geo_componente",
    )

    municipio = filtro2.selectbox(
        "Municipio",
        ["Todos"] + municipios,
        key="geo_municipio",
    )

    capa = filtro3.radio(
        "Capa a visualizar",
        ["Mapa de calor", "Marcadores por actividad"],
        horizontal=True,
    )

    data = [
        r for r in records
        if (componente == "Todos" or r.get("componente") == componente)
        and (municipio == "Todos" or r.get("municipio") == municipio)
    ]
    
    with st.expander("Auditar población por actividad"):
        detalle = []

        for r in data:
            raw = original(r)
            detalle.append({
                "PIN": r["id_pin"],
                "Municipio": r.get("municipio"),
                "Actividad": r.get("actividad"),
                "Población original": raw.get("poblacion"),
                "Población contabilizada": numero(raw.get("poblacion")),
            })

        st.dataframe(
            pd.DataFrame(detalle),
            hide_index=True,
            width="stretch"
        )

    puntos = []
    resumen = {}
    poblacion_total = 0
    armas_total = 0
    poblacion_sin_cifra = 0
    armas_sin_cifra = 0

    for registro in data:
        raw = original(registro)
        mun = str(registro.get("municipio") or "").strip() or "Sin municipio"

        resumen.setdefault(
            mun,
            {"Municipio": mun, "Actividades": 0, "Población impactada": 0}
        )
        resumen[mun]["Actividades"] += 1

        poblacion = numero(raw.get("poblacion"))
        if poblacion is not None:
            poblacion_total += poblacion
            resumen[mun]["Población impactada"] += poblacion
        else:
            poblacion_sin_cifra += 1

        armas = numero(raw.get("armas_blancas"))
        if armas is not None:
            armas_total += armas
        else:
            armas_sin_cifra += 1

        lat = coordenada(raw.get("latitud"), -90, 90)
        lon = coordenada(raw.get("longitud"), -180, 180)

        if lat is not None and lon is not None:
            puntos.append({
                "lat": lat,
                "lon": lon,
                "pin": str(registro.get("id_pin") or ""),
                "municipio": mun,
                "componente": str(registro.get("componente") or ""),
                "poblacion": poblacion,
            })

    tabla = pd.DataFrame(
        list(resumen.values()),
        columns=["Municipio", "Actividades", "Población impactada"],
    )
    
    if componente in ("Banco de Alimentos", "Todos"):
        tabla["Población impactada"] = "Sin desglose verificado"

    if not tabla.empty:
        tabla = tabla.sort_values(
            ["Población impactada", "Actividades"],
            ascending=False
        )

    izquierda, derecha = st.columns([1.85, 1], gap="large")

    with izquierda:
        st.subheader("Mapa de impacto territorial")

        if puntos:
            lat_centro = sum(p["lat"] for p in puntos) / len(puntos)
            lon_centro = sum(p["lon"] for p in puntos) / len(puntos)
        else:
            # Centro aproximado de Nariño, solo para ubicar el mapa vacío.
            lat_centro, lon_centro = 1.29, -77.79

        mapa = folium.Map(
            location=[lat_centro, lon_centro],
            zoom_start=8 if municipio == "Todos" else 11,
            tiles="OpenStreetMap",
            control_scale=True,
        )

        if puntos:
            if capa == "Mapa de calor":
                HeatMap(
                    [[p["lat"], p["lon"], 1] for p in puntos],
                    radius=23,
                    blur=17,
                    min_opacity=0.35,
                    gradient={
                        0.2: "#80B8FF",
                        0.45: "#0871AC",
                        0.7: "#FFD500",
                        1.0: "#D91C24",
                    },
                ).add_to(mapa)
            else:
                for p in puntos:
                    detalle = (
                        f"<b>PIN:</b> {escape(p['pin'])}<br>"
                        f"<b>Municipio:</b> {escape(p['municipio'])}<br>"
                        f"<b>Componente:</b> {escape(p['componente'])}<br>"
                        f"<b>Población:</b> "
                        f"{p['poblacion'] if p['poblacion'] is not None else 'Sin cifra'}"
                    )
                    folium.CircleMarker(
                        location=[p["lat"], p["lon"]],
                        radius=7,
                        color="#10A13B",
                        weight=2,
                        fill=True,
                        fill_color="#FFD500",
                        fill_opacity=0.9,
                        popup=folium.Popup(detalle, max_width=300),
                        tooltip=f"PIN {p['pin']} · {p['municipio']}",
                    ).add_to(mapa)

            if len(puntos) > 1:
                mapa.fit_bounds([
                    [min(p["lat"] for p in puntos), min(p["lon"] for p in puntos)],
                    [max(p["lat"] for p in puntos), max(p["lon"] for p in puntos)],
                ])

        st_folium(
            mapa,
            height=625,
            use_container_width=True,
            returned_objects=[],
            key="mapa_narino_360",
        )

        st.caption(
            f"{len(puntos)} actividades con coordenadas válidas · "
            f"{len(data) - len(puntos)} sin ubicación representable."
        )

    with derecha:
        st.subheader("Indicadores de impacto")

        a, b = st.columns(2, gap="small")
        with a:
            tarjeta("Total actividades", f"{len(data):,}",
                    "Jornadas e intervenciones", "#10A13B")
        with b:
            tarjeta("Municipios alcanzados", str(
                len({r.get("municipio") for r in data if r.get("municipio")})),
                "Municipios con actividades", "#C49300")

        c, d = st.columns(2, gap="small")
        with c:
            if componente == "Banco de Alimentos" and municipio == "Todos":
                poblacion_mostrada = f"{TOTAL_BANCO:,}"
                descripcion = "Impacto general DIAN · Informe oficial"

            elif componente == "Banco de Alimentos":
                poblacion_mostrada = "S/D"
                descripcion = "Sin desglose municipal verificado"

            elif componente == "Todos":
                poblacion_mostrada = "S/D"
                descripcion = "Total intercomponentes no conciliado"

            else:
                poblacion_mostrada = f"{poblacion_total:,}"
                descripcion = "Suma de cifras por actividad"

            tarjeta(
                "Población impactada",
                poblacion_mostrada,
                descripcion,
                "#0871AC"
            )
        with d:
            tarjeta("Armas registradas", f"{armas_total:,}",
                    "Según PIN originales", "#D91C24")

        st.subheader("Impacto por municipio")
        
        if componente == "Banco de Alimentos" and municipio == "Todos":
            with st.expander("Desglose oficial del impacto", expanded=False):
                st.dataframe(
                    pd.DataFrame([
                        {"Línea de intervención": nombre, "Personas": cantidad}
                        for nombre, cantidad in IMPACTO_BANCO.items()
                    ]),
                    hide_index=True,
                    width="stretch"
                )
        
        st.dataframe(
            tabla,
            hide_index=True,
            width="stretch",
            height=255,
        )

        st.caption(
            "Las cifras corresponden únicamente a las actividades filtradas."
        )

    if poblacion_sin_cifra or armas_sin_cifra:
        st.info(
            f"Datos pendientes de normalización: "
            f"{poblacion_sin_cifra} registros sin cifra numérica de población "
            f"y {armas_sin_cifra} sin cifra numérica de armas. "
            "Estos campos no se contabilizaron como cero."
        )

    st.caption(
        "La población impactada es la suma reportada en los PIN; "
        "no representa necesariamente personas únicas. "
        "El mapa de calor muestra concentración de actividades, "
        "no concentración de población."
    )
