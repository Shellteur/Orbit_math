import numpy as np


# ==============================================================================
#                      FALLEXPERIMENTETS MATEMATISKA FORMLER
# ==============================================================================
#
# 1. Keplerian Angular Velocity (Vinkelhastighet för cirkulär bana):
#    Formel:  omega = sqrt( mu / r^3 )
#
# 2. Hohmann Transfer Semi-Major Axis (Halva storaxeln för transferellipsen):
#    Formel:  a_trans = (r_parking + r_target) / 2
#
# 3. Hohmann Transfer Time (Tidsåtgång för halva ellipsen):
#    Formel:  t_trans_half = pi * sqrt( a_trans^3 / mu )
#
# 4. Target Angular Travel During Transfer (Målets förflyttning i vinkel under transfern):
#    Formel:  alpha_target = omega_target * t_trans_half
#
# 5. Required Phase Angle for Ignition (Krävd fasvinkel vid Burn 1):
#    Formel:  phi_required = pi - alpha_target
#
# 6. Current Phase Angle (Nuvarande relativ fasvinkel mellan rymdfarkost och mål):
#    Formel:  phi_current = (theta_target - theta_craft) mod 2*pi
#
# 7. Vis-Viva Equation (Momentan hastighet i en Kepler-bana):
#    Formel:  v = sqrt( mu * (2/r - 1/a) )
#
# 8. Kepler's Equation for Elliptical Orbits (Keplers transcendentalekvation):
#    Formel:  M = E - e * sin(E)
#    Lösning via Newton-Raphson: E_{n+1} = E_n - (E_n - e*sin(E_n) - M) / (1 - e*cos(E_n))
#
# 9. True Anomaly from Eccentric Anomaly (Sann anomali utifrån excentrisk anomali):
#    Formel:  v_true = 2 * arctan2( sqrt(1+e)*sin(E/2), sqrt(1-e)*cos(E/2) )
#
# 10. Elliptical Radius Vector (Radieavstånd från centralkroppens fokuspunkt):
#     Formel:  r = a * (1 - e^2) / (1 + e * cos(v_true))
#
# ==============================================================================

import numpy as np


# ==============================================================================
# 1. ORBITAL ELEMENT & SPACECRAFT ABSTRACTIONS (FYSISK STRUKTUR)
# ==============================================================================
class MissionState:
    """Tillstånd i rymdfarkostens uppdragsslinga."""
    PARKING = "Staging i parkeringsbana"
    WAITING_WINDOW = "Väntar på fönster utåt"
    TRANSFERRING = "Aktiv transferellips utåt"
    RENDEZVOUS = "Målet nått - Omloppsbana synkroniserad"
    WAITING_RETURN = "Väntar på fönster hemåt"
    RETURNING = "Aktiv transferellips hemåt"
    HOLD = "Vänteläge (Hemma)"

class Orbit:
    """Representerar en ren Kepler-bana definierad av dess ban-element."""

    def __init__(self, mu, a, e=0.0, argument_of_periapsis=0.0):
        self.mu = mu  # Standard gravitationsparameter (m^3/s^2)
        self.a = a  # Halva storaxeln (m)
        self.e = e  # Excentricitet (0 = cirkulär, 0-1 = elliptisk)
        self.omega = argument_of_periapsis  # Banans rotationsvinkel i tröghetsrymden (rad)

        # Beräkna härledda element
        self.period = 2 * np.pi * np.sqrt(self.a ** 3 / self.mu)
        self.mean_motion = 2 * np.pi / self.period

    def calculate_state_at_anomaly(self, true_anomaly):
        """Beräknar radie och hastighet utifrån Vis-Viva-ekvationen vid en specifik sann anomali."""
        r = self.a * (1 - self.e ** 2) / (1 + self.e * np.cos(true_anomaly))
        v = np.sqrt(self.mu * (2.0 / r - 1.0 / self.a))
        return r, v


