const state = { provider: 'crypto', data: null, timeframe: '1d' };
const $ = id => document.getElementById(id);
const symbolEl = $('symbol');
const apiKeyEl = $('apiKey');
const apiKeyField = $('apiKeyField');
const analyseBtn = $('analyse');
const statusEl = $('status');
const errorBox = $('errorBox');

apiKeyEl.value = localStorage.getItem('keyLevels.twelveDataKey') || '';
apiKeyEl.addEventListener('change', () => {
  const v = apiKeyEl.value.trim();
  if (v) localStorage.setItem('keyLevels.twelveDataKey', v);
  else localStorage.removeItem('keyLevels.twelveDataKey');
});

document.querySelectorAll('.segment').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.segment').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.provider = btn.dataset.provider;
  const crypto = state.provider === 'crypto';
  apiKeyField.classList.toggle('hidden', crypto);
  symbolEl.value = crypto ? 'BTC/USDT' : 'SPY';
  symbolEl.placeholder = crypto ? 'BTC/USDT' : 'SPY';
  $('symbolHint').textContent = crypto
    ? 'Examples: BTC/USDT, ETH/USDT, SOL/USDT'
    : 'Examples: SPY, AAPL, EUR/USD. Futures availability depends on your Twelve Data plan.';
}));

document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.timeframe = btn.dataset.tf;
  renderChart();
}));

analyseBtn.addEventListener('click', analyse);
symbolEl.addEventListener('keydown', e => { if (e.key === 'Enter') analyse(); });

function setLoading(on) {
  analyseBtn.disabled = on;
  analyseBtn.textContent = on ? 'Analysing…' : 'Analyse market';
  statusEl.innerHTML = `<span class="dot"></span> ${on ? 'Fetching & analysing' : 'Ready'}`;
}
function esc(text) {
  return String(text).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}
function fmtPrice(v) {
  if (!Number.isFinite(v)) return '—';
  const d = v >= 1000 ? 2 : v >= 1 ? 4 : 6;
  return v.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
}
function median(values) {
  const a = values.filter(Number.isFinite).slice().sort((x,y)=>x-y);
  if (!a.length) return NaN;
  const m = Math.floor(a.length/2);
  return a.length % 2 ? a[m] : (a[m-1]+a[m])/2;
}
function mean(values) { return values.length ? values.reduce((a,b)=>a+b,0)/values.length : NaN; }

async function fetchJson(url) {
  const r = await fetch(url, {cache:'no-store'});
  if (!r.ok) throw new Error(`Market data request failed (${r.status})`);
  return r.json();
}

function normalizeBinanceSymbol(raw) {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g,'');
}
async function fetchBinanceKlines(symbol, interval, limit) {
  const s = normalizeBinanceSymbol(symbol);
  const url = `https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(s)}&interval=${encodeURIComponent(interval)}&limit=${limit}`;
  const data = await fetchJson(url);
  if (!Array.isArray(data) || !data.length) throw new Error(`No Binance data returned for ${s}`);
  return data.map(r => ({
    time: new Date(r[0]).toISOString(), open:+r[1], high:+r[2], low:+r[3], close:+r[4], volume:+r[5]
  })).filter(validBar);
}

async function fetchTwelve(symbol, interval, outputsize, apiKey) {
  if (!apiKey) throw new Error('Enter a Twelve Data API key for stocks / FX / futures.');
  const url = `https://api.twelvedata.com/time_series?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&outputsize=${outputsize}&order=asc&timezone=UTC&apikey=${encodeURIComponent(apiKey)}`;
  const data = await fetchJson(url);
  if (data.status === 'error' || data.code) throw new Error(data.message || 'Twelve Data request failed');
  if (!Array.isArray(data.values) || !data.values.length) throw new Error(`No Twelve Data candles returned for ${symbol}`);
  return data.values.map(r => ({
    time: new Date(String(r.datetime).replace(' ','T') + (String(r.datetime).includes('Z') ? '' : 'Z')).toISOString(),
    open:+r.open, high:+r.high, low:+r.low, close:+r.close, volume:Number(r.volume || 0)
  })).filter(validBar);
}
function validBar(r) { return [r.open,r.high,r.low,r.close].every(Number.isFinite); }

