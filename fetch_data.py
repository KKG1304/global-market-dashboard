import json,datetime,os,time
from pathlib import Path
import yfinance as yf
ROOT=Path(__file__).resolve().parent
symbols=[("Nifty 50","India","^NSEI","points"),("Bank Nifty","India","^NSEBANK","points"),("India VIX","India","^INDIAVIX","points"),("Nasdaq Composite","US","^IXIC","points"),("S&P 500","US","^GSPC","points"),("Dow Jones","US","^DJI","points"),("Brent Crude","Commodity","BZ=F","USD/bbl"),("Gold Futures","Commodity","GC=F","USD/oz"),("Silver Futures","Commodity","SI=F","USD/oz"),("Bitcoin","Crypto","BTC-USD","USD"),("USD/INR","FX","INR=X","INR/USD")]
def num(x):
 try:
  v=float(x)
  return round(v,3) if v==v and abs(v)!=float("inf") else None
 except Exception:return None
old={}
try:old=json.loads((ROOT/"data.json").read_text())
except Exception:pass
markets=[]
for name,region,symbol,unit in symbols:
 row={"name":name,"region":region,"symbol":symbol,"unit":unit,"price":None,"change":None,"sma50":None,"sma100":None,"sma200":None,"quoteTime":None,"status":"unavailable","source":"Yahoo Finance via yfinance (unofficial)"}
 try:
  h=yf.Ticker(symbol).history(period="2y",interval="1d",auto_adjust=False).dropna(subset=["Close"])
  if len(h):
   close=h["Close"];row["price"]=num(close.iloc[-1]);row["quoteTime"]=h.index[-1].isoformat()
   if len(close)>1 and close.iloc[-2]:row["change"]=round((float(close.iloc[-1])/float(close.iloc[-2])-1)*100,2)
   for n in (50,100,200):
    if len(close)>=n:row["sma"+str(n)]=num(close.tail(n).mean())
   row["status"]="daily historical/delayed (not live)"
 except Exception as e:row["error"]=str(e)[:120]
 if row["price"] is None:
  prior=next((x for x in old.get("markets",[]) if x.get("symbol")==symbol and x.get("price") is not None),None)
  if prior:
   row=prior.copy()
   row["status"]="STALE: last verified snapshot; automatic source unavailable"
 markets.append(row);time.sleep(.2)
if not any(r["price"] is not None for r in markets) and old.get("markets"):
 markets=old["markets"];status="STALE: all new price requests failed"
else:status="Daily historical/delayed quotes; unavailable symbols retain dated prior snapshots. 15-minute freshness NOT guaranteed"
out={"asOf":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dataStatus":status,"markets":markets,"macro":[],"news":[],"sourceNotes":"NSE and Nasdaq are reference sites, not scraped. Gold and silver here are USD futures, NOT MCX INR prices. Macro and news feeds are not yet connected.","lastSuccessfulMarketData":max((r["quoteTime"] for r in markets if r.get("quoteTime")),default=None)}
(ROOT/"data.json").write_text(json.dumps(out,indent=2))
print("Available",sum(r["price"] is not None for r in markets),"of",len(markets))
