"""Configurações do sistema, lidas de variáveis de ambiente (ou do arquivo .env)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _carregar_env() -> None:
    """Lê um arquivo .env simples (CHAVE=valor) sem depender de biblioteca externa."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{BASE_DIR / 'adm_financeiro.db'}"
    # Render / Neon entregam "postgres://" ou "postgresql://"; o SQLAlchemy precisa do driver psycopg
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


APP_NOME = "Projeto Adm-Financeiro"
DATABASE_URL = _database_url()

# Login do sistema
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

# LLM (Google Gemini)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# Modelos tentados em sequência caso o principal não esteja disponível para a chave
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]

# GitHub (para mostrar o código da última atualização na tela principal)
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # formato: usuario/repositorio
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

MAX_PDF_MB = 10