async function loadMarketData(provider, symbol) {
  if (provider === 'crypto') {
    const [d,h4,h1] = await Promise.all([
      fetchBinanceKlines(symbol,'1d',400),
      fetchBinanceKlines(symbol,'4h',500),
      fetchBinanceKlines(symbol,'1h',700)
    ]);
    return {'1d':d,'4h':h4,'1h':h1};
  }
  const key = apiKeyEl.value.trim();
  if (key) localStorage.setItem('keyLevels.twelveDataKey', key);
  const [d,h4,h1] = await Promise.all([
    fetchTwelve(symbol,'1day',400,key),
    fetchTwelve(symbol,'4h',500,key),
    fetchTwelve(symbol,'1h',700,key)
  ]);
  return {'1d':d,'4h':h4,'1h':h1};
}

function atr(rows, period=14) {
  const out = Array(rows.length).fill(NaN);
  const tr = rows.map((r,i) => {
    if (!i) return r.high-r.low;
    const pc = rows[i-1].close;
    return Math.max(r.high-r.low, Math.abs(r.high-pc), Math.abs(r.low-pc));
  });
  for (let i=0;i<rows.length;i++) {
    const start = Math.max(0,i-period+1);
    const vals = tr.slice(start,i+1);
    if (vals.length >= Math.min(period, i+1)) out[i] = mean(vals);
  }
  const first = out.find(Number.isFinite) || mean(tr.filter(Number.isFinite));
  return out.map(v => Number.isFinite(v) ? v : first);
}
function pivotMask(rows,key,left,right,mode) {
  const mask = Array(rows.length).fill(false);
  for (let i=left;i<rows.length-right;i++) {
    const window = rows.slice(i-left,i+right+1).map(r=>r[key]);
    const val = rows[i][key];
    const target = mode==='high' ? Math.max(...window) : Math.min(...window);
    if (val===target && window.filter(x=>x===val).length===1) mask[i]=true;
  }
  return mask;
}
function countRetests(rows,start,low,high,skip=2) {
  let count=0, was=false;
  for (let i=Math.min(start+skip+1,rows.length);i<rows.length;i++) {
    const hit = rows[i].high>=low && rows[i].low<=high;
    if (hit && !was) count++;
    was=hit;
  }
  return count;
}
function hasSweep(rows,start,low,high,kind) {
  for (let i=start+1;i<rows.length;i++) {
    if (kind==='resistance' && rows[i].high>high && rows[i].close<high) return true;
    if (kind==='support' && rows[i].low<low && rows[i].close>low) return true;
  }
  return false;
}
function hasBreakRetest(rows,start,low,high,kind) {
  for (let i=start+1;i<rows.length;i++) {
    const broke = kind==='resistance' ? rows[i].close>high : rows[i].close<low;
    if (!broke) continue;
    for (let j=i+1;j<Math.min(rows.length,i+8);j++) {
      if (kind==='resistance' && rows[j].low<=high && rows[j].close>=low) return true;
      if (kind==='support' && rows[j].high>=low && rows[j].close<=high) return true;
    }
  }
  return false;
}
function hasImpulse(rows,pivotIdx,price,a,kind) {
  if (!Number.isFinite(a) || a<=0) return false;
  for (let i=pivotIdx+1;i<Math.min(rows.length,pivotIdx+5);i++) {
    if (kind==='support' && rows[i].close>=price+a*1.15) return true;
    if (kind==='resistance' && rows[i].close<=price-a*1.15) return true;
  }
  return false;
}
function freshness(retests) { return retests===0 ? 'fresh' : retests<=2 ? 'tested' : 'mature'; }

