"""Timestamped delayed intraday quotes where available; daily closes for SMA."""
import datetime,json
from pathlib import Path
import pandas as pd
import yfinance as yf
ROOT=Path(__file__).resolve().parent
try: old=json.loads((ROOT/"data.json").read_text())
except Exception: old={}
specs=[("Nifty 50","India","^NSEI","points"),("India VIX","India","^INDIAVIX","points"),("NASDAQ-100 (Tech-focused)","US","^NDX","points"),("Brent Crude","Commodity","BZ=F","USD/bbl"),("Bitcoin","Crypto","BTC-USD","USD"),("USD/INR","FX","INR=X","INR per USD")]
def num(v):
 try:
  v=float(v)
  return round(v,2) if pd.notna(v) else None
 except (ValueError,TypeError):return None
def daily(ticker):
 h=yf.Ticker(ticker).history(period="2y",interval="1d",auto_adjust=False)
 if h is None or h.empty:return pd.Series(dtype="float64")
 c=h["Close"].dropna()
 c.index=pd.to_datetime(c.index).tz_localize(None).normalize()
 return c[~c.index.duplicated(keep="last")].sort_index()
def intraday(ticker):
 try:
  h=yf.Ticker(ticker).history(period="5d",interval="5m",auto_adjust=False)
  if h is None or h.empty:return None,None
  close=h["Close"].dropna()
  if close.empty:return None,None
  stamp=close.index[-1]
  if stamp.tzinfo is None:stamp=stamp.tz_localize("UTC")
  return num(close.iloc[-1]),stamp.tz_convert("UTC").isoformat()
 except Exception as e:
  print("INTRADAY ERROR",ticker,str(e)[:160])
  return None,None
def record(name,region,symbol,unit,series,source,note):
 row={"name":name,"region":region,"symbol":symbol,"unit":unit,"price":None,"change":None,"sma50":None,"sma100":None,"sma200":None,"quoteTime":None,"status":"unavailable","source":source,"note":note}
 if len(series):
  row["price"]=num(series.iloc[-1]);row["quoteTime"]=series.index[-1].date().isoformat()
  if len(series)>=2 and series.iloc[-2]!=0:row["change"]=num(100*(series.iloc[-1]/series.iloc[-2]-1))
  for n in (50,100,200):
   if len(series)>=n:row["sma"+str(n)]=num(series.iloc[-n:].mean())
  row["status"]="Previous/daily close; not intraday"
 return row
cache={}
def get(t):
 if t not in cache:
  try:cache[t]=daily(t)
  except Exception as e:
   print("FETCH ERROR",t,str(e)[:160]);cache[t]=pd.Series(dtype="float64")
 return cache[t]
markets=[]
for name,region,symbol,unit in specs:
 row=record(name,region,symbol,unit,get(symbol),"Yahoo Finance via yfinance (unofficial)","SMA from daily closes; intraday prices can be delayed")
 price,stamp=intraday(symbol)
 if price is not None and stamp:
  now=datetime.datetime.now(datetime.timezone.utc)
  observed=datetime.datetime.fromisoformat(stamp)
  age=(now-observed).total_seconds()/60
  if -5<=age<=120:
   row["previousClose"]=row["price"]
   # On the same date, daily bar can represent today's partial close; use prior daily bar instead.
   series=get(symbol)
   if len(series)>=2 and series.index[-1].date()==observed.date():
    row["previousClose"]=num(series.iloc[-2])
   row["price"]=price
   row["quoteTime"]=stamp
   row["change"]=num(100*(price/row["previousClose"]-1)) if row["previousClose"] else None
   row["status"]="Intraday delayed; quote age "+str(round(age))+" minutes"
  else:
   row["status"]="Previous/daily close; intraday quote too old ("+str(round(age))+" min)"
 markets.append(row)
fx=get("INR=X")
for name,ticker,unit,factor in [("Gold (INR, indicative)","GC=F","INR/10g",10/31.1034768),("Silver (INR, indicative)","SI=F","INR/kg",1000/31.1034768)]:
 usd=get(ticker)
 # Use same-date observations, never mix unrelated closing dates for SMA.
 aligned=pd.concat([usd.rename("metal"),fx.rename("fx")],axis=1,join="inner").dropna()
 converted=(aligned["metal"]*aligned["fx"]*factor).sort_index()
 markets.append(record(name,"Commodity",ticker+" × INR=X",unit,converted,"COMEX futures and USD/INR via Yahoo Finance (unofficial)","Indicative INR conversion, NOT MCX traded price; excludes local premium, duty, tax and contract basis"))
# Never lose a dated verified value when free upstream data fails.
for row in markets:
 if row["price"] is None:
  prev=next((x for x in old.get("markets",[]) if x.get("name")==row["name"] and x.get("price") is not None),None)
  if prev:
   row.update({k:prev.get(k) for k in ("price","change","quoteTime","sma50","sma100","sma200")})
   row["status"]="STALE: preserved previous dated snapshot; upstream unavailable"
count=sum(x["price"] is not None for x in markets)
data={"asOf":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dataStatus":f"Delayed intraday where available; {count}/{len(markets)} prices available. Check each quote time; 20-minute freshness not guaranteed.","markets":markets,"macro":[],"news":[],"sourceNotes":"NASDAQ-100 is tech-heavy, not exclusively technology. Gold INR/10g and Silver INR/kg are indicative COMEX × FX conversions, NOT MCX prices. SMA50/100/200 calculated from daily closing prices only where sufficient observations exist. Missing data remains blank; last verified snapshots are dated.","lastSuccessfulMarketData":max((x["quoteTime"] for x in markets if x.get("quoteTime")),default=None)}
(ROOT/"data.json").write_text(json.dumps(data,indent=2)+"\n")
print(data["dataStatus"])
