"""Best-effort official macro time series and market-moving news RSS.
Never invent forecast/actual values or publication timestamps."""
import csv,io,json,datetime,re
from pathlib import Path
from urllib.parse import quote
import requests,feedparser
P=Path(__file__).resolve().parent/"data.json"
d=json.loads(P.read_text())
S=requests.Session();S.headers.update({"User-Agent":"GlobalMarketDashboard/1.0 (public market research)"})
def get(url):
 r=S.get(url,timeout=13);r.raise_for_status();return r
def fred(code):
 url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
 rows=list(csv.DictReader(io.StringIO(get(url).text)))
 valid=[(r["DATE"],float(r[code])) for r in rows if r.get(code) not in (None,"",".")]
 return valid[-2:] if valid else []
macro=[]
for region,name,code,unit,frequency,impact in [
 ("US","Consumer Price Index (CPI)","CPIAUCSL","Index, seasonally adjusted","Monthly","Inflation / Fed"),
 ("US","Core CPI","CPILFESL","Index, seasonally adjusted","Monthly","Underlying inflation"),
 ("US","Unemployment rate","UNRATE","%","Monthly","Jobs / Fed"),
 ("US","Effective Fed funds rate","EFFR","%","Daily","Fed policy / yields"),
 ("US","Real GDP","GDPC1","Billions of chained USD","Quarterly","Growth / earnings"),
 ("India","Consumer price inflation (annual)","FP.CPI.TOTL.ZG","% YoY","Annual","Inflation / RBI"),
 ("India","GDP growth (annual)","NY.GDP.MKTP.KD.ZG","% YoY","Annual","Growth / earnings")]:
 try:
  if region=="US":
   obs=fred(code);date,val=obs[-1];prev=obs[-2][1] if len(obs)>1 else None
   source="Federal Reserve Economic Data (FRED), original US agency";url=f"https://fred.stlouisfed.org/series/{code}"
  else:
   url=f"https://api.worldbank.org/v2/country/IND/indicator/{code}?format=json&per_page=30"
   obj=get(url).json()
   obs=sorted([(x["date"],float(x["value"])) for x in obj[1] if x.get("value") is not None],key=lambda a:a[0])
   date,val=obs[-1];prev=obs[-2][1] if len(obs)>1 else None
   source="World Bank (annual historical indicator)";url=f"https://data.worldbank.org/indicator/{code}?locations=IN"
  macro.append({"region":region,"event":name,"actual":round(val,3),"previous":round(prev,3) if prev is not None else None,"forecast":None,"period":date,"unit":unit,"frequency":frequency,"impact":impact,"source":source,"url":url})
 except Exception as e:print("MACRO FAILED",name,str(e)[:120])
# Keep previously verified values if a temporary endpoint fails.
for x in d.get("macro",[]):
 if not any(y["event"]==x.get("event") and y["region"]==x.get("region") for y in macro):
  if x.get("actual") is not None:macro.append(x)
macro.sort(key=lambda x:(0 if x["region"]=="US" else 1,x["event"]))
queries=[
 ("US","Federal Reserve inflation jobs treasury stock market when:3d"),
 ("US","Nasdaq technology stocks earnings AI chips when:3d"),
 ("India","RBI inflation rupee Nifty markets when:3d"),
 ("India","India economy companies earnings stock market when:3d")]
news=[];seen=set()
for region,q in queries:
 try:
  rss="https://news.google.com/rss/search?q="+quote(q)+"&hl=en-IN&gl=IN&ceid=IN:en"
  parsed=feedparser.parse(get(rss).content)
  for item in parsed.entries[:6]:
   title=re.sub("<[^>]*>","",item.get("title","")).strip()
   link=item.get("link","")
   if not title or not link or title.lower() in seen:continue
   seen.add(title.lower())
   news.append({"region":region,"title":title,"url":link,"published":item.get("published",""),"source":item.get("source",{}).get("title","Google News RSS"),"type":"Aggregated headline; significance not independently verified"})
 except Exception as e:print("NEWS FAILED",region,str(e)[:120])
if not news:news=d.get("news",[])
d["macro"]=macro;d["news"]=news[:20]
d["macroNewsAsOf"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
d["macroNewsNotes"]="US FRED official-source historical series and India World Bank annual indicators; India annual CPI/GDP are NOT the latest monthly CPI or quarterly GDP. Forecasts and upcoming event calendar are not connected. News is aggregated Google News RSS; verify articles with original publishers."
P.write_text(json.dumps(d,indent=2)+"\n")
print("Macro records",len(macro),"News headlines",len(news))
