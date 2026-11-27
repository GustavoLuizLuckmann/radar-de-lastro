carregar().then(d=>{
  const c=d.carteira, v=c.valor_por_metodo||{};
  const fatos=[
    [c.fundos_com_cri, 'FIIs com CRI na carteira'],
    [brl(c.valor_total), 'aplicados em CRI pelos FIIs'],
    ...(d.fiagro && d.fiagro.fundos ? [[d.fiagro.com_cra, 'Fiagros com CRA na carteira'], [brl(d.fiagro.valor_cra), 'aplicados em CRA pelos Fiagros'], [d.fiagro.com_relatorio, 'Fiagros com relatório gerencial lido']] : []),
    [pct(v.if||0), 'do valor com código IF no informe'],
    [d.eventos.length, 'eventos no histórico'],
    [dia(c.data_referencia).toLocaleDateString('pt-BR'), 'data da carteira de referência'],
    [dia(d.janela.inicio).toLocaleDateString('pt-BR'), 'início do histórico de documentos'],
  ];
  document.getElementById('facts').innerHTML=fatos.map(([n,t])=>`<div><b>${esc(n)}</b><span>${esc(t)}</span></div>`).join('');
  document.getElementById('gloss').innerHTML=Object.entries(EXPLICA).map(([t,x])=>`<div><dt>${esc(t)}</dt><dd>${esc(x)}</dd></div>`).join('');
}).catch(()=>{
  document.getElementById('gloss').innerHTML=Object.entries(EXPLICA).map(([t,x])=>`<div><dt>${esc(t)}</dt><dd>${esc(x)}</dd></div>`).join('');
});
