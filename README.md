# Rota Flow — Agendador de Visitas

Aplicação web em Python e Streamlit para programação de visitas, envio de agendas para aprovação de supervisores e exportação dos resultados.

## Requisitos
- Python 3.10 ou superior
- Windows, macOS ou Linux

## Executar no Windows (PowerShell)

Na pasta raiz `rota-flow`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

Se a ativação do ambiente virtual for bloqueada, execute o Streamlit pelo caminho completo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Estrutura

```text
rota-flow/
├── app.py                    # Entrada da aplicação Streamlit
├── src/
│   ├── __init__.py
│   ├── db.py                 # Banco SQLite e operações de dados
│   └── import_export.py      # Importação da base e exportação de visitas
├── scripts/
│   ├── criar_usuarios.py     # Criação das contas iniciais
│   ├── limpar_banco.py       # Limpeza do banco com backup
│   └── consultar_banco.py    # Exportação das tabelas para CSV
├── data/
│   ├── agendador.db          # Banco local de desenvolvimento
│   ├── input/
│   │   └── base_exemplo.xlsx
│   ├── exports/              # Exportações geradas
│   └── backups/              # Backups locais
├── tests/                    # Testes automatizados (próxima etapa)
├── schema.sql
├── requirements.txt
├── .gitignore
└── README.md
```

## Banco de dados
O banco local fica em `data/agendador.db`. A aplicação o cria quando necessário. O banco incluído nesta cópia foi mantido para preservar os dados locais existentes. Antes de compartilhar a pasta ou publicar o projeto, confira se ele contém dados reais e não o envie ao GitHub.

O `.gitignore` exclui bancos, backups, arquivos exportados, segredos e ambientes virtuais do Git.

## Contas iniciais
Para criar as contas de acesso, execute:

```powershell
python scripts/criar_usuarios.py
```

O script usa a senha temporária definida no próprio arquivo apenas para o fluxo de demonstração. Não utilize credenciais padrão em produção; altere o procedimento para solicitar uma senha segura antes da publicação.

## Ferramentas auxiliares

```powershell
python scripts/consultar_banco.py
python scripts/limpar_banco.py
```

**Atenção:** `limpar_banco.py` apaga registros operacionais após confirmação. Ele cria um backup antes de limpar as tabelas.

## Base Excel
A tela de administração aceita um Excel com uma linha por vínculo colaborador × loja. As colunas obrigatórias são `Colaborador`, `Supervisor`, `Código PDV` e `Loja`; `Cidade`, `UF` e `Ativo` são opcionais. Use uma base completa ao sincronizar os vínculos.

## Próximas melhorias antes de produção
- Migrar de SQLite para PostgreSQL para operação multiusuário.
- Implementar gestão de sessão e controles de acesso com validação de segurança.
- Adicionar testes automatizados para login, agendamento, aprovação e exportação.
- Configurar backups, logs e variáveis de ambiente no servidor.
