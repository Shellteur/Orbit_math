import streamlit as st
import numpy as np
import plotly.graph_objects as go
from orbital_math import CelestialBody, MissionController, MissionState

st.set_page_config(page_title="NASA Mission Control", layout="wide", initial_sidebar_state="expanded")
st.title("🛰️ NASA Flight Dynamics & Hohmann Simulation")

# 1. Initiera planetprofiler
profiles_db = {
    'Jorden': CelestialBody('Jorden', gm=3.986e14, r_parking=6.5e6, r_target=13.0e6, color='#2980b9'),
    'Mars':   CelestialBody('Mars',   gm=4.282e13, r_parking=3.8e6, r_target=8.5e6,  color='#e67e22'),
    'Månen':  CelestialBody('Månen',  gm=4.904e12, r_parking=1.8e6, r_target=4.5e6,  color='#95a5a6')
}

# 2. Välj planet via Streamlits sidomeny
selected_body = st.sidebar.selectbox("Välj Central Himlakropp", list(profiles_db.keys()))

# Spara tillståndet i webbläsarens minne (Session State) så det inte nollställs vid varje klick
if 'computer' not in st.session_state or st.session_state.current_body != selected_body:
    st.session_state.computer = MissionController(profiles_db[selected_body])
    st.session_state.current_body = selected_body

# 3. Kontrollknappar i sidomenyn
st.sidebar.markdown("### 🕹️ Flight Commands")
if st.sidebar.button("🚨 MANUELL OVERRIDE (BURN)", use_container_width=True):
    from orbital_math import Orbit
    comp = st.session_state.computer
    if comp.active_phase == MissionState.WAITING_WINDOW:
        comp.active_phase = MissionState.TRANSFERRING
        comp.transfer_timer = 0.0
        comp.craft.spent_delta_v += comp.dv1
        cx_angle = (comp.craft.orbit.omega + comp.craft.true_anomaly) % (2 * np.pi)
        comp.craft.orbit = Orbit(comp.body.gm, comp.a_t, comp.e_t, cx_angle)
        comp.craft.mean_anomaly = 0.0
    elif comp.active_phase == MissionState.WAITING_RETURN:
        comp.active_phase = MissionState.RETURNING
        comp.transfer_timer = 0.0
        comp.craft.spent_delta_v += comp.dv1
        cx_angle = (comp.craft.orbit.omega + comp.craft.true_anomaly) % (2 * np.pi)
        comp.craft.orbit = Orbit(comp.body.gm, comp.a_t, comp.e_t, cx_angle - np.pi)
        comp.craft.mean_anomaly = np.pi

if st.sidebar.button("🚀 PÅBÖRJA NYTT UPPDRAG", use_container_width=True):
    if st.session_state.computer.active_phase == MissionState.HOLD:
        st.session_state.computer.active_phase = MissionState.WAITING_WINDOW

# 4. Uppdatera fysiken (Kör ett steg framåt i tiden vid varje sidladdning)
cx, cy, tx, ty, r_c, v_c, a = st.session_state.computer.step_simulation(120.0)

# 5. Skapa interaktiv webbgraf via Plotly (Ersätter Matplotlib/PyQtGraph)
fig = go.Figure()
angles = np.linspace(0, 2*np.pi, 200)

# Rita banbanorna
fig.add_trace(go.Scatter(x=body.r1*np.cos(angles), y=body.r1*np.sin(angles), mode='lines', line=dict(color='#4f5b66', width=1, dash='dot'), name="Parking Orbit"))
fig.add_trace(go.Scatter(x=body.r2*np.cos(angles), y=body.r2*np.sin(angles), mode='lines', line=dict(color='#4f5b66', width=1, dash='dash'), name="Target Orbit"))

# Rita himlakroppar, farkost och mål
fig.add_trace(go.Scatter(x=[0], y=[0], mode='markers', marker=dict(size=25, color=body.color), name=body.name))
fig.add_trace(go.Scatter(x=[cx], y=[cy], mode='markers', marker=dict(size=12, color='#f1c40f', symbol='triangle-up'), name="Spacecraft"))
fig.add_trace(go.Scatter(x=[tx], y=[ty], mode='markers', marker=dict(size=10, color='#e74c3c'), name="Target Station"))

fig.update_layout(template="plotly_dark", height=650, width=650, showlegend=True, xaxis=dict(scaleanchor="y", scaleratio=1))

# Layout-uppdelning på webbsidan
col1, col2 = st.columns()
with col1:
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### ══ MISSION STATUS ══")
    st.info(f"**Flight Phase:** {st.session_state.computer.active_phase}")
    countdown_txt = f"{int(st.session_state.computer.time_to_window)} s" if "Väntar" in st.session_state.computer.active_phase else "N/A"
    st.metric(label="Hohmann Window Countdown", value=countdown_txt)
    st.metric(label="Mission Clock", value=f"{st.session_state.computer.global_time:.1f} s")
    
    st.markdown("### ══ VEHICLE TELEMETRY ══")
    st.success(f"**Orbital Velocity:** {v_c:.2f} m/s")
    st.metric(label="Altitude Radius (r)", value=f"{r_c/1e3:.1f} km")
    st.metric(label="Total Delta-V Expended", value=f"{st.session_state.computer.craft.spent_delta_v:.1f} m/s")

# Automatisk uppdatering av webbsidan
st.button("🔄 Uppdatera Telemetri / Nästa tidssteg")
