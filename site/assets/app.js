/* Radar de Lastro: funções compartilhadas pelas páginas */
const SEV = {crit:'Urgente', warn:'Atenção', mon:'Acompanhar'};
const MESES = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const MESES_LONGOS = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];

// explicação em linguagem simples de cada tipo de evento
const EXPLICA = {
  'Pagamento não realizado':'A parcela de juros ou amortização do CRI não foi paga na data. Costuma haver um prazo curto para regularizar antes de virar inadimplência formal.',
  'Recuperação judicial ou falência do devedor':'O devedor do CRI pediu proteção na Justiça contra os credores, ou teve a falência decretada. Os pagamentos passam a depender das garantias e do plano de recuperação.',
  'Vencimento antecipado declarado':'O CRI passou a valer como vencido de uma vez: o saldo inteiro fica cobrável, normalmente porque o devedor descumpriu alguma obrigação.',
  'Execução de garantias':'A securitizadora está cobrando ou tomando as garantias da operação, como imóveis ou recebíveis, para pagar os investidores.',
  'Assembleia sobre vencimento antecipado':'Os investidores vão decidir, ou decidiram, se cobram o CRI de forma antecipada ou se dão uma nova chance ao devedor.',
  'Assembleia sobre inadimplemento':'Assembleia para tratar de pagamentos em atraso e das medidas que serão tomadas.',
  'Uso do fundo de reserva':'O caixa de segurança da operação foi usado para pagar os investidores ou está abaixo do mínimo e precisa ser recomposto.',
  'Pedido de waiver':'O devedor pede autorização dos investidores para descumprir uma regra da operação por um tempo, sem que isso gere vencimento antecipado.',
  'Garantia ou covenant desenquadrado':'Algum limite da operação, como o valor das garantias ou um índice financeiro do devedor, ficou fora do combinado.',
  'Repactuação ou carência':'Mudança nas condições de pagamento do CRI, como novo cronograma, prazo maior ou período sem pagamento de principal.',
  'Rebaixamento de rating':'Uma agência de classificação de risco piorou a nota da operação ou do devedor.',
  'Amortização extraordinária ou resgate antecipado':'Parte ou todo o saldo do CRI foi pago antes do prazo. Em geral reduz o risco, mas o fundo precisa reinvestir o dinheiro.',
  'Troca de garantia':'Uma garantia da operação foi substituída ou liberada. Vale conferir se a nova cobertura é equivalente.',
  'Troca de prestador da operação':'Mudou um prestador de serviço do CRI, como o agente fiduciário, que fiscaliza a operação em nome dos investidores.'
};
const SECS = {'OPEA':'Opea','PROVINCIA':'Província','CANAL SEC':'Canal','ISEC':'Virgo','VIRGO':'Virgo','HABITASEC':'Habitasec','FORTE CAP':'Forte','BARI SEC':'Bari','BRAZILIAN SC':'Brazilian Securities','LEVERAGE SEC':'Leverage','Lever':'Leverage','VERTCIASEC':'Vert','REIT SEC':'Reit','TRAVESSIASEC':'Travessia','CASAPEDRASEC':'Casa de Pedra','PLAYBANCOSEC':'Playbanco','ÉXES':'Éxes','RBCAPITALRES':'RB Capital','OURINVESTSEC':'Ourinvest','PATRIA SEC':'Pátria','OCTANTE SEC':'Octante','BSIP':'BSI Capital','REAG SECURIT':'Reag','CIBRASEC':'Cibrasec','POLO CAP SEC':'Polo Capital','BAMBOO SEC':'Bamboo','BASESEC':'Base','LOGOS CIA':'Logos','B.SEC':'B.Sec'};
const ICON = {
  ext:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>'
};

const store = {
  get(k,d){try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}},
  set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}
};

// estado comum às páginas
const S = {
  listed: store.get('rl-bolsa', false),       // padrão: inclui FIIs de balcão
  carteira: new Set(store.get('rl-carteira', [])),
  gestora: '',
  periodo: store.get('rl-periodo', {modo:'30'}),  // modo: 'hoje' | '7' | '30' | '90' | 'datas'
};
let DATA = null;
const FUNDOS_IDX = new Map();

