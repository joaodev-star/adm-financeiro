"""Funções auxiliares: normalização de texto, CPF/CNPJ, datas, moeda e busca."""
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def sem_acento(texto: str | None) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str | None) -> str:
    """MAIÚSCULO, sem acento e sem espaços duplicados — usado para comparar nomes."""
    return re.sub(r"\s+", " ", sem_acento(texto).upper()).strip()


def so_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def formatar_documento(doc: str | None) -> str:
    d = so_digitos(doc)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return doc or ""


def rotulo_documento(doc: str | None) -> str:
    d = so_digitos(doc)
    if len(d) == 14:
        return "CNPJ"
    if len(d) == 11:
        return "CPF"
    return "CPF/CNPJ"


def para_decimal(valor) -> Decimal:
    """Aceita 1234.56, "1234.56", "1.234,56", "R$ 1.234,56"."""
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    s = str(valor).replace("R$", "").replace(" ", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def para_data(valor) -> date | None:
    """Aceita YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY e datetime."""
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def moeda(valor) -> str:
    v = para_decimal(valor)
    texto = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def data_br(valor) -> str:
    d = para_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def termos_busca(q: str | None) -> list[str]:
    """Busca por mais de um elemento: separa por vírgula, ponto e vírgula ou espaço."""
    if not q:
        return []
    return [normalizar(t) for t in re.split(r"[,;\s]+", q) if t.strip()]


def corresponde(termos: list[str], campos: list) -> bool:
    """Todos os termos precisam aparecer em pelo menos um dos campos (sem diferenciar acento/maiúscula).
    Para CPF/CNPJ também compara só os dígitos (pode buscar com ou sem pontuação)."""
    alvo = " ".join(normalizar(str(c)) for c in campos if c is not None)
    alvo_digitos = " ".join(so_digitos(str(c)) for c in campos if c is not None)
    for termo in termos:
        dig = so_digitos(termo)
        if termo in alvo:
            continue
        if dig and len(dig) >= 3 and dig in alvo_digitos:
            continue
        return False
    return True


def caminho_seguro(url: str | None, padrao: str) -> str:
    """Só aceita redirecionar para caminhos internos (evita open redirect)."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return padrao