function detectLevels(rows,timeframe) {
  const cfg = {
    '1d':{left:3,right:3,atrMult:.45,base:5},
    '4h':{left:4,right:4,atrMult:.38,base:3},
    '1h':{left:5,right:5,atrMult:.32,base:1}
  }[timeframe];
  if (!rows || rows.length<20) return [];
  const atrs=atr(rows), hp=pivotMask(rows,'high',cfg.left,cfg.right,'high'), lp=pivotMask(rows,'low',cfg.left,cfg.right,'low');
  const candidates=[];
  for(let i=0;i<rows.length;i++) {
    if(hp[i]) candidates.push({idx:i,price:rows[i].high,kind:'resistance',atr:atrs[i]});
    if(lp[i]) candidates.push({idx:i,price:rows[i].low,kind:'support',atr:atrs[i]});
  }
  candidates.sort((a,b)=>a.price-b.price);
  const clusters=[];
  for(const c of candidates) {
    if(!clusters.length){clusters.push([c]);continue;}
    const grp=clusters[clusters.length-1], center=median(grp.map(x=>x.price)), a=median(grp.map(x=>x.atr));
    const tol=Math.max(a*cfg.atrMult,center*.0015);
    Math.abs(c.price-center)<=tol ? grp.push(c) : clusters.push([c]);
  }
  const n=rows.length, out=[];
  for(const cluster of clusters) {
    const prices=cluster.map(x=>x.price), as=cluster.map(x=>x.atr), idxs=cluster.map(x=>x.idx), kinds=cluster.map(x=>x.kind);
    const price=median(prices), am=median(as), zoneHalf=Math.max(am*.22,price*.0007), low=price-zoneHalf, high=price+zoneHalf;
    const touches=cluster.length,lastIdx=Math.max(...idxs),firstIdx=Math.min(...idxs),recency=n-1-lastIdx;
    const kind=kinds.filter(x=>x==='resistance').length>=kinds.filter(x=>x==='support').length?'resistance':'support';
    const retests=countRetests(rows,lastIdx,low,high), fresh=freshness(retests), signals=[];
    if(touches>=2) signals.push(kind==='resistance'?'equal highs':'equal lows');
    if(hasImpulse(rows,firstIdx,price,am,kind)) signals.push(kind==='resistance'?'supply':'demand');
    if(hasSweep(rows,firstIdx,low,high,kind)) signals.push('liquidity sweep');
    if(hasBreakRetest(rows,firstIdx,low,high,kind)) signals.push('break & retest');
    const recencyBonus=Math.max(0,2-recency/Math.max(n*.25,1));
    const touchBonus=Math.min(4,1.25*Math.log2(touches+1));
    const freshBonus={fresh:2,tested:.7,mature:-.8}[fresh];
    const bonusMap={'equal highs':1,'equal lows':1,supply:1.4,demand:1.4,'liquidity sweep':1.8,'break & retest':1.7};
    const signalBonus=signals.reduce((s,x)=>s+(bonusMap[x]||0),0);
    out.push({price,low,high,timeframe,kind,touches,retests,recency,strength:Math.max(cfg.base+touchBonus+recencyBonus+freshBonus+signalBonus,.1),freshness:fresh,signals});
  }
  return out.sort((a,b)=>b.strength-a.strength).slice(0,14);
}

function weightedAverage(vals,weights){const den=weights.reduce((a,b)=>a+b,0);return vals.reduce((s,v,i)=>s+v*weights[i],0)/den;}
function mergeTimeframes(levelsByTf,currentPrice) {
  const all=Object.values(levelsByTf).flat().sort((a,b)=>a.price-b.price);
  const merged=[];
  for(const lvl of all) {
    if(!merged.length){merged.push([lvl]);continue;}
    const grp=merged[merged.length-1],weights=grp.map(x=>Math.max(x.strength,.1));
    const center=weightedAverage(grp.map(x=>x.price),weights);
    const tol=Math.max(center*.0025,...grp.concat([lvl]).map(x=>x.high-x.low));
    Math.abs(lvl.price-center)<=tol?grp.push(lvl):merged.push([lvl]);
  }
  const tfOrder={'1d':0,'4h':1,'1h':2}, freshRank={fresh:0,tested:1,mature:2};
  const rows=merged.map(grp=>{
    const weights=grp.map(x=>Math.max(x.strength,.1)),mid=weightedAverage(grp.map(x=>x.price),weights);
    const low=Math.min(...grp.map(x=>x.low)),high=Math.max(...grp.map(x=>x.high));
    const tfs=[...new Set(grp.map(x=>x.timeframe))].sort((a,b)=>tfOrder[a]-tfOrder[b]);
    const score=grp.reduce((s,x)=>s+x.strength,0)+({1:0,2:3,3:5}[tfs.length]||0);
    const fresh=[...grp.map(x=>x.freshness)].sort((a,b)=>freshRank[a]-freshRank[b])[0];
    return {zone:`${fmtPrice(low)} – ${fmtPrice(high)}`,low,high,mid,type:mid>=currentPrice?'resistance':'support',timeframes:tfs.map(x=>x.toUpperCase()).join(' + '),touches:grp.reduce((s,x)=>s+x.touches,0),retests:Math.max(...grp.map(x=>x.retests)),freshness:fresh,signals:[...new Set(grp.flatMap(x=>x.signals))].sort(),score:+score.toFixed(2),distance_pct:+((mid/currentPrice-1)*100).toFixed(2)};
  });
  return rows.map(r=>({...r,rank_metric:r.score-Math.abs(r.distance_pct)*.08})).sort((a,b)=>b.rank_metric-a.rank_metric).slice(0,12).map(({rank_metric,...r})=>r);
}

