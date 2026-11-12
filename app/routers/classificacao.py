"""MANTER CLASSIFICAÇÃO — Tipo de Receita e Tipo de Despesa (mesma tabela, campo tipo)."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import STATUS_ATIVO, STATUS_INATIVO, Classificacao
from app.templating import flash, render
from app.utils import caminho_seguro, corresponde, normalizar, termos_busca

router = APIRouter(prefix="/classificacao")

TIPOS = {
    "despesa": {"tipo": "DESPESA", "plural": "Tipos de Despesa", "singular": "Tipo de Despesa", "icone": "bi-arrow-down-circle"},
    "receita": {"tipo": "RECEITA", "plural": "Tipos de Receita", "singular": "Tipo de Receita", "icone": "bi-arrow-up-circle"},
}


def _cfg(slug: str) -> dict:
    if slug not in TIPOS:
        raise HTTPException(404, "Tipo de classificação inválido")
    return {**TIPOS[slug], "slug": slug}


def _validar(db: Session, tipo: str, descricao: str, id_atual: int | None = None) -> str | None:
    if not descricao.strip():
        return "Informe a descrição."
    alvo = normalizar(descricao)
    for c in db.scalars(select(Classificacao).where(Classificacao.tipo == tipo)).all():
        if normalizar(c.descricao) == alvo and c.id != id_atual:
            situacao = " (INATIVO — reative-o na listagem)" if c.status == STATUS_INATIVO else ""
            return f"Já existe a classificação ID {c.id} - {c.descricao}{situacao}."
    return None


@router.get("/{slug}")
def listar(request: Request, slug: str, acao: str | None = None, q: str = "", status: str = STATUS_ATIVO,
           db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    registros = None
    if acao == "todos":
        status, q = STATUS_ATIVO, ""
        registros = db.scalars(
            select(Classificacao).where(Classificacao.tipo == cfg["tipo"], Classificacao.status == STATUS_ATIVO)
            .order_by(Classificacao.descricao)
        ).all()
    elif acao == "buscar":
        consulta = select(Classificacao).where(Classificacao.tipo == cfg["tipo"])
        if status in (STATUS_ATIVO, STATUS_INATIVO):
            consulta = consulta.where(Classificacao.status == status)
        termos = termos_busca(q)
        registros = [
            c for c in db.scalars(consulta.order_by(Classificacao.descricao)).all()
            if corresponde(termos, [c.id, c.descricao])
        ]
    voltar = request.url.path + ("?" + request.url.query if request.url.query else "")
    return render(request, "classificacao/lista.html", {
        "cfg": cfg, "registros": registros, "q": q, "status": status, "acao": acao, "voltar": voltar,
    })


@router.get("/{slug}/novo")
def novo(request: Request, slug: str):
    return render(request, "classificacao/form.html", {"cfg": _cfg(slug), "c": None, "erro": None})


@router.post("/{slug}/novo")
def criar(request: Request, slug: str, descricao: str = Form(""), db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    erro = _validar(db, cfg["tipo"], descricao)
    if erro:
        return render(request, "classificacao/form.html",
                      {"cfg": cfg, "c": Classificacao(descricao=descricao), "erro": erro, "novo": True}, status_code=400)
    c = Classificacao(tipo=cfg["tipo"], descricao=descricao.strip().upper(), status=STATUS_ATIVO)
    db.add(c)
    db.commit()
    flash(request, f"{cfg['singular']} cadastrado com sucesso (ID {c.id}).")
    return RedirectResponse(f"/classificacao/{slug}?" + urlencode({"acao": "buscar", "q": c.descricao}), status_code=303)


@router.get("/{slug}/{cid}/editar")
def editar(request: Request, slug: str, cid: int, voltar: str = "", db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    c = db.get(Classificacao, cid)
    if not c or c.tipo != cfg["tipo"]:
        raise HTTPException(404)
    return render(request, "classificacao/form.html", {"cfg": cfg, "c": c, "erro": None, "voltar": caminho_seguro(voltar, "")})


@router.post("/{slug}/{cid}/editar")
def atualizar(request: Request, slug: str, cid: int, descricao: str = Form(""), voltar: str = Form(""),
              db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    c = db.get(Classificacao, cid)
    if not c or c.tipo != cfg["tipo"]:
        raise HTTPException(404)
    erro = _validar(db, cfg["tipo"], descricao, id_atual=c.id)
    if erro:
        return render(request, "classificacao/form.html", {"cfg": cfg, "c": c, "erro": erro, "voltar": caminho_seguro(voltar, "")}, status_code=400)
    c.descricao = descricao.strip().upper()
    db.commit()
    flash(request, f"{cfg['singular']} ID {c.id} atualizado com sucesso.")
    return RedirectResponse(caminho_seguro(voltar, f"/classificacao/{slug}?" + urlencode({"acao": "buscar", "q": c.descricao})), status_code=303)


@router.post("/{slug}/{cid}/inativar")
def inativar(request: Request, slug: str, cid: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    c = db.get(Classificacao, cid)
    if not c or c.tipo != cfg["tipo"]:
        raise HTTPException(404)
    c.status = STATUS_INATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {c.id} inativado.", "warning")
    return RedirectResponse(caminho_seguro(voltar, f"/classificacao/{slug}"), status_code=303)


@router.post("/{slug}/{cid}/reativar")
def reativar(request: Request, slug: str, cid: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    c = db.get(Classificacao, cid)
    if not c or c.tipo != cfg["tipo"]:
        raise HTTPException(404)
    c.status = STATUS_ATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {c.id} reativado.")
    return RedirectResponse(caminho_seguro(voltar, f"/classificacao/{slug}"), status_code=303)
