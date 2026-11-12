"""MANTER PESSOAS — Fornecedor, Cliente e Faturado (mesma tabela, campo tipo)."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import STATUS_ATIVO, STATUS_INATIVO, Pessoa
from app.templating import flash, render
from app.utils import caminho_seguro, corresponde, so_digitos, termos_busca

router = APIRouter(prefix="/pessoas")

TIPOS = {
    "fornecedor": {"tipo": "FORNECEDOR", "plural": "Fornecedores", "singular": "Fornecedor", "icone": "bi-truck"},
    "cliente": {"tipo": "CLIENTE", "plural": "Clientes", "singular": "Cliente", "icone": "bi-people"},
    "faturado": {"tipo": "FATURADO", "plural": "Faturados", "singular": "Faturado", "icone": "bi-person-vcard"},
}


def _cfg(slug: str) -> dict:
    if slug not in TIPOS:
        raise HTTPException(404, "Tipo de cadastro inválido")
    return {**TIPOS[slug], "slug": slug}


def _validar(db: Session, tipo: str, razao_social: str, documento: str, id_atual: int | None = None) -> str | None:
    if not razao_social.strip():
        return "Informe a razão social / nome."
    if documento and len(documento) not in (11, 14):
        return "CPF deve ter 11 dígitos e CNPJ 14 dígitos."
    if documento:
        existente = db.scalar(select(Pessoa).where(Pessoa.tipo == tipo, Pessoa.documento == documento))
        if existente and existente.id != id_atual:
            situacao = " (INATIVO — reative-o na listagem)" if existente.status == STATUS_INATIVO else ""
            return f"Já existe cadastro com este CPF/CNPJ: ID {existente.id} - {existente.razao_social}{situacao}."
    return None


@router.get("/{slug}")
def listar(request: Request, slug: str, acao: str | None = None, q: str = "", status: str = STATUS_ATIVO,
           db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    registros = None  # tabela começa vazia
    if acao == "todos":
        status, q = STATUS_ATIVO, ""
        registros = db.scalars(
            select(Pessoa).where(Pessoa.tipo == cfg["tipo"], Pessoa.status == STATUS_ATIVO).order_by(Pessoa.razao_social)
        ).all()
    elif acao == "buscar":
        consulta = select(Pessoa).where(Pessoa.tipo == cfg["tipo"])
        if status in (STATUS_ATIVO, STATUS_INATIVO):
            consulta = consulta.where(Pessoa.status == status)
        termos = termos_busca(q)
        registros = [
            p for p in db.scalars(consulta.order_by(Pessoa.razao_social)).all()
            if corresponde(termos, [p.id, p.razao_social, p.fantasia, p.documento, p.email, p.telefone])
        ]
    voltar = request.url.path + ("?" + request.url.query if request.url.query else "")
    return render(request, "pessoas/lista.html", {
        "cfg": cfg, "registros": registros, "q": q, "status": status, "acao": acao, "voltar": voltar,
    })


@router.get("/{slug}/novo")
def novo(request: Request, slug: str):
    return render(request, "pessoas/form.html", {"cfg": _cfg(slug), "p": None, "erro": None})


@router.post("/{slug}/novo")
def criar(request: Request, slug: str, razao_social: str = Form(""), fantasia: str = Form(""),
          documento: str = Form(""), email: str = Form(""), telefone: str = Form(""),
          db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    doc = so_digitos(documento)
    erro = _validar(db, cfg["tipo"], razao_social, doc)
    if erro:
        rascunho = Pessoa(razao_social=razao_social, fantasia=fantasia, documento=documento, email=email, telefone=telefone)
        return render(request, "pessoas/form.html", {"cfg": cfg, "p": rascunho, "erro": erro, "novo": True}, status_code=400)
    p = Pessoa(
        tipo=cfg["tipo"], razao_social=razao_social.strip().upper(), fantasia=fantasia.strip() or None,
        documento=doc or None, email=email.strip() or None, telefone=telefone.strip() or None,
        status=STATUS_ATIVO,  # CREATE: status oculto == ATIVO
    )
    db.add(p)
    db.commit()
    flash(request, f"{cfg['singular']} cadastrado com sucesso (ID {p.id}).")
    return RedirectResponse(f"/pessoas/{slug}?" + urlencode({"acao": "buscar", "q": doc or p.razao_social}), status_code=303)


@router.get("/{slug}/{pid}/editar")
def editar(request: Request, slug: str, pid: int, voltar: str = "", db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    p = db.get(Pessoa, pid)
    if not p or p.tipo != cfg["tipo"]:
        raise HTTPException(404)
    return render(request, "pessoas/form.html", {"cfg": cfg, "p": p, "erro": None, "voltar": caminho_seguro(voltar, "")})


@router.post("/{slug}/{pid}/editar")
def atualizar(request: Request, slug: str, pid: int, razao_social: str = Form(""), fantasia: str = Form(""),
              documento: str = Form(""), email: str = Form(""), telefone: str = Form(""), voltar: str = Form(""),
              db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    p = db.get(Pessoa, pid)
    if not p or p.tipo != cfg["tipo"]:
        raise HTTPException(404)
    doc = so_digitos(documento)
    erro = _validar(db, cfg["tipo"], razao_social, doc, id_atual=p.id)
    if erro:
        return render(request, "pessoas/form.html", {"cfg": cfg, "p": p, "erro": erro, "voltar": caminho_seguro(voltar, "")}, status_code=400)
    # UPDATE: o status não é alterado aqui (campo oculto)
    p.razao_social = razao_social.strip().upper()
    p.fantasia = fantasia.strip() or None
    p.documento = doc or None
    p.email = email.strip() or None
    p.telefone = telefone.strip() or None
    db.commit()
    flash(request, f"{cfg['singular']} ID {p.id} atualizado com sucesso.")
    return RedirectResponse(caminho_seguro(voltar, f"/pessoas/{slug}?" + urlencode({"acao": "buscar", "q": p.razao_social})), status_code=303)


@router.post("/{slug}/{pid}/inativar")
def inativar(request: Request, slug: str, pid: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    """Exclusão lógica: cadastros nunca são apagados, apenas INATIVADOS."""
    cfg = _cfg(slug)
    p = db.get(Pessoa, pid)
    if not p or p.tipo != cfg["tipo"]:
        raise HTTPException(404)
    p.status = STATUS_INATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {p.id} inativado.", "warning")
    return RedirectResponse(caminho_seguro(voltar, f"/pessoas/{slug}"), status_code=303)


@router.post("/{slug}/{pid}/reativar")
def reativar(request: Request, slug: str, pid: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    p = db.get(Pessoa, pid)
    if not p or p.tipo != cfg["tipo"]:
        raise HTTPException(404)
    p.status = STATUS_ATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {p.id} reativado.")
    return RedirectResponse(caminho_seguro(voltar, f"/pessoas/{slug}"), status_code=303)
