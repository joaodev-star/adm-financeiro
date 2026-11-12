"""ETAPA 2 — Análise dos dados extraídos e lançamento no banco.

1. Consulta se FORNECEDOR, FATURADO e cada classificação de DESPESA existem.
2. Mostra o resultado na tela (EXISTE – ID: x / NÃO EXISTE).
3. Cria o que não existe, cria o MOVIMENTOCONTAS (APAGAR) e suas PARCELACONTAS.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    STATUS_ATIVO,
    STATUS_INATIVO,
    Classificacao,
    MovimentoContas,
    ParcelaContas,
    Pessoa,
)
from app.utils import (
    formatar_documento,
    normalizar,
    para_data,
    para_decimal,
    rotulo_documento,
    so_digitos,
)


class ErroLancamento(Exception):
    pass


# ---------------------------------------------------------------------------
# Normalização do JSON vindo da etapa 1 (aceita variações de nomes de campos)
# ---------------------------------------------------------------------------
def _pegar(d: dict | None, *chaves, padrao=None):
    if not isinstance(d, dict):
        return padrao
    for c in chaves:
        if c in d and d[c] not in (None, ""):
            return d[c]
    return padrao


def _lista_classificacoes(dados: dict) -> list[str]:
    bruto = _pegar(
        dados, "classificacoes_despesa", "classificacao_despesa", "classificacoes",
        "classificacao", "despesas", "despesa", padrao=[],
    )
    if isinstance(bruto, (str, dict)):
        bruto = [bruto]
    nomes = []
    for item in bruto or []:
        nome = _pegar(item, "descricao", "nome", "categoria") if isinstance(item, dict) else item
        nome = normalizar(nome) and str(nome).strip().upper()
        if nome and normalizar(nome) not in {normalizar(n) for n in nomes}:
            nomes.append(nome)
    return nomes


def normalizar_dados(dados: dict) -> dict:
    forn = _pegar(dados, "fornecedor", "emitente", padrao={}) or {}
    fat = _pegar(dados, "faturado", "destinatario", "remetente", padrao={}) or {}

    data_emissao = para_data(_pegar(dados, "data_emissao", "dataEmissao", "emissao"))
    produtos = _pegar(dados, "descricao_produtos", "produtos", "descricao", padrao=[])
    if isinstance(produtos, list):
        produtos = [(_pegar(p, "descricao", "nome") if isinstance(p, dict) else p) for p in produtos]
        descricao = "; ".join(str(p) for p in produtos if p)
    else:
        descricao = str(produtos or "")

    parcelas_brutas = _pegar(dados, "parcelas", "duplicatas", padrao=[]) or []
    valor_total = para_decimal(_pegar(dados, "valor_total", "valorTotal", "total"))

    parcelas = []
    for p in parcelas_brutas:
        if not isinstance(p, dict):
            continue
        parcelas.append({
            "data_vencimento": para_data(_pegar(p, "data_vencimento", "vencimento", "dataVencimento")),
            "valor": para_decimal(_pegar(p, "valor", "valor_parcela")),
        })
    if not parcelas:
        parcelas = [{"data_vencimento": data_emissao, "valor": valor_total}]

    # Parcelas sem valor: divide o total igualmente
    if valor_total and all(p["valor"] == 0 for p in parcelas):
        base = (valor_total / len(parcelas)).quantize(Decimal("0.01"))
        for p in parcelas:
            p["valor"] = base
        parcelas[-1]["valor"] = valor_total - base * (len(parcelas) - 1)
    if not valor_total:
        valor_total = sum((p["valor"] for p in parcelas), Decimal("0"))

    total_parcelas = len(parcelas)
    for i, p in enumerate(parcelas, start=1):
        p["identificacao"] = "ÚNICA" if total_parcelas == 1 else f"{i}/{total_parcelas}"
        p["data_vencimento"] = p["data_vencimento"] or data_emissao or date.today()

    return {
        "fornecedor": {
            "razao_social": str(_pegar(forn, "razao_social", "razaoSocial", "nome", padrao="")).strip(),
            "fantasia": _pegar(forn, "fantasia", "nome_fantasia"),
            "documento": so_digitos(_pegar(forn, "cnpj", "cpf", "documento", "cpf_cnpj", padrao="")),
        },
        "faturado": {
            "razao_social": str(_pegar(fat, "nome_completo", "razao_social", "nome", padrao="")).strip(),
            "documento": so_digitos(_pegar(fat, "cpf", "cnpj", "documento", "cpf_cnpj", padrao="")),
        },
        "numero_nota_fiscal": str(_pegar(dados, "numero_nota_fiscal", "numero_nota", "numero", padrao="")).strip(),
        "data_emissao": data_emissao,
        "descricao": descricao,
        "valor_total": valor_total,
        "parcelas": parcelas,
        "classificacoes": _lista_classificacoes(dados),
    }


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def buscar_pessoa(db: Session, tipo: str, nome: str, documento: str) -> Pessoa | None:
    candidatos = []
    if documento:
        candidatos = db.scalars(
            select(Pessoa).where(Pessoa.tipo == tipo, Pessoa.documento == documento)
        ).all()
    if not candidatos and nome:
        alvo = normalizar(nome)
        todos = db.scalars(select(Pessoa).where(Pessoa.tipo == tipo)).all()
        candidatos = [
            p for p in todos
            if normalizar(p.razao_social) == alvo and (not documento or not p.documento)
        ]
    if not candidatos:
        return None
    candidatos.sort(key=lambda p: (p.status != STATUS_ATIVO, p.id))  # prioriza ATIVO
    return candidatos[0]


def buscar_classificacao(db: Session, tipo: str, descricao: str) -> Classificacao | None:
    alvo = normalizar(descricao)
    todas = db.scalars(select(Classificacao).where(Classificacao.tipo == tipo)).all()
    achadas = [c for c in todas if normalizar(c.descricao) == alvo]
    achadas.sort(key=lambda c: (c.status != STATUS_ATIVO, c.id))
    return achadas[0] if achadas else None


def _resultado_pessoa(p: Pessoa | None, nome: str, documento: str) -> dict:
    return {
        "razao_social": nome,
        "documento": documento,
        "documento_fmt": formatar_documento(documento),
        "rotulo": rotulo_documento(documento),
        "existe": p is not None,
        "id": p.id if p else None,
        "status": p.status if p else None,
    }


def analisar(db: Session, dados_brutos: dict) -> dict:
    d = normalizar_dados(dados_brutos)
    forn = buscar_pessoa(db, "FORNECEDOR", d["fornecedor"]["razao_social"], d["fornecedor"]["documento"])
    fat = buscar_pessoa(db, "FATURADO", d["faturado"]["razao_social"], d["faturado"]["documento"])

    despesas = []
    for nome in d["classificacoes"]:
        c = buscar_classificacao(db, "DESPESA", nome)
        despesas.append({
            "descricao": nome,
            "existe": c is not None,
            "id": c.id if c else None,
            "status": c.status if c else None,
        })

    duplicado = None
    if forn and d["numero_nota_fiscal"]:
        duplicado = db.scalar(
            select(MovimentoContas.id).where(
                MovimentoContas.tipo == "APAGAR",
                MovimentoContas.pessoa_id == forn.id,
                MovimentoContas.numero_nota_fiscal == d["numero_nota_fiscal"],
                MovimentoContas.status == STATUS_ATIVO,
            )
        )

    erros = []
    if not d["fornecedor"]["razao_social"]:
        erros.append("Fornecedor não identificado na nota.")
    if not d["faturado"]["razao_social"]:
        erros.append("Faturado não identificado na nota.")
    if not d["classificacoes"]:
        erros.append("Nenhuma classificação de despesa foi informada.")
    if d["valor_total"] <= 0:
        erros.append("Valor total da nota não identificado.")

    return {
        "dados": d,
        "fornecedor": _resultado_pessoa(forn, d["fornecedor"]["razao_social"], d["fornecedor"]["documento"]),
        "faturado": _resultado_pessoa(fat, d["faturado"]["razao_social"], d["faturado"]["documento"]),
        "despesas": despesas,
        "duplicado_id": duplicado,
        "erros": erros,
    }


# ---------------------------------------------------------------------------
# Lançamento
# ---------------------------------------------------------------------------
def _obter_ou_criar_pessoa(db: Session, tipo: str, nome: str, documento: str, fantasia=None) -> tuple[Pessoa, str]:
    p = buscar_pessoa(db, tipo, nome, documento)
    if p is None:
        p = Pessoa(
            tipo=tipo, razao_social=nome.upper(), fantasia=(fantasia or None),
            documento=documento or None, status=STATUS_ATIVO,
        )
        db.add(p)
        db.flush()
        return p, "CRIADO"
    if p.status == STATUS_INATIVO:
        p.status = STATUS_ATIVO
        return p, "REATIVADO"
    return p, "EXISTENTE"


def _obter_ou_criar_classificacao(db: Session, descricao: str) -> tuple[Classificacao, str]:
    c = buscar_classificacao(db, "DESPESA", descricao)
    if c is None:
        c = Classificacao(tipo="DESPESA", descricao=descricao.upper(), status=STATUS_ATIVO)
        db.add(c)
        db.flush()
        return c, "CRIADO"
    if c.status == STATUS_INATIVO:
        c.status = STATUS_ATIVO
        return c, "REATIVADO"
    return c, "EXISTENTE"


def lancar(db: Session, dados_brutos: dict) -> dict:
    """Cria (se for o caso) fornecedor, faturado e despesas, depois o movimento e as parcelas.
    Tudo em uma única transação: se algo falhar, nada é gravado."""
    analise = analisar(db, dados_brutos)
    if analise["erros"]:
        raise ErroLancamento(" ".join(analise["erros"]))
    if analise["duplicado_id"]:
        raise ErroLancamento(
            f"Esta nota já foi lançada para este fornecedor (Movimento ID {analise['duplicado_id']})."
        )

    d = analise["dados"]
    try:
        fornecedor, acao_forn = _obter_ou_criar_pessoa(
            db, "FORNECEDOR", d["fornecedor"]["razao_social"], d["fornecedor"]["documento"], d["fornecedor"]["fantasia"]
        )
        faturado, acao_fat = _obter_ou_criar_pessoa(
            db, "FATURADO", d["faturado"]["razao_social"], d["faturado"]["documento"]
        )
        classificacoes, acoes_desp = [], []
        for nome in d["classificacoes"]:
            c, acao = _obter_ou_criar_classificacao(db, nome)
            classificacoes.append(c)
            acoes_desp.append({"id": c.id, "descricao": c.descricao, "acao": acao})

        mov = MovimentoContas(
            tipo="APAGAR",
            numero_nota_fiscal=d["numero_nota_fiscal"] or None,
            data_emissao=d["data_emissao"],
            descricao=d["descricao"][:2000] if d["descricao"] else None,
            valor_total=d["valor_total"],
            pessoa_id=fornecedor.id,
            faturado_id=faturado.id,
            origem="NOTA_FISCAL",
            status=STATUS_ATIVO,
        )
        mov.classificacoes = classificacoes
        for p in d["parcelas"]:
            mov.parcelas.append(ParcelaContas(
                identificacao=p["identificacao"],
                data_vencimento=p["data_vencimento"],
                valor_parcela=p["valor"],
            ))
        db.add(mov)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "movimento_id": mov.id,
        "fornecedor": {"id": fornecedor.id, "razao_social": fornecedor.razao_social, "acao": acao_forn},
        "faturado": {"id": faturado.id, "razao_social": faturado.razao_social, "acao": acao_fat},
        "despesas": acoes_desp,
        "parcelas": [
            {"id": p.id, "identificacao": p.identificacao, "data_vencimento": p.data_vencimento, "valor": p.valor_parcela}
            for p in mov.parcelas
        ],
        "valor_total": mov.valor_total,
        "numero_nota_fiscal": mov.numero_nota_fiscal,
    }
