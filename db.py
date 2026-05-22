"""Ficha · Control Horario — Database layer (RDL 8/2019 compliant)"""



import sqlite3



import hashlib
import hmac as _hmac



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

# ── Persistent per-thread PG connection (avoids reconnect on every query) ─────
import threading as _threading
_pg_local = _threading.local()

def _make_raw_pg():
    import psycopg2
    from urllib.parse import urlparse, unquote
    _p = urlparse(_PG_URL)
    return psycopg2.connect(
        host=_p.hostname,
        port=_p.port or 5432,
        dbname=(_p.path or "/postgres").lstrip("/"),
        user=unquote(_p.username or "postgres"),
        password=unquote(_p.password or ""),
        sslmode="require",
        connect_timeout=15,
    )

def _get_raw_pg():
    cn = getattr(_pg_local, "cn", None)
    if cn is None or cn.closed:
        _pg_local.cn = _make_raw_pg()
    return _pg_local.cn

def _reset_raw_pg():
    try:
        cn = getattr(_pg_local, "cn", None)
        if cn: cn.close()
    except Exception: pass
    _pg_local.cn = _make_raw_pg()
    return _pg_local.cn
# ─────────────────────────────────────────────────────────────────────────────


class _PGConn:
    """
    Wraps psycopg2 to behave like sqlite3.
    Handles: ?->%s, INSERT OR IGNORE, datetime(), AUTOINCREMENT, lastrowid via RETURNING.
    """
    def __init__(self):
        import psycopg2.extras
        self._cn    = _get_raw_pg()
        self._cur   = self._cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self.lastrowid = None
        self._dirty = False   # tracks if any write happened

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
        sql = _re.sub(r"strftime\('%Y',\s*(\w+)\)",
                      r"EXTRACT(YEAR FROM \1::date)::TEXT", sql)
        sql = _re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                      "SERIAL PRIMARY KEY", sql, flags=_re.I)
        sql = _re.sub(r"\bAUTOINCREMENT\b", "", sql, flags=_re.I)
        sql = _re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=_re.I)
        if is_ignore:
            sql = sql.rstrip("; ") + " ON CONFLICT DO NOTHING"
        return sql, is_ignore

    def execute(self, sql, params=()):
        sql, is_ignore = self._adapt(sql)
        is_ins  = sql.strip().upper().startswith("INSERT")
        is_write = is_ins or bool(_re.match(r"\s*(UPDATE|DELETE)", sql, _re.I))
        has_ret = "RETURNING" in sql.upper()
        if is_ins and not has_ret and not is_ignore:
            sql = sql.rstrip("; ") + " RETURNING id"
        try:
            self._cur.execute(sql, params if params else None)
        except Exception as _e:
            import psycopg2
            if isinstance(_e, (psycopg2.OperationalError, psycopg2.InterfaceError)):
                import psycopg2.extras
                self._cn  = _reset_raw_pg()
                self._cur = self._cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                self._cur.execute(sql, params if params else None)
            else:
                raise
        if is_write:
            self._dirty = True
        if is_ins and not is_ignore:
            row = self._cur.fetchone()
            self.lastrowid = row["id"] if row else None
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        class _Row(dict):
            def __getitem__(self, key):
                if isinstance(key, int):
                    return list(self.values())[key]
                return super().__getitem__(key)
        return _Row(row)

    def fetchall(self):
        class _Row(dict):
            def __getitem__(self, key):
                if isinstance(key, int):
                    return list(self.values())[key]
                return super().__getitem__(key)
        return [_Row(r) for r in (self._cur.fetchall() or [])]

    def commit(self):
        self._cn.commit()
        self._dirty = False

    def close(self):
        if self._dirty:
            try:
                self._cn.commit()
                self._dirty = False
            except Exception:
                try: self._cn.rollback()
                except Exception: pass

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
    """Hash password with bcrypt (cost=12). Falls back to SHA-256 only for seeding."""
    try:
        import bcrypt
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()
    except Exception:
        # bcrypt not available (unit tests / local dev without package)
        return hashlib.sha256(pw.encode()).hexdigest()


def _verify_pw(plain: str, stored_hash: str) -> bool:
    """
    Verify password supporting both bcrypt ($2b$) and legacy SHA-256.
    Returns (matches, needs_upgrade).
    """
    if stored_hash.startswith("$2"):
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode(), stored_hash.encode()), False
        except Exception:
            return False, False
    # Legacy SHA-256 — matches means we should upgrade on the fly
    matches = hashlib.sha256(plain.encode()).hexdigest() == stored_hash
    return matches, matches  # (matches, needs_upgrade)


