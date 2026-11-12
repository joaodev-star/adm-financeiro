# Projeto Administrativo-Financeiro — N2 (Etapas 1 e 2)

Sistema web em **Python + FastAPI** que lê notas fiscais em PDF com IA (**Google Gemini**), verifica no banco se
fornecedor, faturado e classificação de despesa já existem, cria o que faltar e lança a **conta a pagar com suas parcelas**.

Disciplina: Projeto Administrativo-Financeiro — UniRV · Aluno: João Pedro Alves Pereira

---

## Funcionalidades

| Requisito | Onde está |
|---|---|
| MANTER FORNECEDOR / CLIENTE / FATURADO → **MANTER PESSOAS** | Menu *Pessoas* (`/pessoas/fornecedor`, `/pessoas/cliente`, `/pessoas/faturado`) |
| MANTER TIPO DE RECEITA / DESPESA → **MANTER CLASSIFICAÇÃO** | Menu *Classificação* (`/classificacao/despesa`, `/classificacao/receita`) |
| REGISTRAR CONTAS A PAGAR / RECEBER → **REGISTRAR CONTAS** | Menu *Contas* (`/contas/pagar`, `/contas/receber`) |
| Etapa 1 — extração da nota fiscal (PDF → JSON) com LLM | *Lançar Nota Fiscal (IA)* (`/notas`) |
| Etapa 2 — consulta EXISTE / NÃO EXISTE e lançamento | Tela de análise após a extração |
| Código da última atualização no GitHub na tela principal | Dashboard (`/`) e rodapé do menu |
| Login e senha | `/login` |

### Regras de negócio
- Cadastros **não podem ser excluídos**: o botão *Excluir* faz exclusão lógica (`STATUS = INATIVO`).
- Registros inativos podem ser **reativados** (busque com o filtro *Inativos* e clique em *Reativar*).
- Uma conta a pagar pode ter **uma ou mais classificações** (Tipos de Despesa); a receber, uma ou mais Tipos de Receita.
- Uma conta pode ter **uma ou mais parcelas** com vencimentos distintos (identificação `ÚNICA`, `1/3`, `2/3`...).

### Layout (recomendações do professor)
- a. A tabela de registros abre **vazia**.
- b. Os dados são carregados pelos botões **Buscar** ou **Todos**.
- c. **Todos** carrega apenas `status = ATIVO`.
- d. **Indexação por coluna**: clique no cabeçalho para ordenar (crescente/decrescente).
- e. **Busca por mais de um elemento**: termos separados por espaço ou vírgula (ex.: `iguaçu 11.111`).
- f. Duas ações na tabela: **Editar / Excluir (lógico)**.
- g. No CREATE o campo `STATUS` é oculto e sempre `ATIVO`.
- h. No UPDATE o campo `STATUS` é oculto (não é alterado).
- i. No DELETE o `STATUS` vira `INATIVO`.

### Fluxo da Etapa 2
1. Envie o PDF em **Lançar Nota Fiscal (IA)**. O Gemini devolve o JSON (Etapa 1).
2. O sistema consulta o banco e mostra:
   ```
   FORNECEDOR
   IGUAÇU MAQUINAS LTDA
   CNPJ: 11.111.111/0001-00
   NÃO EXISTE

   FATURADO
   BELTRANO DA SILVA
   CPF: 999.999.999-99
   EXISTE – ID: 19

   DESPESA
   MANUTENÇÃO E OPERAÇÃO
   EXISTE – ID: 22
   ```
3. Ao clicar em **Confirmar lançamento**, em uma única transação:
   1. cria o novo FORNECEDOR (se for o caso);
   2. cria o novo FATURADO (se for o caso);
   3. cria a nova DESPESA (se for o caso);
   4. cria o registro em MOVIMENTOCONTAS (`APAGAR`) e suas PARCELACONTAS;
   5. informa que o registro foi lançado com sucesso, listando as entidades afetadas.

Notas já lançadas para o mesmo fornecedor são detectadas e bloqueadas (evita duplicidade).
Para testar sem a chave da IA, use *“colar o JSON já extraído”* na mesma tela.
Há uma nota de exemplo em `exemplos/nota_fiscal_exemplo.pdf`.

---

## Modelo de dados

```
PESSOAS (id, tipo[FORNECEDOR|CLIENTE|FATURADO], razao_social, fantasia, documento, email, telefone, status)
CLASSIFICACAO (id, tipo[RECEITA|DESPESA], descricao, status)
MOVIMENTOCONTAS (id, tipo[APAGAR|ARECEBER], numero_nota_fiscal, data_emissao, descricao, valor_total,
                 pessoa_id → PESSOAS, faturado_id → PESSOAS, origem, status)
PARCELACONTAS (id, movimento_id → MOVIMENTOCONTAS, identificacao, data_vencimento, valor_parcela, situacao)
MOVIMENTO_CLASSIFICACAO (movimento_id, classificacao_id)   ← N:N
```

As tabelas são criadas automaticamente na primeira execução, junto com as classificações padrão de despesa e receita.

---

## Rodando localmente

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env      # (Linux/Mac: cp .env.example .env) e preencha a GEMINI_API_KEY
uvicorn app.main:app --reload
```

Acesse http://127.0.0.1:8000 — login padrão `admin` / `admin123` (altere no `.env`).
Sem `DATABASE_URL` o sistema usa SQLite (`adm_financeiro.db`).

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `GEMINI_API_KEY` | Chave da API do Google Gemini (https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | Modelo (padrão `gemini-3.5-flash`; se não existir, tenta outros automaticamente) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Login do sistema |
| `SECRET_KEY` | Chave da sessão (texto aleatório) |
| `DATABASE_URL` | PostgreSQL em produção (vazio = SQLite) |
| `GITHUB_REPO` | `usuario/repositorio` — mostra o último commit na tela principal |

---

## Hospedagem (Render)

1. Suba o projeto para o GitHub (veja abaixo).
2. Em https://render.com → **New → Blueprint** → selecione o repositório. O `render.yaml` cria o site e o PostgreSQL.
3. Preencha as variáveis pedidas: `ADMIN_PASSWORD`, `GEMINI_API_KEY` e `GITHUB_REPO` (ex.: `joaopedro/adm-financeiro`).
4. Após o deploy, o link fica no formato `https://adm-financeiro-xxxx.onrender.com`.

> Plano gratuito do Render: o site “dorme” após 15 min sem acesso (o primeiro acesso demora ~1 min) e o
> PostgreSQL gratuito expira em 30 dias. Se precisar de mais tempo, crie um banco gratuito no https://neon.tech e
> coloque a URL dele em `DATABASE_URL`.

## Subindo para o GitHub

```bash
git init
git add .
git commit -m "Projeto Adm-Financeiro - N2 Etapa 2"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/adm-financeiro.git
git push -u origin main
```

O `.env` e o `README.txt` (com a chave) estão no `.gitignore` — **nunca suba a chave da API para o GitHub**.

---

## Estrutura

```
app/
  main.py               # app FastAPI, login, dashboard
  config.py             # variáveis de ambiente
  database.py, models.py, seed.py, utils.py
  routers/              # pessoas, classificacao, contas, notas
  services/
    extrator.py         # Etapa 1 — PDF → JSON com Gemini
    analise.py          # Etapa 2 — consulta e lançamento
    versao.py           # último commit do GitHub
  templates/            # telas (Jinja2 + Bootstrap)
  static/               # CSS, JS e Bootstrap local
exemplos/nota_fiscal_exemplo.pdf
render.yaml             # deploy no Render
```
