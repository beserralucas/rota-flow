import sqlite3
import hashlib
import hmac
import secrets
from pathlib import Path
import pandas as pd
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "agendador.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS app_users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Colaborador','Supervisor','Administrador')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            supervisor_name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS stores (
            store_code TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            city TEXT,
            uf TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS assignments (
            employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
            store_code TEXT NOT NULL REFERENCES stores(store_code),
            active INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (employee_id, store_code)
        );
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
            week_start TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDENTE_APROVACAO','APROVADA','REPROVADA')),
            submitted_at TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            review_comment TEXT
        );
        CREATE TABLE IF NOT EXISTS visits (
            visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
            store_code TEXT NOT NULL REFERENCES stores(store_code),
            visit_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(submission_id, store_code, visit_date)
        );
        CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visit_date);
        """)

def list_collaborators():
    with get_connection() as c:
        rows = c.execute("SELECT name FROM employees WHERE active=1 ORDER BY name").fetchall()
    return [r["name"] for r in rows]

def list_supervisors():
    with get_connection() as c:
        rows = c.execute("""SELECT DISTINCT supervisor_name AS name FROM employees
                            WHERE active=1 AND supervisor_name IS NOT NULL AND TRIM(supervisor_name) <> ''
                            ORDER BY supervisor_name""").fetchall()
    return [r["name"] for r in rows]

def list_collaborators_for_supervisor(supervisor):
    """Lista somente colaboradores ativos vinculados ao supervisor informado."""
    with get_connection() as c:
        rows = c.execute("""SELECT name FROM employees
                            WHERE active=1 AND supervisor_name=?
                            ORDER BY name""", (supervisor,)).fetchall()
    return [r["name"] for r in rows]


def get_stores_for_collaborator(name):
    with get_connection() as c:
        df = pd.read_sql_query("""
            SELECT s.store_code, s.store_name, s.city, s.uf
            FROM stores s
            JOIN assignments a ON a.store_code=s.store_code AND a.active=1
            JOIN employees e ON e.employee_id=a.employee_id AND e.active=1
            WHERE e.name=? AND s.active=1
            ORDER BY s.store_name
        """, c, params=(name,))
    return df

def save_submission(employee_name, week_start, draft):
    if not draft:
        raise ValueError("A agenda precisa conter pelo menos uma visita.")
    with get_connection() as c:
        emp = c.execute("SELECT employee_id, supervisor_name FROM employees WHERE name=? AND active=1", (employee_name,)).fetchone()
        if not emp:
            raise ValueError("Colaborador inválido ou inativo.")
        if not emp["supervisor_name"]:
            raise ValueError("Este colaborador não possui supervisor definido na base.")
        allowed = {r["store_code"] for r in c.execute("""
            SELECT a.store_code FROM assignments a JOIN stores s ON s.store_code=a.store_code
            WHERE a.employee_id=? AND a.active=1 AND s.active=1
        """, (emp["employee_id"],)).fetchall()}
        seen = set()
        for v in draft:
            code, visit_date = str(v["store_code"]), str(v["visit_date"])
            if code not in allowed:
                raise ValueError(f"A loja {code} não está vinculada ao colaborador.")
            if not (week_start <= visit_date <= _week_end(week_start)):
                raise ValueError(f"A data {visit_date} está fora da semana selecionada.")
            key = (code, visit_date)
            if key in seen:
                raise ValueError(f"Visita duplicada no rascunho: {code} em {visit_date}.")
            seen.add(key)
            conflict = c.execute("""
                SELECT COUNT(*) FROM visits v JOIN submissions s ON s.submission_id=v.submission_id
                WHERE v.store_code=? AND v.visit_date=? AND s.status IN ('PENDENTE_APROVACAO','APROVADA')
            """, (code, visit_date)).fetchone()[0]
            if conflict:
                raise ValueError(f"A loja {code} já possui uma visita pendente ou aprovada em {visit_date}.")
        cur = c.execute("""INSERT INTO submissions(employee_id, week_start, status, submitted_at)
                           VALUES (?, ?, 'PENDENTE_APROVACAO', ?)""",
                        (emp["employee_id"], week_start, datetime.now().isoformat(timespec="seconds")))
        submission_id = cur.lastrowid
        now = datetime.now().isoformat(timespec="seconds")
        for v in draft:
            c.execute("INSERT INTO visits(submission_id, store_code, visit_date, created_at) VALUES (?,?,?,?)",
                      (submission_id, str(v["store_code"]), str(v["visit_date"]), now))
        return submission_id

def _week_end(week_start):
    from datetime import date, timedelta
    return (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()

def list_submissions_for_supervisor(supervisor):
    with get_connection() as c:
        return pd.read_sql_query("""
            SELECT s.submission_id, e.name AS collaborator, s.week_start, s.status,
                   s.submitted_at, COUNT(v.visit_id) AS visit_count
            FROM submissions s JOIN employees e ON e.employee_id=s.employee_id
            JOIN visits v ON v.submission_id=s.submission_id
            WHERE e.supervisor_name=? AND s.status='PENDENTE_APROVACAO'
            GROUP BY s.submission_id ORDER BY s.submitted_at
        """, c, params=(supervisor,))

def get_submission_visits(submission_id):
    with get_connection() as c:
        return pd.read_sql_query("""
            SELECT v.store_code AS 'Código PDV', s.store_name AS Loja, s.city AS Cidade,
                   s.uf AS UF, v.visit_date AS 'Data da visita'
            FROM visits v JOIN stores s ON s.store_code=v.store_code
            WHERE v.submission_id=? ORDER BY v.visit_date, s.store_name
        """, c, params=(submission_id,))

def review_submission(submission_id, supervisor, decision, comment=""):
    if decision not in ("APROVADA", "REPROVADA"):
        raise ValueError("Decisão inválida.")
    if decision == "REPROVADA" and not comment.strip():
        raise ValueError("Informe o motivo da reprovação.")
    with get_connection() as c:
        row = c.execute("""
            SELECT s.submission_id, s.status, e.supervisor_name
            FROM submissions s JOIN employees e ON e.employee_id=s.employee_id
            WHERE s.submission_id=?
        """, (submission_id,)).fetchone()
        if not row:
            raise ValueError("Agenda não encontrada.")
        if row["supervisor_name"] != supervisor:
            raise ValueError("Este supervisor não tem permissão para analisar esta agenda.")
        if row["status"] != "PENDENTE_APROVACAO":
            raise ValueError("Esta agenda já foi analisada.")
        c.execute("""UPDATE submissions SET status=?, reviewed_by=?, reviewed_at=?, review_comment=?
                     WHERE submission_id=?""",
                  (decision, supervisor, datetime.now().isoformat(timespec="seconds"), comment.strip(), submission_id))

def list_submissions():
    with get_connection() as c:
        return pd.read_sql_query("""
            SELECT s.submission_id AS Protocolo, e.name AS Colaborador, s.week_start AS 'Início da semana',
                   s.status AS Status, s.submitted_at AS 'Enviado em', s.reviewed_by AS 'Analisado por',
                   s.reviewed_at AS 'Analisado em', s.review_comment AS Comentário,
                   COUNT(v.visit_id) AS Visitas
            FROM submissions s JOIN employees e ON e.employee_id=s.employee_id
            LEFT JOIN visits v ON v.submission_id=s.submission_id
            GROUP BY s.submission_id ORDER BY s.submitted_at DESC
        """, c).rename(columns={"Protocolo":"submission_id","Colaborador":"collaborator","Início da semana":"week_start","Status":"status","Enviado em":"submitted_at","Analisado por":"reviewed_by","Analisado em":"reviewed_at","Comentário":"review_comment","Visitas":"visit_count"})


# Autenticação do aplicativo: PBKDF2 com salt individual por usuário.
def _hash_password(password, salt=None):
    if not isinstance(password, str) or len(password) < 10:
        raise ValueError("A senha deve ter pelo menos 10 caracteres.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password, encoded):
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 310_000
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, AttributeError):
        return False


def create_or_update_user(username, password, role):
    """Cria ou atualiza uma das contas iniciais. Não cria usuários extras por engano."""
    allowed_roles = {"Colaborador", "Supervisor", "Administrador"}
    username = username.strip().lower()
    if not username:
        raise ValueError("Informe um nome de usuário.")
    if role not in allowed_roles:
        raise ValueError("Perfil inválido.")
    encoded = _hash_password(password)
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as c:
        c.execute("""INSERT INTO app_users(username, password_hash, role, active, created_at)
                     VALUES (?, ?, ?, 1, ?)
                     ON CONFLICT(username) DO UPDATE SET
                         password_hash=excluded.password_hash,
                         role=excluded.role,
                         active=1""", (username, encoded, role, now))


def authenticate_user(username, password):
    username = (username or "").strip().lower()
    with get_connection() as c:
        row = c.execute(
            "SELECT user_id, username, password_hash, role FROM app_users WHERE username=? AND active=1",
            (username,),
        ).fetchone()
    if not row or not _verify_password(password or "", row["password_hash"]):
        return None
    return {"user_id": row["user_id"], "username": row["username"], "role": row["role"]}


def count_app_users():
    with get_connection() as c:
        return c.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]