class Spacecraft:
    """Definierar rymdfarkosten med dess massa, bränslekapacitet och nuvarande bana."""

    def __init__(self, name, initial_orbit: Orbit, mass_kg=1000.0):
        self.name = name
        self.orbit = initial_orbit  # Den aktiva Kepler-banan farkosten färdas på
        self.mean_anomaly = 0.0  # Position mätt i medelanomali (rad)
        self.true_anomaly = 0.0  # Fysisk vinkel relativt periapsis (rad)

        self.total_mass = mass_kg
        self.spent_delta_v = 0.0  # Ackumulerat förbrukat Delta-V (m/s)

    def get_inertial_position(self):
        """Beräknar farkostens exakta tvådimensionella koordinater i tröghetsrymden."""
        r, _ = self.orbit.calculate_state_at_anomaly(self.true_anomaly)
        inertial_angle = self.orbit.omega + self.true_anomaly
        x = r * np.cos(inertial_angle)
        y = r * np.sin(inertial_angle)
        return x, y, r


# ==============================================================================
# 2. UNIVERSAL KEPLER PROPAGATOR & MANEUVER PLANNER (FYSIKMOTOR)
# ==============================================================================

class UniversalPropagator:
    """Propagerar rymdfarkoster framåt i tiden oavsett om banan är cirkulär eller elliptisk."""

    @staticmethod
    def solve_kepler(m, e, tol=1e-6):
        """Löser Keplers ekvation (M = E - e*sin(E)) via Newton-Raphson."""
        e_anom = m
        for _ in range(8):
            delta = e_anom - e * np.sin(e_anom) - m
            if abs(delta) < tol:
                break
            e_anom -= delta / (1.0 - e * np.cos(e_anom))
        return e_anom

    @classmethod
    def propagate(cls, spacecraft: Spacecraft, dt):
        """Avancerar medelanomalin och översätter den till sann anomali via Keplers lagar."""
        spacecraft.mean_anomaly += spacecraft.orbit.mean_motion * dt
        spacecraft.mean_anomaly %= (2 * np.pi)

        if spacecraft.orbit.e == 0.0:
            # Cirkulär bana: Medelanomali = Sann anomali
            spacecraft.true_anomaly = spacecraft.mean_anomaly
        else:
            # Elliptisk bana: Beräkna excentrisk anomali via Newtons metod
            e_anom = cls.solve_kepler(spacecraft.mean_anomaly, spacecraft.orbit.e)
            # Beräkna sann anomali (v)
            spacecraft.true_anomaly = 2 * np.arctan2(
                np.sqrt(1 + spacecraft.orbit.e) * np.sin(e_anom / 2.0),
                np.sqrt(1 - spacecraft.orbit.e) * np.cos(e_anom / 2.0)
            )


class ManeuverPlanner:
    """Beräknar fysikaliskt korrekta Hohmann-fönster och Delta-V för godtyckliga banor."""

    @staticmethod
    def plan_hohmann(mu, r_start, r_final):
        """Beräknar elementen för en transferbana samt nödvändiga Delta-V impulsförändringar."""
        a_transfer = (r_start + r_final) / 2.0
        e_transfer = abs(r_final - r_start) / (r_start + r_final)

        # Cirkulära starthastigheter
        v_start_circular = np.sqrt(mu / r_start)
        v_final_circular = np.sqrt(mu / r_final)

        # Hastigheter på transferellipsen (Vis-Viva)
        v_trans_at_r_start = np.sqrt(mu * (2.0 / r_start - 1.0 / a_transfer))
        v_trans_at_r_final = np.sqrt(mu * (2.0 / r_final - 1.0 / a_transfer))

        # Impulsiva Delta-V krav
        dv1 = abs(v_trans_at_r_start - v_start_circular)
        dv2 = abs(v_final_circular - v_trans_at_r_final)

        # Produktion av transfertid (sekunder för ett halvt varv)
        t_transfer = np.pi * np.sqrt(a_transfer ** 3 / mu)

        return a_transfer, e_transfer, t_transfer, dv1, dv2


# ==============================================================================
# 3. MISSION QUEUE & FLIGHT CONTROL SYSTEMS (SEKVENSSTYRNING MED HOLD-LÄGE)
# ==============================================================================

class CelestialBody:
    """Definierar en centralhimlakropps fysiska konstanter."""

    def __init__(self, name, gm, r_parking, r_target, color):
        self.name = name
        self.gm = gm
        self.r1 = r_parking
        self.r2 = r_target
        self.color = color


