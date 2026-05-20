import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import plotly.express as px

st.set_page_config(
    page_title="Control Horario | España",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 2rem; }
.legal-box {
    background: #fff8e1; border-left: 4px solid #f9a825;
    padding: 10px 14px; border-radius: 4px; margin: 6px 0;
}
</style>
""", unsafe_allow_html=True)

DB_PATH = "control_horario.db"

# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS empresa (
        id INTEGER PRIMARY KEY DEFAULT 1,
        nombre TEXT DEFAULT 'Mi Empresa S.L.',
        cif TEXT DEFAULT '',
        direccion TEXT DEFAULT '',
        convenio TEXT DEFAULT 'Convenio Colectivo General'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS empleados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        apellidos TEXT NOT NULL,
        email TEXT DEFAULT '',
        departamento TEXT DEFAULT '',
        puesto TEXT DEFAULT '',
        fecha_alta TEXT DEFAULT (date('now')),
        horas_semanales REAL DEFAULT 40.0,
        tipo_contrato TEXT DEFAULT 'indefinido',
        activo INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        hora_entrada TEXT,
        hora_salida TEXT,
        tipo TEXT DEFAULT 'presencial',
        observaciones TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (empleado_id) REFERENCES empleados(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS solicitudes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado_id INTEGER NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        tipo TEXT NOT NULL,
        estado TEXT DEFAULT 'pendiente',
        observaciones TEXT DEFAULT '',
        fecha_solicitud TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (empleado_id) REFERENCES empleados(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS festivos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT UNIQUE NOT NULL,
        descripcion TEXT NOT NULL,
        tipo TEXT DEFAULT 'nacional'
    )""")

    conn.commit()

    # Seed festivos nacionales 2025–2026
    festivos = [
        ("2025-01-01", "Año Nuevo", "nacional"),
        ("2025-01-06", "Epifanía del Señor (Reyes)", "nacional"),
        ("2025-04-17", "Jueves Santo", "nacional"),
        ("2025-04-18", "Viernes Santo", "nacional"),
        ("2025-05-01", "Fiesta del Trabajo", "nacional"),
        ("2025-08-15", "Asunción de la Virgen", "nacional"),
        ("2025-10-12", "Fiesta Nacional de España", "nacional"),
        ("2025-11-01", "Todos los Santos", "nacional"),
        ("2025-12-06", "Día de la Constitución Española", "nacional"),
        ("2025-12-08", "Inmaculada Concepción", "nacional"),
        ("2025-12-25", "Natividad del Señor", "nacional"),
        ("2026-01-01", "Año Nuevo", "nacional"),
        ("2026-01-06", "Epifanía del Señor (Reyes)", "nacional"),
        ("2026-04-02", "Jueves Santo", "nacional"),
        ("2026-04-03", "Viernes Santo", "nacional"),
        ("2026-05-01", "Fiesta del Trabajo", "nacional"),
        ("2026-08-15", "Asunción de la Virgen", "nacional"),
        ("2026-10-12", "Fiesta Nacional de España", "nacional"),
        ("2026-11-01", "Todos los Santos", "nacional"),
        ("2026-12-06", "Día de la Constitución Española", "nacional"),
        ("2026-12-08", "Inmaculada Concepción", "nacional"),
        ("2026-12-25", "Natividad del Señor", "nacional"),
    ]
    for f in festivos:
        c.execute("INSERT OR IGNORE INTO festivos (fecha, descripcion, tipo) VALUES (?,?,?)", f)

    c.execute("INSERT OR IGNORE INTO empresa (id) VALUES (1)")
    conn.commit()
    conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def db():
    return sqlite3.connect(DB_PATH)


def get_empleados(solo_activos=True):
    q = "SELECT * FROM empleados" + (" WHERE activo=1" if solo_activos else "")
    q += " ORDER BY apellidos, nombre"
    conn = db()
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def get_registros(empleado_id=None, fecha_inicio=None, fecha_fin=None):
    q = """SELECT r.*, e.nombre || ' ' || e.apellidos AS empleado_nombre
           FROM registros r JOIN empleados e ON r.empleado_id = e.id WHERE 1=1"""
    params = []
    if empleado_id:
        q += " AND r.empleado_id=?"; params.append(empleado_id)
    if fecha_inicio:
        q += " AND r.fecha>=?"; params.append(str(fecha_inicio))
    if fecha_fin:
        q += " AND r.fecha<=?"; params.append(str(fecha_fin))
    q += " ORDER BY r.fecha DESC, r.hora_entrada"
    conn = db()
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_solicitudes(empleado_id=None, estado=None):
    q = """SELECT s.*, e.nombre || ' ' || e.apellidos AS empleado_nombre
           FROM solicitudes s JOIN empleados e ON s.empleado_id = e.id WHERE 1=1"""
    params = []
    if empleado_id:
        q += " AND s.empleado_id=?"; params.append(empleado_id)
    if estado:
        q += " AND s.estado=?"; params.append(estado)
    q += " ORDER BY s.fecha_solicitud DESC"
    conn = db()
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def calcular_horas(entrada, salida):
    if not entrada or not salida:
        return 0.0
    try:
        fmt = "%H:%M"
        e = datetime.strptime(str(entrada)[:5], fmt)
        s = datetime.strptime(str(salida)[:5], fmt)
        diff = (s - e).total_seconds()
        return max(0.0, diff / 3600)
    except Exception:
        return 0.0


