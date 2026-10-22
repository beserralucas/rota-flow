import re
import sqlite3
from io import BytesIO
import pandas as pd
from src.db import get_connection

ALIASES = {
    "colaborador": ["colaborador", "funcionario", "funcionário", "promotor", "nome colaborador", "nome do colaborador"],
    "supervisor": ["supervisor", "nome supervisor", "supervisor responsável"],
    "codigo_pdv": ["codigo pdv", "código pdv", "cod pdv", "id pdv", "codigo loja", "código loja", "id loja", "pdv"],
    "loja": ["loja", "nome loja", "nome do pdv", "ponto de venda", "pdv nome"],
    "cidade": ["cidade", "municipio", "município"],
    "uf": ["uf", "estado"],
    "ativo": ["ativo", "status"]
}

def norm(s):
    s = str(s).strip().lower()
    s = re.sub(r"[\s_\-]+", " ", s)
    return s

def import_base(df):
    if df.empty:
        raise ValueError("A planilha não possui linhas de dados.")
    col_map = {}
    normalized = {norm(c): c for c in df.columns}
    for target, names in ALIASES.items():
        for alias in names:
            if norm(alias) in normalized:
                col_map[target] = normalized[norm(alias)]
                break
    missing = [x for x in ["colaborador", "supervisor", "codigo_pdv", "loja"] if x not in col_map]
    if missing:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(missing) +
                         ". Esperadas: Colaborador, Supervisor, Código PDV e Loja.")
    clean = pd.DataFrame()
    for target, source in col_map.items():
        clean[target] = df[source]
    for c in ["cidade", "uf", "ativo"]:
        if c not in clean:
            clean[c] = ""
    for c in ["colaborador", "supervisor", "codigo_pdv", "loja"]:
        clean[c] = clean[c].fillna("").astype(str).str.strip()
    clean = clean[(clean["colaborador"] != "") & (clean["codigo_pdv"] != "") & (clean["loja"] != "")]
    if clean.empty:
        raise ValueError("Nenhuma linha válida após remover colaborador, código PDV ou loja vazios.")
    clean["codigo_pdv"] = clean["codigo_pdv"].str.replace(r"\.0$", "", regex=True)
    clean["cidade"] = clean["cidade"].fillna("").astype(str).str.strip()
    clean["uf"] = clean["uf"].fillna("").astype(str).str.strip().str.upper()
    clean["supervisor"] = clean["supervisor"].replace("", pd.NA).fillna("Supervisor não definido")
    if "ativo" in clean:
        clean["ativo_flag"] = clean["ativo"].astype(str).str.strip().str.lower().map(
            {"0":0, "false":0, "não":0, "nao":0, "inativo":0, "desligado":0, "1":1, "true":1, "sim":1, "ativo":1, "nan":1, "":1}
        ).fillna(1).astype(int)
    else:
        clean["ativo_flag"] = 1
    # A loja deve ter um único nome/localização por código.
    store_conflicts = clean.groupby("codigo_pdv")["loja"].nunique()
    if (store_conflicts > 1).any():
        bad = ", ".join(store_conflicts[store_conflicts > 1].index.astype(str)[:10])
        raise ValueError(f"Um mesmo Código PDV possui nomes diferentes: {bad}")
    warnings = []
    duplicate_links = int(clean.duplicated(["colaborador", "codigo_pdv"]).sum())
    if duplicate_links:
        warnings.append(f"{duplicate_links} vínculo(s) duplicado(s) foram removidos.")
    clean = clean.drop_duplicates(["colaborador", "codigo_pdv"])
    with get_connection() as c:
        # Upsert de lojas e colaboradores; sincroniza os vínculos com o arquivo importado.
        for code, group in clean.groupby("codigo_pdv"):
            row = group.iloc[0]
            active = int(group["ativo_flag"].max())
            c.execute("""INSERT INTO stores(store_code, store_name, city, uf, active) VALUES(?,?,?,?,?)
                         ON CONFLICT(store_code) DO UPDATE SET store_name=excluded.store_name,
                         city=excluded.city, uf=excluded.uf, active=excluded.active""",
                      (code, row["loja"], row["cidade"], row["uf"], active))
        for name, group in clean.groupby("colaborador"):
            supervisor = group.iloc[0]["supervisor"]
            active = int(group["ativo_flag"].max())
            c.execute("""INSERT INTO employees(name, supervisor_name, active) VALUES(?,?,?)
                         ON CONFLICT(name) DO UPDATE SET supervisor_name=excluded.supervisor_name, active=excluded.active""",
                      (name, supervisor, active))
        c.execute("UPDATE assignments SET active=0")
        for _, row in clean.iterrows():
            emp = c.execute("SELECT employee_id FROM employees WHERE name=?", (row["colaborador"],)).fetchone()
            c.execute("""INSERT INTO assignments(employee_id, store_code, active) VALUES(?,?,?)
                         ON CONFLICT(employee_id, store_code) DO UPDATE SET active=excluded.active""",
                      (emp["employee_id"], row["codigo_pdv"], int(row["ativo_flag"])))
        employees = c.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
        stores = c.execute("SELECT COUNT(*) FROM stores WHERE active=1").fetchone()[0]
        assignments = c.execute("SELECT COUNT(*) FROM assignments WHERE active=1").fetchone()[0]
    return {"employees": employees, "stores": stores, "assignments": assignments, "warnings": warnings}

def export_visits(status=None):
    query = """
    SELECT sub.submission_id AS Protocolo, e.name AS Colaborador, e.supervisor_name AS Supervisor,
           v.store_code AS 'Código PDV', st.store_name AS Loja, st.city AS Cidade, st.uf AS UF,
           v.visit_date AS 'Data da visita', sub.week_start AS 'Início da semana',
           sub.status AS Status, sub.submitted_at AS 'Enviado em', sub.reviewed_by AS 'Analisado por',
           sub.reviewed_at AS 'Analisado em', sub.review_comment AS 'Comentário da análise'
    FROM visits v
    JOIN submissions sub ON sub.submission_id=v.submission_id
    JOIN employees e ON e.employee_id=sub.employee_id
    JOIN stores st ON st.store_code=v.store_code
    """
    params = ()
    if status:
        query += " WHERE sub.status=?"
        params = (status,)
    query += " ORDER BY v.visit_date, e.name, st.store_name"
    with get_connection() as c:
        df = pd.read_sql_query(query, c, params=params)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Agendamentos")
        if not df.empty:
            summary = df.groupby(["Status", "Colaborador"], dropna=False).size().reset_index(name="Quantidade de visitas")
            summary.to_excel(writer, index=False, sheet_name="Resumo")
    output.seek(0)
    return output.getvalue()
