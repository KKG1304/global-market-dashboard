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
 return valid[-16:] if valid else []
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
  # Actual includes verified YoY / QoQ only where comparable observations exist.
  yearly=None;quarterly=None
  if region=="US" and len(obs)>=5 and frequency=="Quarterly" and obs[-5][1]:
   yearly=round(100*(val/obs[-5][1]-1),2)
  if region=="US" and frequency=="Quarterly" and len(obs)>=2 and prev:
   quarterly=round(100*((val/prev)**4-1),2) # annualized quarterly GDP growth
  if region=="US" and frequency=="Monthly" and "Price Index" in name and len(obs)>=13 and obs[-13][1]:
   yearly=round(100*(val/obs[-13][1]-1),2)
  if region=="India" and frequency=="Annual":yearly=round(val,2)
  macro.append({"region":region,"event":name,"date":date,"actual":round(val,3),"previous":round(prev,3) if prev is not None else None,"forecast":None,"estimateRemarks":"No verified consensus estimate available; compare the actual release with the prior period.","period":date,"unit":unit,"frequency":frequency,"impact":impact,"impactLevel":"High" if name in ("Real GDP","Consumer Price Index (CPI)","Unemployment rate","GDP growth (annual)") else "Medium","actualYoY":yearly,"actualQoQ":quarterly,"source":source,"url":url})
 except Exception as e:print("MACRO FAILED",name,str(e)[:120])
# Keep previously verified values if a temporary endpoint fails.
for x in d.get("macro",[]):
 if not any(y["event"]==x.get("event") and y["region"]==x.get("region") for y in macro):
  if x.get("actual") is not None:macro.append(x)
macro.sort(key=lambda x:(0 if x["region"]=="US" else 1,x["event"]))
queries=[
 ("US","Markets","Federal Reserve inflation jobs treasury stock market when:3d"),
 ("US","Technology","Nasdaq technology stocks earnings AI chips when:3d"),
 ("India","Markets","RBI inflation rupee Nifty markets when:3d"),
 ("India","Pharma","India pharmaceutical company USFDA approval when:30d")]
# Official central-bank announcements take precedence over aggregated coverage.
news=[];seen=set()
official_feeds=[
 ("US","Federal Reserve","https://www.federalreserve.gov/feeds/press_all.xml"),
 ("India","RBI policy / circulars","https://www.rbi.org.in/scripts/rss.aspx?Id=1")]
for region,sector,url in official_feeds:
 try:
  parsed=feedparser.parse(get(url).content)
  for item in parsed.entries[:3]:
   title=re.sub("<[^>]*>","",item.get("title","")).strip()
   link=item.get("link","")
   if title and link and title.lower() not in seen:
    seen.add(title.lower())
    news.append({"region":region,"sector":sector,"title":title,"url":link,"published":item.get("published",""),"source":"Official Federal Reserve" if region=="US" else "Official RBI","impactRemark":"Official regulatory or policy release; sector impact depends on the specific decision."})
 except Exception as e:print("OFFICIAL FEED FAILED",region,str(e)[:120])
for region,sector,q in queries:
 try:
  rss="https://news.google.com/rss/search?q="+quote(q)+"&hl=en-IN&gl=IN&ceid=IN:en"
  parsed=feedparser.parse(get(rss).content)
  for item in parsed.entries[:8]:
   title=re.sub("<[^>]*>","",item.get("title","")).strip()
   link=item.get("link","")
   if not title or not link or title.lower() in seen:continue
   seen.add(title.lower())
   news.append({"region":region,"sector":sector,"title":title,"url":link,"published":item.get("published",""),"source":item.get("source",{}).get("title","Google News RSS"),"impactRemark":("Potential impact on Indian insurers and distribution; confirm regulatory details and affected companies." if sector=="Insurance / IRDAI" else "Potential impact on Indian pharma revenue, compliance or product pipeline; verify company-specific exposure." if sector=="Pharma" else "Potential market or sector impact; assess the original article before investing."),"type":"Aggregated headline; significance not independently verified"})
   break
 except Exception as e:print("NEWS FAILED",region,str(e)[:120])
if not news:news=d.get("news",[])
# Exactly three slots per region, prioritizing insurance and pharma among Indian items.
# US: official Fed first, then market headlines. India: one market item, one IRDAI item, one pharma item where available.
selected=[]
for region in ("US","India"):
 pool=[x for x in news if x.get("region")==region]
 if region=="US":selected+=pool[:3]
 else:
  for sector in ("Insurance / IRDAI","Pharma"):
   match=next((x for x in pool if x.get("sector")==sector),None)
   if match:selected.append(match)
  selected+= [x for x in pool if x not in selected][:max(0,3-len([x for x in selected if x.get("region")=="India"]))]
news=selected[:6]
d["macro"]=macro;d["news"]=news[:6]
d["macroNewsAsOf"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
d["macroNewsNotes"]="US FRED official-source historical series and India World Bank annual indicators; India annual CPI/GDP are NOT the latest monthly CPI or quarterly GDP. Forecast consensus and upcoming release dates are not connected; missing estimates are explicitly labeled. US quarterly GDP growth is annualized; YoY changes are calculated from matching periods. News is aggregated Google News RSS; verify articles with original publishers."
P.write_text(json.dumps(d,indent=2)+"\n")
print("Macro records",len(macro),"News headlines",len(news))