def fmt_horas(h):
    if h <= 0:
        return "—"
    return f"{int(h)}h {int((h % 1) * 60):02d}m"


def festivos_set(año):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT fecha FROM festivos WHERE strftime('%Y',fecha)=?", (str(año),))
    fsts = {r[0] for r in c.fetchall()}
    conn.close()
    return fsts


def dias_naturales(f_ini, f_fin):
    return (f_fin - f_ini).days + 1


def dias_habiles(f_ini, f_fin):
    fsts = festivos_set(f_ini.year) | festivos_set(f_fin.year)
    dias = 0
    cur = f_ini
    while cur <= f_fin:
        if cur.weekday() < 5 and str(cur) not in fsts:
            dias += 1
        cur += timedelta(days=1)
    return dias


def emp_opciones(empleados, include_todos=False):
    d = {}
    if include_todos:
        d["Todos los empleados"] = None
    for _, r in empleados.iterrows():
        d[f"{r['nombre']} {r['apellidos']}"] = r["id"]
    return d


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_dashboard():
    st.title("📊 Dashboard — Control Horario")

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())

    conn = db()
    c = conn.cursor()
    total_emp   = c.execute("SELECT COUNT(*) FROM empleados WHERE activo=1").fetchone()[0]
    fichados    = c.execute("SELECT COUNT(*) FROM registros WHERE fecha=? AND hora_entrada IS NOT NULL", (str(hoy),)).fetchone()[0]
    trabajando  = c.execute("SELECT COUNT(*) FROM registros WHERE fecha=? AND hora_entrada IS NOT NULL AND hora_salida IS NULL", (str(hoy),)).fetchone()[0]
    pendientes  = c.execute("SELECT COUNT(*) FROM solicitudes WHERE estado='pendiente'").fetchone()[0]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Empleados activos", total_emp)
    c2.metric("✅ Fichados hoy", fichados)
    c3.metric("🟢 Trabajando ahora", trabajando)
    c4.metric("📋 Solicitudes pendientes", pendientes)

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Horas trabajadas esta semana")
        df_sem = get_registros(fecha_inicio=lunes, fecha_fin=hoy)
        if not df_sem.empty:
            df_sem["horas"] = df_sem.apply(lambda r: calcular_horas(r["hora_entrada"], r["hora_salida"]), axis=1)
            por_dia = df_sem.groupby("fecha")["horas"].sum().reset_index()
            fig = px.bar(por_dia, x="fecha", y="horas",
                         labels={"fecha": "Fecha", "horas": "Horas"},
                         color="horas", color_continuous_scale="Blues")
            fig.add_hline(y=8, line_dash="dash", line_color="steelblue", annotation_text="8h/día")
            fig.add_hline(y=9, line_dash="dash", line_color="tomato", annotation_text="Máx. 9h (Art.34 ET)")
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin registros esta semana.")

    with right:
        st.subheader(f"Situación hoy — {hoy.strftime('%d/%m/%Y')}")
        df_hoy = get_registros(fecha_inicio=hoy, fecha_fin=hoy)
        if not df_hoy.empty:
            df_hoy["horas"] = df_hoy.apply(lambda r: calcular_horas(r["hora_entrada"], r["hora_salida"]), axis=1)
            df_hoy["Estado"] = df_hoy.apply(
                lambda r: "🟢 Trabajando" if r["hora_entrada"] and not r["hora_salida"]
                else ("✅ Completo" if r["hora_salida"] else "⚪ Sin fichar"), axis=1)
            st.dataframe(
                df_hoy[["empleado_nombre", "hora_entrada", "hora_salida", "Estado"]].rename(columns={
                    "empleado_nombre": "Empleado", "hora_entrada": "Entrada", "hora_salida": "Salida"}),
                use_container_width=True, hide_index=True)
        else:
            st.info("Nadie fichado hoy todavía.")

    st.subheader("⚠️ Alertas de cumplimiento legal")
    alertas = []
    if not df_hoy.empty:
        for _, row in df_hoy[df_hoy["horas"] > 9].iterrows():
            alertas.append(f"🔴 **{row['empleado_nombre']}** supera 9h hoy ({row['horas']:.1f}h) — Art. 34.3 ET")
    if not df_sem.empty:
        df_sem["horas"] = df_sem.apply(lambda r: calcular_horas(r["hora_entrada"], r["hora_salida"]), axis=1)
        for emp, h in df_sem.groupby("empleado_nombre")["horas"].sum().items():
            if h > 40:
                alertas.append(f"🟡 **{emp}** acumula {h:.1f}h esta semana — supera 40h/sem (Art. 34 ET)")
    if alertas:
        for a in alertas:
            st.warning(a)
    else:
        st.success("✅ Sin alertas activas. Cumplimiento correcto.")

    with st.expander("ℹ️ Marco legal aplicable — RDL 8/2019 y Estatuto de los Trabajadores"):
        st.markdown("""
| Norma | Contenido |
|---|---|
| **RDL 8/2019** | Registro horario diario **obligatorio** para todas las empresas |
| **Art. 34 ET** | Máximo **40 h/semana** en cómputo anual; máximo **9 h/día** salvo convenio |
| **Art. 34.3 ET** | Descanso mínimo de **12 horas** entre jornadas |
| **Art. 35 ET** | Horas extra: máximo **80 h/año**; deben compensarse |
| **Art. 38 ET** | Vacaciones anuales mínimas: **30 días naturales** |
| **Art. 34.9 ET** | Registros conservados **4 años** y disponibles para la Inspección de Trabajo |
        """)