class MissionController:
    """NASA Flight Computer: Styr sekvenser, beräknar fönster och hanterar händelsekön."""

    def __init__(self, body: CelestialBody):
        self.body = body
        self.reset_system()

    def reset_system(self):
        """Initierar om rymdfarkost, målsatellit och nollställer händelsekön."""
        self.global_time = 0.0
        self.time_to_window = 0.0
        self.phi_current = 0.0
        self.phi_required = 0.0

        # Initiera banor
        self.orbit_inner = Orbit(self.body.gm, self.body.r1)
        self.orbit_outer = Orbit(self.body.gm, self.body.r2)

        # Skapa rymdfarkost och oberoende rörligt mål
        self.craft = Spacecraft("Orion-Capsule", self.orbit_inner)
        self.target = Spacecraft("Gateway-Station", self.orbit_outer)

        # Sätt startförskjutning så att målet inte startar på samma ställe
        self.craft.mean_anomaly = 0.0
        self.target.mean_anomaly = np.pi / 4.0  # 45 graders förskjutning

        # Förbered sekvenser för händelsekön
        self.active_phase = "Väntar på fönster utåt"
        self.transfer_timer = 0.0

        # Räkna ut statiska Hohmann-behov via vår Planner
        res = ManeuverPlanner.plan_hohmann(self.body.gm, self.body.r1, self.body.r2)
        self.a_t, self.e_t, self.t_t, self.dv1, self.dv2 = res

    def step_simulation(self, dt):
        """Körs vid varje klocktick. Propagerar fysiken och utvärderar händelsekön."""
        self.global_time += dt

        # Propagera alltid målsatelliten i sin yttre bana oavsett vad farkosten gör
        UniversalPropagator.propagate(self.target, dt)

        # Beräkna nuvarande tröghetsvinklar
        angle_craft = (self.craft.orbit.omega + self.craft.true_anomaly) % (2 * np.pi)
        angle_target = (self.target.orbit.omega + self.target.true_anomaly) % (2 * np.pi)
        self.phi_current = (angle_target - angle_craft) % (2 * np.pi)

        # Skillnad i vinkelhastighet mellan de två cirklarna (stängningshastighet)
        omega_diff = self.orbit_inner.mean_motion - self.orbit_outer.mean_motion

        # --- SEKVENSSTYRNING AV HÄNDELSEKÖN ---
        if self.active_phase == "Väntar på fönster utåt":
            UniversalPropagator.propagate(self.craft, dt)

            # Krävd fasvinkel utåt: phi = pi - (omega_target * t_transfer)
            self.phi_required = (np.pi - self.orbit_outer.mean_motion * self.t_t) % (2 * np.pi)

            phase_gap = (self.phi_current - self.phi_required) % (2 * np.pi)
            self.time_to_window = phase_gap / omega_diff if omega_diff > 0 else 0.0

            # Villkor för Burn 1 (Utresa)
            if abs(self.phi_current - self.phi_required) < (omega_diff * dt * 1.05):
                # MANÖVER: Applicera momentant Delta-V och flytta till en Transferbana
                self.active_phase = "Aktiv transfer utåt"
                self.transfer_timer = 0.0
                self.craft.spent_delta_v += self.dv1
                # Skapa en ny elliptisk bana. Dess periapsis-rotation är där farkosten befinner sig just nu!
                self.craft.orbit = Orbit(self.body.gm, self.a_t, self.e_t, argument_of_periapsis=angle_craft)
                self.craft.mean_anomaly = 0.0  # Nollställ anomalin så vi startar vid periapsis

        elif self.active_phase == "Aktiv transfer utåt":
            # Propagera farkosten längs den elliptiska banan
            UniversalPropagator.propagate(self.craft, dt)
            self.transfer_timer += dt

            if self.transfer_timer >= self.t_t:
                # MANÖVER: Vi har nått apoapsis, runda av banan med Burn 2 och synkronisera (Rendezvous)
                self.active_phase = "Väntar på fönster hemåt"
                self.craft.spent_delta_v += self.dv2
                self.craft.orbit = self.orbit_outer
                self.craft.mean_anomaly = self.target.mean_anomaly  # Perfekt dockning!

        elif self.active_phase == "Väntar på fönster hemåt":
            # Farkosten och målet glider nu oberoende eftersom målet flyttas framåt, fönstret ändras naturligt
            UniversalPropagator.propagate(self.craft, dt)

            # Krävd fasvinkel hemåt (inåt): phi = pi - (omega_inner * t_transfer)
            self.phi_required = (np.pi - self.orbit_inner.mean_motion * self.t_t) % (2 * np.pi)

            phase_gap = (self.phi_current - self.phi_required) % (2 * np.pi)
            self.time_to_window = phase_gap / omega_diff if omega_diff > 0 else 0.0

            # Villkor för Burn 3 (Hemresa)
            if abs(self.phi_current - self.phi_required) < (omega_diff * dt * 1.05):
                # MANÖVER: Bromsa in i returellipsen från nuvarande position
                self.active_phase = "Aktiv transfer hemåt"
                self.transfer_timer = 0.0
                self.craft.spent_delta_v += self.dv1  # Symmetrisk impuls
                # Returbanans apoapsis är där vi står nu. Vrid periapsis 180 grader bort (pi)
                self.craft.orbit = Orbit(self.body.gm, self.a_t, self.e_t, argument_of_periapsis=angle_craft - np.pi)
                self.craft.mean_anomaly = np.pi  # Vi startar vid apoapsis (M = pi)

        elif self.active_phase == "Aktiv transfer hemåt":
            UniversalPropagator.propagate(self.craft, dt)
            self.transfer_timer += dt

            if self.transfer_timer >= self.t_t:
                # KORRIGERAT: Istället för att starta om direkt, sätter vi farkosten i vänteläge (HOLD)
                self.active_phase = "Vänteläge (Hemma)"
                self.craft.spent_delta_v += self.dv2
                self.craft.orbit = self.orbit_inner
                self.craft.mean_anomaly = (angle_craft + np.pi) % (2 * np.pi)

        elif self.active_phase == "Vänteläge (Hemma)":
            # Farkosten bara cirkulerar passivt i innerbanan utan att påbörja ny nedräkning
            UniversalPropagator.propagate(self.craft, dt)
            self.time_to_window = 0.0
        return self.get_telemetry()

    def get_telemetry(self):
        """Beräknar och returnerar aktuella koordinater och hastigheter."""
        # Koordinater för målsatelliten
        tx = self.body.r2 * np.cos(self.target.orbit.omega + self.target.true_anomaly)
        ty = self.body.r2 * np.sin(self.target.orbit.omega + self.target.true_anomaly)

        # Hämta position för farkosten
        cx, cy, r_c = self.craft.get_inertial_position()

        # Beräkna momentan hastighet via Vis-Viva
        _, v_c = self.craft.orbit.calculate_state_at_anomaly(self.craft.true_anomaly)

        return cx, cy, tx, ty, r_c, v_c, self.craft.orbit.a


