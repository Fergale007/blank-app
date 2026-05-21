"""Ficha · Control Horario SaaS — RDL 8/2019 · ET Arts. 34/35/38 · RGPD — build:20260521"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
from datetime import datetime, date, timedelta
from io import BytesIO
import db

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ficha · Control Horario",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f0f2f5; }
[data-testid="stSidebar"] { background: #1e1f2e !important; }
[data-testid="stSidebar"] * { color: #c9cde6 !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 12px; border-radius: 8px; display:block;
    transition: background .2s; cursor:pointer;
}
[data-testid="stSidebar"] .stRadio label:hover { background: #2d2f45 !important; }

/* Cards */
.card {
    background: white; border-radius: 12px; padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 16px;
}
.card-sm { background: white; border-radius: 10px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.07); }

/* KPI metrics */
.kpi { text-align:center; padding:16px; background:white; border-radius:12px; box-shadow:0 1px 4px rgba(0,0,0,.08); }
.kpi-val { font-size:2.2rem; font-weight:700; color:#4f46e5; margin:0; }
.kpi-label { font-size:.85rem; color:#64748b; margin:0; }

/* Status badges */
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }
.badge-verde    { background:#d1fae5; color:#065f46; }
.badge-amarillo { background:#fef3c7; color:#92400e; }
.badge-rojo     { background:#fee2e2; color:#991b1b; }
.badge-gris     { background:#f1f5f9; color:#475569; }
.badge-blue     { background:#dbeafe; color:#1e40af; }
.badge-purple   { background:#ede9fe; color:#5b21b6; }

/* Calendar */
.cal-wrapper { overflow-x:auto; }
.cal-table { width:100%; border-collapse:separate; border-spacing:4px; }
.cal-table th { text-align:center; font-size:.8rem; color:#94a3b8; font-weight:600; padding:6px; }
.cal-day {
    width:40px; height:40px; border-radius:8px; text-align:center;
    vertical-align:middle; font-size:.85rem; font-weight:500;
    cursor:pointer; transition:transform .1s, box-shadow .1s;
}
.cal-day:hover { transform:scale(1.1); box-shadow:0 2px 8px rgba(0,0,0,.15); }
.cal-verde    { background:#d1fae5; color:#065f46; }
.cal-amarillo { background:#fef9c3; color:#713f12; border:2px solid #fde047; }
.cal-rojo     { background:#fee2e2; color:#991b1b; border:2px solid #fca5a5; }
.cal-festivo  { background:#e0e7ff; color:#3730a3; }
.cal-fin_semana { background:#f8fafc; color:#cbd5e1; }
.cal-vacaciones { background:#fdf4ff; color:#7e22ce; }
.cal-futuro   { background:#f8fafc; color:#94a3b8; }
.cal-empty    { background:transparent; }
.cal-today    { outline:3px solid #4f46e5; }
.cal-selected { outline:3px solid #f59e0b; }

/* Fichaje big buttons */
.btn-ficha {
    display:block; width:100%; padding:18px; border-radius:14px;
    font-size:1.1rem; font-weight:700; border:none; cursor:pointer;
    transition:transform .1s, box-shadow .2s; text-align:center;
    box-shadow:0 4px 14px rgba(0,0,0,.12);
}
.btn-ficha:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.18); }
.btn-entrada { background:linear-gradient(135deg,#10b981,#059669); color:white; }
.btn-salida  { background:linear-gradient(135deg,#ef4444,#dc2626); color:white; }
.btn-pausa   { background:linear-gradient(135deg,#f59e0b,#d97706); color:white; }
.btn-fin_pausa { background:linear-gradient(135deg,#6366f1,#4f46e5); color:white; }

/* Status display */
.status-bar {
    background:white; border-radius:12px; padding:16px 20px;
    box-shadow:0 1px 4px rgba(0,0,0,.08);
    display:flex; align-items:center; gap:16px;
}
.status-dot { width:14px; height:14px; border-radius:50%; flex-shrink:0; }
.dot-trabajando { background:#10b981; animation:pulse 2s infinite; }
.dot-pausado    { background:#f59e0b; }
.dot-libre      { background:#94a3b8; }
.dot-completo   { background:#4f46e5; }
@keyframes pulse {
    0%,100% { box-shadow:0 0 0 0 rgba(16,185,129,.4); }
    50%      { box-shadow:0 0 0 8px rgba(16,185,129,0); }
}

/* Legal box */
.legal-box {
    background:#fefce8; border-left:4px solid #f59e0b;
    padding:12px 16px; border-radius:6px; font-size:.85rem;
}
.legal-box-red {
    background:#fff1f2; border-left:4px solid #f43f5e;
    padding:12px 16px; border-radius:6px; font-size:.85rem;
}

/* Login */
.login-card {
    max-width:420px; margin:80px auto; background:white;
    border-radius:20px; padding:40px; box-shadow:0 8px 40px rgba(0,0,0,.12);
}

/* Progress bar custom */
.prog-wrap { background:#f1f5f9; border-radius:20px; height:10px; overflow:hidden; margin:6px 0; }
.prog-fill  { height:100%; border-radius:20px; transition:width .3s; }
</style>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_h(h: float) -> str:
    if h <= 0: return "0h 00m"
    return f"{int(h)}h {int((h%1)*60):02d}m"

def status_badge(status: str) -> str:
    MAP = {
        "verde":    ("badge-verde",    "✓ Completo"),
        "amarillo": ("badge-amarillo", "⚠ Incidencia"),
        "rojo":     ("badge-rojo",     "✗ Sin fichar"),
        "festivo":  ("badge-blue",     "Festivo"),
        "fin_semana": ("badge-gris",   "Fin de semana"),
        "vacaciones": ("badge-purple", "Vacaciones"),
        "futuro":   ("badge-gris",     "—"),
    }
    cls, label = MAP.get(status, ("badge-gris", status))
    return f'<span class="badge {cls}">{label}</span>'

def req_estado_badge(estado: str) -> str:
    M = {"pendiente": ("badge-amarillo","⏳ Pendiente"),
         "aprobada":  ("badge-verde",   "✓ Aprobada"),
         "denegada":  ("badge-rojo",    "✗ Denegada")}
    cls, label = M.get(estado, ("badge-gris", estado))
    return f'<span class="badge {cls}">{label}</span>'

COMUNIDADES_MAP = {
    "madrid": "Madrid", "cataluña": "Cataluña", "andalucia": "Andalucía",
    "valencia": "Valencia", "galicia": "Galicia", "pais_vasco": "País Vasco",
    "aragon": "Aragón", "castilla_leon": "Castilla y León",
    "castilla_la_mancha": "Castilla-La Mancha", "canarias": "Canarias",
    "baleares": "Baleares", "murcia": "Murcia", "navarra": "Navarra",
    "asturias": "Asturias", "cantabria": "Cantabria",
    "extremadura": "Extremadura", "la_rioja": "La Rioja",
}

MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
            "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# ── Session state ─────────────────────────────────────────────────────────────

def ss(key, default=None):
    return st.session_state.get(key, default)

def logged_in() -> bool:
    return ss("user") is not None

def current_user() -> dict:
    return ss("user", {})

def is_role(*roles) -> bool:
    return current_user().get("role") in roles

# ── Login page ────────────────────────────────────────────────────────────────

def page_login():
    st.markdown(STYLES, unsafe_allow_html=True)
    st.markdown("""
    <div class="login-card">
        <div style="text-align:center;margin-bottom:24px">
            <div style="font-size:2.5rem">⏱️</div>
            <h2 style="margin:8px 0 4px;color:#1e1f2e;font-weight:700">Ficha</h2>
            <p style="color:#64748b;font-size:.9rem;margin:0">Control Horario · RDL 8/2019</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Usuario", placeholder="usuario")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

    st.markdown("""
        <div style="margin-top:20px;padding:12px;background:#f8fafc;border-radius:8px;font-size:.82rem;color:#64748b">
            <b>Credenciales demo:</b><br>
            admin / Admin1234! &nbsp;·&nbsp; manager1 / Manager123! &nbsp;·&nbsp; empleado1 / Empleado123!
        </div>
    </div>
    """, unsafe_allow_html=True)

    if submitted:
        user = db.authenticate(username.strip(), password)
        if user:
            st.session_state["user"] = user
            db.audit(user["id"], "login", ip="0.0.0.0")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    user = current_user()
    unread = db.get_unread_count(user["id"])
    badge = f" 🔴" if unread > 0 else ""

    with st.sidebar:
        st.markdown(f"""
        <div style="padding:16px 0 8px">
            <div style="font-size:1.5rem;font-weight:700;color:#fff">⏱️ Ficha</div>
            <div style="font-size:.8rem;color:#7c7f9e;margin-top:2px">Control Horario SaaS</div>
        </div>
        <div style="background:#2d2f45;border-radius:10px;padding:12px;margin:8px 0 16px">
            <div style="font-weight:600;color:#e2e8f0">{user['nombre']} {user['apellidos']}</div>
            <div style="font-size:.78rem;color:#7c7f9e">{user['role'].upper()}</div>
        </div>
        """, unsafe_allow_html=True)

        nav_options = ["⏱️ Fichaje", "📅 Mi Calendario", "🏖️ Vacaciones", f"🔔 Notificaciones{badge}"]
        if is_role("manager", "admin"):
            nav_options += ["👥 Mi Equipo", "✅ Aprobar Solicitudes"]
        if is_role("admin"):
            nav_options += ["📊 Dashboard Admin", "👤 Usuarios", "📅 Festivos", "📥 Exportaciones", "🔍 Auditoría"]

        page = st.radio("Navegación", nav_options, label_visibility="collapsed")

        st.divider()
        st.markdown("""
        <div style="font-size:.75rem;color:#4a4d6a;line-height:1.7">
            <div><b style="color:#7c7f9e">Normativa</b></div>
            <div>RDL 8/2019 — Registro diario</div>
            <div>Art.34 ET — 40h/sem · 9h/día</div>
            <div>Art.35 ET — Máx. 80h extra/año</div>
            <div>Art.38 ET — 30 días vacaciones</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    return page.split(" ", 1)[1].split("🔴")[0].strip() if " " in page else page

# ── Page: Fichaje ─────────────────────────────────────────────────────────────

def page_fichaje():
    user = current_user()

    # ── Selector de zona horaria (persiste en session_state) ──────────────────
    _TZ_OPTIONS = {
        "Canarias (UTC+0/+1)":    "Atlantic/Canary",
        "Peninsula (UTC+1/+2)": "Europe/Madrid",
    }
    _default_key = ("Canarias (UTC+0/+1)"
                    if user.get("comunidad_autonoma") == "canarias"
                    else "Peninsula (UTC+1/+2)")
    if "tz_label" not in st.session_state:
        st.session_state["tz_label"] = _default_key

    _tz_col, _ = st.columns([1, 4])
    with _tz_col:
        _tz_label = st.selectbox(
            "Zona horaria",
            list(_TZ_OPTIONS.keys()),
            index=list(_TZ_OPTIONS.keys()).index(st.session_state.get("tz_label", _default_key)),
            key="tz_label",
        )

    try:
        from zoneinfo import ZoneInfo
        _tz  = ZoneInfo(_TZ_OPTIONS[_tz_label])
        _now = datetime.now(_tz)
    except Exception:
        _now = datetime.now()

    hoy   = _now.date()
    ahora = _now.strftime("%H:%M")
    zona_label = _tz_label

    entries = db.get_day_entries(user["id"], hoy)
    state   = db.get_fichaje_state(user["id"], hoy)
    worked  = db.calc_worked_hours(entries)
    last_hora = entries[-1]['hora'][:5] if entries else "--:--"

    # ── Extra CSS ──────────────────────────────────────────────────────────────
    st.markdown("""<style>
    .ficha-hero {
        background: linear-gradient(135deg,#1e1f2e 0%,#2d2f45 100%);
        border-radius:20px; padding:28px 32px; margin-bottom:20px;
        display:flex; align-items:center; justify-content:space-between;
        box-shadow:0 8px 32px rgba(0,0,0,.2);
    }
    .ficha-time  { font-size:3.2rem; font-weight:800; color:white; letter-spacing:-2px; line-height:1; }
    .ficha-date  { font-size:.9rem; color:#a0aec0; margin-top:4px; }
    .status-pill {
        display:inline-flex; align-items:center; gap:8px;
        padding:10px 20px; border-radius:50px; font-weight:600; font-size:.95rem;
        box-shadow:0 4px 12px rgba(0,0,0,.2);
    }
    .pill-libre      { background:rgba(148,163,184,.2); color:#94a3b8; }
    .pill-trabajando { background:rgba(16,185,129,.2);  color:#34d399; border:1px solid rgba(16,185,129,.35); }
    .pill-pausado    { background:rgba(245,158,11,.2);  color:#fbbf24; border:1px solid rgba(245,158,11,.35); }
    .pill-completo   { background:rgba(99,102,241,.2);  color:#a5b4fc; border:1px solid rgba(99,102,241,.35); }
    .tl-row {
        display:flex; align-items:center; gap:12px;
        padding:10px 0; border-bottom:1px solid #f1f5f9;
    }
    .tl-icon {
        width:36px; height:36px; border-radius:50%; display:flex;
        align-items:center; justify-content:center; font-size:1rem; flex-shrink:0;
    }
    </style>""", unsafe_allow_html=True)

    # ── Hero card ──────────────────────────────────────────────────────────────
    pill_cls = {"entrada":"pill-trabajando","fin_pausa":"pill-trabajando",
                "pausa":"pill-pausado","salida":"pill-completo"}.get(state,"pill-libre")
    pill_txt = {
        None:       "● Sin fichar hoy",
        "entrada":  f"● Trabajando desde {last_hora}",
        "pausa":    f"● En pausa desde {last_hora}",
        "fin_pausa":f"● Activo tras pausa ({last_hora})",
        "salida":   f"✓ Jornada finalizada",
    }.get(state, "—")

    pct    = min(int(worked / 8 * 100), 100)
    bar_color = "#ef4444" if worked > 9 else "#10b981" if worked >= 8 else "#6366f1"
    overtime_badge = ('<span style="background:#fca5a5;color:#991b1b;padding:2px 8px;'
                      'border-radius:10px;font-size:.72rem;font-weight:700;margin-left:8px">⚠ +9h</span>'
                      if worked > 9 else "")

    st.markdown(f"""
    <div class="ficha-hero">
      <div>
        <div class="ficha-time">{ahora}</div>
        <div class="ficha-date">{_now.strftime('%A, %d de %B de %Y').capitalize()} &nbsp;·&nbsp; {zona_label}</div>
        <div style="margin-top:18px">
          <div style="font-size:.78rem;color:#94a3b8;margin-bottom:5px">
            Horas trabajadas hoy {overtime_badge}
          </div>
          <div style="background:rgba(255,255,255,.12);border-radius:20px;height:8px;width:220px;overflow:hidden">
            <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:20px;transition:width .4s"></div>
          </div>
          <div style="font-size:.82rem;color:#c9cde6;margin-top:5px"><b>{fmt_h(worked)}</b> de 8h objetivo</div>
        </div>
      </div>
      <div style="text-align:right">
        <div class="status-pill {pill_cls}">{pill_txt}</div>
        <div style="margin-top:10px;font-size:.78rem;color:#6b7280">
          Usuario: <b style="color:#a0aec0">{user.get('nombre','')}</b>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Config row (jornada + hora) ────────────────────────────────────────────
    col_j, col_h, col_obs = st.columns([2, 1, 3])
    with col_j:
        tipo_jornada = st.selectbox(
            "Modalidad",
            ["🏢 Presencial", "🏠 Teletrabajo", "🔄 Mixta", "🚗 Desplazamiento"],
            key="tipo_jornada",
        )
    with col_h:
        hora_manual_cb = st.checkbox("⏱ Hora manual", key="hora_manual_cb")
    with col_obs:
        obs = st.text_input("Observación (opcional)",
                            placeholder="Ej: Reunión con cliente…",
                            key="obs_fichaje",
                            label_visibility="collapsed")

    if hora_manual_cb:
        hora_input = st.time_input(
            "Hora del fichaje",
            value=_now.time().replace(second=0, microsecond=0),
            step=60,
            key="hora_input_manual",
        )
        hora_str = hora_input.strftime("%H:%M")
    else:
        hora_str = ahora

    # ── Action buttons ─────────────────────────────────────────────────────────
    can_entrada   = state is None
    can_pausa     = state in ("entrada", "fin_pausa")
    can_fin_pausa = state == "pausa"
    can_salida    = state in ("entrada", "fin_pausa")

    def fichar(tipo):
        eid = db.add_entry(user["id"], hoy, tipo, hora_str,
                           observaciones=obs,
                           is_manual=hora_manual_cb,
                           created_by=user["id"])
        db.audit(user["id"], f"fichaje_{tipo}", "time_entries", eid,
                 {"fecha": str(hoy), "hora": hora_str})
        st.rerun()

    active = []
    if can_entrada:   active.append(("entrada",   "🟢 ENTRADA",   "primary"))
    if can_pausa:     active.append(("pausa",     "🟡 PAUSA",     "secondary"))
    if can_fin_pausa: active.append(("fin_pausa", "🟣 REANUDAR",  "primary"))
    if can_salida:    active.append(("salida",    "🔴 SALIDA",    "secondary"))

    if active:
        btn_cols = st.columns(len(active))
        for idx, (tipo, label, btype) in enumerate(active):
            with btn_cols[idx]:
                if st.button(label, use_container_width=True,
                             type="primary" if btype == "primary" else "secondary",
                             key=f"btn_{tipo}"):
                    worked_at_exit = db.calc_worked_hours(entries)
                    fichar(tipo)
                    if tipo == "salida" and worked_at_exit > 9:
                        db.create_incident(user["id"], hoy, "jornada_excesiva",
                                           f"Jornada de {worked_at_exit:.2f}h supera 9h (Art.34.3 ET)")
    elif state == "salida":
        st.success("✅ ¡Jornada completada! Buen descanso.")

    st.divider()

    # ── Timeline + stats ───────────────────────────────────────────────────────
    col_tl, col_stats = st.columns([3, 2])

    with col_tl:
        st.markdown(f"##### 📋 Registros de hoy — {hoy.strftime('%d/%m/%Y')}")
        if entries:
            TIPO_COLORS = {
                "entrada":   ("#d1fae5", "#065f46", "🟢"),
                "salida":    ("#fee2e2", "#991b1b", "🔴"),
                "pausa":     ("#fef3c7", "#92400e", "🟡"),
                "fin_pausa": ("#ede9fe", "#5b21b6", "🟣"),
            }
            for e in entries:
                bg, fg, ico = TIPO_COLORS.get(e['tipo'], ("#f1f5f9","#475569","⚪"))
                extra = []
                if e["is_manual"]: extra.append("✏️ Manual")
                if e.get("observaciones"): extra.append(e["observaciones"])
                c_ico, c_txt, c_del = st.columns([0.4, 4, 0.6])
                with c_ico:
                    st.markdown(
                        f'<div class="tl-icon" style="background:{bg};color:{fg};margin-top:6px">{ico}</div>',
                        unsafe_allow_html=True)
                with c_txt:
                    label = f"**{e['hora'][:5]}** — {e['tipo'].replace('_',' ').title()}"
                    if extra:
                        label += f"  \n*{' · '.join(extra)}*"
                    st.markdown(label)
                with c_del:
                    if st.button("🗑️", key=f"del_{e['id']}",
                                 help="Eliminar este registro",
                                 use_container_width=True):
                        db.soft_delete_entry(e["id"], user["id"])
                        db.audit(user["id"], "delete_entry", "time_entries", e["id"],
                                 {"fecha": str(hoy), "tipo": e["tipo"], "hora": e["hora"]})
                        st.rerun()
        else:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:#94a3b8">
              <div style="font-size:2.5rem;margin-bottom:8px">⏰</div>
              <div>Sin registros hoy.<br>Pulsa <b>ENTRADA</b> para comenzar.</div>
            </div>""", unsafe_allow_html=True)

    with col_stats:
        st.markdown("##### 📊 Resumen del día")
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:24px">
          <div style="font-size:2.8rem;font-weight:800;color:#4f46e5;line-height:1">{fmt_h(worked)}</div>
          <div style="font-size:.82rem;color:#64748b;margin:6px 0 14px">trabajadas hoy</div>
          <div style="background:#f1f5f9;border-radius:20px;height:10px;overflow:hidden">
            <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:20px"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:.72rem;color:#94a3b8;margin-top:4px">
            <span>0h</span><span>8h</span>
          </div>
        </div>""", unsafe_allow_html=True)
        if worked > 9:
            st.error("⚠️ Supera 9h diarias (Art. 34.3 ET)")
        elif worked > 8:
            st.warning(f"Jornada extendida: {fmt_h(worked)}")
        elif worked >= 8 and state == "salida":
            st.success("✅ Jornada completa")

    # ── Corrección manual ──────────────────────────────────────────────────────
    with st.expander("✏️ Corregir o añadir fichaje en otra fecha"):
        with st.form("manual_form"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                fecha_m = st.date_input("Fecha", value=hoy, max_value=hoy)
            with mc2:
                tipo_m = st.selectbox("Tipo", ["entrada", "salida", "pausa", "fin_pausa"])
            with mc3:
                hora_m = st.time_input(
                    "Hora",
                    value=_now.time().replace(second=0, microsecond=0),
                    step=60,
                )
            es_hoy = (fecha_m == hoy)
            obs_m = st.text_input(
                "Observación (opcional)" if es_hoy else "Motivo / justificación *",
                placeholder="" if es_hoy else "Obligatorio para fechas pasadas",
            )
            reemplazar = st.checkbox(
                "Reemplazar registro existente del mismo tipo",
                value=True,
                help="Si ya hay una Entrada/Salida de ese tipo en esa fecha, se elimina la antigua y se guarda la nueva hora.",
            )
            if st.form_submit_button("💾 Guardar fichaje", use_container_width=True):
                if not es_hoy and not obs_m.strip():
                    st.error("El motivo es obligatorio para fechas pasadas.")
                else:
                    if reemplazar:
                        # Soft-delete ALL existing entries of the same tipo on that date
                        existing = db.get_day_entries(user["id"], fecha_m)
                        for old_e in existing:
                            if old_e["tipo"] == tipo_m:
                                db.soft_delete_entry(old_e["id"], user["id"])
                                db.audit(user["id"], "delete_entry_replaced",
                                         "time_entries", old_e["id"],
                                         {"fecha": str(fecha_m), "tipo": tipo_m,
                                          "hora_old": old_e["hora"]})
                    db.add_entry(user["id"], fecha_m, tipo_m,
                                 hora_m.strftime("%H:%M"),
                                 observaciones=obs_m, is_manual=True,
                                 created_by=user["id"])
                    db.audit(user["id"], "fichaje_manual", "time_entries",
                             datos={"fecha": str(fecha_m), "tipo": tipo_m})
                    st.success("✅ Fichaje guardado correctamente.")
                    st.rerun()

    # ── Legal notice ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="legal-box" style="margin-top:16px">
        📋 <b>RDL 8/2019</b>: Registro de jornada obligatorio. Datos conservados
        <b>4 años</b> y disponibles para la Inspección de Trabajo (Art. 34.9 ET).
    </div>
    """, unsafe_allow_html=True)

# ── Page: Calendario ──────────────────────────────────────────────────────────

def render_calendar(user_id, año, mes, comunidad="madrid"):
    """Returns HTML string for a month calendar with colored days."""
    cal = calendar.monthcalendar(año, mes)
    hoy = date.today()
    sel = ss("cal_selected_day")

    headers = "".join(f"<th>{d}</th>" for d in ["L","M","X","J","V","S","D"])
    rows = ""
    for week in cal:
        row = "<tr>"
        for i, day in enumerate(week):
            if day == 0:
                row += '<td class="cal-day cal-empty"></td>'
            else:
                d = date(año, mes, day)
                status = db.get_day_status(user_id, d, comunidad)
                today_cls = " cal-today" if d == hoy else ""
                sel_cls = " cal-selected" if sel == str(d) else ""
                row += (f'<td class="cal-day cal-{status}{today_cls}{sel_cls}" '
                        f'title="{d}">{day}</td>')
        row += "</tr>"
        rows += row

    legend = """
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;font-size:.78rem">
        <span><span style="background:#d1fae5;padding:2px 8px;border-radius:4px">Verde</span> Completo</span>
        <span><span style="background:#fef9c3;padding:2px 8px;border-radius:4px">Amarillo</span> Incidencia</span>
        <span><span style="background:#fee2e2;padding:2px 8px;border-radius:4px">Rojo</span> Sin fichar</span>
        <span><span style="background:#e0e7ff;padding:2px 8px;border-radius:4px">Azul</span> Festivo</span>
        <span><span style="background:#fdf4ff;padding:2px 8px;border-radius:4px">Violeta</span> Vacaciones</span>
    </div>
    """
    return f"""
    <div class="cal-wrapper">
    <table class="cal-table">
    <thead><tr>{headers}</tr></thead>
    <tbody>{rows}</tbody>
    </table>
    {legend}
    </div>
    """

def page_calendario():
    user = current_user()
    hoy = date.today()

    st.title("📅 Mi Calendario")

    if "cal_year" not in st.session_state:
        st.session_state["cal_year"] = hoy.year
        st.session_state["cal_month"] = hoy.month

    año = st.session_state["cal_year"]
    mes = st.session_state["cal_month"]

    c_left, c_mid, c_right = st.columns([1, 3, 1])
    with c_left:
        if st.button("← Anterior"):
            if mes == 1:
                st.session_state["cal_month"] = 12
                st.session_state["cal_year"] = año - 1
            else:
                st.session_state["cal_month"] -= 1
            st.rerun()
    with c_mid:
        st.markdown(f"<h3 style='text-align:center;margin:0'>{MESES_ES[mes-1]} {año}</h3>",
                    unsafe_allow_html=True)
    with c_right:
        if st.button("Siguiente →"):
            if mes == 12:
                st.session_state["cal_month"] = 1
                st.session_state["cal_year"] = año + 1
            else:
                st.session_state["cal_month"] += 1
            st.rerun()

    comunidad = user.get("comunidad_autonoma", "madrid")
    cal_html = render_calendar(user["id"], año, mes, comunidad)

    st.markdown(f'<div class="card">{cal_html}</div>', unsafe_allow_html=True)

    # Day selector for details
    st.subheader("Detalle del día")
    col1, col2 = st.columns([1, 2])
    with col1:
        sel_day = st.date_input("Selecciona un día", value=hoy,
                                min_value=date(año, mes, 1),
                                max_value=date(año, mes, calendar.monthrange(año, mes)[1]))
    with col2:
        status = db.get_day_status(user["id"], sel_day, comunidad)
        entries = db.get_day_entries(user["id"], sel_day)
        worked = db.calc_worked_hours(entries)

        st.markdown(f"**Estado:** {status_badge(status)}", unsafe_allow_html=True)
        st.markdown(f"**Horas trabajadas:** {fmt_h(worked)}")

        if entries:
            tipo_icons = {"entrada":"🟢","salida":"🔴","pausa":"🟡","fin_pausa":"🟣"}
            for e in entries:
                manual = " ✏️ *manual*" if e["is_manual"] else ""
                st.markdown(f"- {tipo_icons.get(e['tipo'],'⚪')} **{e['hora'][:5]}** {e['tipo'].replace('_',' ').title()}{manual}")
        else:
            if sel_day <= hoy and sel_day.weekday() < 5 and status not in ("festivo","vacaciones"):
                st.warning("Sin registros — día laboral sin fichar.")

        # Incidencias del día
        incidents = [i for i in db.get_user_incidents(user["id"])
                     if i["fecha"] == str(sel_day)]
        if incidents:
            for inc in incidents:
                st.markdown(f"⚠️ **Incidencia**: {inc['tipo'].replace('_',' ').title()} — {inc['descripcion']}")

    # Monthly validation
    st.subheader(f"Validación del mes — {MESES_ES[mes-1]} {año}")
    val = db.get_monthly_validation(user["id"], año, mes)
    if val and val["validado"]:
        st.success(f"✅ Mes validado el {val['fecha_validacion'][:10]}")
    else:
        if mes <= hoy.month and año <= hoy.year:
            if st.button("✅ Confirmar que mis registros de este mes son correctos"):
                db.set_monthly_validation(user["id"], año, mes)
                db.audit(user["id"], "validacion_mensual", datos={"año": año, "mes": mes})
                st.success("Mes validado correctamente. Registro guardado con timestamp.")
                st.rerun()
        else:
            st.info("Podrás validar este mes cuando llegue la fecha.")

    # Stats for the month
    f_ini = date(año, mes, 1)
    last_day = calendar.monthrange(año, mes)[1]
    f_fin = date(año, mes, last_day)
    entries_mes = db.get_entries_range(user["id"], f_ini, f_fin)
    if entries_mes:
        df = pd.DataFrame(entries_mes)
        df_by_day = df.groupby("fecha").apply(
            lambda g: db.calc_worked_hours(g.to_dict("records"))
        ).reset_index(name="horas")
        if not df_by_day.empty:
            fig = px.bar(df_by_day, x="fecha", y="horas",
                         title=f"Horas trabajadas — {MESES_ES[mes-1]} {año}",
                         labels={"fecha": "Fecha", "horas": "Horas"},
                         color="horas", color_continuous_scale="Blues")
            fig.add_hline(y=8, line_dash="dash", line_color="#6366f1", annotation_text="8h")
            fig.add_hline(y=9, line_dash="dash", line_color="#ef4444", annotation_text="Máx. 9h")
            fig.update_layout(showlegend=False, coloraxis_showscale=False, height=280)
            st.plotly_chart(fig, use_container_width=True)

# ── Page: Vacaciones ──────────────────────────────────────────────────────────

def page_vacaciones():
    user = current_user()
    hoy = date.today()
    año = hoy.year

    st.title("🏖️ Vacaciones y Ausencias")

    bal = db.get_vacation_balance(user["id"], año)

    # Balance cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Días totales", bal["total"])
    c2.metric("✅ Disfrutados", bal["used"])
    c3.metric("⏳ Pendientes aprobación", bal["pending"])
    c4.metric("🟢 Disponibles", bal["remaining"])

    pct = int((bal["used"] / bal["total"]) * 100) if bal["total"] > 0 else 0
    st.markdown(f"""
    <div style="margin:8px 0 20px">
        <div style="font-size:.85rem;color:#64748b;margin-bottom:4px">
            Consumo de vacaciones {año} — {pct}% utilizado
        </div>
        <div class="prog-wrap">
            <div class="prog-fill" style="width:{pct}%;background:{'#ef4444' if pct>90 else '#4f46e5'}"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_sol, tab_nueva = st.tabs(["📋 Mis Solicitudes", "➕ Nueva Solicitud"])

    with tab_sol:
        reqs = db.get_user_requests(user["id"])
        if not reqs:
            st.info("No tienes solicitudes registradas.")
        else:
            for r in reqs:
                with st.expander(
                    f"{r['tipo'].replace('_',' ').title()} · "
                    f"{r['fecha_inicio']} → {r['fecha_fin']} "
                    f"({r['dias_laborables']} días laborables)"
                ):
                    st.markdown(f"**Estado:** {req_estado_badge(r['estado'])}", unsafe_allow_html=True)
                    if r.get("manager_nombre"):
                        st.caption(f"Gestionado por: {r['manager_nombre']}")
                    if r["comentario_empleado"]:
                        st.write(f"Tu comentario: {r['comentario_empleado']}")
                    if r["comentario_manager"]:
                        st.write(f"Respuesta manager: {r['comentario_manager']}")
                    st.caption(f"Solicitado: {r['fecha_solicitud'][:10]}")
                    if r.get("fecha_resolucion"):
                        st.caption(f"Resuelto: {r['fecha_resolucion'][:10]}")

    with tab_nueva:
        TIPOS = ["vacaciones", "asuntos_propios", "descanso_compensatorio",
                 "baja_medica", "permiso_retribuido", "maternidad_paternidad",
                 "lactancia", "otros"]
        comunidad = user.get("comunidad_autonoma", "madrid")
        with st.form("nueva_solicitud"):
            tipo = st.selectbox("Tipo de ausencia", TIPOS,
                                format_func=lambda x: x.replace("_", " ").title())
            c1, c2 = st.columns(2)
            f_ini = c1.date_input("Fecha inicio", value=hoy + timedelta(days=1))
            f_fin = c2.date_input("Fecha fin", value=hoy + timedelta(days=1))
            comentario = st.text_area("Comentario / motivo (opcional)")

            if f_fin >= f_ini:
                dl = db.dias_laborables(f_ini, f_fin, comunidad)
                dn = (f_fin - f_ini).days + 1
                st.info(f"📅 **{dn} días naturales · {dl} días laborables**")
                if tipo == "vacaciones" and dl > bal["remaining"]:
                    st.warning(f"⚠️ Solicitas {dl} días pero solo tienes {bal['remaining']} disponibles.")

            submitted = st.form_submit_button("📤 Enviar solicitud", type="primary")
            if submitted:
                if f_fin < f_ini:
                    st.error("La fecha fin no puede ser anterior al inicio.")
                else:
                    rid = db.create_vac_request(user["id"], f_ini, f_fin, tipo,
                                                comentario, comunidad)
                    # notify manager
                    mgr_id = user.get("manager_id")
                    if mgr_id:
                        db.add_notification(mgr_id, "solicitud_vacaciones",
                            f"Nueva solicitud de {user['nombre']} {user['apellidos']}",
                            f"{tipo.replace('_',' ').title()}: {f_ini} → {f_fin} ({db.dias_laborables(f_ini,f_fin,comunidad)} días)")
                    db.audit(user["id"], "solicitud_vacaciones", "vacation_requests", rid)
                    st.success("✅ Solicitud enviada. Tu manager recibirá una notificación.")
                    st.rerun()

        st.markdown("""<div class="legal-box">
        <b>Marco legal:</b> Vacaciones mínimas 30 días naturales/año (Art. 38 ET) ·
        Permisos retribuidos: matrimonio 15d, nacimiento, fallecimiento (Art. 37 ET) ·
        No compensables en metálico salvo extinción de contrato.
        </div>""", unsafe_allow_html=True)

# ── Page: Notificaciones ──────────────────────────────────────────────────────

def page_notificaciones():
    user = current_user()
    st.title("🔔 Notificaciones e Incidencias")

    col_notif, col_inc = st.columns([1, 1])

    with col_notif:
        st.subheader("Notificaciones")
        if st.button("Marcar todas como leídas"):
            db.mark_all_read(user["id"])
            st.rerun()

        notifs = db.get_notifications(user["id"])
        if not notifs:
            st.info("Sin notificaciones.")
        else:
            for n in notifs:
                icon = "🔵" if not n["leido"] else "⚪"
                with st.container():
                    st.markdown(f"""
                    <div class="card-sm" style="margin-bottom:8px;{'border-left:3px solid #4f46e5' if not n['leido'] else ''}">
                        <div style="font-weight:{'600' if not n['leido'] else '400'};color:#1e293b">
                            {icon} {n['titulo']}
                        </div>
                        <div style="font-size:.85rem;color:#64748b">{n['mensaje']}</div>
                        <div style="font-size:.75rem;color:#94a3b8">{n['created_at'][:16]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if not n["leido"]:
                        if st.button("Marcar leída", key=f"nr_{n['id']}"):
                            db.mark_read(n["id"])
                            st.rerun()

    with col_inc:
        st.subheader("Mis Incidencias")
        incidents = db.get_user_incidents(user["id"])

        # Auto-detect new incidents for past 7 days
        for i in range(1, 8):
            d = date.today() - timedelta(days=i)
            if d.weekday() >= 5: continue
            status = db.get_day_status(user["id"], d, user.get("comunidad_autonoma","madrid"))
            if status == "rojo":
                db.create_incident(user["id"], d, "sin_registro",
                                   f"Día laboral {d} sin ningún fichaje")
            elif status == "amarillo":
                db.create_incident(user["id"], d, "dia_incompleto",
                                   f"Día {d} con registros incompletos")

        incidents = db.get_user_incidents(user["id"])

        if not incidents:
            st.success("✅ Sin incidencias. Cumplimiento perfecto.")
        else:
            for inc in incidents:
                color = {"pendiente": "#fef3c7", "resuelto": "#d1fae5", "justificado": "#dbeafe"}.get(inc["estado"], "#f1f5f9")
                st.markdown(f"""
                <div style="background:{color};border-radius:8px;padding:12px;margin-bottom:8px">
                    <div style="font-weight:600">{inc['tipo'].replace('_',' ').title()} — {inc['fecha']}</div>
                    <div style="font-size:.85rem">{inc['descripcion']}</div>
                    <div style="font-size:.75rem;color:#64748b">Estado: {inc['estado'].upper()}</div>
                </div>
                """, unsafe_allow_html=True)

                if inc["estado"] == "pendiente":
                    with st.expander(f"Justificar incidencia {inc['fecha']}"):
                        with st.form(f"just_{inc['id']}"):
                            resolucion = st.text_area("Justificación / explicación")
                            if st.form_submit_button("Enviar justificación"):
                                db.resolve_incident(inc["id"], resolucion, user["id"])
                                st.success("Incidencia justificada.")
                                st.rerun()

# ── Page: Mi Equipo (Manager) ─────────────────────────────────────────────────

def page_equipo():
    user = current_user()
    hoy = date.today()
    st.title("👥 Mi Equipo")

    team = db.get_team(user["id"])
    if not team:
        st.info("No tienes empleados asignados.")
        return

    # Today's overview
    st.subheader(f"Estado hoy — {hoy.strftime('%d/%m/%Y')}")
    cols = st.columns(len(team))
    for i, emp in enumerate(team):
        estado = db.get_day_status(emp["id"], hoy, emp.get("comunidad_autonoma","madrid"))
        entries = db.get_day_entries(emp["id"], hoy)
        worked = db.calc_worked_hours(entries)
        with cols[i]:
            st.markdown(f"""
            <div class="card" style="text-align:center">
                <div style="font-weight:600">{emp['nombre']}</div>
                <div style="font-size:.8rem;color:#64748b">{emp['apellidos']}</div>
                <div style="margin:8px 0">{status_badge(estado)}</div>
                <div style="font-size:.9rem"><b>{fmt_h(worked)}</b></div>
            </div>
            """, unsafe_allow_html=True)

    # Team incidents
    st.subheader("Incidencias del equipo")
    incidents = db.get_team_incidents(user["id"], estado="pendiente")
    if not incidents:
        st.success("✅ Sin incidencias pendientes en el equipo.")
    else:
        for inc in incidents:
            with st.expander(f"{inc['emp_nombre']} — {inc['tipo'].replace('_',' ').title()} ({inc['fecha']})"):
                st.write(inc["descripcion"])
                with st.form(f"resolve_inc_{inc['id']}"):
                    res = st.text_input("Resolución")
                    if st.form_submit_button("Resolver"):
                        db.resolve_incident(inc["id"], res, user["id"])
                        st.success("Resuelta."); st.rerun()

    # Weekly hours per employee
    st.subheader("Horas esta semana por empleado")
    lunes = hoy - timedelta(days=hoy.weekday())
    team_ids = [e["id"] for e in team]
    entries_sem = db.get_all_entries_range(lunes, hoy, user_ids=team_ids)
    if entries_sem:
        df = pd.DataFrame(entries_sem)
        result = df.groupby(["emp_nombre","fecha"]).apply(
            lambda g: db.calc_worked_hours(g.to_dict("records"))
        ).reset_index(name="horas")
        fig = px.bar(result, x="fecha", y="horas", color="emp_nombre",
                     title="Horas semanales por empleado",
                     labels={"fecha":"Fecha","horas":"Horas","emp_nombre":"Empleado"},
                     barmode="group")
        fig.add_hline(y=8, line_dash="dash", line_color="#6366f1")
        fig.add_hline(y=9, line_dash="dash", line_color="#ef4444")
        st.plotly_chart(fig, use_container_width=True)

# ── Page: Aprobar Solicitudes ─────────────────────────────────────────────────

def page_aprobar():
    user = current_user()
    st.title("✅ Aprobar Solicitudes")

    pending = db.get_pending_requests(user["id"] if not is_role("admin") else None)
    if not pending:
        st.success("✅ No hay solicitudes pendientes.")
        return

    st.info(f"**{len(pending)}** solicitudes pendientes de revisión.")

    for r in pending:
        with st.expander(
            f"**{r['emp_nombre']}** · {r['tipo'].replace('_',' ').title()} · "
            f"{r['fecha_inicio']} → {r['fecha_fin']} ({r['dias_laborables']}d laborables)"
        ):
            if r["comentario_empleado"]:
                st.write(f"Comentario: {r['comentario_empleado']}")
            st.caption(f"Solicitado: {r['fecha_solicitud'][:10]}")
            comentario_mgr = st.text_input("Comentario al empleado (opcional)",
                                           key=f"cm_{r['id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Aprobar", key=f"apr_{r['id']}", type="primary"):
                db.resolve_request(r["id"], "aprobada", user["id"], comentario_mgr)
                db.add_notification(r["user_id"], "vacaciones_aprobada",
                    "Tu solicitud ha sido aprobada",
                    f"{r['tipo'].replace('_',' ').title()}: {r['fecha_inicio']} → {r['fecha_fin']}")
                db.audit(user["id"], "aprobar_solicitud", "vacation_requests", r["id"])
                st.success("Aprobada."); st.rerun()
            if c2.button("❌ Denegar", key=f"den_{r['id']}"):
                db.resolve_request(r["id"], "denegada", user["id"], comentario_mgr)
                db.add_notification(r["user_id"], "vacaciones_denegada",
                    "Tu solicitud ha sido denegada",
                    f"{r['tipo'].replace('_',' ').title()}: {r['fecha_inicio']} → {r['fecha_fin']}"
                    + (f"\nMotivo: {comentario_mgr}" if comentario_mgr else ""))
                db.audit(user["id"], "denegar_solicitud", "vacation_requests", r["id"])
                st.warning("Denegada."); st.rerun()

# ── Page: Dashboard Admin ─────────────────────────────────────────────────────

def page_admin_dashboard():
    st.title("📊 Dashboard Administrador")
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    inicio_mes = date(hoy.year, hoy.month, 1)

    stats = db.get_global_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Empleados activos", stats["total_users"])
    c2.metric("✅ Fichajes hoy", stats["total_entries_today"])
    c3.metric("📋 Solicitudes pendientes", stats["pending_requests"])
    c4.metric("⚠️ Incidencias abiertas", stats["open_incidents"])

    # Compliance semáforo
    users = db.get_all_users(activos_only=True)
    green = yellow = red = 0
    for u in users:
        s = db.get_day_status(u["id"], hoy, u.get("comunidad_autonoma","madrid"))
        if s == "verde": green += 1
        elif s == "amarillo": yellow += 1
        elif s == "rojo": red += 1

    total_hoy = max(1, green + yellow + red)
    st.subheader("🚦 Semáforo de cumplimiento — hoy")
    col_g, col_y, col_r = st.columns(3)
    col_g.markdown(f"""<div class="kpi"><div class="kpi-val" style="color:#10b981">{green}</div>
        <div class="kpi-label">✓ Cumplimiento correcto</div>
        <div style="font-size:.8rem;color:#94a3b8">{int(green/total_hoy*100)}%</div></div>""",
        unsafe_allow_html=True)
    col_y.markdown(f"""<div class="kpi"><div class="kpi-val" style="color:#f59e0b">{yellow}</div>
        <div class="kpi-label">⚠ Riesgo medio</div>
        <div style="font-size:.8rem;color:#94a3b8">{int(yellow/total_hoy*100)}%</div></div>""",
        unsafe_allow_html=True)
    col_r.markdown(f"""<div class="kpi"><div class="kpi-val" style="color:#ef4444">{red}</div>
        <div class="kpi-label">✗ Riesgo alto</div>
        <div style="font-size:.8rem;color:#94a3b8">{int(red/total_hoy*100)}%</div></div>""",
        unsafe_allow_html=True)

    # Weekly chart all users
    st.subheader("Horas trabajadas por empleado — semana actual")
    entries_sem = db.get_all_entries_range(lunes, hoy)
    if entries_sem:
        df = pd.DataFrame(entries_sem)
        result = df.groupby(["emp_nombre","fecha"]).apply(
            lambda g: db.calc_worked_hours(g.to_dict("records"))
        ).reset_index(name="horas")
        fig = px.bar(result, x="fecha", y="horas", color="emp_nombre",
                     barmode="group", title="Horas semanales (todos los empleados)",
                     labels={"fecha":"Fecha","horas":"Horas","emp_nombre":"Empleado"})
        fig.add_hline(y=8, line_dash="dash", line_color="#6366f1", annotation_text="8h")
        fig.add_hline(y=9, line_dash="dash", line_color="#ef4444", annotation_text="9h máx.")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin registros esta semana.")

    # Per-user vacation balance
    st.subheader("Balance de vacaciones — todos los empleados")
    bal_data = []
    for u in users:
        bal = db.get_vacation_balance(u["id"], hoy.year)
        bal_data.append({
            "Empleado": f"{u['nombre']} {u['apellidos']}",
            "Total días": bal["total"],
            "Disfrutados": bal["used"],
            "Pendiente aprobación": bal["pending"],
            "Disponibles": bal["remaining"],
        })
    if bal_data:
        df_bal = pd.DataFrame(bal_data)
        fig = px.bar(df_bal, x="Empleado", y=["Disfrutados","Pendiente aprobación","Disponibles"],
                     barmode="stack", title=f"Vacaciones {hoy.year} — mín. 30 días naturales (Art.38 ET)",
                     color_discrete_map={"Disfrutados":"#4f46e5","Pendiente aprobación":"#f59e0b","Disponibles":"#e2e8f0"})
        st.plotly_chart(fig, use_container_width=True)

# ── Page: Gestión Usuarios ────────────────────────────────────────────────────

def page_usuarios():
    st.title("👤 Gestión de Usuarios")
    tab_list, tab_new = st.tabs(["📋 Usuarios", "➕ Nuevo Usuario"])

    with tab_list:
        users = db.get_all_users()
        if not users:
            st.info("Sin usuarios.")
            return

        df = pd.DataFrame(users)
        disp_cols = ["nombre","apellidos","email","role","dept_nombre","manager_nombre",
                     "horas_semanales","dias_vacaciones_anuales","comunidad_autonoma"]
        available = [c for c in disp_cols if c in df.columns]
        st.dataframe(
            df[available].rename(columns={
                "nombre":"Nombre","apellidos":"Apellidos","email":"Email",
                "role":"Rol","dept_nombre":"Depto.","manager_nombre":"Manager",
                "horas_semanales":"H/sem","dias_vacaciones_anuales":"Días vac.",
                "comunidad_autonoma":"Comunidad"
            }),
            use_container_width=True, hide_index=True
        )

        st.subheader("✏️ Editar usuario")
        opts = {f"{u['nombre']} {u['apellidos']} [{u['role']}]": u["id"] for u in users}
        sel = st.selectbox("Seleccionar", list(opts.keys()))
        uid = opts[sel]
        udata = next((u for u in users if u["id"] == uid), {})

        managers = [u for u in users if u["role"] in ("manager","admin")]
        mgr_opts = {"Sin manager": None}
        mgr_opts.update({f"{u['nombre']} {u['apellidos']}": u["id"] for u in managers})

        depts = db.get_departments()
        dept_opts = {"Sin departamento": None}
        dept_opts.update({d["nombre"]: d["id"] for d in depts})

        roles = ["empleado","manager","admin"]
        comunidades = list(COMUNIDADES_MAP.keys())

        with st.form("edit_user"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre", value=udata.get("nombre",""))
            apellidos = c2.text_input("Apellidos", value=udata.get("apellidos",""))
            email = c1.text_input("Email", value=udata.get("email",""))
            telefono = c2.text_input("Teléfono", value=udata.get("telefono",""))
            role = c1.selectbox("Rol", roles,
                                index=roles.index(udata.get("role","empleado")) if udata.get("role") in roles else 0)
            comunidad = c2.selectbox("Comunidad autónoma", comunidades,
                                     index=comunidades.index(udata.get("comunidad_autonoma","madrid"))
                                     if udata.get("comunidad_autonoma") in comunidades else 0,
                                     format_func=lambda x: COMUNIDADES_MAP[x])
            horas = c1.number_input("Horas semanales", value=float(udata.get("horas_semanales",40)),
                                    min_value=1.0, max_value=40.0, step=0.5)
            dias_vac = c2.number_input("Días vacaciones anuales", value=int(udata.get("dias_vacaciones_anuales",22)),
                                       min_value=1, max_value=60)
            mgr_sel = c1.selectbox("Manager directo", list(mgr_opts.keys()),
                                   index=0 if not udata.get("manager_id") else
                                   (list(mgr_opts.values()).index(udata["manager_id"])
                                    if udata["manager_id"] in mgr_opts.values() else 0))
            activo = c2.checkbox("Activo", value=bool(udata.get("activo",1)))
            new_pw = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password")

            if st.form_submit_button("💾 Guardar"):
                kwargs = dict(nombre=nombre, apellidos=apellidos, email=email,
                              telefono=telefono, role=role, comunidad_autonoma=comunidad,
                              horas_semanales=horas, dias_vacaciones_anuales=dias_vac,
                              manager_id=mgr_opts[mgr_sel], activo=int(activo))
                if new_pw:
                    kwargs["password"] = new_pw
                db.update_user(uid, **kwargs)
                db.audit(current_user()["id"], "editar_usuario", "users", uid)
                st.success("✅ Usuario actualizado."); st.rerun()

    with tab_new:
        st.subheader("Crear nuevo usuario")
        managers = [u for u in db.get_all_users(activos_only=True) if u["role"] in ("manager","admin")]
        depts = db.get_departments()
        mgr_opts = {"Sin manager": None}
        mgr_opts.update({f"{u['nombre']} {u['apellidos']}": u["id"] for u in managers})
        dept_opts = {"Sin departamento": None}
        dept_opts.update({d["nombre"]: d["id"] for d in depts})

        with st.form("new_user"):
            c1, c2 = st.columns(2)
            username = c1.text_input("Usuario (login) *")
            password = c2.text_input("Contraseña *", type="password")
            nombre = c1.text_input("Nombre *")
            apellidos = c2.text_input("Apellidos *")
            email = c1.text_input("Email")
            role = c2.selectbox("Rol", ["empleado","manager","admin"])
            comunidad = c1.selectbox("Comunidad autónoma", list(COMUNIDADES_MAP.keys()),
                                     format_func=lambda x: COMUNIDADES_MAP[x])
            horas = c2.number_input("Horas semanales", value=40.0, min_value=1.0, max_value=40.0, step=0.5)
            dias_vac = c1.number_input("Días vacaciones anuales", value=22, min_value=1, max_value=60)
            mgr_sel = c2.selectbox("Manager directo", list(mgr_opts.keys()))

            if st.form_submit_button("✅ Crear usuario", type="primary"):
                if not username or not password or not nombre or not apellidos:
                    st.error("Campos obligatorios: usuario, contraseña, nombre, apellidos.")
                else:
                    try:
                        uid = db.create_user(username, password, nombre, apellidos, email,
                                             role, dept_opts.get(list(dept_opts.keys())[0]),
                                             mgr_opts[mgr_sel], comunidad, horas, dias_vac)
                        db.audit(current_user()["id"], "crear_usuario", "users", uid)
                        st.success(f"✅ Usuario {username} creado."); st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Departments
        st.subheader("Departamentos")
        for d in db.get_departments():
            st.write(f"• {d['nombre']}")
        with st.form("new_dept"):
            dept_nombre = st.text_input("Nuevo departamento")
            if st.form_submit_button("Añadir"):
                if dept_nombre:
                    db.create_department(dept_nombre)
                    st.success("Departamento creado."); st.rerun()

# ── Page: Festivos ────────────────────────────────────────────────────────────

def page_festivos():
    st.title("📅 Gestión de Festivos")
    año = st.number_input("Año", value=date.today().year, min_value=2020, max_value=2035)

    comunidad_filter = st.selectbox("Comunidad autónoma",
                                    ["todas"] + list(COMUNIDADES_MAP.keys()),
                                    format_func=lambda x: "Todas" if x=="todas" else COMUNIDADES_MAP[x])

    festivos = db.get_holidays_df(comunidad=None if comunidad_filter=="todas" else comunidad_filter,
                                  año=año)
    if festivos:
        df = pd.DataFrame(festivos)
        st.dataframe(
            df[["fecha","descripcion","tipo","comunidad_autonoma"]].rename(columns={
                "fecha":"Fecha","descripcion":"Descripción",
                "tipo":"Tipo","comunidad_autonoma":"Comunidad"}),
            use_container_width=True, hide_index=True
        )
        # Delete option
        fid_opts = {f"{f['fecha']} — {f['descripcion']}": f["id"] for f in festivos}
        del_sel = st.selectbox("Eliminar festivo", list(fid_opts.keys()))
        if st.button("🗑️ Eliminar seleccionado"):
            db.delete_holiday(fid_opts[del_sel])
            db.audit(current_user()["id"], "eliminar_festivo")
            st.success("Eliminado."); st.rerun()

    st.subheader("➕ Añadir festivo")
    with st.form("add_fest"):
        c1, c2, c3, c4 = st.columns(4)
        fecha_f = c1.date_input("Fecha")
        desc_f = c2.text_input("Descripción")
        tipo_f = c3.selectbox("Tipo", ["nacional","autonomico","local"])
        com_f = c4.selectbox("Comunidad", ["todas"] + list(COMUNIDADES_MAP.keys()),
                             format_func=lambda x: "Todas" if x=="todas" else COMUNIDADES_MAP[x])
        if st.form_submit_button("Añadir festivo"):
            db.add_holiday(fecha_f, desc_f, tipo_f, com_f, fecha_f.year)
            db.audit(current_user()["id"], "añadir_festivo")
            st.success("Festivo añadido."); st.rerun()

# ── Page: Exportaciones ───────────────────────────────────────────────────────

def page_exportaciones():
    st.title("📥 Exportaciones")
    st.markdown("""<div class="legal-box">
    <b>RDL 8/2019 — Art. 34.9 ET</b>: Registros conservados <b>4 años</b> y disponibles
    para trabajadores, sus representantes y la Inspección de Trabajo y Seguridad Social.
    </div>""", unsafe_allow_html=True)

    hoy = date.today()
    users = db.get_all_users(activos_only=True)
    emp_opts = {"Todos los empleados": None}
    emp_opts.update({f"{u['nombre']} {u['apellidos']}": u["id"] for u in users})

    c1, c2, c3, c4 = st.columns(4)
    emp_sel = c1.selectbox("Empleado", list(emp_opts.keys()))
    emp_id = emp_opts[emp_sel]
    f_ini = c2.date_input("Desde", value=date(hoy.year, hoy.month, 1))
    f_fin = c3.date_input("Hasta", value=hoy)
    tipo_exp = c4.selectbox("Informe", [
        "Registro horario completo",
        "Resumen mensual",
        "Vacaciones y ausencias",
        "Horas extra",
        "Incidencias",
    ])

    if st.button("📊 Generar Excel", type="primary"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            if tipo_exp == "Registro horario completo":
                if emp_id:
                    entries = db.get_entries_range(emp_id, f_ini, f_fin)
                else:
                    entries = db.get_all_entries_range(f_ini, f_fin)
                if entries:
                    df = pd.DataFrame(entries)
                    df = df[["fecha","emp_nombre","tipo","hora","observaciones","is_manual","ip"]].rename(columns={
                        "fecha":"Fecha","emp_nombre":"Empleado","tipo":"Tipo","hora":"Hora",
                        "observaciones":"Observaciones","is_manual":"Manual","ip":"IP"})
                    df.to_excel(writer, sheet_name="Registro Horario", index=False)

            elif tipo_exp == "Resumen mensual":
                if emp_id:
                    entries = db.get_entries_range(emp_id, f_ini, f_fin)
                else:
                    entries = db.get_all_entries_range(f_ini, f_fin)
                if entries:
                    df = pd.DataFrame(entries)
                    def calc(g):
                        return db.calc_worked_hours(g.to_dict("records"))
                    res = df.groupby(["emp_nombre","fecha"]).apply(calc).reset_index(name="horas")
                    res["mes"] = pd.to_datetime(res["fecha"]).dt.to_period("M").astype(str)
                    summary = res.groupby(["mes","emp_nombre"]).agg(
                        dias=("fecha","nunique"), horas_totales=("horas","sum"),
                        max_dia=("horas","max")).reset_index()
                    summary["horas_extra"] = (summary["horas_totales"] - summary["dias"]*8).clip(lower=0)
                    summary.columns = ["Mes","Empleado","Días","Horas totales","Máx/día","Horas extra aprox."]
                    summary.to_excel(writer, sheet_name="Resumen Mensual", index=False)

            elif tipo_exp == "Vacaciones y ausencias":
                reqs = db.get_all_requests()
                if reqs:
                    df = pd.DataFrame(reqs)
                    df[["emp_nombre","tipo","fecha_inicio","fecha_fin","dias_laborables",
                        "estado","comentario_empleado","comentario_manager","manager_nombre","fecha_solicitud"]].rename(columns={
                        "emp_nombre":"Empleado","tipo":"Tipo","fecha_inicio":"Desde",
                        "fecha_fin":"Hasta","dias_laborables":"Días lab.","estado":"Estado",
                        "comentario_empleado":"Comentario emp.","comentario_manager":"Respuesta mgr.",
                        "manager_nombre":"Aprobado por","fecha_solicitud":"Fecha solicitud"
                    }).to_excel(writer, sheet_name="Vacaciones", index=False)

            elif tipo_exp == "Horas extra":
                if emp_id:
                    entries = db.get_entries_range(emp_id, f_ini, f_fin)
                else:
                    entries = db.get_all_entries_range(f_ini, f_fin)
                if entries:
                    df = pd.DataFrame(entries)
                    def calc(g):
                        return db.calc_worked_hours(g.to_dict("records"))
                    res = df.groupby(["emp_nombre","fecha"]).apply(calc).reset_index(name="horas")
                    res["extra"] = (res["horas"] - 8).clip(lower=0)
                    res["alerta"] = res["horas"].apply(lambda h: "SUPERA 9H — Art.34.3 ET" if h > 9 else "")
                    summary = res.groupby("emp_nombre").agg(
                        total_extra=("extra","sum"), dias_con_extra=("extra",lambda x:(x>0).sum())
                    ).reset_index()
                    summary["limite_legal"] = 80
                    summary["excede_Art35"] = summary["total_extra"] > 80
                    summary.columns = ["Empleado","Total H.Extra","Días con extra","Límite legal/año","Excede Art.35 ET"]
                    summary.to_excel(writer, sheet_name="Resumen Horas Extra", index=False)
                    res[["emp_nombre","fecha","horas","extra","alerta"]].rename(columns={
                        "emp_nombre":"Empleado","fecha":"Fecha","horas":"Horas totales",
                        "extra":"Horas extra","alerta":"Alerta legal"
                    }).to_excel(writer, sheet_name="Detalle diario", index=False)

            elif tipo_exp == "Incidencias":
                incs = db.get_all_incidents()
                if incs:
                    df = pd.DataFrame(incs)
                    df[["emp_nombre","fecha","tipo","descripcion","estado","resolucion","created_at"]].rename(columns={
                        "emp_nombre":"Empleado","fecha":"Fecha","tipo":"Tipo",
                        "descripcion":"Descripción","estado":"Estado",
                        "resolucion":"Resolución","created_at":"Creada"
                    }).to_excel(writer, sheet_name="Incidencias", index=False)

            # Legal metadata
            pd.DataFrame({
                "Campo":["Generado el","Período","Normativa","Obligación conservación"],
                "Valor":[
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    f"{f_ini:%d/%m/%Y} — {f_fin:%d/%m/%Y}",
                    "RDL 8/2019 · ET Arts. 34, 35, 38 · RGPD",
                    "4 años (Art. 34.9 ET)",
                ]
            }).to_excel(writer, sheet_name="Info Legal", index=False)

        out.seek(0)
        fname = f"ficha_{tipo_exp.lower().replace(' ','_')}_{f_ini:%Y%m%d}_{f_fin:%Y%m%d}.xlsx"
        st.download_button("⬇️ Descargar Excel", data=out, file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary")
        st.success(f"✅ Archivo generado: **{fname}**")
        db.audit(current_user()["id"], "exportacion", datos={"tipo": tipo_exp, "f_ini": str(f_ini), "f_fin": str(f_fin)})

# ── Page: Auditoría ───────────────────────────────────────────────────────────

def page_auditoria():
    st.title("🔍 Auditoría y Trazabilidad")
    st.markdown("""<div class="legal-box">
    <b>RGPD + RDL 8/2019</b>: Historial completo e inmutable. Ningún registro puede eliminarse físicamente.
    Solo correcciones auditadas con trazabilidad completa.
    </div>""", unsafe_allow_html=True)

    logs = db.get_audit_logs(limit=200)
    if not logs:
        st.info("Sin registros de auditoría.")
        return

    df = pd.DataFrame(logs)
    st.dataframe(
        df[["created_at","user_nombre","accion","tabla","registro_id","datos","ip"]].rename(columns={
            "created_at":"Timestamp","user_nombre":"Usuario","accion":"Acción",
            "tabla":"Tabla","registro_id":"ID Registro","datos":"Datos","ip":"IP"
        }),
        use_container_width=True, hide_index=True
    )

    # Export audit log
    out = BytesIO()
    df.to_excel(out, index=False)
    out.seek(0)
    st.download_button("⬇️ Exportar log auditoría", data=out,
                       file_name=f"auditoria_{date.today()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    st.markdown(STYLES, unsafe_allow_html=True)

    if not logged_in():
        page_login()
        return

    page = render_sidebar()

    # Clean page name (strip emoji prefix)
    clean = page.strip()

    if "Fichaje" in clean:
        page_fichaje()
    elif "Calendario" in clean:
        page_calendario()
    elif "Vacaciones" in clean:
        page_vacaciones()
    elif "Notificaciones" in clean:
        page_notificaciones()
    elif "Equipo" in clean:
        page_equipo()
    elif "Aprobar" in clean:
        page_aprobar()
    elif "Dashboard" in clean:
        page_admin_dashboard()
    elif "Usuarios" in clean:
        page_usuarios()
    elif "Festivos" in clean:
        page_festivos()
    elif "Exportaciones" in clean:
        page_exportaciones()
    elif "Auditoría" in clean:
        page_auditoria()
    else:
        page_fichaje()

if __name__ == "__main__":
    main()
