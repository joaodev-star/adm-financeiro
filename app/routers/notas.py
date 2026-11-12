"""Etapa 1 + Etapa 2 — Upload da nota fiscal, extração com IA, análise no banco e lançamento."""
import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import MAX_PDF_MB
from app.database import get_db
from app.services.analise import ErroLancamento, analisar, lancar
from app.services.extrator import ErroExtracao, extrair_nota
from app.templating import render

router = APIRouter(prefix="/notas")


def _pagina_upload(request: Request, erro: str | None = None, json_texto: str = "", status_code: int = 200):
    return render(request, "notas/upload.html", {"erro": erro, "json_texto": json_texto}, status_code=status_code)


def _pagina_analise(request: Request, db: Session, dados: dict, origem: str):
    analise = analisar(db, dados)
    return render(request, "notas/analise.html", {
        "analise": analise,
        "json_bonito": json.dumps(dados, ensure_ascii=False, indent=2),
        "json_compacto": json.dumps(dados, ensure_ascii=False),
        "origem": origem,
        "modelo": dados.get("_modelo"),
    })


@router.get("")
def upload_form(request: Request):
    return _pagina_upload(request)


@router.post("/extrair")
def extrair(request: Request, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    """ETAPA 1: lê o PDF e extrai os dados com o Gemini. ETAPA 2: já mostra a análise no banco."""
    conteudo = arquivo.file.read(MAX_PDF_MB * 1024 * 1024 + 1)
    if not conteudo:
        return _pagina_upload(request, "Selecione um arquivo PDF.", status_code=400)
    if len(conteudo) > MAX_PDF_MB * 1024 * 1024:
        return _pagina_upload(request, f"O PDF deve ter no máximo {MAX_PDF_MB} MB.", status_code=400)
    try:
        dados = extrair_nota(conteudo)
    except ErroExtracao as e:
        return _pagina_upload(request, str(e), status_code=422)
    return _pagina_analise(request, db, dados, origem=f"PDF: {arquivo.filename}")


@router.post("/analisar-json")
def analisar_json(request: Request, json_texto: str = Form(""), db: Session = Depends(get_db)):
    """Alternativa sem IA: cola o JSON gerado na etapa 1 para testar a análise."""
    try:
        dados = json.loads(json_texto)
        if not isinstance(dados, dict):
            raise ValueError
    except ValueError:
        return _pagina_upload(request, "JSON inválido. Confira o conteúdo colado.", json_texto, status_code=400)
    return _pagina_analise(request, db, dados, origem="JSON informado manualmente")


@router.post("/lancar")
def lancar_nota(request: Request, dados_json: str = Form(...), db: Session = Depends(get_db)):
    """Cria fornecedor/faturado/despesa (se for o caso), o movimento e suas parcelas."""
    try:
        dados = json.loads(dados_json)
        resultado = lancar(db, dados)
    except (ValueError, ErroLancamento) as e:
        return _pagina_upload(request, f"Não foi possível lançar: {e}", status_code=400)
    return render(request, "notas/sucesso.html", {"r": resultado})
