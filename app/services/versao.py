"""Descobre o código (hash) da última atualização no GitHub para mostrar na tela principal.

Ordem de tentativa:
1. API pública do GitHub (variável GITHUB_REPO = usuario/repositorio) -> último commit da branch
2. Variável RENDER_GIT_COMMIT (o Render preenche sozinho com o commit que está no ar)
3. Comando git local (rodando na máquina de desenvolvimento)
"""
import json
import os
import subprocess
import time
import urllib.request

from app.config import BASE_DIR, GITHUB_BRANCH, GITHUB_REPO

_cache: dict = {"quando": 0.0, "dados": None}
_CACHE_SEGUNDOS = 300


def _via_github_api() -> dict | None:
    if not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "adm-financeiro"})
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        commit = dados.get("commit", {})
        return {
            "sha": dados.get("sha", ""),
            "mensagem": (commit.get("message") or "").splitlines()[0] if commit.get("message") else "",
            "data": (commit.get("committer") or {}).get("date", ""),
            "autor": (commit.get("author") or {}).get("name", ""),
            "url": dados.get("html_url", f"https://github.com/{GITHUB_REPO}"),
            "fonte": "GitHub",
        }
    except Exception:
        return None


def _via_render() -> dict | None:
    sha = os.getenv("RENDER_GIT_COMMIT")
    if not sha:
        return None
    url = f"https://github.com/{GITHUB_REPO}/commit/{sha}" if GITHUB_REPO else ""
    return {"sha": sha, "mensagem": "", "data": "", "autor": "", "url": url, "fonte": "Deploy"}


def _via_git_local() -> dict | None:
    try:
        saida = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%cI|%an"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=3,
        )
        if saida.returncode != 0 or not saida.stdout.strip():
            return None
        sha, msg, data, autor = (saida.stdout.strip().split("|", 3) + ["", "", "", ""])[:4]
        url = f"https://github.com/{GITHUB_REPO}/commit/{sha}" if GITHUB_REPO else ""
        return {"sha": sha, "mensagem": msg, "data": data, "autor": autor, "url": url, "fonte": "git local"}
    except Exception:
        return None


def ultima_atualizacao() -> dict:
    agora = time.time()
    if _cache["dados"] and agora - _cache["quando"] < _CACHE_SEGUNDOS:
        return _cache["dados"]
    dados = _via_github_api() or _via_render() or _via_git_local() or {
        "sha": "", "mensagem": "", "data": "", "autor": "", "url": "", "fonte": "indisponível",
    }
    dados["sha_curto"] = dados["sha"][:7] if dados["sha"] else "—"
    if dados.get("data"):
        # 2026-10-27T21:15:00Z -> 27/10/2026 21:15
        d = dados["data"].replace("T", " ")[:16]
        try:
            ano, mes, resto = d.split("-", 2)
            dia, hora = resto.split(" ")
            dados["data_br"] = f"{dia}/{mes}/{ano} {hora}"
        except ValueError:
            dados["data_br"] = d
    else:
        dados["data_br"] = ""
    _cache.update(quando=agora, dados=dados)
    return dados