# ── LEG-01/02: HMAC signature key for time entries ───────────────────────────
def _sig_key() -> bytes:
    """
    Key used to sign time_entries rows (LEG-01 tamper detection).
    Reads ENTRY_SIG_KEY secret; falls back to a hash of DATABASE_URL.
    """
    try:
        import streamlit as _st
        k = _st.secrets.get("ENTRY_SIG_KEY", "")
        if k:
            return k.encode()
    except Exception:
        pass
    base = _os.environ.get("ENTRY_SIG_KEY") or _os.environ.get("DATABASE_URL", "odk-ficha-dev")
    return hashlib.sha256(base.encode()).digest()


def _sign_entry(user_id, fecha, tipo, hora) -> str:
    """Compute HMAC-SHA256 signature for a time entry (LEG-01)."""
    msg = f"{user_id}|{fecha}|{tipo}|{hora}".encode()
    return _hmac.new(_sig_key(), msg, hashlib.sha256).hexdigest()


def verify_entry_signature(entry) -> bool:
    """Returns True if the entry's signature matches its data (tamper check)."""
    sig = entry.get("entry_sig", "")
    if not sig:
        return True  # pre-LEG-01 entries have no sig — treat as OK
    expected = _sign_entry(entry["user_id"], entry["fecha"], entry["tipo"], entry["hora"])
    return _hmac.compare_digest(sig, expected)
