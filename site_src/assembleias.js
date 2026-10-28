const P = { q:'', mine:store.get('rl-mine',false) };

function passa(e){
  if(!fundosVisiveis(e).length) return false;
  if(P.mine && !afetaMeus(e)) return false;
  const q=P.q.trim().toLowerCase();
  if(q){
    const hay=[e.tipo,e.operacao,e.securitizadora,secNome(e.securitizadora),...e.codigos_if,...e.fundos.map(f=>(f.ticker||'')+' '+f.fundo+' '+(f.gestor||''))].join(' ').toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}

function item(e, dataRef, extra){
  const d=dia(dataRef), fs=fundosVisiveis(e).slice().sort((a,b)=>(b.pct_pl||0)-(a.pct_pl||0));
  return `<a class="ag-row" href="index.html#${e.id}">
    <div class="cal"><b>${d.getDate()}</b><span>${MESES[d.getMonth()]}</span></div>
    <div><div class="ev-top"><span class="tag ${e.severidade}">${SEV[e.severidade]}</span><span class="what">${esc(e.tipo)}</span></div>
      <div class="who">${esc(opNome(e.operacao))}, CRI da ${e.emissao}ª emissão, ${esc(secNome(e.securitizadora))}</div>
      <div class="chips">${fs.slice(0,5).map(f=>`<span class="chip${S.carteira.has(f.cnpj_fundo)?' mine':''}"><b class="${f.ticker?'tk':''}">${esc(rotulo(f))}</b><span>${pct(f.pct_pl)}</span></span>`).join('')}${fs.length>5?`<span class="chip"><span>mais ${fs.length-5}</span></span>`:''}</div></div>
    ${extra}
  </a>`;
}

function render(){
  const assem=DATA.eventos.filter(e=>e.categoria==='Assembleia' || e.data_assembleia);
  montarGestoras(document.getElementById('gestora'), assem, render);
  const hoje=isoHoje();
  const prox=assem.filter(e=>e.data_assembleia && e.data_assembleia>=hoje && passa(e)).sort((a,b)=>a.data_assembleia.localeCompare(b.data_assembleia));
  document.getElementById('n-prox').textContent=prox.length+(prox.length===1?' assembleia':' assembleias');
  document.getElementById('prox').innerHTML=prox.length?prox.map(e=>{const n=diasEntre(hoje,e.data_assembleia);
      return item(e,e.data_assembleia,`<span class="in${n<=7?' soon':''}">${n===0?'hoje':'em '+n+(n===1?' dia':' dias')}</span>`);}).join('<hr style="border:0;border-top:1px solid var(--line);margin:0">')
    :'<p class="empty"><b>Nenhuma assembleia futura com data identificada.</b>Quando um edital novo for publicado, ele aparece aqui.</p>';

  const per=assem.filter(e=>noPeriodo(e.data) && passa(e)).sort((a,b)=>b.data.localeCompare(a.data));
  document.getElementById('h-per').textContent='Documentos de assembleia '+periodoTexto();
  document.getElementById('n-per').textContent=per.length+(per.length===1?' documento':' documentos');
  document.getElementById('periodo-lista').innerHTML=per.length?per.map(e=>item(e,e.data,`<span class="in" style="color:var(--muted)">${esc(fase(e))}</span>`)).join('<hr style="border:0;border-top:1px solid var(--line);margin:0">')
    :'<p class="empty"><b>Nenhum documento de assembleia com esses filtros.</b>Amplie o período ou limpe a busca.</p>';
}

carregar().then(()=>{
  montarPeriodo(document.getElementById('periodo'), render);
  const q=document.getElementById('q'); q.addEventListener('input',()=>{P.q=q.value; render();});
  const mine=document.getElementById('mine'); mine.checked=P.mine;
  mine.addEventListener('change',()=>{P.mine=mine.checked; store.set('rl-mine',P.mine); render();});
  ligarBolsa(document.getElementById('listed'), render);
  render();
}).catch(falhaCarga);
