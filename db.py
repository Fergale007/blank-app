"""Ficha · Control Horario — Database layer (RDL 8/2019 compliant)"""



import sqlite3



import hashlib



from datetime import datetime, date, timedelta



import json







DB = "ficha.db"








import os as _os
import re as _re

# ── Database backend: SQLite (local) or PostgreSQL (Supabase/Cloud) ───────────
_PG_URL = ""
try:
    import streamlit as _st
    _PG_URL = (_st.secrets.get("DATABASE_URL", "") or "")
except Exception:
    pass
if not _PG_URL:
    _PG_URL = _os.environ.get("DATABASE_URL", "")
_USE_PG = bool(_PG_URL)


class _PGConn:
    """
    Wraps psycopg2 to behave like sqlite3.
    Handles: ?->%s, INSERT OR IGNORE, datetime(), AUTOINCREMENT, lastrowid via RETURNING.
    """
    def __init__(self):
        import psycopg2
        import psycopg2.extras
        from urllib.parse import urlparse, unquote
        _p = urlparse(_PG_URL)
        _host  = _p.hostname or ""
        _port  = _p.port or 5432
        _db    = (_p.path or "/postgres").lstrip("/")
        _user  = unquote(_p.username or "postgres")
        _pwd   = unquote(_p.password or "")
        try:
            self._cn = psycopg2.connect(
                host=_host, port=_port, dbname=_db,
                user=_user, password=_pwd,
                sslmode="require", connect_timeout=10,
            )
        except Exception as _e:
            raise RuntimeError(
                f"PG_FAIL host={_host} port={_port} user={_user!r} db={_db!r} err={_e}"
            ) from None
        self._cur = self._cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self.lastrowid = None

    @staticmethod
    def _adapt(sql):
        is_ignore = bool(_re.search(r"INSERT\s+OR\s+IGNORE", sql, _re.I))
        sql = sql.replace("?", "%s")
        sql = _re.sub(r"DEFAULT\s*\(datetime\('now'\)\)",
                      "DEFAULT TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS')", sql)
        sql = _re.sub(r"datetime\('now'\)",
                      "TO_CHAR(NOW(),'YYYY-MM-DD HH24:MI:SS')", sql)
        sql = _re.sub(r"date\('now'\)", "CURRENT_DATE::TEXT", sql)
        sql = _re.sub(r"strftime\('%Y-%m',\s*(\w+)\)",
                      r"TO_CHAR(\1::date,'YYYY-MM')", sql)
        sql = _re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                      "SERIAL PRIMARY KEY", sql, flags=_re.I)
        sql = _re.sub(r"\bAUTOINCREMENT\b", "", sql, flags=_re.I)
        sql = _re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=_re.I)
        if is_ignore:
            sql = sql.rstrip("; ") + " ON CONFLICT DO NOTHING"
        return sql, is_ignore

    def execute(self, sql, params=()):
        sql, is_ignore = self._adapt(sql)
        is_ins = sql.strip().upper().startswith("INSERT")
        has_ret = "RETURNING" in sql.upper()
        if is_ins and not has_ret and not is_ignore:
            sql = sql.rstrip("; ") + " RETURNING id"
        self._cur.execute(sql, params if params else None)
        if is_ins and not is_ignore:
            row = self._cur.fetchone()
            self.lastrowid = row["id"] if row else None
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in (self._cur.fetchall() or [])]

    def commit(self):
        self._cn.commit()

    def close(self):
        try:
            self._cn.commit()
        except Exception:
            pass
        self._cn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

# ─────────────────────────────────────────────────────────────────────────────

# ── Connection ────────────────────────────────────────────────────────────────







def _conn():
    if _USE_PG:
        return _PGConn()
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c







def hash_pw(pw: str) -> str:



    return hashlib.sha256(pw.encode()).hexdigest()







def row_to_dict(row):



    return dict(row) if row else None







def rows_to_list(rows):



    return [dict(r) for r in rows]







# ── Schema ────────────────────────────────────────────────────────────────────







