
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Caminhos do projeto
BASE_DIR = PROJECT_ROOT
DB_PATH = BASE_DIR / "data" / "agendador.db"
BACKUP_DIR = BASE_DIR / "data" / "backups"

# Tabelas que serão limpas
# A ordem considera primeiro os registros dependentes.
TABELAS = [
    "submissions",
    "visits",
    "assignments",
    "stores",
    "employees",
]


def limpar_banco():
    if not DB_PATH.exists():
        print(f"Banco não encontrado: {DB_PATH}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"agendador_backup_{timestamp}.db"

    conexao = sqlite3.connect(DB_PATH)

    try:
        # Criar backup consistente do banco
        with sqlite3.connect(backup_path) as backup:
            conexao.backup(backup)

        print(f"Backup criado: {backup_path}")

        # Ativar validação das chaves estrangeiras
        conexao.execute("PRAGMA foreign_keys = ON")

        tabelas_existentes = {
            linha[0]
            for linha in conexao.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        with conexao:
            for tabela in TABELAS:
                if tabela not in tabelas_existentes:
                    continue

                conexao.execute(f'DELETE FROM "{tabela}"')
                print(f"Tabela limpa: {tabela}")

            # Reiniciar contadores AUTOINCREMENT, se existirem
            if "sqlite_sequence" in tabelas_existentes:
                for tabela in TABELAS:
                    conexao.execute(
                        "DELETE FROM sqlite_sequence WHERE name = ?",
                        (tabela,),
                    )

        print("\nBanco de dados limpo com sucesso!")
        print("A estrutura das tabelas foi preservada.")

    except Exception as erro:
        print(f"Erro ao limpar o banco: {erro}")
        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    confirmar = input(
        "Isso apagará todos os dados das tabelas listadas. "
        "Deseja continuar? (S/N): "
    ).strip().upper()

    if confirmar == "S":
        limpar_banco()
    else:
        print("Operação cancelada.")