def page_fichaje():
    st.title("⏱️ Fichaje — Entrada y Salida")

    empleados = get_empleados()
    if empleados.empty:
        st.warning("Sin empleados registrados. Ve a **Empleados** para añadir trabajadores.")
        return

    hoy = date.today()
    opciones = emp_opciones(empleados)

    col_form, col_hoy = st.columns([1, 1])

    with col_form:
        st.subheader("Registrar fichaje")
        emp_nombre = st.selectbox("Empleado", list(opciones.keys()))
        emp_id = opciones[emp_nombre]
        fecha_sel = st.date_input("Fecha", value=hoy)
        tipo_jornada = st.selectbox("Tipo de jornada", ["presencial", "teletrabajo", "mixta", "desplazamiento"])
        obs = st.text_input("Observaciones (opcional)")

        conn = db()
        reg = conn.execute(
            "SELECT * FROM registros WHERE empleado_id=? AND fecha=?",
            (emp_id, str(fecha_sel))
        ).fetchone()
        conn.close()

        hora_actual = datetime.now().time().replace(second=0, microsecond=0)
        hora_manual = st.time_input("Hora (ajusta si necesario)", value=hora_actual)

        if reg:
            st.info(f"Entrada registrada: **{str(reg[3])[:5]}**" if reg[3] else "Sin entrada registrada")
            if reg[4]:
                h = calcular_horas(reg[3], reg[4])
                st.info(f"Salida registrada: **{str(reg[4])[:5]}** — Jornada: **{fmt_horas(h)}**")
                if h > 9:
                    st.error("⚠️ Jornada supera el máximo de 9h (Art. 34.3 ET)")
                elif h > 8:
                    st.warning(f"Jornada de {h:.2f}h (supera las 8h habituales)")

        st.divider()
        b1, b2, b3 = st.columns(3)

        if b1.button("🟢 ENTRADA", use_container_width=True, type="primary"):
            hora_str = hora_manual.strftime("%H:%M")
            conn = db()
            if reg:
                conn.execute("UPDATE registros SET hora_entrada=?, tipo=?, observaciones=? WHERE id=?",
                             (hora_str, tipo_jornada, obs, reg[0]))
            else:
                conn.execute("INSERT INTO registros (empleado_id, fecha, hora_entrada, tipo, observaciones) VALUES (?,?,?,?,?)",
                             (emp_id, str(fecha_sel), hora_str, tipo_jornada, obs))
            conn.commit(); conn.close()
            st.success(f"✅ Entrada registrada: {hora_str}")
            st.rerun()

        if b2.button("🔴 SALIDA", use_container_width=True):
            if not reg or not reg[3]:
                st.error("Debes registrar primero la entrada.")
            else:
                hora_str = hora_manual.strftime("%H:%M")
                conn = db()
                conn.execute("UPDATE registros SET hora_salida=?, tipo=?, observaciones=? WHERE id=?",
                             (hora_str, tipo_jornada, obs, reg[0]))
                conn.commit(); conn.close()
                h = calcular_horas(reg[3], hora_str)
                if h > 9:
                    st.error(f"⚠️ Salida registrada: {hora_str}. Jornada: {h:.2f}h — supera 9h (Art. 34.3 ET)")
                else:
                    st.success(f"✅ Salida registrada: {hora_str} — Jornada: {fmt_horas(h)}")
                st.rerun()

        if b3.button("🗑️ Borrar", use_container_width=True):
            if reg:
                conn = db(); conn.execute("DELETE FROM registros WHERE id=?", (reg[0],))
                conn.commit(); conn.close()
                st.success("Registro eliminado.")
                st.rerun()

    with col_hoy:
        st.subheader(f"Registros de hoy — {hoy.strftime('%d/%m/%Y')}")
        df_hoy = get_registros(fecha_inicio=hoy, fecha_fin=hoy)
        if not df_hoy.empty:
            df_hoy["horas"] = df_hoy.apply(lambda r: calcular_horas(r["hora_entrada"], r["hora_salida"]), axis=1)
            df_hoy["Horas"] = df_hoy["horas"].apply(fmt_horas)
            df_hoy["⚠️"] = df_hoy["horas"].apply(lambda h: "⚠️" if h > 9 else ("🟢" if h > 0 else "🕐"))
            st.dataframe(
                df_hoy[["empleado_nombre", "hora_entrada", "hora_salida", "Horas", "tipo", "⚠️"]].rename(columns={
                    "empleado_nombre": "Empleado", "hora_entrada": "Entrada",
                    "hora_salida": "Salida", "tipo": "Tipo"}),
                use_container_width=True, hide_index=True)
            total = df_hoy["horas"].sum()
            st.metric("Total horas equipo hoy", fmt_horas(total))
        else:
            st.info("Sin registros hoy.")

        st.markdown("""<div class="legal-box">
        📋 <strong>RDL 8/2019</strong>: El registro diario de jornada es <strong>obligatorio</strong>.
        Los datos se conservan 4 años.</div>""", unsafe_allow_html=True)