def init_db():



    c = _conn()



    stmts = [



        """CREATE TABLE IF NOT EXISTS departments (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            nombre TEXT NOT NULL,



            activo INTEGER DEFAULT 1



        )""",



        """CREATE TABLE IF NOT EXISTS users (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            username TEXT UNIQUE NOT NULL,



            password_hash TEXT NOT NULL,



            nombre TEXT NOT NULL,



            apellidos TEXT NOT NULL,



            email TEXT DEFAULT '',



            telefono TEXT DEFAULT '',



            role TEXT DEFAULT 'empleado',



            department_id INTEGER REFERENCES departments(id),



            manager_id INTEGER REFERENCES users(id),



            comunidad_autonoma TEXT DEFAULT 'madrid',



            horas_semanales REAL DEFAULT 40.0,



            dias_vacaciones_anuales INTEGER DEFAULT 22,



            activo INTEGER DEFAULT 1,



            last_login TEXT,



            created_at TEXT DEFAULT (datetime('now'))



        )""",



        """CREATE TABLE IF NOT EXISTS time_entries (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER NOT NULL REFERENCES users(id),



            fecha TEXT NOT NULL,



            tipo TEXT NOT NULL,



            hora TEXT NOT NULL,



            ip TEXT DEFAULT '',



            observaciones TEXT DEFAULT '',



            is_manual INTEGER DEFAULT 0,



            created_by INTEGER REFERENCES users(id),



            deleted INTEGER DEFAULT 0,



            created_at TEXT DEFAULT (datetime('now'))



        )""",



        """CREATE TABLE IF NOT EXISTS time_incidents (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER NOT NULL REFERENCES users(id),



            fecha TEXT NOT NULL,



            tipo TEXT NOT NULL,



            descripcion TEXT DEFAULT '',



            estado TEXT DEFAULT 'pendiente',



            resolucion TEXT DEFAULT '',



            created_at TEXT DEFAULT (datetime('now')),



            resolved_at TEXT,



            resolved_by INTEGER REFERENCES users(id)



        )""",



        """CREATE TABLE IF NOT EXISTS vacation_requests (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER NOT NULL REFERENCES users(id),



            fecha_inicio TEXT NOT NULL,



            fecha_fin TEXT NOT NULL,



            tipo TEXT DEFAULT 'vacaciones',



            dias_laborables INTEGER DEFAULT 0,



            estado TEXT DEFAULT 'pendiente',



            comentario_empleado TEXT DEFAULT '',



            comentario_manager TEXT DEFAULT '',



            manager_id INTEGER REFERENCES users(id),



            fecha_solicitud TEXT DEFAULT (datetime('now')),



            fecha_resolucion TEXT



        )""",



        """CREATE TABLE IF NOT EXISTS holidays (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            fecha TEXT NOT NULL,



            descripcion TEXT NOT NULL,



            tipo TEXT DEFAULT 'nacional',



            comunidad_autonoma TEXT DEFAULT 'todas',



            año INTEGER,



            UNIQUE(fecha, comunidad_autonoma)



        )""",



        """CREATE TABLE IF NOT EXISTS notifications (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER NOT NULL REFERENCES users(id),



            tipo TEXT NOT NULL,



            titulo TEXT NOT NULL,



            mensaje TEXT NOT NULL,



            leido INTEGER DEFAULT 0,



            created_at TEXT DEFAULT (datetime('now'))



        )""",



        """CREATE TABLE IF NOT EXISTS audit_logs (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER REFERENCES users(id),



            accion TEXT NOT NULL,



            tabla TEXT DEFAULT '',



            registro_id INTEGER,



            datos TEXT DEFAULT '{}',



            ip TEXT DEFAULT '',



            created_at TEXT DEFAULT (datetime('now'))



        )""",



        """CREATE TABLE IF NOT EXISTS monthly_validations (



            id INTEGER PRIMARY KEY AUTOINCREMENT,



            user_id INTEGER NOT NULL REFERENCES users(id),



            año INTEGER NOT NULL,



            mes INTEGER NOT NULL,



            validado INTEGER DEFAULT 0,



            fecha_validacion TEXT,



            ip TEXT DEFAULT '',



            UNIQUE(user_id, año, mes)



        )""",



    ]



    for s in stmts:



        c.execute(s)



    c.commit()



    # Migration: add columns if not present
    for col, defval in [("provincia","''"), ("localidad","''"), ("cargo","''")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {defval}")
        except Exception:
            pass
    c.commit()

    _seed_holidays(c)



    _seed_users(c)



    c.commit()



    c.close()











def _seed_holidays(c):



    data = [



        ("2025-01-01", "Año Nuevo", "nacional", "todas", 2025),



        ("2025-01-06", "Epifanía del Señor", "nacional", "todas", 2025),



        ("2025-04-17", "Jueves Santo", "nacional", "todas", 2025),



        ("2025-04-18", "Viernes Santo", "nacional", "todas", 2025),



        ("2025-05-01", "Fiesta del Trabajo", "nacional", "todas", 2025),



        ("2025-08-15", "Asunción de la Virgen", "nacional", "todas", 2025),



        ("2025-10-12", "Fiesta Nacional", "nacional", "todas", 2025),



        ("2025-11-01", "Todos los Santos", "nacional", "todas", 2025),



        ("2025-12-06", "Día de la Constitución", "nacional", "todas", 2025),



        ("2025-12-08", "Inmaculada Concepción", "nacional", "todas", 2025),



        ("2025-12-25", "Navidad", "nacional", "todas", 2025),



        ("2026-01-01", "Año Nuevo", "nacional", "todas", 2026),



        ("2026-01-06", "Epifanía del Señor", "nacional", "todas", 2026),



        ("2026-04-02", "Jueves Santo", "nacional", "todas", 2026),



        ("2026-04-03", "Viernes Santo", "nacional", "todas", 2026),



        ("2026-05-01", "Fiesta del Trabajo", "nacional", "todas", 2026),



        ("2026-08-15", "Asunción de la Virgen", "nacional", "todas", 2026),



        ("2026-10-12", "Fiesta Nacional", "nacional", "todas", 2026),



        ("2026-11-01", "Todos los Santos", "nacional", "todas", 2026),



        ("2026-12-06", "Día de la Constitución", "nacional", "todas", 2026),



        ("2026-12-08", "Inmaculada Concepción", "nacional", "todas", 2026),



        ("2026-12-25", "Navidad", "nacional", "todas", 2026),



        # Madrid específicos



        ("2025-05-02", "Día de la Com. de Madrid", "autonomico", "madrid", 2025),



        ("2025-11-09", "Almudena (Madrid)", "autonomico", "madrid", 2025),



        ("2026-05-02", "Día de la Com. de Madrid", "autonomico", "madrid", 2026),



        # Cataluña



        ("2025-04-23", "Sant Jordi", "autonomico", "cataluña", 2025),



        ("2025-06-24", "Sant Joan", "autonomico", "cataluña", 2025),



        ("2025-09-11", "Diada Nacional", "autonomico", "cataluña", 2025),



        # Andalucía



        ("2025-02-28", "Día de Andalucía", "autonomico", "andalucia", 2025),



        ("2026-02-28", "Día de Andalucía", "autonomico", "andalucia", 2026),



        # País Vasco



        ("2025-07-25", "Santiago Apóstol", "autonomico", "pais_vasco", 2025),



        # Canarias autonomico
        ("2025-05-30", "Día de Canarias", "autonomico", "canarias", 2025),
        ("2026-05-30", "Día de Canarias", "autonomico", "canarias", 2026),
        # Valencia
        ("2025-10-09", "Día de la Comunitat Valenciana", "autonomico", "valencia", 2025),
        ("2026-10-09", "Día de la Comunitat Valenciana", "autonomico", "valencia", 2026),
        # Galicia
        ("2025-07-25", "Día de Galicia", "autonomico", "galicia", 2025),
        ("2026-07-25", "Día de Galicia", "autonomico", "galicia", 2026),
        # Castilla y Leon
        ("2025-04-23", "Día de Castilla y León", "autonomico", "castilla_leon", 2025),
        ("2026-04-23", "Día de Castilla y León", "autonomico", "castilla_leon", 2026),
        # Navarra
        ("2025-09-27", "Día de Navarra", "autonomico", "navarra", 2025),
        ("2026-09-27", "Día de Navarra", "autonomico", "navarra", 2026),
        # Aragon
        ("2025-04-23", "San Jorge (Aragón)", "autonomico", "aragon", 2025),
        ("2026-04-23", "San Jorge (Aragón)", "autonomico", "aragon", 2026),



    ]



    for row in data:



        try:



            c.execute("INSERT OR IGNORE INTO holidays (fecha,descripcion,tipo,comunidad_autonoma,año) VALUES (?,?,?,?,?)", row)



        except Exception:



            pass











def _seed_departments(c):
    depts = ["Direccion General", "Comercial", "Administracion"]
    for d in depts:
        try:
            c.execute("INSERT OR IGNORE INTO departments (nombre) VALUES (?)", (d,))
        except Exception:
            pass

def _seed_users(c):
    # Always seed departments first
    _seed_departments(c)
    c.commit()

    # Helper: get dept id by name
    def dept_id(name):
        row = c.execute("SELECT id FROM departments WHERE nombre=?", (name,)).fetchone()
        return row["id"] if row else None

    # Helper: get user id by username
    def uid(uname):
        row = c.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone()
        return row["id"] if row else None

    # --------------------------------------------------------------------------
    # LEVEL 0 — Director General (admin)
    # Password inicial: Temporal1234!  (cambiar en primer login)
    # --------------------------------------------------------------------------
    admins = [
        # (username, pw, nombre, apellidos, email, role, dept, cargo, provincia, comunidad)
        ("admin",      "bartendercocktail",    "Admin",      "Sistema",           "admin@empresa.com",              "admin", "Direccion General", "Director General",  "",            "madrid"),
        ("fmartinez",  "bartendercocktail", "Fernando",   "Martinez Robles",   "f.martinez@bartendercocktail.es","admin", "Direccion General", "Director General",  "A Coruna",    "galicia"),
    ]
    for u in admins:
        username, pw, nombre, apellidos, email, role, dept, cargo, provincia, com = u
        try:
            c.execute(
                "INSERT OR IGNORE INTO users (username,password_hash,nombre,apellidos,email,role,department_id,comunidad_autonoma,cargo,provincia,activo) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (username, hash_pw(pw), nombre, apellidos, email, role, dept_id(dept), com, cargo, provincia)
            )
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # LEVEL 1 — Directores de Area (manager)
    # --------------------------------------------------------------------------
    mgr_dir = uid("fmartinez") or uid("admin")

    managers = [
        # (username, pw, nombre, apellidos, email, dept, cargo, provincia, comunidad)
        ("chiki",      "bartendercocktail", "Chiki",     "",                   "chiki@caparta.com",                          "Comercial",       "Director de Area", "Formentera",           "baleares"),
        ("triera",     "bartendercocktail", "Antonio",   "Riera",              "tonirierabartendercocktail@gmail.com",        "Comercial",       "Director de Area", "Albacete",             "castilla_la_mancha"),
        ("farqueros",  "bartendercocktail", "Fernando",  "Arqueros Figueiredo","f.arqueros@bartendercocktail.es",             "Comercial",       "Director de Area", "Las Palmas",           "canarias"),
        ("edelgado",   "bartendercocktail", "Eduardo",   "Delgado",            "e.delgado@bartendercocktail.es",              "Comercial",       "Director de Area", "Palencia",             "castilla_leon"),
        ("susana",     "bartendercocktail", "Susana",    "",                   "administracion@bartendercocktail.es",         "Administracion",  "Director de Area", "",                    "madrid"),
    ]
    for u in managers:
        username, pw, nombre, apellidos, email, dept, cargo, provincia, com = u
        try:
            c.execute(
                "INSERT OR IGNORE INTO users (username,password_hash,nombre,apellidos,email,role,department_id,manager_id,comunidad_autonoma,cargo,provincia,activo) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                (username, hash_pw(pw), nombre, apellidos, email, "manager", dept_id(dept), mgr_dir, com, cargo, provincia)
            )
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # LEVEL 2 — Empleados (Comerciales y Administrativos)
    # --------------------------------------------------------------------------
    empleados = [
        # (username, pw, nombre, apellidos, email, dept, cargo, manager_username)
        ("menriquez",  "bartendercocktail", "Manuel",   "Enriquez",  "m.enriquez@bartendercocktail.es",   "Comercial",      "Comercial",                "fmartinez"),
        ("arosa",      "bartendercocktail", "Antonio",  "Rosa",      "a.rosa@bartendercocktail.es",        "Comercial",      "Comercial",                "fmartinez"),
        ("cferreira",  "bartendercocktail", "Carlos",   "Ferreira",  "c.ferreira@bartendercocktail.es",    "Comercial",      "Comercial",                "triera"),
        ("damian",     "bartendercocktail", "Damian",   "",          "damianodk2025@gmail.com",             "Comercial",      "Comercial",                "chiki"),
        ("vbonilla",   "bartendercocktail", "Vicente",  "Bonilla",   "bonillapuertas@gmail.com",            "Comercial",      "Comercial",                "fmartinez"),
        ("pablo",      "bartendercocktail", "Pablo",    "",          "info@bartendercocktail.es",           "Administracion", "Responsable Administracion","susana"),
    ]
    for u in empleados:
        username, pw, nombre, apellidos, email, dept, cargo, mgr_uname = u
        mgr = uid(mgr_uname) or mgr_dir
        try:
            c.execute(
                "INSERT OR IGNORE INTO users (username,password_hash,nombre,apellidos,email,role,department_id,manager_id,cargo,activo) VALUES (?,?,?,?,?,?,?,?,?,1)",
                (username, hash_pw(pw), nombre, apellidos, email, "empleado", dept_id(dept), mgr, cargo)
            )
        except Exception:
            pass


# ── Auth ──────────────────────────────────────────────────────────────────────







def get_user(username: str):



    c = _conn()



    row = c.execute("SELECT * FROM users WHERE username=? AND activo=1", (username,)).fetchone()



    c.close()



    return row_to_dict(row)







def get_user_by_id(uid: int):



    c = _conn()



    row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()



    c.close()



    return row_to_dict(row)







def authenticate(username: str, password: str):



    user = get_user(username)



    if user and user["password_hash"] == hash_pw(password):



        c = _conn()



        c.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user["id"],))



        c.commit()



        c.close()



        return user



    return None







