// Cloudflare Worker: receives Discord HTTP interactions. No persistent process needed.
const EPIC = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=ja-JP&country=JP&allowCountries=JP';
const json = (body, status=200) => new Response(JSON.stringify(body), {status,headers:{'Content-Type':'application/json;charset=utf-8'}});
const hex = s => new Uint8Array((s.match(/.{2}/g)||[]).map(x=>parseInt(x,16)));
const truncate = (s,n) => s.length > n ? s.slice(0,n-1)+'…' : s;

async function verify(req, raw, publicKey) {
  const signature=req.headers.get('x-signature-ed25519');
  const stamp=req.headers.get('x-signature-timestamp');
  if (!signature || !stamp || !publicKey || !/^[0-9a-f]{128}$/i.test(signature) || !/^[0-9a-f]{64}$/i.test(publicKey)) return false;
  if (!/^\d+$/.test(stamp) || Math.abs(Date.now()/1000 - Number(stamp)) > 300) return false;
  try {
    const key=await crypto.subtle.importKey('raw',hex(publicKey),{name:'Ed25519'},false,['verify']);
    return await crypto.subtle.verify('Ed25519',key,hex(signature),new TextEncoder().encode(stamp+raw));
  } catch { return false; }
}
function parseGames(data) {
  const now=Date.now(), current=new Map(), upcoming=new Map();
  for (const g of data?.data?.Catalog?.searchStore?.elements||[]) {
    if (g.offerType && g.offerType!=='BASE_GAME') continue;
    for (const [field,map] of [['promotionalOffers',current],['upcomingPromotionalOffers',upcoming]]) {
      for (const group of (g.promotions?.[field]||[])) for (const offer of (group.promotionalOffers||[])) {
        const start=Date.parse(offer.startDate), end=Date.parse(offer.endDate);
        if (offer.discountSetting?.discountPercentage!==0 || !Number.isFinite(start) || !Number.isFinite(end) || start>=end) continue;
        if (field==='promotionalOffers' && !(start<=now && now<end)) continue;
        if (field==='upcomingPromotionalOffers' && !(now<start)) continue;
        let slug=(g.offerMappings||[]).find(x=>x.pageSlug)?.pageSlug||g.productSlug||g.urlSlug;
        let url='https://store.epicgames.com/ja/free-games';
        if (slug?.startsWith('https://store.epicgames.com/')) url=slug;
        else if (slug) url='https://store.epicgames.com/ja/p/'+encodeURI(slug.replace(/^\/+|\/+$/g,'').replace(/\/home$/,''));
        const id=(g.id||g.namespace||slug||g.title)+'|'+offer.startDate;
        map.set(id,{title:g.title||'タイトル未発表',start,end,url});
      }
    }
  }
  return {current:[...current.values()].sort((a,b)=>a.end-b.end),upcoming:[...upcoming.values()].sort((a,b)=>a.start-b.start)};
}
function displayDate(ms) { return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(ms))+' JST'; }
function makeReply(games,type) {
  const isCurrent=type==='free';
  const title=isCurrent?'🎁 現在配布中の無料ゲーム':'📅 次回無料配布の予告';
  const list=isCurrent?games.current:games.upcoming;
  const entries=list.slice(0,10).map(g=>`**${truncate(g.title,150)}**\n${isCurrent?'終了':'開始'}：${displayDate(isCurrent?g.end:g.start)}\n${g.url}`);
  const content=entries.length?`${title}\n\n${entries.join('\n\n')}`:`${title}\n現在、該当する情報を取得できませんでした。未発表・配信地域などが理由の可能性があります。`;
  return {type:4,data:{content:truncate(content,1900),flags:64,allowed_mentions:{parse:[]}}};
}
export default {
  async fetch(request,env,ctx) {
    if (request.method!=='POST') return new Response('Discord interaction endpoint', {status:200});
    const raw=await request.text();
    if (!(await verify(request,raw,env.DISCORD_PUBLIC_KEY))) return new Response('Invalid signature',{status:401});
    let interaction;try {interaction=JSON.parse(raw);}catch {return new Response('Bad JSON',{status:400});}
    if (interaction.type===1) return json({type:1});
    if (interaction.type!==2) return json({type:4,data:{content:'対応していない操作です。',flags:64}});
    const name=interaction.data?.name;
    if (name==='ヘルプ')return json({type:4,data:{flags:64,content:'**Epic Free Game Notifier**\n`/無料ゲーム`：現在無料で受け取れるゲーム\n`/次回配布`：予告されている次回無料ゲーム\n`/ヘルプ`：この説明\n\n新規配布・予告・終了前のお知らせはGitHub Actionsから自動投稿されます。'}});
    if (name!=='無料ゲーム' && name!=='次回配布')return json({type:4,data:{content:'不明なコマンドです。',flags:64}});
    // Defer within 3 seconds, then edit the original interaction response asynchronously.
    const work=async()=>{
      let result;
      try {
        const response=await fetch(EPIC,{headers:{'Accept':'application/json'}});
        if (!response.ok)throw Error(`Epic API HTTP ${response.status}`);
        result=makeReply(parseGames(await response.json()),name==='無料ゲーム'?'free':'next').data;
      } catch (e) {result={content:'Epic Gamesの情報取得に失敗しました。時間をおいて再実行してください。',flags:64};console.error(e);}
      const endpoint=`https://discord.com/api/v10/webhooks/${interaction.application_id}/${interaction.token}/messages/@original`;
      const response=await fetch(endpoint,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
      if(!response.ok) console.error('Discord edit failed',response.status);
    };
    // Cloudflare runs this async work after the deferred response is returned.
    ctx.waitUntil(work());
    return json({type:5,data:{flags:64}});
  }
};
