
import sqlite3
import pandas as pd
from pathlib import Path

# Caminho da pasta onde está o script
PASTA_ATUAL = Path(__file__).resolve().parents[1]

# Caminhos do banco e da pasta de saída
CAMINHO_BANCO = PASTA_ATUAL / "data" / "agendador.db"
PASTA_SAIDA = PASTA_ATUAL / "data" / "exports"

# Criar pasta de saída, caso não exista
PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

if not CAMINHO_BANCO.exists():
    raise FileNotFoundError(
        f"Banco não encontrado: {CAMINHO_BANCO}"
    )

# Conectar ao banco
with sqlite3.connect(CAMINHO_BANCO) as conexao:

    # Identificar todas as tabelas
    tabelas = pd.read_sql_query(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """,
        conexao
    )["name"].tolist()

    if not tabelas:
        print("Nenhuma tabela encontrada no banco.")

    # Exportar cada tabela para CSV
    for tabela in tabelas:

        df = pd.read_sql_query(
            f'SELECT * FROM "{tabela}"',
            conexao
        )

        caminho_csv = PASTA_SAIDA / f"{tabela}.csv"

        df.to_csv(
            caminho_csv,
            index=False,
            sep=";",
            encoding="utf-8-sig"
        )

        print(
            f"Tabela: {tabela} | "
            f"Registros: {len(df)} | "
            f"Arquivo: {caminho_csv}"
        )

print("\nExportação concluída!")
