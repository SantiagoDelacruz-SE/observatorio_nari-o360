"""Clasificación e importación selectiva de PIN históricos."""

import pandas as pd
import streamlit as st

from src.database.store import (
    init_db,
    source_records,
    get_classifications,
    save_classifications,
    existing_ids,
    import_records,
    COMPONENTES_HISTORICOS,
)


def render():
    from src.core.auth import require_roles

    require_roles("Administrador")
    init_db()

    st.title("Importación de PIN")
    st.caption(
        "Selecciona los PIN que deseas importar. "
        "Los demás permanecerán pendientes."
    )

    source = source_records()
    classified = get_classifications()
    existing = existing_ids()

    if not source:
        st.warning("No se encontró el consolidado de PIN.")
        return

    source_ids = {str(r["id_pin"]) for r in source}

    a, b, c = st.columns(3)
    a.metric("Total de PIN", len(source))
    b.metric("Importados", len(source_ids & existing))
    c.metric("Pendientes", len(source_ids - existing))

    rows = []

    for item in source:
        pin = str(item["id_pin"])
        imported = pin in existing

        rows.append({
            "Importar": False,
            "ID PIN": pin,
            "Estado": "Importado" if imported else "Pendiente",
            "Municipio": str(item.get("municipio") or ""),
            "Fecha original": str(item.get("fecha") or ""),
            "Actividad": str(item.get("actividad") or ""),
            "Componente": classified.get(pin, "Sin clasificar"),
        })

    df = pd.DataFrame(rows)

    st.info(
        "Marca los PIN que quieras importar y asigna su componente. "
        "No necesitas clasificar todos los registros."
    )

    edited = st.data_editor(
        df,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=[
            "ID PIN",
            "Estado",
            "Municipio",
            "Fecha original",
            "Actividad",
        ],
        column_config={
            "Importar": st.column_config.CheckboxColumn(
                "Importar",
                help="Seleccionar para importar",
                default=False,
            ),
            "Componente": st.column_config.SelectboxColumn(
                "Componente",
                options=[
                    "Sin clasificar",
                    *COMPONENTES_HISTORICOS,
                ],
                required=True,
            ),
            "Actividad": st.column_config.TextColumn(
                "Actividad",
                width="large",
            ),
        },
        key="editor_importacion_selectiva",
    )

    # Guardar clasificaciones de registros pendientes.
    choices = {}

    for _, row in edited.iterrows():
        pin = str(row["ID PIN"])

        if (
            pin not in existing
            and row["Componente"] in COMPONENTES_HISTORICOS
        ):
            choices[pin] = row["Componente"]

    selected = edited[
        edited["Importar"] == True
    ]

    selected_ids = [
        str(pin)
        for pin in selected["ID PIN"].tolist()
    ]

    already_imported = [
        pin for pin in selected_ids if pin in existing
    ]

    pending_selection = [
        pin for pin in selected_ids if pin not in existing
    ]

    missing_classification = [
        pin for pin in pending_selection
        if pin not in choices
    ]

    st.caption(
        f"Seleccionados: {len(pending_selection)} · "
        f"Sin clasificar: {len(missing_classification)} · "
        f"Ya importados seleccionados: {len(already_imported)}"
    )

    if already_imported:
        st.warning(
            "Los PIN ya importados serán omitidos: "
            + ", ".join(already_imported)
        )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Guardar clasificación",
            width="stretch",
        ):
            try:
                save_classifications(choices)
                st.success("Clasificaciones guardadas.")
            except ValueError as exc:
                st.error(str(exc))

    with col2:
        disabled = (
            not pending_selection
            or bool(missing_classification)
        )

        confirm = st.checkbox(
            "Confirmar importación seleccionada",
            disabled=disabled,
        )

    if missing_classification:
        st.warning(
            "Asigna un componente a estos PIN: "
            + ", ".join(missing_classification)
        )

    if st.button(
        f"Importar {len(pending_selection)} PIN seleccionados",
        type="primary",
        disabled=disabled or not confirm,
        width="stretch",
    ):
        try:
            # Guardar las clasificaciones antes de importar.
            save_classifications(choices)

            total = import_records(pending_selection)

            st.success(
                f"{total} PIN importados correctamente. "
                "Los demás permanecen pendientes."
            )

            st.rerun()

        except Exception as exc:
            st.error(f"No se realizó la importación: {exc}")