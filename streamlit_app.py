import streamlit as st
import sqlite3
import json
import uuid
from datetime import datetime

DB_PATH = "sessions.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS sessions
             (id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              device_name TEXT,
              created_at TEXT,
              updated_at TEXT,
              data TEXT)"""
    )
    conn.commit()
    conn.close()


def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, name, device_name, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
    )
    rows = c.fetchall()
    conn.close()
    return rows


def create_session(name, device_name):
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, name, device_name, now, now, json.dumps({"notes": ""})),
    )
    conn.commit()
    conn.close()
    return session_id


def load_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    return row


def save_session(session_id, notes):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET data = ?, updated_at = ? WHERE id = ?",
        (json.dumps({"notes": notes}), now, session_id),
    )
    conn.commit()
    conn.close()


def delete_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def fmt_dt(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")


init_db()

st.set_page_config(page_title="Sync de Sesiones", page_icon="🔄", layout="wide")

# --- State initialization ---
if "device_name" not in st.session_state:
    st.session_state.device_name = "Mi dispositivo"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "notes_draft" not in st.session_state:
    st.session_state.notes_draft = ""
if "saved_flag" not in st.session_state:
    st.session_state.saved_flag = False

# --- Sidebar ---
with st.sidebar:
    st.title("🔄 Session Sync")
    st.caption("Accede a tus sesiones desde cualquier dispositivo")

    st.divider()
    st.subheader("📱 Este dispositivo")
    new_name = st.text_input(
        "Nombre del dispositivo",
        value=st.session_state.device_name,
        help="Así aparecerá en la lista de sesiones",
    )
    if new_name != st.session_state.device_name:
        st.session_state.device_name = new_name

    st.divider()
    st.subheader("➕ Nueva sesión")
    session_label = st.text_input("Nombre de la sesión", placeholder="Ej. Trabajo del portátil")
    if st.button("Crear sesión", type="primary", use_container_width=True):
        if session_label.strip():
            sid = create_session(session_label.strip(), st.session_state.device_name)
            st.session_state.current_session_id = sid
            st.session_state.notes_draft = ""
            st.session_state.saved_flag = False
            st.rerun()
        else:
            st.warning("Introduce un nombre para la sesión.")

    st.divider()
    st.caption(
        "**Cómo sincronizar:** Abre la misma URL de esta app en tu móvil o portátil. "
        "Todos los dispositivos comparten la misma base de datos de sesiones."
    )

# --- Main layout ---
list_col, detail_col = st.columns([2, 3], gap="large")

with list_col:
    st.subheader("Todas las sesiones")
    sessions = get_all_sessions()

    if not sessions:
        st.info("Aún no hay sesiones. Crea una desde el panel lateral.")
    else:
        for row in sessions:
            sess_id, name, device, created, updated = row
            is_active = sess_id == st.session_state.current_session_id

            with st.container(border=True):
                header_cols = st.columns([4, 1, 1])
                with header_cols[0]:
                    label = f"**🟢 {name}**" if is_active else f"**{name}**"
                    st.markdown(label)
                    st.caption(f"📱 {device}  ·  🕐 {fmt_dt(updated)}")
                with header_cols[1]:
                    open_disabled = is_active
                    if st.button("Abrir", key=f"open_{sess_id}", disabled=open_disabled, use_container_width=True):
                        full = load_session(sess_id)
                        data = json.loads(full[5]) if full and full[5] else {}
                        st.session_state.current_session_id = sess_id
                        st.session_state.notes_draft = data.get("notes", "")
                        st.session_state.saved_flag = False
                        st.rerun()
                with header_cols[2]:
                    if st.button("🗑", key=f"del_{sess_id}", use_container_width=True):
                        if is_active:
                            st.session_state.current_session_id = None
                            st.session_state.notes_draft = ""
                        delete_session(sess_id)
                        st.rerun()

with detail_col:
    if st.session_state.current_session_id:
        full = load_session(st.session_state.current_session_id)
        if not full:
            st.session_state.current_session_id = None
            st.rerun()
        else:
            sess_id, name, device, created, updated, data_json = full
            data = json.loads(data_json) if data_json else {}

            st.subheader(f"📝 {name}")
            st.caption(f"Creada en **{device}** · {fmt_dt(created)}")

            notes = st.text_area(
                "Notas de esta sesión",
                value=st.session_state.notes_draft,
                height=350,
                placeholder="Escribe aquí... los cambios se guardan y se verán en todos tus dispositivos.",
                key="notes_area",
            )

            save_col, status_col = st.columns([1, 3])
            with save_col:
                if st.button("💾 Guardar", type="primary", use_container_width=True):
                    save_session(sess_id, notes)
                    st.session_state.notes_draft = notes
                    st.session_state.saved_flag = True
                    st.rerun()
            with status_col:
                if st.session_state.saved_flag:
                    st.success("Guardado correctamente.")
    else:
        st.subheader("Ninguna sesión abierta")
        st.info(
            "Selecciona una sesión de la lista o crea una nueva desde el panel lateral. "
            "Las sesiones creadas en cualquier dispositivo aparecen en esta lista."
        )