# ── Users ─────────────────────────────────────────────────────────────────────







def get_all_users(activos_only=False):



    c = _conn()



    q = "SELECT u.*, d.nombre as dept_nombre, m.nombre||' '||m.apellidos as manager_nombre FROM users u LEFT JOIN departments d ON u.department_id=d.id LEFT JOIN users m ON u.manager_id=m.id"



    q += " WHERE u.activo=1" if activos_only else ""



    q += " ORDER BY u.apellidos, u.nombre"



    rows = c.execute(q).fetchall()



    c.close()



    return rows_to_list(rows)







def get_team(manager_id: int):



    c = _conn()



    rows = c.execute("SELECT * FROM users WHERE manager_id=? AND activo=1 ORDER BY apellidos,nombre", (manager_id,)).fetchall()



    c.close()



    return rows_to_list(rows)







def create_user(username, password, nombre, apellidos, email, role, dept_id, manager_id, comunidad, horas, dias_vac):



    c = _conn()



    cur = c.execute("""INSERT INTO users (username,password_hash,nombre,apellidos,email,role,department_id,manager_id,comunidad_autonoma,horas_semanales,dias_vacaciones_anuales)



                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",



              (username, hash_pw(password), nombre, apellidos, email, role, dept_id or None, manager_id or None, comunidad, horas, dias_vac))



    uid = cur.lastrowid



    c.commit()



    c.close()



    return uid







def update_user(uid: int, **kwargs):



    if not kwargs:



        return



    if "password" in kwargs:



        kwargs["password_hash"] = hash_pw(kwargs.pop("password"))



    cols = ", ".join(f"{k}=?" for k in kwargs)



    c = _conn()



    c.execute(f"UPDATE users SET {cols} WHERE id=?", (*kwargs.values(), uid))



    c.commit()



    c.close()







def get_departments():



    c = _conn()



    rows = c.execute("SELECT * FROM departments WHERE activo=1 ORDER BY nombre").fetchall()



    c.close()



    return rows_to_list(rows)







def create_department(nombre: str):



    c = _conn()



    c.execute("INSERT INTO departments (nombre) VALUES (?)", (nombre,))



    c.commit()



    c.close()







# ── Time entries ──────────────────────────────────────────────────────────────







def add_entry(user_id, fecha, tipo, hora, ip="", observaciones="", is_manual=False, created_by=None):



    conn = _conn()



    cur = conn.execute("""INSERT INTO time_entries (user_id,fecha,tipo,hora,ip,observaciones,is_manual,created_by)



                 VALUES (?,?,?,?,?,?,?,?)""",



              (user_id, str(fecha), tipo, hora, ip, observaciones, int(is_manual), created_by))



    eid = cur.lastrowid



    conn.commit()



    conn.close()



    return eid







def get_day_entries(user_id, fecha):



    c = _conn()



    rows = c.execute(



        "SELECT * FROM time_entries WHERE user_id=? AND fecha=? AND deleted=0 ORDER BY hora",



        (user_id, str(fecha))



    ).fetchall()



    c.close()



    return rows_to_list(rows)







def get_entries_range(user_id, f_ini, f_fin):



    c = _conn()



    rows = c.execute(



        "SELECT te.*, u.nombre||' '||u.apellidos as emp_nombre FROM time_entries te JOIN users u ON te.user_id=u.id WHERE te.user_id=? AND te.fecha>=? AND te.fecha<=? AND te.deleted=0 ORDER BY te.fecha, te.hora",



        (user_id, str(f_ini), str(f_fin))



    ).fetchall()



    c.close()



    return rows_to_list(rows)







def get_all_entries_range(f_ini, f_fin, user_ids=None):



    c = _conn()



    q = "SELECT te.*, u.nombre||' '||u.apellidos as emp_nombre FROM time_entries te JOIN users u ON te.user_id=u.id WHERE te.fecha>=? AND te.fecha<=? AND te.deleted=0"



    params = [str(f_ini), str(f_fin)]



    if user_ids:



        q += f" AND te.user_id IN ({','.join('?'*len(user_ids))})"



        params.extend(user_ids)



    q += " ORDER BY te.fecha, u.apellidos, te.hora"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def soft_delete_entry(entry_id: int, deleted_by: int):



    c = _conn()



    c.execute("UPDATE time_entries SET deleted=1 WHERE id=?", (entry_id,))



    c.commit()



    c.close()







# ── Day status ────────────────────────────────────────────────────────────────







def _get_holiday_set(comunidad, año):



    c = _conn()



    rows = c.execute(



        "SELECT fecha FROM holidays WHERE (comunidad_autonoma='todas' OR comunidad_autonoma=?) AND año=?",



        (comunidad, año)



    ).fetchall()



    c.close()



    return {r[0] for r in rows}







def get_holidays_for_day(fecha, comunidad="madrid"):
    """Returns list of (descripcion, tipo) for a given date."""
    conn = _conn()
    rows = conn.execute(
        """SELECT descripcion, tipo FROM holidays
           WHERE fecha=? AND (comunidad_autonoma='todas' OR comunidad_autonoma=?)
           ORDER BY tipo""",
        (str(fecha), comunidad)
    ).fetchall()
    conn.close()
    return [(r["descripcion"], r["tipo"]) for r in rows]







PROVINCIA_TZ = {
    "Las Palmas": "Atlantic/Canary",
    "Santa Cruz de Tenerife": "Atlantic/Canary",
}


def get_user_tz(user: dict) -> str:
    """Returns IANA timezone string based on user's provincia or comunidad."""
    prov = user.get("provincia", "") or ""
    if prov in PROVINCIA_TZ:
        return PROVINCIA_TZ[prov]
    if user.get("comunidad_autonoma") == "canarias":
        return "Atlantic/Canary"
    return "Europe/Madrid"







def _is_on_vacation(user_id, fecha):



    c = _conn()



    row = c.execute(



        "SELECT 1 FROM vacation_requests WHERE user_id=? AND fecha_inicio<=? AND fecha_fin>=? AND estado='aprobada'",



        (user_id, str(fecha), str(fecha))



    ).fetchone()



    c.close()



    return row is not None







def get_day_status(user_id, fecha, comunidad="madrid"):



    d = date.fromisoformat(str(fecha)) if not isinstance(fecha, date) else fecha



    if d.weekday() >= 5:



        return "fin_semana"



    holidays = _get_holiday_set(comunidad, d.year)



    if str(d) in holidays:



        return "festivo"



    if _is_on_vacation(user_id, d):



        return "vacaciones"



    if d > date.today():



        return "futuro"



    entries = get_day_entries(user_id, d)



    if not entries:



        return "rojo"



    tipos = [e["tipo"] for e in entries]



    has_entrada = "entrada" in tipos



    has_salida = "salida" in tipos



    pausas = tipos.count("pausa")



    fin_pausas = tipos.count("fin_pausa")



    if has_entrada and has_salida and pausas == fin_pausas:



        return "verde"



    return "amarillo"







def get_fichaje_state(user_id, fecha):



    """Returns last entry tipo for today to drive button states."""



    entries = get_day_entries(user_id, fecha)



    if not entries:



        return None



    return entries[-1]["tipo"]







# ── Worked hours ──────────────────────────────────────────────────────────────







def calc_worked_hours(entries):



    """Calculate net worked hours from a list of entries for one day.



    Handles duplicate entry types by always pairing the earliest unmatched one."""



    sorted_entries = sorted(entries, key=lambda x: x["hora"])



    entrada = None



    pausa_start = None



    total = 0.0



    pausa_total = 0.0



    for e in sorted_entries:



        t = e["tipo"]



        h = e["hora"][:5]



        try:



            dt = datetime.strptime(h, "%H:%M")



            if t == "entrada":



                # Only set if we don't already have an open entrada



                if entrada is None:



                    entrada = dt



            elif t == "salida":



                if entrada is not None:



                    total += (dt - entrada).total_seconds() / 3600



                    entrada = None



            elif t == "pausa":



                if pausa_start is None:



                    pausa_start = dt



            elif t == "fin_pausa":



                if pausa_start is not None:



                    pausa_total += (dt - pausa_start).total_seconds() / 3600



                    pausa_start = None



        except Exception:



            pass



    net = max(0.0, total - pausa_total)



    return round(net, 2)







# ── Incidents ─────────────────────────────────────────────────────────────────







def create_incident(user_id, fecha, tipo, descripcion=""):



    c = _conn()



    # avoid duplicates



    existing = c.execute(



        "SELECT id FROM time_incidents WHERE user_id=? AND fecha=? AND tipo=? AND estado='pendiente'",



        (user_id, str(fecha), tipo)



    ).fetchone()



    if not existing:



        c.execute("INSERT INTO time_incidents (user_id,fecha,tipo,descripcion) VALUES (?,?,?,?)",



                  (user_id, str(fecha), tipo, descripcion))



        c.commit()



    c.close()







def get_user_incidents(user_id, estado=None):



    c = _conn()



    q = "SELECT * FROM time_incidents WHERE user_id=?"



    params = [user_id]



    if estado:



        q += " AND estado=?"; params.append(estado)



    q += " ORDER BY fecha DESC"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def get_team_incidents(manager_id, estado=None):



    c = _conn()



    team_ids = [u["id"] for u in get_team(manager_id)]



    if not team_ids:



        return []



    ph = ",".join("?" * len(team_ids))



    q = f"SELECT ti.*, u.nombre||' '||u.apellidos as emp_nombre FROM time_incidents ti JOIN users u ON ti.user_id=u.id WHERE ti.user_id IN ({ph})"



    params = list(team_ids)



    if estado:



        q += " AND ti.estado=?"; params.append(estado)



    q += " ORDER BY ti.fecha DESC"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def get_all_incidents(estado=None):



    c = _conn()



    q = "SELECT ti.*, u.nombre||' '||u.apellidos as emp_nombre FROM time_incidents ti JOIN users u ON ti.user_id=u.id WHERE 1=1"



    params = []



    if estado:



        q += " AND ti.estado=?"; params.append(estado)



    q += " ORDER BY ti.fecha DESC"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def resolve_incident(inc_id: int, resolucion: str, resolved_by: int):



    c = _conn()



    c.execute("UPDATE time_incidents SET estado='resuelto',resolucion=?,resolved_at=datetime('now'),resolved_by=? WHERE id=?",



              (resolucion, resolved_by, inc_id))



    c.commit()



    c.close()







# ── Vacation requests ─────────────────────────────────────────────────────────







def dias_laborables(f_ini: date, f_fin: date, comunidad="madrid"):



    hols = _get_holiday_set(comunidad, f_ini.year) | _get_holiday_set(comunidad, f_fin.year)



    days = 0



    cur = f_ini



    while cur <= f_fin:



        if cur.weekday() < 5 and str(cur) not in hols:



            days += 1



        cur += timedelta(days=1)



    return days







def send_vacation_email(to_email, empleado_nombre, tipo_aus, estado,
                        fecha_ini, fecha_fin, dias_lab, comentario_mgr,
                        dias_disfrutados, dias_anuales):
    """Send email notification for vacation approval/denial. Returns True if sent."""
    if not to_email:
        return False
    try:
        import smtplib, streamlit as st
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        cfg = getattr(st, "secrets", {})
        host = cfg.get("SMTP_HOST", "")
        port = int(cfg.get("SMTP_PORT", 587))
        user = cfg.get("SMTP_USER", "")
        pwd  = cfg.get("SMTP_PASS", "")
        frm  = cfg.get("SMTP_FROM", user)
        if not host or not user or not pwd:
            return False
        icon = "✅" if estado == "aprobada" else "❌"
        dias_pendientes = max(0, dias_anuales - dias_disfrutados)
        subject = f"{icon} Solicitud de {tipo_aus} — {estado.upper()}"
        body = f"""Hola {empleado_nombre},

Tu solicitud de {tipo_aus} ha sido {estado.upper()} {icon}

📅 Período: {fecha_ini} — {fecha_fin}
📊 Días laborables: {dias_lab}
💬 Comentario del responsable: {comentario_mgr or 'Sin comentario'}

📈 Resumen de vacaciones ({date.today().year}):
   • Días disfrutados: {dias_disfrutados} de {dias_anuales}
   • Días pendientes: {dias_pendientes}

— Sistema Ficha · Control Horario SaaS (RDL 8/2019)
"""
        msg = MIMEMultipart()
        msg["From"] = frm
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port) as srv:
            srv.starttls()
            srv.login(user, pwd)
            srv.sendmail(frm, to_email, msg.as_string())
        return True
    except Exception:
        return False








