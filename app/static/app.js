// Indexação (ordenação) por coluna: clique no cabeçalho para ordenar crescente/decrescente
document.querySelectorAll("table.ordenavel").forEach((tabela) => {
  const cabecalhos = tabela.querySelectorAll("th[data-ordenar]");
  cabecalhos.forEach((th) => {
    th.addEventListener("click", () => {
      const indice = Array.from(th.parentNode.children).indexOf(th);
      const crescente = !th.classList.contains("asc");
      cabecalhos.forEach((h) => h.classList.remove("asc", "desc"));
      th.classList.add(crescente ? "asc" : "desc");

      const tbody = tabela.tBodies[0];
      const linhas = Array.from(tbody.rows).filter((r) => !r.classList.contains("tabela-vazia"));
      const tipo = th.dataset.ordenar; // texto | numero | data
      const valor = (linha) => {
        const celula = linha.cells[indice];
        const bruto = (celula.dataset.valor ?? celula.innerText).trim();
        if (tipo === "numero") return parseFloat(bruto) || 0;
        return bruto.toLocaleLowerCase("pt-BR");
      };
      linhas.sort((a, b) => {
        const va = valor(a), vb = valor(b);
        if (va < vb) return crescente ? -1 : 1;
        if (va > vb) return crescente ? 1 : -1;
        return 0;
      });
      linhas.forEach((l) => tbody.appendChild(l));
    });
  });
});

// Confirmação antes de inativar / reativar
document.querySelectorAll("form[data-confirmar]").forEach((form) => {
  form.addEventListener("submit", (e) => {
    if (!confirm(form.dataset.confirmar)) e.preventDefault();
  });
});

// Máscara simples de CPF/CNPJ
document.querySelectorAll("input[data-mascara='documento']").forEach((input) => {
  input.addEventListener("input", () => {
    let d = input.value.replace(/\D/g, "").slice(0, 14);
    if (d.length <= 11) {
      d = d.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
    } else {
      d = d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
           .replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
    }
    input.value = d;
  });
});

// Botão de envio com indicador de carregamento (upload da nota)
document.querySelectorAll("form[data-carregando]").forEach((form) => {
  form.addEventListener("submit", () => {
    const btn = form.querySelector("button[type=submit]");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> ' + form.dataset.carregando;
    }
  });
});
