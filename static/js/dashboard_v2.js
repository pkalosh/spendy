

<!-- FILE: static/js/dashboard_v2.js -->
(function(){
// Theme toggle
const html = document.documentElement;
const btnDark = document.getElementById('btnDark');
btnDark && btnDark.addEventListener('click', ()=>{
const isDark = html.getAttribute('data-theme') === 'dark';
html.setAttribute('data-theme', isDark ? 'light' : 'dark');
});


// Chart: small sparkline for spend (uses template-provided data)
function toArraySafe(val){ try{ return JSON.parse(val); }catch(e){ return []; } }


const spendCtx = document.getElementById('chartSpend');
if(spendCtx){
const spendData = toArraySafe(document.getElementById('spendTrendData') ? document.getElementById('spendTrendData').textContent : '[]');
new Chart(spendCtx,{ type:'line', data:{ labels: spendData.map((_,i)=>i+1), datasets:[{data:spendData, tension:0.35, borderWidth:2, borderColor:getComputedStyle(document.documentElement).getPropertyValue('--primary') || '#98e23f', fill:false, pointRadius:0 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false} }, scales:{ x:{ display:false }, y:{ display:false } } } });
}


// Spend Trend big chart
const spendTrendEl = document.getElementById('spendTrend');
if(spendTrendEl){
// Example: pull data from data attributes or provide sample fallback
const trendData = (function(){
try{ return JSON.parse(document.getElementById('spendTrendJson').textContent) }catch(e){ return {labels:[], data:[]} }
})();


new Chart(spendTrendEl,{
type:'line',
data:{ labels: trendData.labels || [], datasets:[{label:'Spend', data: trendData.data || [], tension:0.3, borderWidth:2, pointRadius:3, backgroundColor:'rgba(152,226,63,0.12)', borderColor:'rgba(152,226,63,1)', fill:true }] },
options:{ responsive:true, plugins:{ legend:{display:false} }, scales:{ y:{ ticks:{callback:function(val){ return 'KES ' + val.toLocaleString(); } } } }
});
}


// Simple search UI (client-side filter of visible activity items)
const searchInput = document.getElementById('searchInput');
if(searchInput){
searchInput.addEventListener('input', (e)=>{
const q = e.target.value.toLowerCase();
document.querySelectorAll('.activity-item').forEach(item=>{
const txt = item.innerText.toLowerCase();
item.style.display = txt.includes(q) ? '' : 'none';
});
});
}


})();


