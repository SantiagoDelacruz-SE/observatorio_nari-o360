from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BOLETINES_DIR = ROOT / "assets" / "boletines"
CONSOLIDADO_ORIGINAL = ROOT / "data" / "pendientes" / "consolidado_original.xlsx"
COMPONENTES = ["Acción Unificada", "Banco de Alimentos", "Cultivos para la Paz"]
PUBLICACIONES = [
    {"titulo": "Reporte delictivo y operativo diario", "tipo": "Diario", "fecha": "2026-10-27", "archivo": "diario_2026-10-27.pdf"},
    {"titulo": "Boletín estadístico semanal", "tipo": "Semanal", "fecha": "2026-10-18", "archivo": "semanal_2026-10-18.pdf"},
    {"titulo": "Monitoreo de violencias y delitos contra las mujeres", "tipo": "Temático", "fecha": "2026-08", "archivo": "tematico_feminicidios_2026-08.pdf"},
    {"titulo": "Radiografía de la violencia letal en Nariño", "tipo": "Investigación", "fecha": "2026-10-25", "archivo": "investigacion_homicidio_2026-10-25.pdf"},
]