def create_vac_request(user_id, f_ini, f_fin, tipo, comentario, comunidad="madrid"):



    dl = dias_laborables(date.fromisoformat(str(f_ini)), date.fromisoformat(str(f_fin)), comunidad)



    c = _conn()



    cur = c.execute("""INSERT INTO vacation_requests (user_id,fecha_inicio,fecha_fin,tipo,dias_laborables,comentario_empleado)



                 VALUES (?,?,?,?,?,?)""",



              (user_id, str(f_ini), str(f_fin), tipo, dl, comentario))



    rid = cur.lastrowid



    c.commit()



    c.close()



    return rid







def get_user_requests(user_id):



    c = _conn()



    rows = c.execute("""SELECT vr.*, u.nombre||' '||u.apellidos as manager_nombre



                        FROM vacation_requests vr LEFT JOIN users u ON vr.manager_id=u.id



                        WHERE vr.user_id=? ORDER BY vr.fecha_solicitud DESC""", (user_id,)).fetchall()



    c.close()



    return rows_to_list(rows)







def get_pending_requests(manager_id=None):



    c = _conn()



    if manager_id:



        team_ids = [u["id"] for u in get_team(manager_id)]



        if not team_ids:



            c.close(); return []



        ph = ",".join("?" * len(team_ids))



        rows = c.execute(f"""SELECT vr.*, u.nombre||' '||u.apellidos as emp_nombre



                              FROM vacation_requests vr JOIN users u ON vr.user_id=u.id



                              WHERE vr.user_id IN ({ph}) AND vr.estado='pendiente'



                              ORDER BY vr.fecha_solicitud""", team_ids).fetchall()



    else:



        rows = c.execute("""SELECT vr.*, u.nombre||' '||u.apellidos as emp_nombre



                             FROM vacation_requests vr JOIN users u ON vr.user_id=u.id



                             WHERE vr.estado='pendiente' ORDER BY vr.fecha_solicitud""").fetchall()



    c.close()



    return rows_to_list(rows)







