"""Cria exatamente as três contas iniciais do Agendador de Visitas.
Execute com: python criar_usuarios.py
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.db import init_db, create_or_update_user, get_connection

SENHA_PADRAO = "Agendador@2026!"  # Apenas para testes; altere antes de publicar o app.

PERFIS = [
    ("Administrador", "Administrador"),
    ("Supervisor", "Supervisor"),
    ("Colaborador", "Colaborador"),
]


def main():
    init_db()
    print("Cadastro das 3 contas iniciais.\n")
    print("Senha padrão temporária para os três perfis: Agendador@2026!")
    print("Use somente em testes locais e altere antes de publicar o aplicativo.\n")
    contas = []
    for role, label in PERFIS:
        print(f"Conta: {label}")
        username = input(f"Login para {label}: ").strip().lower()
        contas.append((username, SENHA_PADRAO, role))
        print()

    usernames = [u for u, _, _ in contas]
    if len(set(usernames)) != 3:
        raise SystemExit("Cada perfil deve ter um login diferente. Execute novamente.")

    for username, password, role in contas:
        create_or_update_user(username, password, role)

    # Remove contas adicionais da tabela de autenticação, mantendo exatamente as 3 definidas acima.
    with get_connection() as c:
        placeholders = ",".join("?" for _ in usernames)
        c.execute(f"DELETE FROM app_users WHERE username NOT IN ({placeholders})", usernames)

    print("\nContas criadas/atualizadas com sucesso:")
    for username, _, role in contas:
        print(f"- {role}: {username}")
    print(f"Senha padrão temporária dos três usuários: {SENHA_PADRAO}")
    print("A senha é armazenada no banco como hash. Não use essa senha em produção.")


if __name__ == "__main__":
    main()
