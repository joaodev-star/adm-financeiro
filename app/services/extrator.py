"""ETAPA 1 — Extração dos dados da nota fiscal (PDF) com o Google Gemini, devolvendo JSON."""
import json
import re

from app.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_MODEL
from app.seed import DESPESAS_PADRAO


class ErroExtracao(Exception):
    pass


PROMPT = f"""
Você é um assistente especialista em notas fiscais brasileiras (NF-e / DANFE).
Analise o PDF anexado e extraia os dados abaixo. Responda SOMENTE com um JSON válido,
sem comentários e sem markdown, exatamente neste formato:

{{
  "fornecedor": {{
    "razao_social": "nome do EMITENTE da nota",
    "fantasia": "nome fantasia do emitente ou null",
    "cnpj": "CNPJ do emitente no formato 00.000.000/0000-00"
  }},
  "faturado": {{
    "nome_completo": "nome do DESTINATÁRIO/REMETENTE (quem foi faturado)",
    "cpf": "CPF ou CNPJ do destinatário, com pontuação"
  }},
  "numero_nota_fiscal": "número da nota",
  "data_emissao": "AAAA-MM-DD",
  "descricao_produtos": ["descrição de cada produto/serviço"],
  "quantidade_parcelas": 1,
  "parcelas": [
    {{"numero": 1, "data_vencimento": "AAAA-MM-DD", "valor": 0.00}}
  ],
  "valor_total": 0.00,
  "classificacoes_despesa": ["CATEGORIA"]
}}

Regras:
- Datas sempre no formato AAAA-MM-DD. Valores numéricos com ponto decimal (ex.: 1530.75).
- Parcelas: use as duplicatas/fatura da nota. Se não houver duplicatas, gere UMA parcela com o
  valor total e vencimento igual à data de emissão.
- "classificacoes_despesa": classifique a despesa em UMA OU MAIS destas categorias, conforme os
  produtos/serviços da nota (use o texto exatamente como abaixo):
  {", ".join(DESPESAS_PADRAO)}.
  Exemplos: sementes, fertilizantes, defensivos -> INSUMOS AGRÍCOLAS; peças, pneus, óleo, filtros,
  combustível, manutenção de máquinas -> MANUTENÇÃO E OPERAÇÃO; energia, água, construção, reformas
  -> INFRAESTRUTURA E UTILIDADES; frete, colheita terceirizada, transporte -> SERVIÇOS OPERACIONAIS;
  escritório, contabilidade, honorários -> ADMINISTRATIVAS; seguros -> SEGUROS E PROTEÇÃO;
  tributos -> IMPOSTOS E TAXAS; máquinas, equipamentos, veículos novos -> INVESTIMENTOS;
  salários, EPIs, uniformes -> RECURSOS HUMANOS.
- Se um campo não existir na nota, use null.
"""


def _limpar_json(texto: str) -> dict:
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.MULTILINE).strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ErroExtracao("A IA não devolveu um JSON válido.")
    try:
        return json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError as e:
        raise ErroExtracao(f"JSON inválido retornado pela IA: {e}") from e


def extrair_nota(pdf_bytes: bytes) -> dict:
    """Envia o PDF para o Gemini e devolve o dicionário extraído."""
    if not GEMINI_API_KEY:
        raise ErroExtracao("Chave do Gemini não configurada (variável GEMINI_API_KEY).")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ErroExtracao("O arquivo enviado não é um PDF válido.")

    from google import genai
    from google.genai import errors, types

    cliente = genai.Client(api_key=GEMINI_API_KEY)
    modelos = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    ultimo_erro = None

    for modelo in modelos:
        try:
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            dados = _limpar_json(resposta.text)
            dados["_modelo"] = modelo
            return dados
        except errors.ClientError as e:
            # 404 = modelo não existe para esta chave -> tenta o próximo
            if getattr(e, "code", None) == 404:
                ultimo_erro = e
                continue
            if getattr(e, "code", None) in (401, 403) or "API key" in str(e):
                raise ErroExtracao("Chave do Gemini inválida ou sem permissão.") from e
            if getattr(e, "code", None) == 429:
                raise ErroExtracao("Limite de uso da API do Gemini atingido. Tente novamente em instantes.") from e
            raise ErroExtracao(f"Erro na API do Gemini: {e}") from e
        except errors.ServerError as e:
            ultimo_erro = e
            continue
    raise ErroExtracao(f"Não foi possível usar nenhum modelo do Gemini. Último erro: {ultimo_erro}")
