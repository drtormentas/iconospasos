# pasos.py
import os, io, requests, math
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FuncFormatter
from PIL import Image
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import streamlit as st

st.set_page_config(page_title="El reto de los pasos", layout="wide")
st.title("El reto de los pasos")

URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT2_0hqikR5l91BeYz_3ndukNZjRWq1cC5Cbh2RhkrEdqSaAlhYrxsE9bADLnIzVLyuEkWzQfllh12H/pub?gid=0&single=true&output=csv"

@st.cache_data(ttl=60)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    cols = list(df.columns)
    rename = {cols[0]: "Nombre", cols[1]: "Pasos"}
    if len(cols) >= 3:
        rename[cols[2]] = "Icon"
    df = df.rename(columns=rename)
    df = df.dropna(subset=["Nombre"])
    df["Pasos"] = (
        df["Pasos"].astype(str).str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df = df.dropna(subset=["Pasos"]).astype({"Pasos": int})
    return df

def is_url(s): return isinstance(s, str) and s.lower().startswith(("http://","https://"))
def looks_img_path(s):
    if not isinstance(s, str): return False
    s = s.lower()
    return s.endswith((".png",".jpg",".jpeg",".webp"))

def fetch_image(icon_str, px=48):
    try:
        if is_url(icon_str):
            r = requests.get(icon_str, timeout=10)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        else:
            if not os.path.exists(icon_str): return None
            img = Image.open(icon_str).convert("RGBA")
        return img.resize((px, px), Image.LANCZOS)
    except Exception as e:
        st.warning(f"No pude cargar imagen '{icon_str}': {e}")
        return None

def draw_png(ax, x, y, pil_img):
    oi = OffsetImage(pil_img, zoom=1.0)
    ab = AnnotationBbox(oi, (x, y), frameon=False, box_alignment=(0.5, 0.5))
    ax.add_artist(ab)

# ---- helpers for “nice” axis
def nice_ceiling(x: int) -> int:
    if x <= 0:
        return 10
    exp = math.floor(math.log10(x))
    base = 10 ** exp
    for m in (1, 2, 5, 10):
        if x <= m * base:
            return m * base
    return 10 * base

def thousands(x, pos):
    return f"{int(x):,}"

def render_chart(df: pd.DataFrame):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    # winner * 2, then round up to a “nice” 1–2–5×10ⁿ
    winner = int(df["Pasos"].max())
    raw_max = max(winner * 2, 10)
    MAX_STEPS = nice_ceiling(raw_max)

    fig, ax = plt.subplots(figsize=(11, 3))
    ax.axhline(0, linewidth=1)

    STACK_STEP = 0.35
    groups = {}
    for _, row in df.iterrows():
        x = int(row["Pasos"])
        groups.setdefault(x, []).append(row)

    for x, rows in sorted(groups.items()):
        n = len(rows)
        start_y = 0.55 - (n - 1) * (STACK_STEP / 2.0)
        for i, row in enumerate(rows):
            y = start_y + i * STACK_STEP
            name = str(row["Nombre"])
            steps = int(row["Pasos"])
            icon = str(row.get("Icon", "")).strip() if "Icon" in row and pd.notna(row.get("Icon")) else ""

            placed = False
            if icon:
                if is_url(icon) or looks_img_path(icon):
                    img = fetch_image(icon, px=48)
                    if img is not None:
                        draw_png(ax, steps, y, img)
                        placed = True
                else:
                    ax.text(steps, y, icon, ha="center", va="center", fontsize=22)
                    placed = True

            if not placed:
                ax.plot(steps, y, "o", markersize=8)

            ax.text(steps, y + 0.35, name, ha="center", va="bottom",
                    fontsize=9, fontweight="bold")
            ax.plot([steps, steps], [0.02, y - 0.02], linewidth=0.8, alpha=0.6)

    # nice ticks: 10 divisions across the rounded MAX_STEPS
    tick_step = max(1, MAX_STEPS // 10)
    ax.set_xlim(0, MAX_STEPS)
    ax.xaxis.set_major_locator(MultipleLocator(tick_step))
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))

    ax.set_ylim(-0.6, 1.6)
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Cantidad caminada", fontsize=14, pad=10)

    st.pyplot(fig, clear_figure=True)

# ---- main
try:
    df = load_data(URL)
    with st.expander("Ver datos"):
        st.dataframe(df, use_container_width=True)
    render_chart(df)
except Exception as e:
    st.error("Ocurrió un error al construir la página.")
    st.exception(e)