def get_all_requests(estado=None):



    c = _conn()



    q = """SELECT vr.*, u.nombre||' '||u.apellidos as emp_nombre,



                  m.nombre||' '||m.apellidos as manager_nombre



           FROM vacation_requests vr



           JOIN users u ON vr.user_id=u.id



           LEFT JOIN users m ON vr.manager_id=m.id



           WHERE 1=1"""



    params = []



    if estado:



        q += " AND vr.estado=?"; params.append(estado)



    q += " ORDER BY vr.fecha_solicitud DESC"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def resolve_request(req_id, action, manager_id, comentario=""):



    c = _conn()



    c.execute("""UPDATE vacation_requests SET estado=?,manager_id=?,comentario_manager=?,fecha_resolucion=datetime('now')



                 WHERE id=?""", (action, manager_id, comentario, req_id))



    c.commit()



    c.close()







def get_vacation_balance(user_id, año):



    user = get_user_by_id(user_id)



    total = user["dias_vacaciones_anuales"] if user else 22



    c = _conn()



    rows = c.execute("""SELECT dias_laborables FROM vacation_requests



                         WHERE user_id=? AND strftime('%Y',fecha_inicio)=? AND estado='aprobada'""",



                     (user_id, str(año))).fetchall()



    c.close()



    used = sum(r[0] for r in rows)



    pending_rows = _conn().execute("""SELECT dias_laborables FROM vacation_requests



                         WHERE user_id=? AND strftime('%Y',fecha_inicio)=? AND estado='pendiente'""",



                     (user_id, str(año))).fetchall()



    pending = sum(r[0] for r in pending_rows)



    return {"total": total, "used": used, "pending": pending, "remaining": total - used - pending}







