# Radar de Lastro

Site que acompanha eventos de crédito nos CRIs da carteira dos FIIs, só com dados públicos.

## Como funciona

1. `pipeline/holdings.py` baixa o informe trimestral estruturado (tabela de ativos) e o informe mensal de FII nos dados abertos da CVM e monta a carteira de CRI/CRA de cada fundo, com valor e % do PL.
2. `pipeline/collect.py` lista, na consulta pública do Fundos.Net (página de certificados), os fatos relevantes, comunicados, avisos e documentos de assembleia de CRI dos últimos 30 dias.
3. `pipeline/fetch_docs.py` baixa cada documento e guarda só o texto (`pdftotext`).
4. `pipeline/match.py` liga documento e fundo. Ordem de confiança: código IF na descrição do Fundos.Net, código IF citado no texto, e por fim securitizadora + emissão + série (desligado para securitizadoras que repetem numeração de emissão, como a Opea).
5. `pipeline/classify.py` classifica o evento por regras e define a severidade.
6. `pipeline/build.py` grava `site/data.json`, que o `site/index.html` lê.

`python pipeline/run.py 30` roda tudo. O workflow em `.github/workflows/atualizar.yml` roda de hora em hora (6h às 23h) e publica o site no GitHub Pages.

## Limitações conhecidas

- A carteira vem do informe trimestral: é uma foto com alguns meses de atraso.
- Cerca de 30% do valor em CRI nos informes não traz o código IF; parte disso cruza por emissão e série, parte não cruza.
- A classificação é por regras e erra. Todo evento linka o documento original.
- O de-para de nomes de securitizadora (`SECURITIZADORAS` em `match.py`) é mantido à mão.

## Dependências

Python 3.11+, `pandas`, `requests` e `pdftotext` (pacote `poppler-utils`).

## Domínio radardelastro.com.br

1. No GitHub: Settings > Pages > Source: **GitHub Actions**. Em **Custom domain**, preencha `radardelastro.com.br` e marque **Enforce HTTPS** quando liberar.
2. No Registro.br, em "Editar zona" do domínio, crie quatro registros **A** para o domínio raiz apontando para o GitHub Pages:
   `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   e um **CNAME** `www` apontando para `SEU-USUARIO.github.io`.
3. A propagação do DNS pode levar algumas horas.
