const state = { provider: 'crypto', data: null, timeframe: '1d' };
const $ = (id) => document.getElementById(id);
const symbol = $('symbol');
const exchange = $('exchange');
const exchangeField = $('exchangeField');
const analyseBtn = $('analyse');
const status = $('status');
const errorBox = $('errorBox');

async function loadConfig(){
  const r = await fetch('/api/config');
  const cfg = await r.json();
  exchange.innerHTML = cfg.crypto_exchanges.map(x => `<option value="${x}">${x}</option>`).join('');
}

document.querySelectorAll('.segment').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.segment').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.provider = btn.dataset.provider;
  const crypto = state.provider === 'crypto';
  exchangeField.classList.toggle('hidden', !crypto);
  symbol.value = crypto ? 'BTC/USDT' : 'SPY';
  symbol.placeholder = crypto ? 'BTC/USDT' : 'SPY';
  $('symbolHint').textContent = crypto ? 'Examples: BTC/USDT, ETH/USDT' : 'Examples: SPY, AAPL, ^GSPC, EURUSD=X, ES=F';
}));

document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active'); state.timeframe = btn.dataset.tf; renderChart();
}));

analyseBtn.addEventListener('click', analyse);
symbol.addEventListener('keydown', e => { if(e.key === 'Enter') analyse(); });

function setLoading(on){
  analyseBtn.disabled = on; analyseBtn.textContent = on ? 'Analysing…' : 'Analyse market';
  status.innerHTML = `<span class="dot"></span> ${on ? 'Fetching & analysing' : 'Ready'}`;
}
function fmtPrice(v){
  if(!Number.isFinite(v)) return '—';
  const decimals = v >= 1000 ? 2 : v >= 1 ? 4 : 6;
  return v.toLocaleString(undefined,{minimumFractionDigits:decimals,maximumFractionDigits:decimals});
}

async function analyse(){
  errorBox.classList.add('hidden'); setLoading(true);
  try{
    const payload = { provider: state.provider, symbol: symbol.value.trim(), exchange: state.provider === 'crypto' ? exchange.value : null };
    const r = await fetch('/api/analyse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const body = await r.json();
    if(!r.ok) throw new Error(body.detail || 'Analysis failed');
    state.data = body; renderAll();
  }catch(err){ errorBox.textContent = err.message; errorBox.classList.remove('hidden'); }
  finally{ setLoading(false); }
}

function renderAll(){
  const d = state.data, levels = d.levels || [];
  $('summary').classList.remove('hidden'); $('results').classList.remove('hidden');
  $('mSymbol').textContent = d.symbol;
  $('mPrice').textContent = fmtPrice(d.current_price);
  $('mZones').textContent = levels.length;
  $('mScore').textContent = levels.length ? Math.max(...levels.map(x=>x.score)).toFixed(1) : '—';

  const supports = levels.filter(x=>x.mid < d.current_price).sort((a,b)=>b.mid-a.mid);
  const resistances = levels.filter(x=>x.mid >= d.current_price).sort((a,b)=>a.mid-b.mid);
  $('nearestSupport').textContent = supports[0] ? `${supports[0].zone} · score ${supports[0].score.toFixed(1)}` : 'None detected';
  $('nearestResistance').textContent = resistances[0] ? `${resistances[0].zone} · score ${resistances[0].score.toFixed(1)}` : 'None detected';

  $('levelsBody').innerHTML = levels.map(l => `<tr>
    <td><span class="pill ${l.type}">${l.type}</span></td><td>${l.zone}</td><td>${l.timeframes}</td>
    <td>${l.touches}</td><td><strong>${l.score.toFixed(1)}</strong></td><td>${l.distance_pct > 0 ? '+' : ''}${l.distance_pct.toFixed(2)}%</td>
  </tr>`).join('') || '<tr><td colspan="6">No reliable zones detected.</td></tr>';
  renderChart();
}

function visibleLevels(tf){
  if(!state.data) return [];
  const tag = tf.toUpperCase();
  return state.data.levels.filter(l => l.timeframes.includes(tag) || tf === '1h');
}

function renderChart(){
  if(!state.data || !window.Plotly) return;
  const tf = state.timeframe, rows = state.data.charts[tf] || [];
  const x = rows.map(r=>r.time);
  const trace = {type:'candlestick',x,open:rows.map(r=>r.open),high:rows.map(r=>r.high),low:rows.map(r=>r.low),close:rows.map(r=>r.close),
    increasing:{line:{color:'#50d890'}},decreasing:{line:{color:'#ff6978'}},name:state.data.symbol};
  const shapes = visibleLevels(tf).map(l=>({type:'rect',xref:'x',yref:'y',x0:x[0],x1:x[x.length-1],y0:l.low,y1:l.high,
    fillcolor:l.type==='support'?'rgba(81,216,138,.10)':'rgba(255,107,122,.10)',line:{color:l.type==='support'?'rgba(81,216,138,.52)':'rgba(255,107,122,.52)',width:1},layer:'below'}));
  const annotations = visibleLevels(tf).slice(0,7).map(l=>({xref:'paper',x:1,y:l.mid,yref:'y',text:`${l.type[0].toUpperCase()} · ${fmtPrice(l.mid)} · ${l.score.toFixed(1)}`,
    showarrow:false,xanchor:'right',font:{size:10,color:l.type==='support'?'#7aeba8':'#ff8f9b'},bgcolor:'rgba(7,16,24,.72)',borderpad:3}));
  Plotly.react('chart',[trace],{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'#08131c',font:{color:'#9db2c0'},margin:{l:58,r:25,t:12,b:32},
    xaxis:{rangeslider:{visible:false},gridcolor:'#132635',linecolor:'#274052'},yaxis:{side:'right',gridcolor:'#132635',linecolor:'#274052',fixedrange:false},
    shapes,annotations,dragmode:'pan',showlegend:false,hovermode:'x unified'}, {responsive:true,displaylogo:false,scrollZoom:true});
}

loadConfig();
