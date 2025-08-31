# pasos.py
import os, io, requests, math
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, FuncFormatter
from PIL import Image
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import streamlit as st

st.set_page_config(page_title="El reto de las tesis", layout="wide")
st.title("El reto de las tesis")

URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT2_0hqikR5l91BeYz_3ndukNZjRWq1cC5Cbh2RhkrEdqSaAlhYrxsE9bADLnIzVLyuEkWzQfllh12H/pub?gid=0&single=true&output=csv"

# ----------------------- Data -----------------------

@st.cache_data(ttl=60)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url).dropna(how="all")

    # Normaliza primeras 3 columnas a: Nombre, Paginas, Icon
    cols = list(df.columns)
    rename = {cols[0]: "Nombre", cols[1]: "Paginas"}
    if len(cols) >= 3:
        rename[cols[2]] = "Icon"
    df = df.rename(columns=rename)

    # Primero descarta nombres nulos, luego limpia strings
    df = df.dropna(subset=["Nombre"])
    df["Nombre"] = df["Nombre"].astype(str).str.strip()
    df = df[df["Nombre"] != ""]

    # Paginas → int
    df["Paginas"] = (
        df["Paginas"].astype(str).str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df = df.dropna(subset=["Paginas"]).astype({"Paginas": int})

    keep = ["Nombre", "Paginas"] + (["Icon"] if "Icon" in df.columns else [])
    return df[keep]

def is_url(s: str) -> bool:
    return isinstance(s, str) and s.lower().startswith(("http://", "https://"))

def looks_img_path(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.lower()
    return s.endswith((".png", ".jpg", ".jpeg", ".webp"))

def to_raw_if_github(url: str) -> str:
    # https://github.com/u/r/blob/sha/path -> https://raw.githubusercontent.com/u/r/sha/path
    if isinstance(url, str) and "github.com" in url and "/blob/" in url:
        return url.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
    return url

@st.cache_data(show_spinner=False)
def fetch_image(icon_str: str, px: int = 48):
    try:
        if not isinstance(icon_str, str) or not icon_str.strip():
            return None
        icon_str = to_raw_if_github(icon_str.strip())

        if is_url(icon_str):
            r = requests.get(
                icon_str, timeout=10, allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        else:
            if not os.path.exists(icon_str):
                return None
            img = Image.open(icon_str).convert("RGBA")

        return img.resize((px, px), Image.LANCZOS)

    except Exception as e:
        st.warning(f"No pude cargar imagen: {icon_str}\nDetalles: {e}")
        return None

def draw_png(ax, x, y, pil_img):
    oi = OffsetImage(pil_img, zoom=1.0)
    ab = AnnotationBbox(oi, (x, y), frameon=False, box_alignment=(0.5, 0.5))
    ax.add_artist(ab)

def thousands(x, pos):
    return f"{int(x):,}"

# --------------------- Plotting ---------------------

def render_chart(df: pd.DataFrame):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    # Eje máximo = 1.5× el líder (exacto)
    winner = int(df["Paginas"].max())
    MAX_STEPS = max(int(math.ceil(winner * 1.5)), 10)

    fig, ax = plt.subplots(figsize=(11, 3))
    ax.axhline(0, linewidth=1)

    # 1) Entradas con y-base (apila si comparten x)
    STACK_STEP = 0.35
    by_x = {}
    entries = []
    for _, row in df.iterrows():
        steps = int(row["Paginas"])
        name = str(row["Nombre"])
        icon = str(row.get("Icon", "")).strip() if "Icon" in row and pd.notna(row.get("Icon")) else ""
        level = by_x.get(steps, 0)
        base_y = 0.55 + (level * STACK_STEP)
        by_x[steps] = level + 1
        entries.append({"steps": steps, "name": name, "icon": icon, "base_y": base_y})

    # 2) Escalonar etiquetas (nombres) cuando están cerca en x
    NEAR_PCT = 0.03                    # cercanía = 3% del eje
    dx_thresh = MAX_STEPS * NEAR_PCT
    LABEL_LEVELS = [0.35, 0.60, 0.85]  # offsets verticales

    entries.sort(key=lambda e: e["steps"])
    cluster_start = 0
    for i in range(len(entries)):
        if i == cluster_start:
            entries[i]["label_level"] = 0
            continue
        if entries[i]["steps"] - entries[i-1]["steps"] > dx_thresh:
            cluster_start = i
            entries[i]["label_level"] = 0
        else:
            prev_level = entries[i-1].get("label_level", 0)
            entries[i]["label_level"] = (prev_level + 1) % len(LABEL_LEVELS)

    # 3) Dibujar iconos / marcadores + nombres
    for e in entries:
        steps, name, icon, base_y = e["steps"], e["name"], e["icon"], e["base_y"]

        placed = False
        if icon:
            if is_url(icon) or looks_img_path(icon):
                img = fetch_image(icon, px=48)
                if img is not None:
                    draw_png(ax, steps, base_y, img); placed = True
            else:
                ax.text(steps, base_y, icon, ha="center", va="center", fontsize=22); placed = True

        if not placed:
            ax.plot(steps, base_y, "o", markersize=8)

        name_y = base_y + LABEL_LEVELS[e["label_level"]]
        ax.text(steps, name_y, name, ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.plot([steps, steps], [0.02, base_y - 0.02], linewidth=0.8, alpha=0.6)

    # 4) Ticks & estilo
    ax.set_xlim(0, MAX_STEPS)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=10, integer=True, steps=[1, 2, 5, 10]))
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_ylim(-0.6, 2.0)
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Cantidad caminada", fontsize=14, pad=10)

    st.pyplot(fig, clear_figure=True)

# ---------------------- Main -----------------------

if __name__ == "__main__":
    try:
        df = load_data(URL)

        # En la tabla solo mostramos Nombre + Paginas (sin índice)
        with st.expander("Ver datos"):
            st.dataframe(
                df[["Nombre", "Paginas"]].reset_index(drop=True).style.hide(axis="index"),
                use_container_width=True
            )

        # Para el gráfico usamos el df completo (con Icon)
        render_chart(df)

    except Exception as e:
        st.error("Ocurrió un error al construir la página.")
        st.exception(e)
