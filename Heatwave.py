\
import io
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta

from heatwave.utils import normalize_columns, enforce_daily
from heatwave.metrics import heat_index_c, heat_risk_band
from heatwave.forecast import forecast_location
from heatwave.alerting import compile_alerts
from heatwave.data import make_synthetic

st.set_page_config(page_title="Heatwave Early Warning System", layout="wide")

st.title("🌡 Heatwave Early Warning System")
st.caption("Streamlit demo • Local, private, and fast")

# ---------------- Sidebar Controls ----------------
with st.sidebar:
    st.header("Controls")
    data_src = st.radio("Data source", ["Sample data", "Upload CSV"], help="Upload a CSV with date, location, tmax_c, rh_percent")
    horizon = st.slider("Forecast horizon (days)", 3, 7, 5)
    gen_btn = st.button("Generate synthetic 120‑day dataset")

    st.divider()
    st.write("*Risk bands (Heat Index, °C)*")
    st.write("- < 27: Safe")
    st.write("- 27–32: Caution")
    st.write("- 32–41: Extreme Caution")
    st.write("- 41–54: Danger")
    st.write("- ≥ 54: Extreme Danger")
    st.caption("Temperature triggers: Tmax ≥ 40°C → Heatwave; ≥ 45°C → Severe")

# --------------- Load Data ------------------------
@st.cache_data(show_spinner=False)
def load_sample():
    return pd.read_csv("data/sample_weather.csv")

if data_src == "Sample data":
    df = load_sample()
else:
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up is not None:
        df = pd.read_csv(up)
    else:
        st.info("Please upload a CSV to continue, or switch to 'Sample data'.")
        st.stop()

if gen_btn:
    df = make_synthetic()

# Normalize & daily aggregate
df = normalize_columns(df)
df = enforce_daily(df)

# Derived: Heat Index and risk on history
df["heat_index_c"] = [heat_index_c(t, r) for t, r in zip(df["tmax_c"], df["rh_percent"])]
risk_cols = [heat_risk_band(hi, t) for hi, t in zip(df["heat_index_c"], df["tmax_c"])]
df["risk_level"] = [r[0] for r in risk_cols]
df["risk_color"] = [r[1] for r in risk_cols]
df["risk_note"]  = [r[2] for r in risk_cols]

# Location picker
locations = sorted(df["location"].unique())
loc = st.selectbox("Location", locations)

df_loc = df[df["location"] == loc].sort_values("date")

# ---------------- KPIs ---------------------------
today_row = df_loc.iloc[-1]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Today Tmax (°C)", f"{today_row['tmax_c']:.1f}")
k2.metric("Today RH (%)", f"{today_row['rh_percent']:.0f}")
k3.metric("Heat Index (°C)", f"{today_row['heat_index_c']:.1f}")
k4.metric("Risk", today_row["risk_level"])

# ---------------- Charts -------------------------
fig_hist = px.line(df_loc, x="date", y=["tmax_c","heat_index_c"],
                   labels={"value":"°C","variable":"Metric"}, title=f"Temperature & Heat Index — {loc}")
st.plotly_chart(fig_hist, use_container_width=True)

# Color map for risk
risk_palette = {
    "Safe":"#808080", "Caution":"#f1c40f", "Extreme Caution":"#e67e22",
    "Danger":"#e74c3c", "Extreme Danger":"#8e0000",
    "Heatwave":"#e74c3c", "Severe Heatwave":"#8e0000"
}

# Risk over time
fig_risk = px.scatter(df_loc, x="date", y="heat_index_c",
                      color="risk_level", color_discrete_map=risk_palette,
                      title=f"Risk Banding by Day — {loc}",
                      labels={"heat_index_c":"Heat Index (°C)"})
st.plotly_chart(fig_risk, use_container_width=True)

# ---------------- Forecast & Alerts ---------------
fc = forecast_location(df_loc[["date","tmax_c","rh_percent"]], horizon=horizon)
alerts = compile_alerts(df_loc, fc)

c1, c2 = st.columns([2,1])
with c1:
    fig_fc = px.line(pd.concat([
        df_loc[["date","tmax_c"]].assign(series="History"),
        fc[["date","tmax_c"]].assign(series="Forecast")
    ]), x="date", y="tmax_c", color="series", title="Tmax Forecast")
    st.plotly_chart(fig_fc, use_container_width=True)

with c2:
    st.subheader("Forecast Risk")
    st.dataframe(fc.style.format({"tmax_c":"{:.1f}","rh_percent":"{:.0f}","heat_index_c":"{:.1f}"}))

st.subheader("Early Warnings")
st.dataframe(alerts.style.format({"tmax_c":"{:.1f}","rh_percent":"{:.0f}","heat_index_c":"{:.1f}"}))

# Download alerts
csv = alerts.to_csv(index=False).encode("utf-8")
st.download_button("Download Alerts CSV", csv, file_name=f"{loc}_heatwave_alerts.csv", mime="text/csv")

st.caption("Demo only — replace with authoritative thresholds and forecasts for production.")