def page_historial():
    st.title("📅 Historial de Registros")

    empleados = get_empleados()
    if empleados.empty:
        st.warning("Sin empleados registrados.")
        return

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    f1, f2, f3 = st.columns(3)
    opciones = emp_opciones(empleados, include_todos=True)
    emp_sel = f1.selectbox("Empleado", list(opciones.keys()))
    emp_id = opciones[emp_sel]
    fecha_inicio = f2.date_input("Desde", value=inicio_mes)
    fecha_fin = f3.date_input("Hasta", value=hoy)

    df = get_registros(empleado_id=emp_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    if df.empty:
        st.info("Sin registros en el período seleccionado.")
        return

    df["horas"] = df.apply(lambda r: calcular_horas(r["hora_entrada"], r["hora_salida"]), axis=1)

    c1, c2, c3, c4 = st.columns(4)
    dias = df["fecha"].nunique()
    total_h = df["horas"].sum()
    extra_h = max(0, total_h - dias * 8)
    alertas_d = (df["horas"] > 9).sum()
    c1.metric("Días registrados", dias)
    c2.metric("Horas totales", fmt_horas(total_h))
    c3.metric("Horas extra aprox.", fmt_horas(extra_h))
    c4.metric("Días > 9h (alerta)", int(alertas_d))

    st.divider()

    if emp_id:
        por_dia = df.groupby("fecha")["horas"].sum().reset_index()
        fig = px.bar(por_dia, x="fecha", y="horas",
                     labels={"fecha": "Fecha", "horas": "Horas"},
                     title=f"Horas diarias — {emp_sel}")
    else:
        por_dia = df.groupby(["fecha", "empleado_nombre"])["horas"].sum().reset_index()
        fig = px.bar(por_dia, x="fecha", y="horas", color="empleado_nombre",
                     labels={"fecha": "Fecha", "horas": "Horas", "empleado_nombre": "Empleado"},
                     title="Horas diarias por empleado")
    fig.add_hline(y=8, line_dash="dash", line_color="steelblue", annotation_text="8h")
    fig.add_hline(y=9, line_dash="dash", line_color="tomato", annotation_text="Máx. 9h")
    st.plotly_chart(fig, use_container_width=True)

    df["Horas"] = df["horas"].apply(fmt_horas)
    df["⚠️"] = df["horas"].apply(lambda h: "⚠️ >9h" if h > 9 else "")
    st.dataframe(
        df[["fecha", "empleado_nombre", "hora_entrada", "hora_salida", "Horas", "tipo", "observaciones", "⚠️"]].rename(columns={
            "fecha": "Fecha", "empleado_nombre": "Empleado", "hora_entrada": "Entrada",
            "hora_salida": "Salida", "tipo": "Tipo", "observaciones": "Obs."}),
        use_container_width=True, hide_index=True)

    st.subheader("Resumen semanal")
    df["semana"] = pd.to_datetime(df["fecha"]).dt.isocalendar().week.astype(int)
    df["año"] = pd.to_datetime(df["fecha"]).dt.year
    sem = df.groupby(["año", "semana", "empleado_nombre"])["horas"].sum().reset_index()
    sem.columns = ["Año", "Semana", "Empleado", "H. semana"]
    sem["Estado"] = sem["H. semana"].apply(lambda h: "⚠️ >40h (Art.34 ET)" if h > 40 else "✅ OK")
    st.dataframe(sem, use_container_width=True, hide_index=True)


def page_empleados():
    st.title("👥 Gestión de Empleados")
    tab_lista, tab_nuevo = st.tabs(["📋 Lista", "➕ Nuevo Empleado"])

    with tab_lista:
        df = get_empleados(solo_activos=False)
        if df.empty:
            st.info("Sin empleados.")
        else:
            show_inact = st.checkbox("Mostrar inactivos")
            disp = df if show_inact else df[df["activo"] == 1]
            disp = disp.copy()
            disp["Estado"] = disp["activo"].apply(lambda x: "✅ Activo" if x else "❌ Inactivo")
            st.dataframe(
                disp[["nombre", "apellidos", "email", "departamento", "puesto",
                       "horas_semanales", "tipo_contrato", "fecha_alta", "Estado"]].rename(columns={
                    "nombre": "Nombre", "apellidos": "Apellidos", "email": "Email",
                    "departamento": "Dpto.", "puesto": "Puesto", "horas_semanales": "H/sem",
                    "tipo_contrato": "Contrato", "fecha_alta": "Alta"}),
                use_container_width=True, hide_index=True)

            st.subheader("✏️ Editar empleado")
            opc = {f"{r['nombre']} {r['apellidos']}": r["id"] for _, r in disp.iterrows()}
            sel = st.selectbox("Seleccionar", list(opc.keys()), key="edit_emp")
            eid = opc[sel]
            row = disp[disp["id"] == eid].iloc[0]

            contratos = ["indefinido", "temporal", "practicas", "formacion", "parcial"]
            with st.form("f_editar"):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre", value=row["nombre"])
                apellidos = c2.text_input("Apellidos", value=row["apellidos"])
                email = c1.text_input("Email", value=row["email"] or "")
                depto = c2.text_input("Departamento", value=row["departamento"] or "")
                puesto = c1.text_input("Puesto", value=row["puesto"] or "")
                horas = c2.number_input("H/semana", value=float(row["horas_semanales"]),
                                        min_value=1.0, max_value=40.0, step=0.5)
                idx_cont = contratos.index(row["tipo_contrato"]) if row["tipo_contrato"] in contratos else 0
                contrato = c1.selectbox("Tipo contrato", contratos, index=idx_cont)
                activo = c2.checkbox("Activo", value=bool(row["activo"]))
                if st.form_submit_button("💾 Guardar cambios"):
                    conn = db()
                    conn.execute("""UPDATE empleados SET nombre=?,apellidos=?,email=?,departamento=?,
                                   puesto=?,horas_semanales=?,tipo_contrato=?,activo=? WHERE id=?""",
                                 (nombre, apellidos, email, depto, puesto, horas, contrato, int(activo), eid))
                    conn.commit(); conn.close()
                    st.success("✅ Empleado actualizado."); st.rerun()

    with tab_nuevo:
        st.subheader("Registrar nuevo empleado")
        contratos = ["indefinido", "temporal", "practicas", "formacion", "parcial"]
        with st.form("f_nuevo"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre *")
            apellidos = c2.text_input("Apellidos *")
            email = c1.text_input("Email")
            depto = c2.text_input("Departamento")
            puesto = c1.text_input("Puesto / Categoría profesional")
            fecha_alta = c2.date_input("Fecha de alta", value=date.today())
            horas = c1.number_input("Horas semanales pactadas", value=40.0,
                                    min_value=1.0, max_value=40.0, step=0.5,
                                    help="Máximo legal: 40h/semana (Art. 34 ET)")
            contrato = c2.selectbox("Tipo de contrato", contratos)
            if st.form_submit_button("✅ Registrar", type="primary"):
                if not nombre or not apellidos:
                    st.error("Nombre y apellidos son obligatorios.")
                else:
                    conn = db()
                    conn.execute("""INSERT INTO empleados
                                   (nombre,apellidos,email,departamento,puesto,fecha_alta,horas_semanales,tipo_contrato)
                                   VALUES (?,?,?,?,?,?,?,?)""",
                                 (nombre, apellidos, email, depto, puesto, str(fecha_alta), horas, contrato))
                    conn.commit(); conn.close()
                    st.success(f"✅ {nombre} {apellidos} registrado."); st.rerun()


def page_vacaciones():
    st.title("🏖️ Vacaciones y Ausencias")

    empleados = get_empleados()
    if empleados.empty:
        st.warning("Sin empleados registrados.")
        return

    tab_sol, tab_nueva, tab_resumen = st.tabs(["📋 Solicitudes", "➕ Nueva Solicitud", "📊 Resumen Anual"])

    with tab_sol:
        c1, c2 = st.columns(2)
        filtro_est = c1.selectbox("Estado", ["Todas", "pendiente", "aprobada", "rechazada"])
        opciones = emp_opciones(empleados, include_todos=True)
        emp_sel = c2.selectbox("Empleado", list(opciones.keys()))
        emp_id = opciones[emp_sel]

        df = get_solicitudes(empleado_id=emp_id,
                             estado=None if filtro_est == "Todas" else filtro_est)
        if df.empty:
            st.info("Sin solicitudes con los filtros actuales.")
        else:
            for _, row in df.iterrows():
                fi = date.fromisoformat(row["fecha_inicio"])
                ff = date.fromisoformat(row["fecha_fin"])
                dn = dias_naturales(fi, ff)
                label = (f"**{row['empleado_nombre']}** — "
                         f"{row['tipo'].replace('_', ' ').title()} | "
                         f"{row['fecha_inicio']} → {row['fecha_fin']} ({dn}d) | "
                         f"{row['estado'].upper()}")
                with st.expander(label):
                    if row["observaciones"]:
                        st.write(f"Observaciones: {row['observaciones']}")
                    st.caption(f"Solicitado: {row['fecha_solicitud'][:10]}")
                    if row["estado"] == "pendiente":
                        ba, br = st.columns(2)
                        if ba.button("✅ Aprobar", key=f"a{row['id']}", type="primary"):
                            conn = db()
                            conn.execute("UPDATE solicitudes SET estado='aprobada' WHERE id=?", (row["id"],))
                            conn.commit(); conn.close()
                            st.success("Aprobada."); st.rerun()
                        if br.button("❌ Rechazar", key=f"r{row['id']}"):
                            conn = db()
                            conn.execute("UPDATE solicitudes SET estado='rechazada' WHERE id=?", (row["id"],))
                            conn.commit(); conn.close()
                            st.warning("Rechazada."); st.rerun()

    with tab_nueva:
        tipos = ["vacaciones", "asuntos_propios", "descanso_compensatorio",
                 "baja_medica", "lactancia", "maternidad_paternidad",
                 "permiso_retribuido", "otros"]
        opciones2 = emp_opciones(empleados)
        with st.form("f_solicitud"):
            emp_sel2 = st.selectbox("Empleado", list(opciones2.keys()))
            emp_id2 = opciones2[emp_sel2]
            tipo = st.selectbox("Tipo de ausencia", tipos,
                                format_func=lambda x: x.replace("_", " ").title())
            c1, c2 = st.columns(2)
            fi = c1.date_input("Fecha inicio", value=date.today())
            ff = c2.date_input("Fecha fin", value=date.today())
            obs = st.text_area("Observaciones / Motivo")

            if ff >= fi:
                dn = dias_naturales(fi, ff)
                dh = dias_habiles(fi, ff)
                st.info(f"📅 **{dn} días naturales** / **{dh} días hábiles**")

            if st.form_submit_button("📤 Enviar solicitud", type="primary"):
                if ff < fi:
                    st.error("La fecha fin no puede ser anterior a la de inicio.")
                else:
                    conn = db()
                    conn.execute("""INSERT INTO solicitudes
                                   (empleado_id,fecha_inicio,fecha_fin,tipo,observaciones)
                                   VALUES (?,?,?,?,?)""",
                                 (emp_id2, str(fi), str(ff), tipo, obs))
                    conn.commit(); conn.close()
                    st.success("✅ Solicitud enviada. Pendiente de aprobación."); st.rerun()

        st.markdown("""<div class="legal-box">
        <strong>Referencia legal:</strong><br>
        • <strong>Vacaciones</strong> (Art. 38 ET): mínimo 30 días naturales/año, no compensables en metálico salvo fin de contrato.<br>
        • <strong>Permisos retribuidos</strong> (Art. 37 ET): matrimonio 15 días, nacimiento, fallecimiento familiar, traslado, etc.<br>
        • <strong>Descanso compensatorio</strong>: a pactar por horas extra realizadas (Art. 35 ET).
        </div>""", unsafe_allow_html=True)

    with tab_resumen:
        año_sel = st.number_input("Año", value=date.today().year, min_value=2020, max_value=2030)
        resumen = []
        for _, emp in empleados.iterrows():
            conn = db()
            df_v = pd.read_sql_query("""SELECT fecha_inicio, fecha_fin FROM solicitudes
                WHERE empleado_id=? AND strftime('%Y',fecha_inicio)=?
                AND estado='aprobada' AND tipo='vacaciones'""",
                conn, params=(emp["id"], str(año_sel)))
            conn.close()
            tomados = sum(
                dias_naturales(date.fromisoformat(r["fecha_inicio"]),
                               date.fromisoformat(r["fecha_fin"]))
                for _, r in df_v.iterrows()
            )
            resumen.append({
                "Empleado": f"{emp['nombre']} {emp['apellidos']}",
                "Días disfrutados": tomados,
                "Días restantes": max(0, 30 - tomados),
                "Estado": "⚠️ Exceso" if tomados > 30 else "✅ OK",
            })
        df_res = pd.DataFrame(resumen)
        st.dataframe(df_res, use_container_width=True, hide_index=True)
        if not df_res.empty:
            fig = px.bar(df_res, x="Empleado",
                         y=["Días disfrutados", "Días restantes"],
                         barmode="stack",
                         title=f"Vacaciones {año_sel} — mínimo legal 30 días naturales (Art. 38 ET)",
                         color_discrete_map={"Días disfrutados": "#1976D2", "Días restantes": "#E0E0E0"})
            fig.add_hline(y=30, line_dash="dash", line_color="tomato", annotation_text="30 días mínimo")
            st.plotly_chart(fig, use_container_width=True)


def page_exportar():
    st.title("📥 Exportar a Excel")

    empleados = get_empleados()
    if empleados.empty:
        st.warning("Sin empleados registrados.")
        return

    st.markdown("""<div class="legal-box">
    <strong>RDL 8/2019 — Art. 34.9 ET</strong>: Los registros de jornada deben conservarse
    <strong>4 años</strong> y estar disponibles para trabajadores, sus representantes
    y la Inspección de Trabajo y Seguridad Social.</div>""", unsafe_allow_html=True)

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    c1, c2, c3 = st.columns(3)
    opciones = emp_opciones(empleados, include_todos=True)
    emp_sel = c1.selectbox("Empleado", list(opciones.keys()))
    emp_id = opciones[emp_sel]
    fecha_inicio = c2.date_input("Desde", value=inicio_mes)
    fecha_fin = c3.date_input("Hasta", value=hoy)

    tipo_exp = st.selectbox("Tipo de informe", [
        "Registro horario completo",
        "Resumen mensual por empleado",
        "Solicitudes de vacaciones y ausencias",
        "Informe de horas extra",
    ])

    if st.button("📊 Generar Excel", type="primary"):
        output = BytesIO()
        conn = db()
        empresa = conn.execute("SELECT nombre, cif FROM empresa WHERE id=1").fetchone()
        conn.close()
        empresa_nombre = empresa[0] if empresa else "Empresa"
        empresa_cif = empresa[1] if empresa else ""

        with pd.ExcelWriter(output, engine="openpyxl") as writer:

            if tipo_exp == "Registro horario completo":
                df = get_registros(empleado_id=emp_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
                if not df.empty:
                    df["Horas trabajadas"] = df.apply(
                        lambda r: round(calcular_horas(r["hora_entrada"], r["hora_salida"]), 2), axis=1)
                    df["Alerta legal"] = df["Horas trabajadas"].apply(
                        lambda h: "SUPERA 9H — Art. 34.3 ET" if h > 9 else "")
                    df[["fecha", "empleado_nombre", "hora_entrada", "hora_salida",
                        "Horas trabajadas", "tipo", "observaciones", "Alerta legal"]].rename(columns={
                        "fecha": "Fecha", "empleado_nombre": "Empleado",
                        "hora_entrada": "Hora Entrada", "hora_salida": "Hora Salida",
                        "tipo": "Tipo Jornada", "observaciones": "Observaciones",
                    }).to_excel(writer, sheet_name="Registro Horario", index=False)

            elif tipo_exp == "Resumen mensual por empleado":
                df = get_registros(empleado_id=emp_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
                if not df.empty:
                    df["horas"] = df.apply(lambda r: round(calcular_horas(r["hora_entrada"], r["hora_salida"]), 2), axis=1)
                    df["mes"] = pd.to_datetime(df["fecha"]).dt.to_period("M").astype(str)
                    res = df.groupby(["mes", "empleado_nombre"]).agg(
                        Dias=("fecha", "nunique"),
                        Horas_totales=("horas", "sum"),
                        Max_horas_dia=("horas", "max"),
                    ).reset_index()
                    res["Horas_extra"] = (res["Horas_totales"] - res["Dias"] * 8).clip(lower=0)
                    res.columns = ["Mes", "Empleado", "Días trabajados",
                                   "Horas totales", "Máx. horas/día", "Horas extra aprox."]
                    res.to_excel(writer, sheet_name="Resumen Mensual", index=False)

            elif tipo_exp == "Solicitudes de vacaciones y ausencias":
                df = get_solicitudes(empleado_id=emp_id)
                if not df.empty:
                    df["Días naturales"] = df.apply(
                        lambda r: dias_naturales(date.fromisoformat(r["fecha_inicio"]),
                                                 date.fromisoformat(r["fecha_fin"])), axis=1)
                    df[["empleado_nombre", "tipo", "fecha_inicio", "fecha_fin",
                        "Días naturales", "estado", "observaciones", "fecha_solicitud"]].rename(columns={
                        "empleado_nombre": "Empleado", "tipo": "Tipo",
                        "fecha_inicio": "Desde", "fecha_fin": "Hasta",
                        "estado": "Estado", "observaciones": "Observaciones",
                        "fecha_solicitud": "Fecha solicitud",
                    }).to_excel(writer, sheet_name="Vacaciones y Ausencias", index=False)

            elif tipo_exp == "Informe de horas extra":
                df = get_registros(empleado_id=emp_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
                if not df.empty:
                    df["horas"] = df.apply(lambda r: round(calcular_horas(r["hora_entrada"], r["hora_salida"]), 2), axis=1)
                    df["extra_dia"] = (df["horas"] - 8).clip(lower=0)
                    resumen = df.groupby("empleado_nombre").agg(
                        Total_extra=("extra_dia", "sum"),
                        Dias_con_extra=("extra_dia", lambda x: (x > 0).sum()),
                    ).reset_index()
                    resumen["Límite anual (Art.35 ET)"] = 80
                    resumen["Excede límite"] = resumen["Total_extra"] > 80
                    resumen.columns = ["Empleado", "Total H. Extra", "Días con Extra",
                                       "Límite legal/año", "Excede límite Art.35 ET"]
                    resumen.to_excel(writer, sheet_name="Resumen Horas Extra", index=False)
                    df[["fecha", "empleado_nombre", "hora_entrada", "hora_salida",
                        "horas", "extra_dia"]].rename(columns={
                        "fecha": "Fecha", "empleado_nombre": "Empleado",
                        "hora_entrada": "Entrada", "hora_salida": "Salida",
                        "horas": "Horas totales", "extra_dia": "Horas extra"
                    }).to_excel(writer, sheet_name="Detalle diario", index=False)

            # Hoja de metadatos / pie legal
            pd.DataFrame({
                "Campo": ["Empresa", "CIF", "Período", "Generado el",
                          "Normativa aplicable", "Obligación conservación"],
                "Valor": [
                    empresa_nombre, empresa_cif,
                    f"{fecha_inicio.strftime('%d/%m/%Y')} — {fecha_fin.strftime('%d/%m/%Y')}",
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "RDL 8/2019 · ET Art. 34, 35, 38",
                    "4 años (Art. 34.9 ET)",
                ],
            }).to_excel(writer, sheet_name="Info Legal", index=False)

        output.seek(0)
        filename = f"control_horario_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"
        st.download_button(
            "⬇️ Descargar Excel",
            data=output,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.success(f"✅ Archivo generado: **{filename}**")


def page_configuracion():
    st.title("⚙️ Configuración")
    tab_emp, tab_fest = st.tabs(["🏢 Datos Empresa", "📅 Festivos"])

    with tab_emp:
        conn = db()
        row = conn.execute("SELECT * FROM empresa WHERE id=1").fetchone()
        conn.close()
        with st.form("f_empresa"):
            nombre = st.text_input("Nombre empresa", value=row[1] if row else "")
            cif = st.text_input("CIF", value=row[2] if row else "")
            direccion = st.text_input("Dirección", value=row[3] if row else "")
            convenio = st.text_input("Convenio colectivo", value=row[4] if row else "")
            if st.form_submit_button("💾 Guardar"):
                conn = db()
                conn.execute("INSERT OR REPLACE INTO empresa (id,nombre,cif,direccion,convenio) VALUES (1,?,?,?,?)",
                             (nombre, cif, direccion, convenio))
                conn.commit(); conn.close()
                st.success("✅ Datos guardados.")

    with tab_fest:
        año_sel = st.number_input("Año", value=date.today().year, min_value=2020, max_value=2030, key="año_f")
        conn = db()
        df_f = pd.read_sql_query(
            "SELECT id, fecha, descripcion, tipo FROM festivos WHERE strftime('%Y',fecha)=? ORDER BY fecha",
            conn, params=(str(año_sel),))
        conn.close()
        if not df_f.empty:
            st.dataframe(df_f[["fecha", "descripcion", "tipo"]].rename(columns={
                "fecha": "Fecha", "descripcion": "Descripción", "tipo": "Tipo"}),
                use_container_width=True, hide_index=True)

        st.subheader("Añadir festivo")
        with st.form("f_festivo"):
            c1, c2, c3 = st.columns(3)
            fecha_f = c1.date_input("Fecha")
            desc_f = c2.text_input("Descripción")
            tipo_f = c3.selectbox("Tipo", ["nacional", "autonomico", "local"])
            if st.form_submit_button("✅ Añadir"):
                conn = db()
                try:
                    conn.execute("INSERT INTO festivos (fecha,descripcion,tipo) VALUES (?,?,?)",
                                 (str(fecha_f), desc_f, tipo_f))
                    conn.commit()
                    st.success("Festivo añadido."); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ya existe un festivo para esa fecha.")
                finally:
                    conn.close()

        st.subheader("Eliminar festivo")
        if not df_f.empty:
            opts = {f"{r['fecha']} — {r['descripcion']}": r["id"] for _, r in df_f.iterrows()}
            sel = st.selectbox("Seleccionar festivo", list(opts.keys()))
            if st.button("🗑️ Eliminar festivo seleccionado"):
                conn = db()
                conn.execute("DELETE FROM festivos WHERE id=?", (opts[sel],))
                conn.commit(); conn.close()
                st.success("Eliminado."); st.rerun()


# ── Navigation ────────────────────────────────────────────────────────────────

def main():
    init_db()

    with st.sidebar:
        st.title("⏱️ Control Horario")
        st.caption("Cumplimiento RDL 8/2019")
        st.divider()
        pagina = st.radio("", [
            "📊 Dashboard",
            "⏱️ Fichaje",
            "📅 Historial",
            "👥 Empleados",
            "🏖️ Vacaciones",
            "📥 Exportar Excel",
            "⚙️ Configuración",
        ], label_visibility="collapsed")
        st.divider()
        st.caption("**Normativa**")
        st.caption("RDL 8/2019 — Registro diario")
        st.caption("Art. 34 ET — 40h/sem · 9h/día")
        st.caption("Art. 35 ET — Máx. 80h extra/año")
        st.caption("Art. 38 ET — 30 días vacaciones")

    pages = {
        "📊 Dashboard":    page_dashboard,
        "⏱️ Fichaje":      page_fichaje,
        "📅 Historial":    page_historial,
        "👥 Empleados":    page_empleados,
        "🏖️ Vacaciones":   page_vacaciones,
        "📥 Exportar Excel": page_exportar,
        "⚙️ Configuración": page_configuracion,
    }
    pages[pagina]()


if __name__ == "__main__":
    main()
