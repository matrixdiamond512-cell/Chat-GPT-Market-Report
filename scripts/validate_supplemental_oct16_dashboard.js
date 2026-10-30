#!/usr/bin/env node
"use strict";
/* Exactly the six read-back quotes, never substitute latest-market quotes. */
const {chromium} = require("playwright");
const base=(process.env.PORTAL_URL||"http://127.0.0.1:8765").replace(/\/$/,"");
const expectations=[
 ["金先物（COMEX 12月限）","4,170.10","10/15 NY終値・COMEX金12月限","ドル安","4,180","4,100"],
 ["WTI原油先物（11月限）","97.97","10/15 NY終値・WTI11月限","上昇警戒","98ドル","95ドル"],
 ["日経225先物（大阪・夜間）","65,520","10/16 06:00夜間終値・OSE12月限","自律反発","65,500","65,000"],
 ["USD/JPY","158.00","10/15 NY終値・USD/JPY","米10年金利","158.35","157.55"],
 ["EUR/USD","1.1220","10/15 NY終値・EUR/USD","ドル安","1.1241","1.1200"],
 ["BTC/USD（07:33参考）","82,454.9","10/16 07:33頃の参考値・BTC/USD","反発","82,600","81,000"]
];
(async()=>{
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];
 page.on("pageerror",e=>errors.push(e.message));
 await page.goto(base+"/index.html?date=2026-10-16&time=08%3A00&cardCheck="+Date.now(),{waitUntil:"domcontentloaded",timeout:60000});
 await page.waitForFunction(()=>document.querySelectorAll("#marketCards .market-card").length===6
     && document.querySelector("#marketCards .market-card .market-basis-line")?.textContent?.includes("補充保存本文"),
     null,{timeout:45000});
 const records=await page.evaluate(()=>({
   chosen:[selectedReport?.date,selectedReport?.time],
   archive:selectedReport?.archiveStatus,
   published:selectedReport?.report_status,
   quotes:selectedReport?.archiveQuotes,
   cards:Array.from(document.querySelectorAll("#marketCards .market-card")).map(card=>({
     heading:card.querySelector("h3")?.innerText||"",
     price:card.querySelector(".market-value")?.innerText||"",
     basis:card.querySelector(".market-basis-line")?.innerText||"",
     change:card.querySelector(".change-line")?.innerText||"",
     reason:card.querySelectorAll("dl dd")[0]?.innerText||"",
     keyPoint:card.querySelectorAll("dl dd")[1]?.innerText||"",
     risk:card.querySelectorAll("dl dd")[2]?.innerText||"",
     verdict:card.querySelector(".consistency-badge")?.innerText||""
   }))
 }));
 const fail=[];
 if(records.chosen.join(" ")!=="2026-10-16 08:00")fail.push("wrong selected slot: "+records.chosen);
 if(records.archive!=="HISTORICAL_ARCHIVE")fail.push("archive status lost");
 if(records.published==="PUBLISHED"||records.published==="DOC_READBACK_PASS")fail.push("unverified archive promoted to formal");
 if(records.cards.length!==6)fail.push("six market cards missing");
 for(let i=0;i<expectations.length;i++){
  const [heading,price,basis,reason,level,risk]=expectations[i],card=records.cards[i]||{};
  if(!card.heading?.includes(heading))fail.push("heading "+i+": "+card.heading);
  if(!card.price?.includes(price))fail.push("price "+i+": "+card.price);
  if(!card.basis?.includes(basis))fail.push("basis "+i+": "+card.basis);
  if(!card.reason?.includes(reason))fail.push("reason "+i+": "+card.reason);
  if(!card.keyPoint?.includes(level))fail.push("key point "+i+": "+card.keyPoint);
  if(!card.risk?.includes(risk))fail.push("risk "+i+": "+card.risk);
  if(card.reason===card.keyPoint||card.reason===card.risk||card.keyPoint===card.risk)fail.push("duplicated reason/levels/risk "+i);
  if(!card.verdict?.includes("判定保留"))fail.push("unjustified verified causation badge "+i+": "+card.verdict);
 }
 if(!records.cards[5]?.change?.includes("比較対象なし"))fail.push("BTC unmatched price presented as daily close");
 if(!records.cards[2]?.change?.includes("+720"))fail.push("OSE daily settlement change missing");
 if(errors.length)fail.push("javascript errors: "+errors.join("; "));
 if(fail.length)throw Error(fail.join("\n"));
 console.log("PASS: 2026-10-16 08:00 six archive market cards show 6 exact scoped prices, distinct reasons/levels/risks, and unchanged verification gates");
} finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