/* ---------- formatação ---------- */
const esc = s => String(s ?? '').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function pct(x){ if(x==null) return '–'; const v=x*100; if(v>0 && v<0.1) return '< 0,1%'; return v.toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%'; }
function brl(v){ if(v>=1e9) return 'R$ '+(v/1e9).toLocaleString('pt-BR',{maximumFractionDigits:1})+' bi'; if(v>=1e6) return 'R$ '+(v/1e6).toLocaleString('pt-BR',{maximumFractionDigits:1})+' mi'; return 'R$ '+Math.round(v/1e3).toLocaleString('pt-BR')+' mil'; }
function titulo(s){ return s.toLowerCase().split(' ').map(w=>{ if(['de','da','do','das','dos','e'].includes(w)) return w; if(w.length<=3 && /^[a-z]+$/.test(w) && !['sul','rio','sao','são','paz','mar','sol','lar'].includes(w)) return w.toUpperCase(); return w.charAt(0).toUpperCase()+w.slice(1);}).join(' '); }
function nomeCurto(n){
  if(!n) return 'FII sem nome';
  let s=n.replace(/FUNDO DE INVESTIMENTO IMOBILI[ÁA]RIO|FUNDO DE INVESTIMENTO IMOB\.?|FUNDO DE INV\.? IMOB\.?|FDO\.? INV\.? IMOB\.?|RESPONSABILIDADE LIMITADA|RESP\.? LIMITADA|\bFII\b|\bFI IMOB\w*|CLASSE [ÚU]NICA/gi,' ').replace(/\s+/g,' ').trim().replace(/(\s+(de|da|do|das|dos|e|-|–|,))+$/i,'').replace(/[-–,\s]+$/,'');
  s=titulo(s);
  if(s.length<=36) return s;
  const corte=s.lastIndexOf(' ',34); return s.slice(0,corte>18?corte:34)+'…';
}
const rotulo = f => f.ticker || nomeCurto(f.fundo);
const urlFundo = f => f.slug ? '/fii/'+f.slug+'/' : '/?q='+encodeURIComponent(f.ticker||f.fundo);
function gestoraCurta(n){
  if(!n) return 'Gestora não informada';
  let t=n.replace(/\b(LTDA|S\/?A|S\.A|EIRELI)\b\.?/gi,' ').replace(/GEST(Ã|A)O DE RECURSOS|GESTORA DE RECURSOS|ADMINISTRA(Ç|C)(Ã|A)O DE RECURSOS|ASSET MANAGEMENT|GEST(Ã|A)O E CONSULTORIA DE INVESTIMENTOS|INVESTIMENTOS E PARTICIPA(Ç|C)(Õ|O)ES|\bGESTORA\b|INVESTIMENTOS|\bDTVM\b|DISTRIBUIDORA DE T(Í|I)TULOS E VALORES MOBILI(Á|A)RIOS|CORRETORA DE T(Í|I)TULOS E VALORES MOBILI(Á|A)RIOS/gi,' ');
  t=t.replace(/[.,\-–\s]+$/,'').replace(/\s+/g,' ').trim().split(' ').map(w=>{const l=w.toLowerCase(); if(['de','da','do','das','dos','e'].includes(l)) return l; if(w.length<=3) return w.toUpperCase(); return l.charAt(0).toUpperCase()+l.slice(1);}).join(' ');
  return t||n;
}
const secNome = s => SECS[s] || titulo(s||'');
// nome da operação no Fundos.Net vem truncado e com mês/ano de emissão no fim
function opNome(o){ let t=(o||'').replace(/\s+\d{2}\/\d{4}\s*$/,'').trim(); if(!t) return 'Operação sem nome'; if(t===t.toUpperCase()) t=titulo(t); return t; }
function serieTxt(e){ return e.outras_series ? `séries ${e.serie} a ${+e.serie+e.outras_series}` : `${e.serie}ª série`; }

/* ---------- datas (sempre no horário de Brasília) ---------- */
const isoHoje = () => new Date().toLocaleDateString('sv-SE',{timeZone:'America/Sao_Paulo'});
const dia = s => new Date(s.slice(0,10)+'T00:00:00-03:00');
const somaDias = (iso,n) => { const d=dia(iso); d.setUTCDate(d.getUTCDate()+n); return d.toLocaleDateString('sv-SE',{timeZone:'America/Sao_Paulo'}); };
const diasEntre = (a,b) => Math.round((dia(b)-dia(a))/864e5);
function dataLonga(iso){const d=dia(iso); return d.getDate()+' de '+MESES_LONGOS[d.getMonth()];}
function dataCurta(iso){const d=dia(iso); return d.getDate().toString().padStart(2,'0')+'/'+(d.getMonth()+1).toString().padStart(2,'0');}
function relativo(iso){const n=diasEntre(iso.slice(0,10),isoHoje()); return n<=0?'hoje':n===1?'ontem':'há '+n+' dias';}
function fase(e){
  if(e.fase==='convocada') return e.data_assembleia ? 'Assembleia marcada para '+dataCurta(e.data_assembleia) : 'Assembleia convocada';
  if(e.fase==='deliberada') return 'Assembleia realizada';
  return e.categoria;
}

/* ---------- período ---------- */
function limitesPeriodo(){
  const hoje=isoHoje(), p=S.periodo;
  if(p.modo==='hoje') return [hoje,hoje];
  if(p.modo==='datas') return [p.de||DATA.janela.inicio, p.ate||hoje];
  const n=+p.modo||30; return [somaDias(hoje,-(n-1)),hoje];
}
function noPeriodo(iso){ const [a,b]=limitesPeriodo(); const d=iso.slice(0,10); return d>=a && d<=b; }
function periodoTexto(){
  const p=S.periodo;
  if(p.modo==='hoje') return 'hoje';
  if(p.modo==='datas'){ const [a,b]=limitesPeriodo(); return a===b?'em '+dataCurta(a):'de '+dataCurta(a)+' a '+dataCurta(b); }
  return 'nos últimos '+(p.modo||30)+' dias';
}
function montarPeriodo(el, aoMudar){
  const opcoes=[['hoje','Hoje'],['7','7 dias'],['30','30 dias'],['90','90 dias'],['datas','Escolher datas']];
  const min=DATA.janela.inicio, max=isoHoje();
  el.innerHTML=`<div class="sevs" role="group" aria-label="Período">${opcoes.map(([v,t])=>`<button type="button" data-p="${v}" aria-pressed="${S.periodo.modo===v}">${t}</button>`).join('')}</div>
    <span class="datas" ${S.periodo.modo==='datas'?'':'hidden'}><label for="p-de">de</label><input type="date" id="p-de" min="${min}" max="${max}" value="${S.periodo.de||somaDias(max,-29)}"><label for="p-ate">até</label><input type="date" id="p-ate" min="${min}" max="${max}" value="${S.periodo.ate||max}"></span>`;
  const salvar=()=>{store.set('rl-periodo',S.periodo); aoMudar();};
  el.querySelector('.sevs').addEventListener('click',ev=>{
    const b=ev.target.closest('button[data-p]'); if(!b) return;
    S.periodo.modo=b.dataset.p;
    el.querySelectorAll('button[data-p]').forEach(x=>x.setAttribute('aria-pressed',x===b));
    const datas=el.querySelector('.datas'); datas.hidden=S.periodo.modo!=='datas';
    if(S.periodo.modo==='datas'){ S.periodo.de=el.querySelector('#p-de').value; S.periodo.ate=el.querySelector('#p-ate').value; }
    salvar();
  });
  el.querySelectorAll('input[type=date]').forEach(i=>i.addEventListener('change',()=>{
    let de=el.querySelector('#p-de').value, ate=el.querySelector('#p-ate').value;
    if(de && ate && de>ate){ [de,ate]=[ate,de]; el.querySelector('#p-de').value=de; el.querySelector('#p-ate').value=ate; }
    S.periodo.de=de; S.periodo.ate=ate; salvar();
  }));
}

/* ---------- fundos ---------- */
// "em bolsa" = tem código de negociação; o campo de mercado da CVM marca também cotas só registradas na B3
const emBolsa = f => !!f.ticker;
const passaFundo = f => (!S.listed || emBolsa(f)) && (!S.gestora || f.gestor===S.gestora);
const fundosVisiveis = e => e.fundos.filter(passaFundo);
const afetaMeus = e => e.fundos.some(f=>S.carteira.has(f.cnpj_fundo));
function salvarCarteira(){ store.set('rl-carteira',[...S.carteira]); }
function acharFundo(texto){
  const t=texto.trim().toLowerCase(); if(!t) return null;
  const todos=[...FUNDOS_IDX.values()];
  return todos.find(x=>(x.ticker||'').toLowerCase()===t) || todos.find(x=>rotulo(x).toLowerCase()===t) || todos.find(x=>(x.fundo||'').toLowerCase().includes(t));
}

// exposição de cada fundo aos eventos dados; uma operação conta uma vez, pela pior severidade
function calcExpo(eventos){
  const ORD={crit:0,warn:1,mon:2}, m=new Map();
  eventos.forEach(e=>e.fundos.forEach(f=>{
    let x=m.get(f.cnpj_fundo);
    if(!x){ x={...f, expo:{crit:0,warn:0,mon:0}, eventos:0, ops:new Map()}; m.set(f.cnpj_fundo,x); }
    x.eventos++;
    const op=e.securitizadora+'|'+e.emissao+'|'+e.serie, atual=x.ops.get(op);
    if(f.pct_pl!=null && (!atual || ORD[e.severidade]<ORD[atual[0]])) x.ops.set(op,[e.severidade,f.pct_pl]);
  }));
  return [...m.values()].map(x=>{ x.ops.forEach(([s,p])=>x.expo[s]+=p); delete x.ops; x.total=x.expo.crit+x.expo.warn+x.expo.mon; return x; });
}

function montarGestoras(sel, eventos, aoMudar){
  const cont=new Map();
  eventos.forEach(e=>new Set(e.fundos.filter(f=>!S.listed||emBolsa(f)).map(f=>f.gestor).filter(Boolean)).forEach(g=>cont.set(g,(cont.get(g)||0)+1)));
  const lista=[...cont.entries()].sort((a,b)=>b[1]-a[1]||gestoraCurta(a[0]).localeCompare(gestoraCurta(b[0])));
  if(S.gestora && !cont.has(S.gestora)) S.gestora='';
  sel.innerHTML='<option value="">Todas as gestoras</option>'+lista.map(([g,n])=>`<option value="${esc(g)}"${g===S.gestora?' selected':''}>${esc(gestoraCurta(g))} (${n})</option>`).join('');
  sel.classList.toggle('on',!!S.gestora);
  if(!sel.dataset.ligado){ sel.dataset.ligado='1'; sel.addEventListener('change',()=>{S.gestora=sel.value; aoMudar();}); }
}

function ligarBolsa(input, aoMudar){
  input.checked=S.listed;
  input.addEventListener('change',()=>{S.listed=input.checked; store.set('rl-bolsa',S.listed); aoMudar();});
}

/* ---------- carga e moldura da página ---------- */
function marcarNav(){} // a página atual já vem marcada no HTML gerado
function rodape(){
  const el=document.getElementById('foot'); if(!el||!DATA) return;
  el.innerHTML=`<p>O Radar de Lastro reúne informação pública e não faz recomendação de investimento. A classificação dos eventos é automática e pode errar: abra sempre o documento original antes de qualquer decisão.</p>
    <p>Fontes: Fundos.Net (B3 e CVM) e Portal de Dados Abertos da CVM. Carteira de referência: informe trimestral de ${dia(DATA.carteira.data_referencia).toLocaleDateString('pt-BR')}. <a href="/como-funciona.html">Como funciona</a>.</p>`;
}
function carregar(){
  marcarNav();
  return fetch('/data.json',{cache:'no-cache'}).then(r=>{if(!r.ok) throw new Error(r.status); return r.json();}).then(d=>{
    DATA=d;
    d.eventos.forEach(e=>e.fundos.forEach(f=>{ if(!FUNDOS_IDX.has(f.cnpj_fundo)) FUNDOS_IDX.set(f.cnpj_fundo,f); }));
    const g=new Date(d.gerado_em), up=document.getElementById('updated');
    if(up) up.textContent='Atualizado em '+g.toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'})+' às '+g.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'})+'.';
    rodape();
    return d;
  });
}
function falhaCarga(){
  const h=document.getElementById('headline'); if(h) h.textContent='Os dados não carregaram.';
  const s=document.getElementById('subline'); if(s) s.textContent='Recarregue a página. Se o problema continuar, a atualização pode estar em andamento.';
}
