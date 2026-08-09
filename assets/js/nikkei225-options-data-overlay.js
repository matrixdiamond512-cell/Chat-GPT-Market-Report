(function(){
'use strict';

const BASE_RE=/nikkei225-supply-demand\.json(?:$|[?#])/;
const OVERLAY_URL='data/nikkei225-options-latest.json';
const nativeFetch=window.fetch.bind(window);

window.fetch=async function(input,init){
  const url=typeof input==='string'?input:(input&&input.url)||'';
  const response=await nativeFetch(input,init);
  if(!BASE_RE.test(url)||!response.ok)return response;
  try{
    const [base,overlayResponse]=await Promise.all([
      response.clone().json(),
      nativeFetch(OVERLAY_URL,{cache:'no-store'}).catch(()=>null)
    ]);
    if(!overlayResponse||!overlayResponse.ok)return response;
    const overlay=await overlayResponse.json();
    base.options=Object.assign({},base.options||{},overlay||{});
    return new Response(JSON.stringify(base),{
      status:response.status,
      statusText:response.statusText,
      headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}
    });
  }catch(err){
    console.warn('nikkei225 options overlay unavailable',err);
    return response;
  }
};
})();