# ── Holidays ──────────────────────────────────────────────────────────────────







def get_holidays_df(comunidad=None, año=None):



    c = _conn()



    q = "SELECT * FROM holidays WHERE 1=1"



    params = []



    if comunidad:



        q += " AND (comunidad_autonoma='todas' OR comunidad_autonoma=?)"; params.append(comunidad)



    if año:



        q += " AND año=?"; params.append(año)



    q += " ORDER BY fecha"



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







def add_holiday(fecha, descripcion, tipo, comunidad, año):



    c = _conn()



    try:



        c.execute("INSERT INTO holidays (fecha,descripcion,tipo,comunidad_autonoma,año) VALUES (?,?,?,?,?)",



                  (str(fecha), descripcion, tipo, comunidad, año))



        c.commit()



    except Exception:



        pass



    c.close()







def delete_holiday(hid: int):



    c = _conn()



    c.execute("DELETE FROM holidays WHERE id=?", (hid,))



    c.commit()



    c.close()







# ── Notifications ─────────────────────────────────────────────────────────────







def add_notification(user_id, tipo, titulo, mensaje):



    c = _conn()



    c.execute("INSERT INTO notifications (user_id,tipo,titulo,mensaje) VALUES (?,?,?,?)",



              (user_id, tipo, titulo, mensaje))



    c.commit()



    c.close()