# ==============================================================================
# 4. DECOUPLED RENDERING ENGINE & INTERACTIVE GRIDS (GRÄNSSNITT - DEL 1)
# ==============================================================================

class TelemetryDashboard:
    """Grafisk motor: Ansvarar enbart för fönsterplaceringar och kontrollpaneler."""

    def __init__(self, controller: MissionController, profiles: dict):
        self.controller = controller
        self.profiles = profiles

        # Huvudfönster med mörkt kontrollrumstema
        self.fig = plt.figure(figsize=(14, 8.5), facecolor='#11141a')
        self.setup_axes()
        self.setup_widgets()
        self.rebuild_orbit_view()

    def setup_axes(self):
        """Konfigurerar statiska, icke-överlappande koordinatsystem på skärmen."""

        self.ax_orbit = self.fig.add_axes([0.05, 0.10, 0.55, 0.72], facecolor='#0b0c10')
        self.ax_radio = self.fig.add_axes([0.65, 0.76, 0.30, 0.14], facecolor='#1f2833')
        self.ax_armillary = self.fig.add_axes([0.65, 0.08, 0.30, 0.30], projection='polar', facecolor='#0b0c10')
        self.ax_slider = self.fig.add_axes([0.05, 0.90, 0.25, 0.03], facecolor='#1f2833')

        # De två fysiska knapp-axlarna staplade snyggt vertikalt under varandra
        self.ax_button = self.fig.add_axes([0.65, 0.44, 0.30, 0.04], facecolor='#1f2833')
        self.ax_btn_start = self.fig.add_axes([0.65, 0.38, 0.30, 0.04], facecolor='#1f2833')

        # Textlager (Placeras säkert i mitten utan risk för överlappning)
        self.text_mission = self.fig.text(0.65, 0.70, '', color='#ffffff', fontfamily='monospace', fontsize=10,
                                          va='top')
        self.text_telemetry = self.fig.text(0.38, 0.24, '', color='#45f3ff', fontfamily='monospace', fontsize=10,
                                            va='top')
        # MODIFIERAD (Flyttad till vänster via X-koordinat 0.05 och sänkt Y till 0.90):
        self.text_equations = self.fig.text(0.65, 0.60, '', color='#f1c40f', fontfamily='monospace', fontsize=9,
                                            va='top')

    def setup_widgets(self):
        """Initierar kontrollskjutreglage, planetväljare och de två kontrollknapparna."""
        self.warp_slider = Slider(self.ax_slider, 'Tidsskala', 1.0, 100.0, valinit=30.0, color='#45f3ff')
        self.warp_slider.label.set_color('white')

        self.radio = RadioButtons(self.ax_radio, list(self.profiles.keys()), active=0, activecolor='#45f3ff')
        for label in self.radio.labels:
            label.set_color('white')
        self.radio.on_clicked(self.handle_body_change)

        # Konfigurera Armillarsfären (Spårar Right Ascension polärt)
        self.ax_armillary.set_theta_zero_location('N')
        self.ax_armillary.set_yticklabels([])
        self.ax_armillary.tick_params(colors='#666666', labelsize=8)
        self.ax_armillary.grid(True, color='#222831', linewidth=1)
        self.armillary_craft, = self.ax_armillary.plot([], [], 'o-', color='#f1c40f', markersize=6, label='Craft RA')
        self.armillary_target, = self.ax_armillary.plot([], [], 'o--', color='#e74c3c', markersize=5, label='Target RA')
        self.ax_armillary.legend(loc='lower left', frameon=False, labelcolor='white', fontsize=7)

        # RÖD KNAPP: Manuell tvångsknapp / Override
        self.btn_return = Button(self.ax_button, 'AVFYRA MANUELL OVERRIDE (BURN)', color='#e74c3c',
                                 hovercolor='#c0392b')
        self.btn_return.label.set_color('white')
        self.btn_return.label.set_fontweight('bold')
        self.btn_return.label.set_fontsize(8)
        self.btn_return.on_clicked(self.trigger_force_burn)

        # GRÖN KNAPP: Starta ett helt nytt uppdrag utåt när man är i HOLD-läge
        self.btn_start = Button(self.ax_btn_start, 'PÅBÖRJA NYTT UPPDRAG OUTBOUND', color='#2ecc71',
                                hovercolor='#27ae60')
        self.btn_start.label.set_color('white')
        self.btn_start.label.set_fontweight('bold')
        self.btn_start.label.set_fontsize(8)
        self.btn_start.on_clicked(self.trigger_start_mission)

    def rebuild_orbit_view(self):
        """Ritar om basskalorna och banbanorna vid byte av planet."""
        self.ax_orbit.clear()
        self.ax_orbit.set_facecolor('#0b0c10')
        self.ax_orbit.grid(True, color='#1f2833', linestyle=':')
        self.ax_orbit.tick_params(colors='white')

        body = self.controller.body
        self.center_pt, = self.ax_orbit.plot(0, 0, 'o', color=body.color, markersize=22, zorder=4)
        self.line_r1, = self.ax_orbit.plot([], [], color='#4f5b66', linestyle=':', label='Parking (r1)')
        self.line_r2, = self.ax_orbit.plot([], [], color='#4f5b66', linestyle='--', label='Target (r2)')

        self.craft_dot, = self.ax_orbit.plot([], [], '^', color='#f1c40f', markersize=10, zorder=5)
        self.target_dot, = self.ax_orbit.plot([], [], 'o', color='#e74c3c', markersize=8, zorder=5)

        limit = body.r2 * 1.5
        self.ax_orbit.set_xlim(-limit, limit)
        self.ax_orbit.set_ylim(-limit, limit)
        self.ax_orbit.set_aspect('equal')
        self.ax_orbit.legend(loc='upper left', facecolor='#1f2833', labelcolor='white', fontsize=9)

    def handle_body_change(self, name):
        """Hanterar hot-swap av planetmiljö."""
        self.controller.body = self.profiles[name]
        self.controller.reset_system()
        self.rebuild_orbit_view()


    def trigger_force_burn(self, event):
        """Tvingar fram en omedelbar bränning (Override) och hoppar över väntetiden."""
        if self.controller.active_phase == "Väntar på fönster utåt":
            self.controller.active_phase = "Aktiv transfer utåt"
            self.controller.transfer_timer = 0.0
            self.controller.craft.spent_delta_v += self.controller.dv1
            cx_angle = (self.controller.craft.orbit.omega + self.controller.craft.true_anomaly) % (2 * np.pi)
            self.controller.craft.orbit = Orbit(self.controller.body.gm, self.controller.a_t, self.controller.e_t, cx_angle)
            self.controller.craft.mean_anomaly = 0.0
        elif self.controller.active_phase == "Väntar på fönster hemåt":
            self.controller.active_phase = "Aktiv transfer hemåt"
            self.controller.transfer_timer = 0.0
            self.controller.craft.spent_delta_v += self.controller.dv1
            cx_angle = (self.controller.craft.orbit.omega + self.controller.craft.true_anomaly) % (2 * np.pi)
            self.controller.craft.orbit = Orbit(self.controller.body.gm, self.controller.a_t, self.controller.e_t, cx_angle - np.pi)
            self.controller.craft.mean_anomaly = np.pi

    def trigger_start_mission(self, event):
        """Aktiverar Flight Computern och startar sökningen efter nästa utresefönster."""
        if self.controller.active_phase == "Vänteläge (Hemma)":
            self.controller.active_phase = "Väntar på fönster utåt"

    def draw_frame(self, event):
        """Renderingsloopen: Hämtar färdigberäknade tröghetskoordinater från Flight Computer."""
        dt = self.warp_slider.val * 2.0
        self.controller.step_simulation(dt)

        # Hämta råa tröghetskoordinater från rymdfarkosten och målet
        cx, cy, r_c = self.controller.craft.get_inertial_position()
        tx, ty, _ = self.controller.target.get_inertial_position()

        # Beräkna den momentana hastigheten på den nuvarande aktiva banan via Vis-Viva
        _, v_c = self.controller.craft.orbit.calculate_state_at_anomaly(self.controller.craft.true_anomaly)

        # 1. Flytta positionsmarkörerna på huvudskärmen
        self.craft_dot.set_data([cx], [cy])
        self.target_dot.set_data([tx], [ty])

        # 2. Uppdatera referenscirklarna för omloppsbanorna utifrån aktiv planet
        angles = np.linspace(0, 2 * np.pi, 120)
        self.line_r1.set_data(self.controller.body.r1 * np.cos(angles), self.controller.body.r1 * np.sin(angles))
        self.line_r2.set_data(self.controller.body.r2 * np.cos(angles), self.controller.body.r2 * np.sin(angles))

        # 3. Uppdatera Armillarsfärens vinklar (Right Ascension)
        ra_craft = (self.controller.craft.orbit.omega + self.controller.craft.true_anomaly) % (2 * np.pi)
        ra_target = (self.controller.target.orbit.omega + self.controller.target.true_anomaly) % (2 * np.pi)
        self.armillary_craft.set_data([ra_craft, ra_craft], [0, 1.0])
        self.armillary_target.set_data([ra_target, ra_target], [0, 1.0])

        # 4. Uppdatera nedräkningstexten beroende på om vi söker ett fönster eller är i HOLD-läge
        if "Väntar" in self.controller.active_phase:
            countdown_txt = f"T-Minus {int(self.controller.time_to_window)} s"
        elif self.controller.active_phase == "Vänteläge (Hemma)":
            countdown_txt = "SYSTEM READY - KLAR FÖR AVFÄRD"
        else:
            countdown_txt = "INJEKTION LOGGAD OCH AKTIV"

        # 5. Rendera textfälten till NASA-instrumentpanelerna
        mission_data = (
            f"══ MISSION CONTROL QUEUE ══════════════════\n"
            f" active body      : {self.controller.body.name}\n"
            f" mission clock    : {self.controller.global_time:.1f} s\n"
            f" flight phase     : {self.controller.active_phase}\n"
            f" hohmann window   : {countdown_txt}"
        )
        self.text_mission.set_text(mission_data)

        telemetry_data = (
            f"══ VEHICLE TELEMETRY NODE ═════════════════\n"
            f" altitude radius  : {r_c / 1e3:.1f} km\n"
            f" orbital velocity : {v_c:.2f} m/s\n"
            f" active axis (a)  : {self.controller.craft.orbit.a / 1e3:.1f} km\n"
            f" active eccentricity: {self.controller.craft.orbit.e:.4f}\n"
            f" total delta-v exp: {self.controller.craft.spent_delta_v:.1f} m/s\n"
            f" phase angle gap  : {np.degrees(self.controller.phi_current):.1f}° / Req: {np.degrees(self.controller.phi_required):.1f}°"
        )
        self.text_telemetry.set_text(telemetry_data)
        # NYTT: Bestäm vilken matematisk ekvation som körs just nu baserat på aktiv fas
        if "transfer" in self.controller.active_phase:
            equations_txt = (
                f"🧮 ACTIVE EQUATION ENGINE: VIS-VIVA & KEPLER\n"
                f"   Radius Vector: r = a*(1-e²)/(1+e*cos(v))  |  Velocity: v = sqrt(μ*(2/r - 1/a))\n"
                f"   Kepler Time Solver: M = E - e*sin(E)  -->  Newton-Raphson Iterations Active"
            )
        elif "Väntar" in self.controller.active_phase:
            equations_txt = (
                f"🧮 ACTIVE EQUATION ENGINE: SYNCHRONIZATION WINDOW\n"
                f"   Mean Motion: n = sqrt(μ/a³)  |  Transfer Time: t_trans = π*sqrt(a_trans³/μ)\n"
                f"   Required Ignition Phase Angle: φ_req = π - ω_target * t_trans"
            )
        else:
            equations_txt = (
                f"🧮 ACTIVE EQUATION ENGINE: CIRCULAR HODOGRAPH\n"
                f"   Eccentricity (e) = 0.0000  |  Constant Orbital Velocity: v = sqrt(μ/r)\n"
                f"   Mean Anomaly (M) == True Anomaly (v)"
            )

        # Skriv ut ekvationerna live i den övre panelen
        self.text_equations.set_text(equations_txt)
        self.fig.canvas.draw_idle()


# ==============================================================================
# MAIN EXECUTOR (STARTPROGRAM) - HELT UTDRAGEN TILL VÄNSTERKANTEN
# ==============================================================================
if __name__ == "__main__":
    # Registrera planetdata med exakta reella GM-konstanter
    profiles_db = {
        'Jorden': CelestialBody('Jorden', gm=3.986e14, r_parking=6.5e6, r_target=13.0e6, color='#2980b9'),
        'Mars':   CelestialBody('Mars',   gm=4.282e13, r_parking=3.8e6, r_target=8.5e6,  color='#e67e22'),
        'Månen':  CelestialBody('Månen',  gm=4.904e12, r_parking=1.8e6, r_target=4.5e6,  color='#95a5a6')
    }

    # Starta flight-computern och gränssnittet
    flight_computer = MissionController(profiles_db['Jorden'])
    dashboard = TelemetryDashboard(flight_computer, profiles_db)

    # Skapa master-klockan (30 millisekunder mellan bildrutorna)
    timer = dashboard.fig.canvas.new_timer(interval=30)
    timer.add_callback(dashboard.draw_frame, None)
    timer.start()

    # Öppna gränssnittsfönstret på skärmen
    plt.show()
