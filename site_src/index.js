const P = { q:'', sev:new Set(['crit','warn','mon']), mine:store.get('rl-mine',false), limite:25, forcar:null };

function filtrar(){
  const q=P.q.trim().toLowerCase();
  return DATA.eventos.filter(e=>{
    if(e.id===P.forcar) return true;
    if(!noPeriodo(e.data)) return false;
    if(!P.sev.has(e.severidade)) return false;
    if(!fundosVisiveis(e).length) return false;
    if(P.mine && !afetaMeus(e)) return false;
    if(q){
      const hay=[e.tipo,e.securitizadora,secNome(e.securitizadora),e.operacao,e.trecho,...e.codigos_if,...e.fundos.map(f=>(f.ticker||'')+' '+f.fundo+' '+(f.gestor||''))].join(' ').toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  }).sort((a,b)=>(S.carteira.size?(afetaMeus(b)-afetaMeus(a)):0) || b.data.localeCompare(a.data));
}
const doPeriodo = () => DATA.eventos.filter(e=>noPeriodo(e.data) && fundosVisiveis(e).length);

function renderHero(){
  const base=doPeriodo();
  const c={crit:0,warn:0,mon:0}; base.forEach(e=>c[e.severidade]++);
  for(const k in c) document.getElementById('n-'+k).textContent=c[k];
  const nf=new Set(base.flatMap(e=>fundosVisiveis(e).map(f=>f.cnpj_fundo))).size;
  const h=document.getElementById('headline'), s=document.getElementById('subline'), per=periodoTexto();
  if(S.carteira.size){
    const meus=base.filter(afetaMeus), mc=meus.filter(e=>e.severidade==='crit').length;
    h.textContent = meus.length
      ? `Seus fundos tiveram ${meus.length} ${meus.length===1?'evento':'eventos'} de crédito ${per}${mc?`, ${mc} ${mc===1?'urgente':'urgentes'}`:''}.`
      : `Nenhum CRI dos seus fundos teve evento de crédito ${per}.`;
    s.textContent=`No mercado todo foram ${base.length} ${base.length===1?'evento':'eventos'}, em CRIs de ${nf} FIIs.`;
  } else {
    h.textContent = base.length
      ? `${base.length} ${base.length===1?'evento de crédito atingiu':'eventos de crédito atingiram'} CRIs de ${nf} ${nf===1?'FII':'FIIs'} ${per}.`
      : `Nenhum evento de crédito em CRIs de FIIs ${per}.`;
    s.textContent='Inadimplência, assembleias, waivers e outros eventos publicados pelas securitizadoras, ligados aos fundos que têm cada CRI na carteira.';
  }
}

function chips(e){
  const fs=fundosVisiveis(e).slice().sort((a,b)=>(S.carteira.has(b.cnpj_fundo)-S.carteira.has(a.cnpj_fundo))||((b.pct_pl||0)-(a.pct_pl||0)));
  const vis=fs.slice(0,4);
  let h=vis.map(f=>`<span class="chip${S.carteira.has(f.cnpj_fundo)?' mine':''}"><b class="${f.ticker?'tk':''}">${esc(rotulo(f))}</b>${f.ticker?'':'<em>balcão</em>'}<span>${pct(f.pct_pl)}</span></span>`).join('');
  if(fs.length>vis.length) h+=`<span class="chip"><span>mais ${fs.length-vis.length}</span></span>`;
  return h;
}

function linha(e){
  const fs=fundosVisiveis(e).slice().sort((a,b)=>(b.pct_pl||0)-(a.pct_pl||0));
  const lista=fs.length?fs:e.fundos;
  const maior=lista[0]?.pct_pl, d=dia(e.data);
  const historico=e.historico.slice(0,3).map(x=>`<a class="btn" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.especie)} de ${dataCurta(x.data)}</a>`).join('');
  return `<li><details class="ev" id="${e.id}">
    <summary>
      <div class="when"><b>${d.getDate()} ${MESES[d.getMonth()]}</b>${relativo(e.data)}</div>
      <div class="ev-main">
        <div class="ev-top"><span class="tag ${e.severidade}">${SEV[e.severidade]}</span><span class="ev-title">${esc(e.tipo)}</span></div>
        <div class="ev-op"><strong>${esc(opNome(e.operacao))}</strong>, CRI da ${e.emissao}ª emissão, ${serieTxt(e)}, ${esc(secNome(e.securitizadora))}. <span class="phase">${esc(fase(e))}.</span></div>
        <div class="chips">${chips(e)}</div>
      </div>
      <div class="max">${maior!=null?`até<b>${pct(maior)}</b>do PL`:''}</div>
    </summary>
    <div class="body">
      ${EXPLICA[e.tipo]?`<div><h3>O que isso significa</h3><p>${esc(EXPLICA[e.tipo])}</p></div>`:''}
      ${e.trecho?`<div><h3>Trecho do documento</h3><p class="quote">${esc(e.trecho)}</p></div>`:''}
      ${e.data_assembleia?`<div><h3>Próximo passo</h3><p>Assembleia marcada para ${dataLonga(e.data_assembleia)}, segundo o edital.</p></div>`:''}
      <div><h3>FIIs com esse CRI na carteira</h3>
        <div class="tbl-wrap"><table><thead><tr><th>Fundo</th><th>Gestora</th><th class="num">Valor</th><th class="num">% do PL</th></tr></thead><tbody>
        ${lista.map(f=>`<tr><td><a href="${esc(urlFundo(f))}" style="color:inherit"><b class="${f.ticker?'tk':''}">${esc(rotulo(f))}</b></a><small>${f.ticker?esc(nomeCurto(f.fundo)):'Sem negociação em bolsa'}</small></td><td>${esc(gestoraCurta(f.gestor))}</td><td class="num">${brl(f.valor)}</td><td class="num"><b>${pct(f.pct_pl)}</b></td></tr>`).join('')}
        </tbody></table></div>
      </div>
      <div class="links"><a class="btn primary" href="${esc(e.url)}" target="_blank" rel="noopener">${ICON.ext}Abrir documento no Fundos.Net</a>${historico}</div>
      <p class="note">${e.cruzamento==='emissao_serie'
        ? 'O documento não cita o código IF; ligamos aos fundos por securitizadora, emissão e série. Confira no documento antes de tirar conclusões.'
        : 'Ligado aos fundos pelo código IF '+esc(e.codigos_if.slice(0,3).join(', '))+'.'} Carteira de referência: ${dia(DATA.carteira.data_referencia).toLocaleDateString('pt-BR')}.</p>
    </div>
  </details></li>`;
}

function renderFeed(){
  const lista=filtrar();
  document.getElementById('h-ev').textContent='Eventos '+periodoTexto();
  document.getElementById('count').textContent=lista.length+(lista.length===1?' evento':' eventos');
  const feed=document.getElementById('feed');
  if(!lista.length){
    const dica = P.mine && !S.carteira.size ? 'Adicione seus fundos no painel ao lado ou desligue "Só meus fundos".'
      : S.periodo.modo==='hoje' ? 'Ainda não saiu nenhum evento hoje. Veja os últimos 7 dias.'
      : 'Amplie o período, limpe a busca, troque a gestora ou inclua outras severidades.';
    feed.innerHTML=`<li class="empty"><b>Nenhum evento com esses filtros.</b>${dica}</li>`;
    document.getElementById('loadmore').hidden=true; return;
  }
  feed.innerHTML=lista.slice(0,P.limite).map(linha).join('');
  const lm=document.getElementById('loadmore');
  lm.hidden=lista.length<=P.limite;
  lm.textContent='Mostrar mais '+Math.min(25,lista.length-P.limite)+' eventos';
}

function renderExpo(){
  const fs=calcExpo(doPeriodo()).filter(passaFundo);
  const peso=f=>f.expo.crit*10+f.expo.warn*3+f.expo.mon;
  fs.sort((a,b)=>peso(b)-peso(a));
  const vis=fs.slice(0,8);
  const maxV=Math.max(...vis.map(f=>f.total),0.0001);
  const passo=[0.01,0.02,0.05,0.1,0.15,0.2,0.25,0.5,1].find(p=>p*4>=maxV)||1;
  document.getElementById('expo').innerHTML=vis.length?vis.map(f=>`<li>
      <button type="button" class="fn" data-q="${esc(f.ticker||f.fundo)}" title="Ver eventos deste fundo"><b class="${f.ticker?'tk':''}">${esc(rotulo(f))}</b><small>${esc(gestoraCurta(f.gestor))}${f.ticker?'':', balcão'}, ${f.eventos} ${f.eventos===1?'evento':'eventos'}</small></button>
      <span class="tot">${pct(f.total)}</span>
      <div class="bar" role="img" aria-label="Urgente ${pct(f.expo.crit)}, atenção ${pct(f.expo.warn)}, acompanhar ${pct(f.expo.mon)}">${['crit','warn','mon'].filter(s=>f.expo[s]>0).map(s=>`<i class="${s}" style="width:${Math.min(100,f.expo[s]/(passo*4)*100).toFixed(2)}%"></i>`).join('')}</div>
    </li>`).join(''):'<li class="note">Nenhum fundo com eventos no período.</li>';
  document.getElementById('scale').innerHTML=vis.length?[0,1,2,3,4].map(i=>`<span>${(passo*i*100).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</span>`).join(''):'';
}

function renderAgenda(){
  const hoje=isoHoje();
  const prox=DATA.eventos.filter(e=>e.data_assembleia && e.data_assembleia>=hoje && fundosVisiveis(e).length)
    .sort((a,b)=>a.data_assembleia.localeCompare(b.data_assembleia)).slice(0,4);
  const el=document.getElementById('agenda-list');
  if(!prox.length){el.innerHTML='<li class="note">Nenhuma assembleia futura com data identificada nos editais.</li>';return}
  el.innerHTML=prox.map(e=>{const d=dia(e.data_assembleia), n=diasEntre(hoje,e.data_assembleia);
    return `<li><button type="button" data-ev="${e.id}"><div class="cal"><b>${d.getDate()}</b><span>${MESES[d.getMonth()]}</span></div>
      <div><div class="what">${esc(e.tipo)}</div><div class="who">${esc(opNome(e.operacao))}, ${esc((fundosVisiveis(e).length?fundosVisiveis(e):e.fundos).map(rotulo).slice(0,3).join(', '))}</div><div class="in${n<=7?' soon':''}">${n===0?'hoje':'em '+n+(n===1?' dia':' dias')}</div></div></button></li>`}).join('');
}

function renderCarteira(){
  const itens=[...S.carteira].map(c=>FUNDOS_IDX.get(c)).filter(Boolean);
  document.getElementById('mine-list').innerHTML=itens.map(f=>`<button type="button" data-rm="${esc(f.cnpj_fundo)}" aria-label="Remover ${esc(rotulo(f))}">${esc(rotulo(f))}<span aria-hidden="true">×</span></button>`).join('');
  document.getElementById('mine-empty').hidden=itens.length>0;
}

function render(){ montarGestoras(document.getElementById('gestora'), doPeriodoSemGestora(), ()=>{P.limite=25; render();}); renderHero(); renderFeed(); renderExpo(); renderAgenda(); renderCarteira(); }
const doPeriodoSemGestora = () => DATA.eventos.filter(e=>noPeriodo(e.data));

function abrirEvento(id){
  if(!document.getElementById(id)){ P.forcar=id; P.limite=999; renderFeed(); }
  const d=document.getElementById(id); if(!d) return;
  d.open=true; d.scrollIntoView({behavior:'smooth',block:'start'});
}

carregar().then(()=>{
  const params=new URLSearchParams(location.search);
  const q=document.getElementById('q');
  if(params.get('q')){ P.q=params.get('q'); q.value=P.q; }
  document.getElementById('fundos-list').innerHTML=[...FUNDOS_IDX.values()].sort((a,b)=>rotulo(a).localeCompare(rotulo(b)))
    .map(f=>`<option value="${esc(f.ticker||nomeCurto(f.fundo))}">${esc(f.ticker?nomeCurto(f.fundo):'Sem negociação em bolsa')}</option>`).join('');

  montarPeriodo(document.getElementById('periodo'), ()=>{P.limite=25; P.forcar=null; render();});
  document.getElementById('sevs').addEventListener('click',ev=>{const b=ev.target.closest('button[data-sev]'); if(!b) return;
    const v=b.dataset.sev; P.sev.has(v)?P.sev.delete(v):P.sev.add(v); b.setAttribute('aria-pressed',P.sev.has(v)); P.limite=25; renderFeed();});
  q.addEventListener('input',()=>{P.q=q.value; P.limite=25; renderFeed();});
  const mine=document.getElementById('mine'); mine.checked=P.mine;
  mine.addEventListener('change',()=>{P.mine=mine.checked; store.set('rl-mine',P.mine); P.limite=25; renderFeed();});
  ligarBolsa(document.getElementById('listed'), render);
  document.getElementById('loadmore').addEventListener('click',()=>{P.limite+=25; renderFeed();});
  document.getElementById('expo').addEventListener('click',ev=>{const t=ev.target.closest('.fn'); if(!t) return;
    q.value=t.dataset.q; P.q=t.dataset.q; P.limite=25; renderFeed(); document.getElementById('eventos').scrollIntoView({behavior:'smooth',block:'start'});});
  document.getElementById('agenda-list').addEventListener('click',ev=>{const b=ev.target.closest('button[data-ev]'); if(b) abrirEvento(b.dataset.ev);});
  const form=document.getElementById('add-form'), inp=document.getElementById('add-input');
  form.addEventListener('submit',ev=>{ev.preventDefault();
    const f=acharFundo(inp.value);
    if(f){ S.carteira.add(f.cnpj_fundo); salvarCarteira(); inp.value=''; inp.setCustomValidity(''); render(); }
    else { inp.setCustomValidity('Não encontramos esse fundo entre os FIIs com eventos no histórico.'); inp.reportValidity(); }});
  inp.addEventListener('input',()=>inp.setCustomValidity(''));
  document.getElementById('mine-list').addEventListener('click',ev=>{const b=ev.target.closest('button[data-rm]'); if(!b) return;
    S.carteira.delete(b.dataset.rm); salvarCarteira(); render();});

  render();
  if(/^#e\d+$/.test(location.hash)) abrirEvento(location.hash.slice(1));
}).catch(falhaCarga);
