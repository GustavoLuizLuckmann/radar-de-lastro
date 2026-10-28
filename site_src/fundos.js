const P = { q:'', mine:store.get('rl-mine',false), ordem:'total' };

function linhas(){
  const eventos=DATA.eventos.filter(e=>noPeriodo(e.data));
  const q=P.q.trim().toLowerCase();
  let fs=calcExpo(eventos).filter(passaFundo);
  if(P.mine) fs=fs.filter(f=>S.carteira.has(f.cnpj_fundo));
  if(q) fs=fs.filter(f=>((f.ticker||'')+' '+f.fundo+' '+(f.gestor||'')+' '+gestoraCurta(f.gestor)).toLowerCase().includes(q));
  const v=f=>P.ordem==='total'?f.total:P.ordem==='eventos'?f.eventos:f.expo[P.ordem];
  return fs.sort((a,b)=>v(b)-v(a)||b.total-a.total);
}

function render(){
  montarGestoras(document.getElementById('gestora'), DATA.eventos.filter(e=>noPeriodo(e.data)), render);
  const fs=linhas();
  document.getElementById('h-rank').textContent='Fundos com eventos '+periodoTexto();
  document.getElementById('count').textContent=fs.length+(fs.length===1?' fundo':' fundos');
  const corpo=document.getElementById('rank');
  if(!fs.length){
    corpo.innerHTML=`<tr><td colspan="8" class="empty"><b>Nenhum fundo com esses filtros.</b>${P.mine&&!S.carteira.size?'Adicione seus fundos na página de eventos ou com o botão Acompanhar.':'Amplie o período ou limpe a busca.'}</td></tr>`;
    return;
  }
  const max=Math.max(...fs.map(f=>f.total),0.0001);
  corpo.innerHTML=fs.map(f=>{
    const m=S.carteira.has(f.cnpj_fundo), alvo=urlFundo(f);
    return `<tr data-href="${esc(alvo)}">
      <td><a href="${esc(alvo)}"><b class="${f.ticker?'tk':''}">${esc(rotulo(f))}</b></a><small>${f.ticker?esc(nomeCurto(f.fundo)):'Sem negociação em bolsa'}</small></td>
      <td>${esc(gestoraCurta(f.gestor))}</td>
      <td class="num">${f.eventos}</td>
      <td class="num">${f.expo.crit?pct(f.expo.crit):'–'}</td>
      <td class="num">${f.expo.warn?pct(f.expo.warn):'–'}</td>
      <td class="num">${f.expo.mon?pct(f.expo.mon):'–'}</td>
      <td class="num"><b>${pct(f.total)}</b><div class="bar" role="img" aria-label="Total ${pct(f.total)}">${['crit','warn','mon'].filter(s=>f.expo[s]>0).map(s=>`<i class="${s}" style="width:${(f.expo[s]/max*100).toFixed(2)}%"></i>`).join('')}</div></td>
      <td><button type="button" class="btn" data-f="${esc(f.cnpj_fundo)}" aria-pressed="${m}">${m?'Acompanhando':'Acompanhar'}</button></td>
    </tr>`;
  }).join('');
}

carregar().then(()=>{
  montarPeriodo(document.getElementById('periodo'), render);
  const q=document.getElementById('q'); q.addEventListener('input',()=>{P.q=q.value; render();});
  const mine=document.getElementById('mine'); mine.checked=P.mine;
  mine.addEventListener('change',()=>{P.mine=mine.checked; store.set('rl-mine',P.mine); render();});
  ligarBolsa(document.getElementById('listed'), render);
  document.querySelector('.rank thead').addEventListener('click',ev=>{
    const th=ev.target.closest('th[data-sort]'); if(!th) return;
    P.ordem=th.dataset.sort;
    document.querySelectorAll('.rank th[data-sort]').forEach(x=>x===th?x.setAttribute('aria-sort','descending'):x.removeAttribute('aria-sort'));
    render();
  });
  document.getElementById('rank').addEventListener('click',ev=>{
    const b=ev.target.closest('button[data-f]');
    if(b){ const c=b.dataset.f; S.carteira.has(c)?S.carteira.delete(c):S.carteira.add(c); salvarCarteira(); render(); return; }
    if(ev.target.closest('a')) return;
    const tr=ev.target.closest('tr[data-href]'); if(tr) location.href=tr.dataset.href;
  });
  render();
}).catch(falhaCarga);