def get_notifications(user_id, unread_only=False):



    c = _conn()



    q = "SELECT * FROM notifications WHERE user_id=?"



    if unread_only:



        q += " AND leido=0"



    q += " ORDER BY created_at DESC LIMIT 50"



    rows = c.execute(q, (user_id,)).fetchall()



    c.close()



    return rows_to_list(rows)







def mark_read(notif_id: int):



    c = _conn()



    c.execute("UPDATE notifications SET leido=1 WHERE id=?", (notif_id,))



    c.commit()



    c.close()







def mark_all_read(user_id: int):



    c = _conn()



    c.execute("UPDATE notifications SET leido=1 WHERE user_id=?", (user_id,))



    c.commit()



    c.close()







def get_unread_count(user_id: int) -> int:



    c = _conn()



    n = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND leido=0", (user_id,)).fetchone()[0]



    c.close()



    return n







# ── Audit ─────────────────────────────────────────────────────────────────────







def audit(user_id, accion, tabla="", registro_id=None, datos=None, ip=""):



    c = _conn()



    c.execute("INSERT INTO audit_logs (user_id,accion,tabla,registro_id,datos,ip) VALUES (?,?,?,?,?,?)",



              (user_id, accion, tabla, registro_id, json.dumps(datos or {}), ip))



    c.commit()



    c.close()