async function analyse() {
  errorBox.classList.add('hidden'); setLoading(true);
  try {
    const symbol=symbolEl.value.trim();
    if(!symbol) throw new Error('Enter a symbol.');
    const charts=await loadMarketData(state.provider,symbol);
    const currentPrice=charts['1h'][charts['1h'].length-1].close;
    const byTf={'1d':detectLevels(charts['1d'],'1d'),'4h':detectLevels(charts['4h'],'4h'),'1h':detectLevels(charts['1h'],'1h')};
    const levels=mergeTimeframes(byTf,currentPrice);
    state.data={symbol,current_price:currentPrice,levels,charts};
    renderAll();
  } catch(err) {
    errorBox.textContent = err && err.message ? err.message : String(err);
    errorBox.classList.remove('hidden');
  } finally { setLoading(false); }
}

function renderAll() {
  const d=state.data,levels=d.levels||[];
  $('summary').classList.remove('hidden'); $('results').classList.remove('hidden');
  $('mSymbol').textContent=d.symbol; $('mPrice').textContent=fmtPrice(d.current_price); $('mZones').textContent=levels.length;
  $('mScore').textContent=levels.length?Math.max(...levels.map(x=>x.score)).toFixed(1):'—';
  const supports=levels.filter(x=>x.mid<d.current_price).sort((a,b)=>b.mid-a.mid),res=levels.filter(x=>x.mid>=d.current_price).sort((a,b)=>a.mid-b.mid);
  $('nearestSupport').textContent=supports[0]?`${supports[0].zone} · ${supports[0].freshness} · score ${supports[0].score.toFixed(1)}`:'None detected';
  $('nearestResistance').textContent=res[0]?`${res[0].zone} · ${res[0].freshness} · score ${res[0].score.toFixed(1)}`:'None detected';
  $('levelsBody').innerHTML=levels.map(l=>`<tr><td><span class="pill ${esc(l.type)}">${esc(l.type)}</span></td><td>${esc(l.zone)}</td><td>${esc(l.timeframes)}</td><td>${esc(l.freshness)} · ${l.retests} retest${l.retests===1?'':'s'}</td><td>${l.signals.length?l.signals.map(esc).join(', '):'—'}</td><td><strong>${l.score.toFixed(1)}</strong></td><td>${l.distance_pct>0?'+':''}${l.distance_pct.toFixed(2)}%</td></tr>`).join('')||'<tr><td colspan="7">No reliable zones detected.</td></tr>';
  renderChart();
}
function visibleLevels(tf) {
  if(!state.data) return [];
  const tag=tf.toUpperCase();
  return state.data.levels.filter(l=>l.timeframes.includes(tag)||tf==='1h');
}
function renderChart() {
  if(!state.data||!window.Plotly)return;
  const tf=state.timeframe,rows=state.data.charts[tf]||[]; if(!rows.length)return;
  const x=rows.map(r=>r.time);
  const trace={type:'candlestick',x,open:rows.map(r=>r.open),high:rows.map(r=>r.high),low:rows.map(r=>r.low),close:rows.map(r=>r.close),increasing:{line:{color:'#50d890'}},decreasing:{line:{color:'#ff6978'}},name:state.data.symbol};
  const shapes=visibleLevels(tf).map(l=>({type:'rect',xref:'x',yref:'y',x0:x[0],x1:x[x.length-1],y0:l.low,y1:l.high,fillcolor:l.type==='support'?'rgba(81,216,138,.10)':'rgba(255,107,122,.10)',line:{color:l.type==='support'?'rgba(81,216,138,.52)':'rgba(255,107,122,.52)',width:1},layer:'below'}));
  const annotations=visibleLevels(tf).slice(0,7).map(l=>({xref:'paper',x:1,y:l.mid,yref:'y',text:`${l.freshness[0].toUpperCase()} · ${fmtPrice(l.mid)} · ${l.score.toFixed(1)}`,showarrow:false,xanchor:'right',font:{size:10,color:l.type==='support'?'#7aeba8':'#ff8f9b'},bgcolor:'rgba(7,16,24,.72)',borderpad:3}));
  Plotly.react('chart',[trace],{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'#08131c',font:{color:'#9db2c0'},margin:{l:58,r:25,t:12,b:32},xaxis:{rangeslider:{visible:false},gridcolor:'#132635',linecolor:'#274052'},yaxis:{side:'right',gridcolor:'#132635',linecolor:'#274052',fixedrange:false},shapes,annotations,dragmode:'pan',showlegend:false,hovermode:'x unified'},{responsive:true,displaylogo:false,scrollZoom:true});
}
