from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import APP_NOME, BASE_DIR
from app.services.versao import ultima_atualizacao
from app.utils import data_br, formatar_documento, moeda, rotulo_documento

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.filters["moeda"] = moeda
templates.env.filters["data_br"] = data_br
templates.env.filters["documento"] = formatar_documento
templates.env.filters["rotulo_doc"] = rotulo_documento
templates.env.globals["APP_NOME"] = APP_NOME


def render(request: Request, nome: str, contexto: dict | None = None, status_code: int = 200):
    ctx = dict(contexto or {})
    ctx.setdefault("versao", ultima_atualizacao())
    ctx.setdefault("usuario", request.session.get("usuario"))
    ctx.setdefault("rota", request.url.path)
    # mensagens "flash" guardadas na sessão
    ctx.setdefault("flash", request.session.pop("flash", None))
    return templates.TemplateResponse(request, nome, ctx, status_code=status_code)


def flash(request: Request, mensagem: str, categoria: str = "success") -> None:
    request.session["flash"] = {"mensagem": mensagem, "categoria": categoria}