def get_audit_logs(user_id=None, limit=200):



    c = _conn()



    q = "SELECT al.*, u.nombre||' '||u.apellidos as user_nombre FROM audit_logs al LEFT JOIN users u ON al.user_id=u.id"



    params = []



    if user_id:



        q += " WHERE al.user_id=?"; params.append(user_id)



    q += " ORDER BY al.created_at DESC LIMIT ?"



    params.append(limit)



    rows = c.execute(q, params).fetchall()



    c.close()



    return rows_to_list(rows)







# ── Monthly validation ────────────────────────────────────────────────────────







def get_monthly_validation(user_id, año, mes):



    c = _conn()



    row = c.execute("SELECT * FROM monthly_validations WHERE user_id=? AND año=? AND mes=?",



                    (user_id, año, mes)).fetchone()



    c.close()



    return row_to_dict(row)







def set_monthly_validation(user_id, año, mes, ip=""):



    c = _conn()



    c.execute("""INSERT INTO monthly_validations (user_id,año,mes,validado,fecha_validacion,ip)



                 VALUES (?,?,?,1,datetime('now'),?)



                 ON CONFLICT(user_id,año,mes) DO UPDATE SET validado=1,fecha_validacion=datetime('now'),ip=?""",



              (user_id, año, mes, ip, ip))



    c.commit()



    c.close()







# ── Global stats ──────────────────────────────────────────────────────────────







def get_global_stats():



    c = _conn()



    total_users = c.execute("SELECT COUNT(*) FROM users WHERE activo=1").fetchone()[0]



    total_entries_today = c.execute("SELECT COUNT(*) FROM time_entries WHERE fecha=date('now') AND deleted=0").fetchone()[0]



    pending_requests = c.execute("SELECT COUNT(*) FROM vacation_requests WHERE estado='pendiente'").fetchone()[0]



    open_incidents = c.execute("SELECT COUNT(*) FROM time_incidents WHERE estado='pendiente'").fetchone()[0]



    c.close()



    return {



        "total_users": total_users,



        "total_entries_today": total_entries_today,



        "pending_requests": pending_requests,



        "open_incidents": open_incidents,



    }



