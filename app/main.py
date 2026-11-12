"""Projeto Administrativo-Financeiro — aplicação FastAPI."""
import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import ADMIN_PASSWORD, ADMIN_USER, BASE_DIR, SECRET_KEY
from app.database import get_db
from app.models import STATUS_ATIVO, Classificacao, MovimentoContas, ParcelaContas, Pessoa
from app.routers import classificacao, contas, notas, pessoas
from app.seed import inicializar_banco
from app.templating import render

@asynccontextmanager
async def lifespan(_app: FastAPI):
    inicializar_banco()  # cria tabelas e classificações padrão
    yield


app = FastAPI(title="Projeto Adm-Financeiro", docs_url=None, redoc_url=None, lifespan=lifespan)

ROTAS_PUBLICAS = ("/login", "/static", "/health")


class LoginObrigatorio(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(ROTAS_PUBLICAS) and not request.session.get("usuario"):
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)


# A ordem importa: a sessão precisa ser processada antes da checagem de login
app.add_middleware(LoginObrigatorio)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 8, same_site="lax")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(pessoas.router)
app.include_router(classificacao.router)
app.include_router(contas.router)
app.include_router(notas.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_form(request: Request):
    if request.session.get("usuario"):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", {"erro": None})


@app.post("/login")
def login(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    ok_user = hmac.compare_digest(usuario.strip(), ADMIN_USER)
    ok_senha = hmac.compare_digest(senha, ADMIN_PASSWORD)
    if ok_user and ok_senha:
        request.session["usuario"] = usuario.strip()
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", {"erro": "Usuário ou senha inválidos."}, status_code=401)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    def contar_pessoas(tipo):
        return db.scalar(select(func.count()).where(Pessoa.tipo == tipo, Pessoa.status == STATUS_ATIVO))

    def total_aberto(tipo):
        return db.scalar(
            select(func.coalesce(func.sum(ParcelaContas.valor_parcela), 0))
            .join(MovimentoContas)
            .where(MovimentoContas.tipo == tipo, MovimentoContas.status == STATUS_ATIVO, ParcelaContas.situacao == "ABERTA")
        )

    resumo = {
        "fornecedores": contar_pessoas("FORNECEDOR"),
        "clientes": contar_pessoas("CLIENTE"),
        "faturados": contar_pessoas("FATURADO"),
        "despesas": db.scalar(select(func.count()).where(Classificacao.tipo == "DESPESA", Classificacao.status == STATUS_ATIVO)),
        "receitas": db.scalar(select(func.count()).where(Classificacao.tipo == "RECEITA", Classificacao.status == STATUS_ATIVO)),
        "a_pagar": total_aberto("APAGAR"),
        "a_receber": total_aberto("ARECEBER"),
    }
    ultimos = db.scalars(
        select(MovimentoContas).where(MovimentoContas.status == STATUS_ATIVO)
        .order_by(MovimentoContas.id.desc()).limit(5)
    ).all()
    return render(request, "dashboard.html", {"resumo": resumo, "ultimos": ultimos})
