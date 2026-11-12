"""REGISTRAR CONTAS — Contas a Pagar (APAGAR) e Contas a Receber (ARECEBER).

- Um registro pode ter uma ou mais classificações (Tipo de Despesa / Tipo de Receita).
- Um registro pode ter uma ou mais parcelas com datas de vencimento distintas.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import STATUS_ATIVO, STATUS_INATIVO, Classificacao, MovimentoContas, ParcelaContas, Pessoa
from app.templating import flash, render
from app.utils import caminho_seguro, corresponde, para_data, para_decimal, termos_busca

router = APIRouter(prefix="/contas")

TIPOS = {
    "pagar": {
        "tipo": "APAGAR", "plural": "Contas a Pagar", "singular": "Conta a Pagar", "icone": "bi-cash-coin",
        "pessoa_tipo": "FORNECEDOR", "pessoa_rotulo": "Fornecedor", "class_tipo": "DESPESA", "class_rotulo": "Tipos de Despesa",
    },
    "receber": {
        "tipo": "ARECEBER", "plural": "Contas a Receber", "singular": "Conta a Receber", "icone": "bi-wallet2",
        "pessoa_tipo": "CLIENTE", "pessoa_rotulo": "Cliente", "class_tipo": "RECEITA", "class_rotulo": "Tipos de Receita",
    },
}


def _cfg(slug: str) -> dict:
    if slug not in TIPOS:
        raise HTTPException(404, "Tipo de conta inválido")
    return {**TIPOS[slug], "slug": slug}


def _movimento(db: Session, cfg: dict, mid: int) -> MovimentoContas:
    m = db.get(MovimentoContas, mid)
    if not m or m.tipo != cfg["tipo"]:
        raise HTTPException(404)
    return m


def _opcoes(db: Session, cfg: dict, m: MovimentoContas | None = None) -> dict:
    """Listas para os selects do formulário (somente ATIVOS + os já vinculados ao registro)."""
    ids_extra = set()
    if m:
        ids_extra = {m.pessoa_id, m.faturado_id}

    def pessoas(tipo):
        return db.scalars(
            select(Pessoa).where(Pessoa.tipo == tipo, (Pessoa.status == STATUS_ATIVO) | Pessoa.id.in_(ids_extra))
            .order_by(Pessoa.razao_social)
        ).all()

    class_ids = {c.id for c in m.classificacoes} if m else set()
    classificacoes = db.scalars(
        select(Classificacao).where(
            Classificacao.tipo == cfg["class_tipo"],
            (Classificacao.status == STATUS_ATIVO) | Classificacao.id.in_(class_ids),
        ).order_by(Classificacao.descricao)
    ).all()
    return {"pessoas": pessoas(cfg["pessoa_tipo"]), "faturados": pessoas("FATURADO"), "classificacoes": classificacoes}


async def _ler_formulario(request: Request, db: Session, cfg: dict) -> tuple[dict, list[str]]:
    form = await request.form()
    erros = []
    dados = {
        "pessoa_id": int(form.get("pessoa_id") or 0) or None,
        "faturado_id": int(form.get("faturado_id") or 0) or None,
        "numero_nota_fiscal": (form.get("numero_nota_fiscal") or "").strip() or None,
        "data_emissao": para_data(form.get("data_emissao")),
        "descricao": (form.get("descricao") or "").strip() or None,
        "valor_total": para_decimal(form.get("valor_total")),
        "classificacao_ids": [int(x) for x in form.getlist("classificacao_ids") if x],
        "parcelas": [],
        "voltar": form.get("voltar") or "",
    }
    vencs, valores = form.getlist("parcela_vencimento"), form.getlist("parcela_valor")
    for venc, valor in zip(vencs, valores):
        if not venc and not valor:
            continue
        dados["parcelas"].append({"data_vencimento": para_data(venc), "valor": para_decimal(valor)})

    if not dados["pessoa_id"]:
        erros.append(f"Selecione o {cfg['pessoa_rotulo'].lower()}.")
    if not dados["data_emissao"]:
        erros.append("Informe a data de emissão.")
    if dados["valor_total"] <= 0:
        erros.append("Informe o valor total.")
    if not dados["classificacao_ids"]:
        erros.append(f"Selecione pelo menos uma classificação ({cfg['class_rotulo']}).")
    if not dados["parcelas"]:
        erros.append("Informe pelo menos uma parcela.")
    for i, p in enumerate(dados["parcelas"], start=1):
        if not p["data_vencimento"]:
            erros.append(f"Parcela {i}: informe o vencimento.")
        if p["valor"] <= 0:
            erros.append(f"Parcela {i}: informe um valor maior que zero.")
    soma = sum((p["valor"] for p in dados["parcelas"]), Decimal("0"))
    if dados["parcelas"] and abs(soma - dados["valor_total"]) > Decimal("0.01"):
        erros.append(f"A soma das parcelas (R$ {soma}) é diferente do valor total (R$ {dados['valor_total']}).")
    return dados, erros


def _aplicar(db: Session, m: MovimentoContas, dados: dict) -> None:
    m.pessoa_id = dados["pessoa_id"]
    m.faturado_id = dados["faturado_id"]
    m.numero_nota_fiscal = dados["numero_nota_fiscal"]
    m.data_emissao = dados["data_emissao"]
    m.descricao = dados["descricao"]
    m.valor_total = dados["valor_total"]
    m.classificacoes = list(db.scalars(select(Classificacao).where(Classificacao.id.in_(dados["classificacao_ids"]))).all())
    m.parcelas.clear()
    db.flush()
    total = len(dados["parcelas"])
    for i, p in enumerate(sorted(dados["parcelas"], key=lambda x: x["data_vencimento"]), start=1):
        m.parcelas.append(ParcelaContas(
            identificacao="ÚNICA" if total == 1 else f"{i}/{total}",
            data_vencimento=p["data_vencimento"],
            valor_parcela=p["valor"],
        ))


def _rascunho(dados: dict) -> dict:
    """Mantém o que o usuário digitou quando o formulário volta com erro."""
    return {**dados, "parcelas": dados["parcelas"] or [{"data_vencimento": None, "valor": None}]}


@router.get("/{slug}")
def listar(request: Request, slug: str, acao: str | None = None, q: str = "", status: str = STATUS_ATIVO,
           db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    registros = None
    if acao in ("todos", "buscar"):
        if acao == "todos":
            status, q = STATUS_ATIVO, ""
        consulta = select(MovimentoContas).where(MovimentoContas.tipo == cfg["tipo"])
        if status in (STATUS_ATIVO, STATUS_INATIVO):
            consulta = consulta.where(MovimentoContas.status == status)
        termos = termos_busca(q)
        registros = [
            m for m in db.scalars(consulta.order_by(MovimentoContas.id.desc())).all()
            if corresponde(termos, [
                m.id, m.numero_nota_fiscal, m.descricao,
                m.pessoa.razao_social if m.pessoa else None, m.pessoa.documento if m.pessoa else None,
                m.faturado.razao_social if m.faturado else None, m.faturado.documento if m.faturado else None,
                *[c.descricao for c in m.classificacoes],
            ])
        ]
    voltar = request.url.path + ("?" + request.url.query if request.url.query else "")
    return render(request, "contas/lista.html", {
        "cfg": cfg, "registros": registros, "q": q, "status": status, "acao": acao, "voltar": voltar,
    })


@router.get("/{slug}/novo")
def novo(request: Request, slug: str, db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    vazio = {"classificacao_ids": [], "parcelas": [{"data_vencimento": None, "valor": None}]}
    return render(request, "contas/form.html", {"cfg": cfg, "m": None, "f": vazio, "erros": [], **_opcoes(db, cfg)})


@router.post("/{slug}/novo")
async def criar(request: Request, slug: str, db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    dados, erros = await _ler_formulario(request, db, cfg)
    if erros:
        return render(request, "contas/form.html",
                      {"cfg": cfg, "m": None, "f": _rascunho(dados), "erros": erros, **_opcoes(db, cfg)}, status_code=400)
    m = MovimentoContas(tipo=cfg["tipo"], status=STATUS_ATIVO, origem="MANUAL")  # CREATE: status oculto == ATIVO
    db.add(m)
    _aplicar(db, m, dados)
    db.commit()
    flash(request, f"{cfg['singular']} lançada com sucesso (ID {m.id}, {len(m.parcelas)} parcela(s)).")
    return RedirectResponse(f"/contas/{slug}/{m.id}", status_code=303)


@router.get("/{slug}/{mid}")
def detalhe(request: Request, slug: str, mid: int, voltar: str = "", db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    m = _movimento(db, cfg, mid)
    return render(request, "contas/detalhe.html", {"cfg": cfg, "m": m, "voltar": caminho_seguro(voltar, f"/contas/{slug}")})


@router.get("/{slug}/{mid}/editar")
def editar(request: Request, slug: str, mid: int, voltar: str = "", db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    m = _movimento(db, cfg, mid)
    f = {
        "pessoa_id": m.pessoa_id, "faturado_id": m.faturado_id, "numero_nota_fiscal": m.numero_nota_fiscal,
        "data_emissao": m.data_emissao, "descricao": m.descricao, "valor_total": m.valor_total,
        "classificacao_ids": [c.id for c in m.classificacoes],
        "parcelas": [{"data_vencimento": p.data_vencimento, "valor": p.valor_parcela} for p in m.parcelas],
    }
    return render(request, "contas/form.html",
                  {"cfg": cfg, "m": m, "f": f, "erros": [], "voltar": caminho_seguro(voltar, ""), **_opcoes(db, cfg, m)})


@router.post("/{slug}/{mid}/editar")
async def atualizar(request: Request, slug: str, mid: int, db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    m = _movimento(db, cfg, mid)
    dados, erros = await _ler_formulario(request, db, cfg)
    if erros:
        return render(request, "contas/form.html",
                      {"cfg": cfg, "m": m, "f": _rascunho(dados), "erros": erros, "voltar": caminho_seguro(dados["voltar"], ""),
                       **_opcoes(db, cfg, m)}, status_code=400)
    _aplicar(db, m, dados)  # UPDATE: status não é alterado (campo oculto)
    db.commit()
    flash(request, f"{cfg['singular']} ID {m.id} atualizada com sucesso.")
    return RedirectResponse(caminho_seguro(dados["voltar"], f"/contas/{slug}/{m.id}"), status_code=303)


@router.post("/{slug}/{mid}/inativar")
async def inativar(request: Request, slug: str, mid: int, db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    m = _movimento(db, cfg, mid)
    voltar = (await request.form()).get("voltar", "")
    m.status = STATUS_INATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {m.id} inativada.", "warning")
    return RedirectResponse(caminho_seguro(voltar, f"/contas/{slug}"), status_code=303)


@router.post("/{slug}/{mid}/reativar")
async def reativar(request: Request, slug: str, mid: int, db: Session = Depends(get_db)):
    cfg = _cfg(slug)
    m = _movimento(db, cfg, mid)
    voltar = (await request.form()).get("voltar", "")
    m.status = STATUS_ATIVO
    db.commit()
    flash(request, f"{cfg['singular']} ID {m.id} reativada.")
    return RedirectResponse(caminho_seguro(voltar, f"/contas/{slug}"), status_code=303)