# ─────────────────────────────────────────────────────────────────────────────







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



            created_at TEXT DEFAULT (datetime('now')),

            entry_sig TEXT DEFAULT '',

            retain_until TEXT DEFAULT ''

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

        """CREATE TABLE IF NOT EXISTS approval_tokens (

            token TEXT PRIMARY KEY,

            request_id INTEGER NOT NULL REFERENCES vacation_requests(id),

            action TEXT NOT NULL,

            manager_id INTEGER REFERENCES users(id),

            expires_at TEXT NOT NULL,

            used INTEGER DEFAULT 0,

            created_at TEXT DEFAULT (datetime('now'))

        )""",



    ]



    for s in stmts:



        c.execute(s)



    c.commit()



    # Migration: add columns if not present (users)
    for col, defval in [("provincia","''"), ("localidad","''"), ("cargo","''")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {defval}")
        except Exception:
            pass

    # Migration: LEG-01/02 — add entry_sig + retain_until to time_entries
    for col, defval in [("entry_sig", "''"), ("retain_until", "''")]:
        try:
            c.execute(f"ALTER TABLE time_entries ADD COLUMN {col} TEXT DEFAULT {defval}")
        except Exception:
            pass
    c.commit()

    _seed_holidays(c)



    _seed_users(c)



    c.commit()



    c.close()











def _seed_holidays(c):

    # Skip if already seeded for current year (avoids 80+ PG round-trips on every cold start)
    try:
        row = c.execute("SELECT COUNT(*) as n FROM holidays WHERE año >= ?", (date.today().year,)).fetchone()
        if row and (row["n"] if isinstance(row, dict) else row[0]) > 10:
            return
    except Exception:
        pass

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
    # Skip if users already exist (avoids re-seeding on every cold start)
    try:
        row = c.execute("SELECT COUNT(*) as n FROM users").fetchone()
        if row and (row["n"] if isinstance(row, dict) else row[0]) > 0:
            return
    except Exception:
        pass
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



    if user:
        matches, needs_upgrade = _verify_pw(password, user["password_hash"])
        if matches:
            c = _conn()
            if needs_upgrade:
                # SEC-02: auto-migrate SHA-256 → bcrypt on first login
                c.execute("UPDATE users SET password_hash=?, last_login=datetime('now') WHERE id=?",
                          (hash_pw(password), user["id"]))
            else:
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







def create_user(username, password, nombre, apellidos, email, role, dept_id, manager_id, comunidad, horas, dias_vac, cargo="", provincia="", localidad="", telefono=""):



    c = _conn()



    cur = c.execute("""INSERT INTO users (username,password_hash,nombre,apellidos,email,role,department_id,manager_id,comunidad_autonoma,horas_semanales,dias_vacaciones_anuales,cargo,provincia,localidad,telefono)



                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",



              (username, hash_pw(password), nombre, apellidos, email, role, dept_id or None, manager_id or None, comunidad, horas, dias_vac, cargo, provincia, localidad, telefono))



    uid = cur.lastrowid



    c.commit()



    c.close()



    return uid







def update_user(uid: int, **kwargs):



    if not kwargs:



        return



    if "password" in kwargs:



        kwargs["password_hash"] = hash_pw(kwargs.pop("password"))



    ALLOWED_COLS = {"nombre","apellidos","email","telefono","role","cargo",
                    "department_id","manager_id","comunidad_autonoma",
                    "horas_semanales","dias_vacaciones_anuales","activo",
                    "password_hash","provincia","localidad","last_login"}
    kwargs = {k: v for k, v in kwargs.items() if k in ALLOWED_COLS}
    if not kwargs:
        return

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



    # LEG-01: sign entry; LEG-02: set 4-year retention
    _sig = _sign_entry(user_id, str(fecha), tipo, hora)
    _retain = str(date.fromisoformat(str(fecha)).replace(year=date.fromisoformat(str(fecha)).year + 4))

    cur = conn.execute("""INSERT INTO time_entries (user_id,fecha,tipo,hora,ip,observaciones,is_manual,created_by,entry_sig,retain_until)



                 VALUES (?,?,?,?,?,?,?,?,?,?)""",



              (user_id, str(fecha), tipo, hora, ip, observaciones, int(is_manual), created_by, _sig, _retain))



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
    # LEG-02: block deletion if within 4-year legal retention period
    row = c.execute("SELECT retain_until FROM time_entries WHERE id=?", (entry_id,)).fetchone()
    if row:
        ru = (row.get("retain_until") or row[0] or "") if row else ""
        if ru:
            try:
                if date.fromisoformat(ru) > date.today():
                    c.close()
                    raise ValueError(
                        f"LEG-02: Este registro debe conservarse hasta {ru} "
                        f"(RDL 8/2019 — retención mínima 4 años). No se puede eliminar."
                    )
            except ValueError as e:
                if "LEG-02" in str(e):
                    raise
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



    return {r["fecha"] for r in rows}







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







def _odk_email_wrap(inner_html: str, title: str) -> str:
    """Wraps inner HTML in the ODK branded email shell (dark luxury, email-safe inline CSS)."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#f0ead8;font-family:Georgia,'Times New Roman',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0ead8;padding:28px 12px;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;background:#0d0b08;border-radius:16px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.35);">

  <!-- Header -->
  <tr><td style="background:linear-gradient(160deg,#100c04,#1a1005);padding:32px 36px 24px;text-align:center;border-bottom:1px solid rgba(202,138,4,.20);">
    <div style="font-family:Georgia,serif;font-size:30px;font-weight:bold;font-style:italic;color:#CA8A04;letter-spacing:8px;">ODK</div>
    <div style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;letter-spacing:4px;text-transform:uppercase;margin-top:5px;">Ficha &middot; Control Horario</div>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 36px;">
    {inner_html}
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:14px 36px 22px;border-top:1px solid rgba(202,138,4,.12);text-align:center;">
    <span style="color:rgba(220,195,140,.22);font-family:Arial,sans-serif;font-size:9px;letter-spacing:2px;text-transform:uppercase;">ODK &middot; Control Horario RDL 8/2019 &middot; RGPD</span>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""


def send_vacation_email(to_email, empleado_nombre, tipo_aus, estado,
                        fecha_ini, fecha_fin, dias_lab, comentario_mgr,
                        dias_disfrutados, dias_anuales):
    """Send HTML email notification to employee after approval/denial."""
    if not to_email:
        return False
    try:
        import smtplib, streamlit as st
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        cfg = getattr(st, "secrets", {})
        host = cfg.get("SMTP_HOST", "")
        port = int(cfg.get("SMTP_PORT", 587))
        smtp_user = cfg.get("SMTP_USER", "")
        pwd  = cfg.get("SMTP_PASS", "")
        frm  = cfg.get("SMTP_FROM", smtp_user)
        if not host or not smtp_user or not pwd:
            return False

        aprobada = estado == "aprobada"
        icon_color = "#16a34a" if aprobada else "#dc2626"
        icon_bg    = "rgba(22,163,74,.12)" if aprobada else "rgba(220,38,38,.12)"
        icon_txt   = "✓ APROBADA" if aprobada else "✗ DENEGADA"
        dias_pendientes = max(0, dias_anuales - dias_disfrutados)
        tipo_label = tipo_aus.replace("_", " ").title()

        inner = f"""
<div style="text-align:center;margin-bottom:28px;">
  <div style="display:inline-block;background:{icon_bg};border:1px solid {icon_color};border-radius:50px;padding:10px 28px;color:{icon_color};font-family:Arial,sans-serif;font-size:14px;font-weight:bold;letter-spacing:3px;">{icon_txt}</div>
</div>
<p style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:15px;margin:0 0 6px;">Hola <strong>{empleado_nombre}</strong>,</p>
<p style="color:rgba(220,195,140,.65);font-family:Arial,sans-serif;font-size:13px;line-height:1.7;margin:0 0 24px;">
  Tu solicitud de <strong style="color:#f0e8d5;">{tipo_label}</strong> ha sido {"<strong style='color:#16a34a;'>aprobada</strong>" if aprobada else "<strong style='color:#dc2626;'>denegada</strong>"}.
</p>

<table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,.04);border:1px solid rgba(202,138,4,.18);border-radius:12px;margin-bottom:24px;">
  <tr><td style="padding:18px 20px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding-bottom:12px;border-bottom:1px solid rgba(202,138,4,.10);">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Período</span><br>
        <span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:14px;">{fecha_ini} &rarr; {fecha_fin} &nbsp;·&nbsp; <strong style="color:#CA8A04;">{dias_lab} días laborables</strong></span>
      </td></tr>
      {"" if not comentario_mgr else f'<tr><td style="padding:12px 0;border-bottom:1px solid rgba(202,138,4,.10);"><span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Comentario del responsable</span><br><span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:13px;font-style:italic;">{comentario_mgr}</span></td></tr>'}
      <tr><td style="padding-top:12px;">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Saldo {date.today().year}</span><br>
        <span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:13px;">Disfrutados: <strong style="color:#CA8A04;">{dias_disfrutados}</strong> de {dias_anuales} &nbsp;·&nbsp; Pendientes: <strong style="color:#CA8A04;">{dias_pendientes}</strong></span>
      </td></tr>
    </table>
  </td></tr>
</table>
"""
        subject = f"{'✓' if aprobada else '✗'} Tu solicitud de {tipo_label} ha sido {estado}"
        html = _odk_email_wrap(inner, subject)

        msg = MIMEMultipart("alternative")
        msg["From"] = frm
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(host, port) as srv:
            srv.starttls()
            srv.login(smtp_user, pwd)
            srv.sendmail(frm, to_email, msg.as_string())
        return True
    except Exception:
        return False


def _create_approval_tokens(request_id: int, manager_id: int) -> tuple:
    """Create one-click approve/deny tokens for a vacation request. Returns (approve_token, deny_token)."""
    import secrets as _secrets
    tok_apr = _secrets.token_urlsafe(32)
    tok_den = _secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
    c = _conn()
    try:
        for tok, action in [(tok_apr, "approve"), (tok_den, "deny")]:
            c.execute(
                "INSERT INTO approval_tokens (token,request_id,action,manager_id,expires_at) VALUES (?,?,?,?,?)",
                (tok, request_id, action, manager_id, expires)
            )
        c.commit()
    except Exception:
        try: c.execute("ROLLBACK")
        except Exception: pass
    finally:
        c.close()
    return tok_apr, tok_den


def validate_and_use_token(token: str) -> dict:
    """
    Validate an email one-click token, execute the action if valid, and mark it used.
    Returns dict with keys: status ('ok'|'expired'|'used'|'invalid'), action, request_id, emp_nombre, tipo, fecha_ini, fecha_fin
    """
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM approval_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return {"status": "invalid"}
        row = dict(row)
        if row["used"]:
            return {"status": "used", "action": row["action"]}
        if datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
            return {"status": "expired", "action": row["action"]}

        req = c.execute(
            """SELECT vr.*, u.nombre, u.apellidos, u.email, u.dias_vacaciones_anuales
               FROM vacation_requests vr JOIN users u ON vr.user_id=u.id
               WHERE vr.id=?""", (row["request_id"],)
        ).fetchone()
        if not req:
            return {"status": "invalid"}
        req = dict(req)
        if req["estado"] != "pendiente":
            return {"status": "used", "action": row["action"], "estado": req["estado"]}

        nuevo_estado = "aprobada" if row["action"] == "approve" else "denegada"
        resolve_request(row["request_id"], nuevo_estado, row["manager_id"], "Aprobado desde email")

        # Invalidate BOTH tokens for this request
        c.execute("UPDATE approval_tokens SET used=1 WHERE request_id=?", (row["request_id"],))
        c.commit()

        # Send result email to employee
        try:
            bal = get_vacation_balance(req["user_id"], date.today().year)
            used_days = (bal or {}).get("used", 0)
            send_vacation_email(
                req["email"],
                f"{req['nombre']} {req['apellidos']}",
                req.get("tipo","vacaciones"), nuevo_estado,
                req["fecha_inicio"], req["fecha_fin"],
                req.get("dias_laborables",0),
                "Aprobado desde email", used_days,
                req.get("dias_vacaciones_anuales", 22)
            )
        except Exception:
            pass

        return {
            "status": "ok",
            "action": row["action"],
            "nuevo_estado": nuevo_estado,
            "emp_nombre": f"{req['nombre']} {req['apellidos']}",
            "tipo": req.get("tipo","vacaciones"),
            "fecha_ini": req["fecha_inicio"],
            "fecha_fin": req["fecha_fin"],
        }
    except Exception as e:
        return {"status": "invalid", "error": str(e)}
    finally:
        c.close()


def send_manager_request_email(manager_email: str, manager_nombre: str,
                                empleado_nombre: str, tipo_aus: str,
                                fecha_ini: str, fecha_fin: str, dias_lab: int,
                                comentario_emp: str,
                                tok_approve: str, tok_deny: str,
                                app_url: str = "") -> bool:
    """Send ODK-branded HTML email to manager with one-click approve/deny links."""
    if not manager_email:
        return False
    try:
        import smtplib, streamlit as st
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        cfg = getattr(st, "secrets", {})
        host      = cfg.get("SMTP_HOST", "")
        port      = int(cfg.get("SMTP_PORT", 587))
        smtp_user = cfg.get("SMTP_USER", "")
        pwd       = cfg.get("SMTP_PASS", "")
        frm       = cfg.get("SMTP_FROM", smtp_user)
        if not app_url:
            app_url = cfg.get("APP_URL", "https://ficha.streamlit.app")
        if not host or not smtp_user or not pwd:
            return False

        tipo_label = tipo_aus.replace("_", " ").title()
        approve_url = f"{app_url}?tok={tok_approve}"
        deny_url    = f"{app_url}?tok={tok_deny}"

        inner = f"""
<h2 style="color:#f0e8d5;font-family:Georgia,serif;font-size:20px;margin:0 0 6px;">Nueva solicitud pendiente</h2>
<p style="color:rgba(220,195,140,.60);font-family:Arial,sans-serif;font-size:13px;line-height:1.7;margin:0 0 24px;">
  <strong style="color:#f0e8d5;">{empleado_nombre}</strong> ha solicitado {tipo_label.lower()} y requiere tu aprobación.
</p>

<table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,.04);border:1px solid rgba(202,138,4,.18);border-radius:12px;margin-bottom:26px;">
  <tr><td style="padding:18px 20px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding-bottom:12px;border-bottom:1px solid rgba(202,138,4,.10);">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Empleado</span><br>
        <span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:15px;font-weight:bold;">{empleado_nombre}</span>
      </td></tr>
      <tr><td style="padding:12px 0;border-bottom:1px solid rgba(202,138,4,.10);">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Tipo</span><br>
        <span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:14px;">{tipo_label}</span>
      </td></tr>
      <tr><td style="padding:12px 0;border-bottom:1px solid rgba(202,138,4,.10);">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Período</span><br>
        <span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:14px;">{fecha_ini} &rarr; {fecha_fin}</span>
      </td></tr>
      <tr><td style="padding-top:12px;">
        <span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Días laborables</span><br>
        <span style="color:#CA8A04;font-family:Georgia,serif;font-size:26px;font-weight:bold;">{dias_lab}</span>
      </td></tr>
      {"" if not comentario_emp else f'<tr><td style="padding-top:12px;border-top:1px solid rgba(202,138,4,.10);"><span style="color:rgba(220,195,140,.45);font-family:Arial,sans-serif;font-size:9px;text-transform:uppercase;letter-spacing:2px;">Nota del empleado</span><br><span style="color:#f0e8d5;font-family:Arial,sans-serif;font-size:13px;font-style:italic;">{comentario_emp}</span></td></tr>'}
    </table>
  </td></tr>
</table>

<!-- Action buttons -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
  <tr>
    <td width="48%">
      <a href="{approve_url}" style="display:block;background:linear-gradient(135deg,#14532d,#16a34a);color:#ffffff;text-decoration:none;text-align:center;padding:14px 10px;border-radius:10px;font-family:Arial,sans-serif;font-size:12px;font-weight:bold;letter-spacing:3px;text-transform:uppercase;">&#10003;&nbsp; APROBAR</a>
    </td>
    <td width="4%"></td>
    <td width="48%">
      <a href="{deny_url}" style="display:block;background:rgba(220,38,38,.12);border:1px solid rgba(220,38,38,.35);color:#fca5a5;text-decoration:none;text-align:center;padding:13px 10px;border-radius:10px;font-family:Arial,sans-serif;font-size:12px;font-weight:bold;letter-spacing:3px;text-transform:uppercase;">&#10007;&nbsp; DENEGAR</a>
    </td>
  </tr>
</table>

<p style="color:rgba(220,195,140,.28);font-family:Arial,sans-serif;font-size:10px;text-align:center;margin:0;line-height:1.6;">
  Enlace de un solo uso &middot; caduca en 72&nbsp;horas<br>
  También puedes gestionar esta solicitud desde la aplicación.
</p>
"""
        subject = f"⏳ Solicitud de {tipo_label} de {empleado_nombre} — pendiente de aprobación"
        html = _odk_email_wrap(inner, subject)

        msg = MIMEMultipart("alternative")
        msg["From"] = frm
        msg["To"] = manager_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(host, port) as srv:
            srv.starttls()
            srv.login(smtp_user, pwd)
            srv.sendmail(frm, manager_email, msg.as_string())
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

    # ── Email manager with one-click approve/deny ─────────────────────────────
    try:
        emp = get_user_by_id(user_id)
        if emp and emp.get("manager_id"):
            mgr = get_user_by_id(emp["manager_id"])
            if mgr and mgr.get("email"):
                tok_a, tok_d = _create_approval_tokens(rid, mgr["id"])
                send_manager_request_email(
                    manager_email=mgr["email"],
                    manager_nombre=f"{mgr['nombre']} {mgr.get('apellidos','')}",
                    empleado_nombre=f"{emp['nombre']} {emp.get('apellidos','')}",
                    tipo_aus=tipo,
                    fecha_ini=str(f_ini),
                    fecha_fin=str(f_fin),
                    dias_lab=dl,
                    comentario_emp=comentario or "",
                    tok_approve=tok_a,
                    tok_deny=tok_d,
                )
    except Exception:
        pass  # Email failure never blocks the request creation

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



    d_ini = f"{año}-01-01"
    d_fin = f"{año+1}-01-01"

    c = _conn()

    rows = c.execute(
        "SELECT dias_laborables FROM vacation_requests"
        " WHERE user_id=? AND fecha_inicio>=? AND fecha_inicio<? AND estado='aprobada'",
        (user_id, d_ini, d_fin)).fetchall()

    used = sum((r["dias_laborables"] or 0) for r in rows)

    pending_rows = c.execute(
        "SELECT dias_laborables FROM vacation_requests"
        " WHERE user_id=? AND fecha_inicio>=? AND fecha_inicio<? AND estado='pendiente'",
        (user_id, d_ini, d_fin)).fetchall()

    c.close()

    pending = sum((r["dias_laborables"] or 0) for r in pending_rows)



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



    except Exception as e:
        err = str(e).lower()
        if "unique" not in err and "duplicate" not in err and "conflict" not in err:
            raise



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



    n = c.execute("SELECT COUNT(*) as n FROM notifications WHERE user_id=? AND leido=0", (user_id,)).fetchone()["n"]



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



    row = c.execute("SELECT COUNT(*) as n FROM users WHERE activo=1").fetchone()
    total_users = row["n"] if row else 0

    row = c.execute("SELECT COUNT(*) as n FROM time_entries WHERE fecha=date('now') AND deleted=0").fetchone()
    total_entries_today = row["n"] if row else 0

    row = c.execute("SELECT COUNT(*) as n FROM vacation_requests WHERE estado='pendiente'").fetchone()
    pending_requests = row["n"] if row else 0

    row = c.execute("SELECT COUNT(*) as n FROM time_incidents WHERE estado='pendiente'").fetchone()
    open_incidents = row["n"] if row else 0



    c.close()



    return {



        "total_users": total_users,



        "total_entries_today": total_entries_today,



        "pending_requests": pending_requests,



        "open_incidents": open_incidents,



    }



