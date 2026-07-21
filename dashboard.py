from pathlib import Path
from datetime import timedelta
import io
import os

import anthropic
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

st.set_page_config(page_title="CFO Command Center", page_icon="◈", layout="wide")
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@500;600;700&display=swap');
  :root {--canvas:#F6F5F1;--surface:#FCFCFA;--ink:#17181C;--muted:#6B6F7B;--indigo:#5B5BD6;--soft:#EEEEFF;--teal:#168C7E;--coral:#D95757;--amber:#C98218;--border:#E5E3DD}
  html,body,[class*="css"] {font-family:'Inter',sans-serif;color:var(--ink)}
  h1,h2,h3,[data-testid="stSidebar"] {font-family:'Manrope',sans-serif}
  .stApp {background:var(--canvas)}
  .block-container {padding-top:1.4rem;padding-bottom:3rem;max-width:1480px}
  [data-testid="stSidebar"] {background:#EEEDE8;border-right:1px solid var(--border)}
  [data-testid="stSidebar"] * {color:var(--ink)}
  [data-testid="stSidebar"] [role="radiogroup"] label {padding:.55rem .7rem;border-radius:9px;transition:all 160ms ease}
  [data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#E3E1FF;transform:translateX(2px)}
  .hero {display:flex;align-items:center;justify-content:space-between;padding:22px 24px;background:var(--surface);border:1px solid var(--border);border-radius:16px;margin-bottom:18px;box-shadow:0 1px 2px rgba(20,20,20,.03)}
  .hero h1 {font-size:30px;letter-spacing:-.8px;margin:0;color:var(--ink)}
  .hero p {color:var(--muted);margin:5px 0 0;font-size:14px}
  .period {font:600 12px 'Manrope';color:var(--indigo);background:var(--soft);padding:8px 12px;border-radius:999px;white-space:nowrap}
  .kpi-card {position:relative;min-height:142px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:17px 18px;transition:transform 160ms ease,border-color 160ms ease,box-shadow 160ms ease;box-shadow:0 1px 2px rgba(20,20,20,.02)}
  .kpi-card:hover {transform:translateY(-2px);border-color:#B7B4F4;box-shadow:0 8px 24px rgba(42,39,94,.08)}
  .kpi-label {font:600 11px 'Manrope';color:var(--muted);letter-spacing:.07em;text-transform:uppercase;display:flex;align-items:center;justify-content:space-between}
  .kpi-value {font:700 29px 'Manrope';letter-spacing:-1px;color:var(--ink);margin:13px 0 7px;font-variant-numeric:tabular-nums}
  .kpi-context {font-size:12px;color:var(--muted);line-height:1.45}
  .kpi-status {display:inline-block;margin-top:9px;font-size:11px;font-weight:600;padding:3px 7px;border-radius:999px;background:var(--soft);color:var(--indigo)}
  .kpi-status.bad {background:#FCEAEA;color:var(--coral)} .kpi-status.good {background:#E7F5F1;color:var(--teal)}
  .info-dot {width:18px;height:18px;border-radius:50%;background:#EFEEE9;color:var(--muted);display:inline-flex;align-items:center;justify-content:center;font:600 11px 'Inter';cursor:help}
  .tooltip {position:relative;display:inline-flex}.tooltip-text {visibility:hidden;opacity:0;position:absolute;z-index:999;width:260px;right:-4px;top:27px;background:#1E2027;color:#fff;padding:12px 13px;border-radius:9px;font:400 12px/1.5 'Inter';box-shadow:0 10px 30px rgba(0,0,0,.18);transition:opacity 140ms ease;text-transform:none;letter-spacing:0}
  .tooltip:hover .tooltip-text {visibility:visible;opacity:1}.tooltip-text b{color:#C7C5FF}
  .brief {background:#F0F0FF;border:1px solid #DEDCF9;border-left:4px solid var(--indigo);padding:17px 19px;border-radius:10px;color:#292A35;line-height:1.65}
  .section-head {font:700 18px 'Manrope';letter-spacing:-.25px;margin:24px 0 4px}.section-copy{font-size:13px;color:var(--muted);margin-bottom:12px}
  div[data-testid="stDataFrame"] {border:1px solid var(--border);border-radius:12px;overflow:hidden}
  div[data-testid="stFileUploader"] {background:var(--surface);border:1px dashed #CBC8BF;border-radius:12px;padding:4px 10px;transition:border-color 160ms ease,background 160ms ease}
  div[data-testid="stFileUploader"]:hover {border-color:var(--indigo);background:#FAFAFF}
  .stButton>button,.stDownloadButton>button {border-radius:9px;border:1px solid var(--indigo);font:600 13px 'Manrope';transition:transform 150ms ease,box-shadow 150ms ease}
  .stButton>button:hover,.stDownloadButton>button:hover {transform:translateY(-1px);box-shadow:0 6px 16px rgba(91,91,214,.16)}
  .demo-note {font-size:12px;color:var(--muted);padding:9px 12px;background:#F0EFEA;border:1px solid var(--border);border-radius:9px}
  @media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
""", unsafe_allow_html=True)

def money(x):
    sign = "-" if x < 0 else ""
    x = abs(float(x))
    return f"{sign}${x/1_000_000:.2f}M" if x >= 1_000_000 else f"{sign}${x/1_000:.1f}K"

def kpi_card(label, value, context, tooltip, status="", tone=""):
    status_html = f'<span class="kpi-status {tone}">{status}</span>' if status else ""
    st.markdown(f'''<div class="kpi-card">
      <div class="kpi-label"><span>{label}</span><span class="tooltip"><span class="info-dot">i</span><span class="tooltip-text">{tooltip}</span></span></div>
      <div class="kpi-value">{value}</div><div class="kpi-context">{context}</div>{status_html}
    </div>''', unsafe_allow_html=True)

def section_header(title, copy=""):
    st.markdown(f'<div class="section-head">{title}</div><div class="section-copy">{copy}</div>',unsafe_allow_html=True)

def load_csv(upload, default_name, required):
    source = io.BytesIO(upload.getvalue()) if upload else BASE_DIR / default_name
    df = pd.read_csv(source)
    missing = set(required) - set(df.columns)
    if missing:
        st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        st.stop()
    return df

def variance_analysis(df):
    df = df.copy()
    df["budget"] = pd.to_numeric(df["budget"], errors="coerce")
    df["actual"] = pd.to_numeric(df["actual"], errors="coerce")
    if df[["budget", "actual"]].isna().any().any():
        raise ValueError("Budget and actual must contain only numbers.")
    df["variance"] = df["actual"] - df["budget"]
    df["variance_pct"] = df["variance"].div(df["budget"].replace(0, pd.NA)).mul(100).fillna(0)
    df["impact"] = df["variance"].where(df["category"].ne("Cost"), -df["variance"])
    df["direction"] = df["impact"].ge(0).map({True:"Favorable", False:"Unfavorable"})
    df["materiality"] = df["variance"].abs()
    return df

def reconcile(bank, gl, tolerance_days=3):
    bank, gl = bank.copy(), gl.copy()
    for frame in (bank, gl):
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    if bank[["date","amount"]].isna().any().any() or gl[["date","amount"]].isna().any().any():
        raise ValueError("Dates or amounts contain invalid values.")

    used_gl, matches, bank_exceptions = set(), [], []
    for bi, b in bank.iterrows():
        exact = gl[(~gl.index.isin(used_gl)) & (gl.reference.astype(str) == str(b.reference)) & (gl.amount == b.amount)]
        candidates = exact
        match_type = "Exact reference"
        if candidates.empty:
            candidates = gl[(~gl.index.isin(used_gl)) & (gl.amount == b.amount) & ((gl.date-b.date).abs() <= timedelta(days=tolerance_days))]
            match_type = "Amount + date"
        if not candidates.empty:
            gi = (candidates.date-b.date).abs().idxmin()
            used_gl.add(gi)
            matches.append({"bank_date":b.date.date(),"bank_description":b.description,"gl_description":gl.loc[gi,"description"],"amount":b.amount,"reference":b.reference,"match_type":match_type})
        else:
            desc = str(b.description).lower()
            prior_same = any(m["amount"] == b.amount and str(m["bank_description"]).lower()[:10] == desc[:10] for m in matches)
            if prior_same:
                kind, risk = "Potential duplicate payment", "High"
            elif b.amount > 0 and ("unknown" in desc or "unidentified" in desc):
                kind, risk = "Unidentified bank credit", "Medium"
            elif b.amount > 0:
                kind, risk = "Receipt missing from GL", "High"
            else:
                kind, risk = "Payment missing from GL", "High"
            bank_exceptions.append({"source":"Bank","date":b.date.date(),"description":b.description,"amount":b.amount,"reference":b.reference,"exception_type":kind,"risk":risk})
    gl_exceptions = [{"source":"GL","date":r.date.date(),"description":r.description,"amount":r.amount,"reference":r.reference,"exception_type":"GL entry missing from bank","risk":"Medium"} for i,r in gl.loc[~gl.index.isin(used_gl)].iterrows()]
    return pd.DataFrame(matches), pd.DataFrame(bank_exceptions + gl_exceptions)

def claude_text(prompt):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        st.warning("Add your new ANTHROPIC_API_KEY to a local .env file to enable AI commentary.")
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        return client.messages.create(model="claude-sonnet-4-6", max_tokens=1100, messages=[{"role":"user","content":prompt}]).content[0].text
    except Exception as exc:
        st.error(f"AI request failed: {exc}")
        return None

with st.sidebar:
    st.title("CFO/OS")
    st.caption("Finance intelligence workspace")
    page = st.radio("Workspace", ["Executive Overview","Variance Intelligence","Reconciliation Control Center"])
    st.divider()
    st.caption("COMPANY")
    st.markdown("**ColdChain Logistics Inc.**")
    st.caption("Meridian Capital portfolio company")
    st.markdown('<div class="demo-note">● Demo workspace<br>Data refreshed January 31, 2025</div>',unsafe_allow_html=True)

st.markdown('<div class="hero"><div><h1>CFO Command Center</h1><p>Performance, controls and AI-supported decisions in one view</p></div><span class="period">JANUARY 2025 · CLOSED</span></div>', unsafe_allow_html=True)

try:
    if "variance_data" not in st.session_state:
        st.session_state.variance_data = variance_analysis(load_csv(None,"variance_data.csv",["line_item","category","budget","actual"]))
    if "bank_data" not in st.session_state:
        st.session_state.bank_data = load_csv(None,"bank_statement.csv",["date","description","amount","reference"])
    if "gl_data" not in st.session_state:
        st.session_state.gl_data = load_csv(None,"gl_export.csv",["date","description","amount","reference"])
    variance = st.session_state.variance_data.copy()
    bank = st.session_state.bank_data.copy()
    gl = st.session_state.gl_data.copy()
    matches, exceptions = reconcile(bank, gl)
except ValueError as exc:
    st.error(str(exc)); st.stop()

def row(name):
    result = variance.loc[variance.line_item.str.casefold() == name.casefold()]
    return None if result.empty else result.iloc[0]

ebitda, revenue, gp = row("EBITDA"), row("Total Revenue"), row("Gross Profit")
match_rate = len(matches) / len(bank) * 100 if len(bank) else 0

if page == "Executive Overview":
    active_sources = []
    if st.session_state.get("variance_uploaded", False): active_sources.append("uploaded variance data")
    if st.session_state.get("reconciliation_uploaded", False): active_sources.append("uploaded reconciliation data")
    source_text = " and ".join(active_sources) if active_sources else "January 2025 demonstration data"
    st.markdown(f'<div class="demo-note">Executive Overview is currently calculated from <b>{source_text}</b>.</div>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    margin = ebitda.actual/revenue.actual*100
    budget_margin = ebitda.budget/revenue.budget*100
    exposure = exceptions.amount.abs().sum() if not exceptions.empty else 0
    with c1: kpi_card("Revenue",money(revenue.actual),f"Budget {money(revenue.budget)}",f"<b>Revenue</b><br>Total income earned during the period.<br><br><b>Variance formula</b><br>Actual − Budget<br>{money(revenue.actual)} − {money(revenue.budget)} = {money(revenue.variance)}",f"{money(abs(revenue.variance))} below plan","bad")
    with c2: kpi_card("EBITDA",money(ebitda.actual),f"Budget {money(ebitda.budget)}",f"<b>EBITDA variance</b><br>Measures operating profit performance against plan.<br><br><b>Formula</b><br>Actual EBITDA − Budget EBITDA<br>{money(ebitda.actual)} − {money(ebitda.budget)} = {money(ebitda.variance)}",f"{money(abs(ebitda.variance))} unfavorable","bad")
    with c3: kpi_card("EBITDA margin",f"{margin:.1f}%",f"Budget margin {budget_margin:.1f}%",f"<b>EBITDA margin</b><br>Operating profitability per dollar of revenue.<br><br><b>Formula</b><br>EBITDA ÷ Revenue × 100<br>{money(ebitda.actual)} ÷ {money(revenue.actual)} = {margin:.1f}%",f"{margin-budget_margin:+.1f} pts vs plan","bad")
    with c4: kpi_card("Match rate",f"{match_rate:.1f}%",f"{len(matches)} of {len(bank)} bank transactions",f"<b>Match rate</b><br>Share of bank transactions linked to the GL.<br><br><b>Formula</b><br>Matched ÷ Total × 100<br>{len(matches)} ÷ {len(bank)} × 100 = {match_rate:.1f}%",f"{len(exceptions)} exceptions open","bad")
    with c5: kpi_card("Exception exposure",money(exposure),"Gross absolute value requiring review",f"<b>Exception exposure</b><br>Total absolute value of unresolved items. It does not represent confirmed loss.<br><br><b>Formula</b><br>Sum of absolute exception amounts = {money(exposure)}","Controller review","bad")

    largest = variance[~variance.line_item.str.startswith("Total") & ~variance.line_item.isin(["Gross Profit","EBITDA"])].nsmallest(3,"impact")
    drivers = ", ".join(f"{r.line_item} ({money(abs(r.variance))})" for _,r in largest.iterrows())
    brief = f"EBITDA finished {money(abs(ebitda.variance))} below budget at {money(ebitda.actual)}, with margin {margin:.1f}% versus {budget_margin:.1f}% planned. The largest adverse drivers were {drivers}. Bank reconciliation is {match_rate:.1f}% complete with {len(exceptions)} open exceptions representing {money(exposure)} of gross exposure."
    section_header("Executive briefing","A calculated summary of the issues most relevant to management.")
    st.markdown(f'<div class="brief">{brief}</div>', unsafe_allow_html=True)
    left,right = st.columns([1.25,1])
    with left:
        fig = go.Figure([go.Bar(name="Budget",x=["Revenue","Gross Profit","EBITDA"],y=[revenue.budget,gp.budget,ebitda.budget],marker_color="#b8c5d8"),go.Bar(name="Actual",x=["Revenue","Gross Profit","EBITDA"],y=[revenue.actual,gp.actual,ebitda.actual],marker_color="#2f6fed")])
        fig.update_layout(title="Plan vs actual",barmode="group",height=380,margin=dict(l=10,r=10,t=50,b=10),yaxis_tickprefix="$")
        st.plotly_chart(fig,width="stretch")
    with right:
        chart = largest.copy(); chart["Driver"] = chart.line_item; chart["Adverse impact"] = chart.impact
        fig = px.bar(chart,x="Adverse impact",y="Driver",orientation="h",title="Largest adverse drivers",color_discrete_sequence=["#d94841"])
        fig.update_layout(height=380,margin=dict(l=10,r=10,t=50,b=10),xaxis_tickprefix="$")
        st.plotly_chart(fig,width="stretch")
    if not exceptions.empty:
        section_header("Items requiring attention","Exceptions are shown before successful matches so the Controller can act quickly.")
        st.dataframe(exceptions[["risk","source","date","description","amount","exception_type"]],width="stretch",hide_index=True,column_config={"amount":st.column_config.NumberColumn("Amount",format="$%.2f")})

elif page == "Variance Intelligence":
    section_header("Variance intelligence","Identify the financial drivers that explain performance against plan.")
    uploaded = st.file_uploader("Upload actual vs budget CSV",type="csv")
    if uploaded:
        uploaded_variance = variance_analysis(load_csv(uploaded,"variance_data.csv",["line_item","category","budget","actual"]))
        upload_signature = f"{uploaded.name}:{uploaded.size}"
        if st.session_state.get("variance_upload_signature") != upload_signature:
            st.session_state.variance_data = uploaded_variance
            st.session_state.variance_uploaded = True
            st.session_state.variance_upload_signature = upload_signature
        variance = st.session_state.variance_data.copy()
        st.success(f"{uploaded.name} is now feeding Variance Intelligence and Executive Overview.")
    elif st.session_state.get("variance_uploaded", False):
        variance = st.session_state.variance_data.copy()
        st.info("Using the variance file previously uploaded during this session.")
    if st.button("Restore demonstration variance data"):
        st.session_state.variance_data = variance_analysis(load_csv(None,"variance_data.csv",["line_item","category","budget","actual"]))
        st.session_state.variance_uploaded = False
        st.session_state.pop("variance_upload_signature", None)
        st.rerun()
    controls1,controls2 = st.columns(2)
    categories = controls1.multiselect("Category",sorted(variance.category.unique()),default=sorted(variance.category.unique()))
    threshold = controls2.number_input("Materiality threshold ($)",min_value=0,value=10000,step=5000)
    view = variance[variance.category.isin(categories) & (variance.materiality >= threshold)]
    a,b,c,d = st.columns(4)
    with a: kpi_card("Material variances",len(view),f"Threshold: {money(threshold)}","<b>Material variances</b><br>Items whose absolute variance meets the selected threshold.<br><br><b>Formula</b><br>|Actual − Budget| ≥ threshold")
    with b: kpi_card("Unfavorable",int((view.direction=="Unfavorable").sum()),"Performance below plan","<b>Unfavorable</b><br>Revenue/profit below budget or costs above budget.",tone="bad")
    with c: kpi_card("Favorable",int((view.direction=="Favorable").sum()),"Performance above plan","<b>Favorable</b><br>Revenue/profit above budget or costs below budget.",tone="good")
    with d: kpi_card("Largest variance",money(view.materiality.max() if len(view) else 0),"Absolute dollar movement","<b>Largest variance</b><br>Highest absolute difference between actual and budget.<br><br><b>Formula</b><br>Maximum of |Actual − Budget|")
    chart = view[~view.line_item.str.startswith("Total") & ~view.line_item.isin(["Gross Profit","EBITDA"])].sort_values("impact")
    fig = px.bar(chart,x="impact",y="line_item",orientation="h",color="direction",color_discrete_map={"Favorable":"#238636","Unfavorable":"#d94841"},title="Contribution to performance")
    fig.update_layout(height=max(380,len(chart)*34),xaxis_title="Favorable / (unfavorable) impact",yaxis_title="")
    st.plotly_chart(fig,width="stretch")
    display = view[["line_item","category","budget","actual","variance","variance_pct","direction"]]
    st.dataframe(display,width="stretch",hide_index=True,column_config={c:st.column_config.NumberColumn(c.replace('_',' ').title(),format="$%.0f") for c in ["budget","actual","variance"]})
    st.download_button("Download variance analysis",display.to_csv(index=False),"variance_analysis.csv","text/csv")
    if st.button("Generate board commentary",type="primary"):
        summary = view.to_csv(index=False)
        result = claude_text(f"You are a senior FP&A analyst for a PE-backed cold-chain company. Using the data below, write a factual board-ready narrative under 300 words. Lead with EBITDA, explain revenue, cost and SGA drivers, distinguish facts from assumptions, and end with proposed management actions. Do not invent causes not present in the data.\n\n{summary}")
        if result: st.markdown(f'<div class="brief">{result}</div>',unsafe_allow_html=True)

else:
    section_header("Reconciliation control center","Resolve unmatched activity and understand gross financial exposure.")
    u1,u2 = st.columns(2)
    bank_up = u1.file_uploader("Upload bank statement",type="csv")
    gl_up = u2.file_uploader("Upload GL export",type="csv")
    days = st.slider("Date tolerance for amount matches",0,7,3)
    if bank_up:
        st.session_state.bank_data = load_csv(bank_up,"bank_statement.csv",["date","description","amount","reference"])
        st.session_state.bank_uploaded = True
    if gl_up:
        st.session_state.gl_data = load_csv(gl_up,"gl_export.csv",["date","description","amount","reference"])
        st.session_state.gl_uploaded = True
    st.session_state.reconciliation_uploaded = bool(st.session_state.get("bank_uploaded") and st.session_state.get("gl_uploaded"))
    bank2 = st.session_state.bank_data.copy()
    gl2 = st.session_state.gl_data.copy()
    if st.session_state.reconciliation_uploaded:
        st.success("Uploaded bank and GL data are now feeding this page and Executive Overview.")
    elif st.session_state.get("bank_uploaded") or st.session_state.get("gl_uploaded"):
        st.warning("Only one reconciliation file has been uploaded. The other side is still using demonstration data.")
    if st.button("Restore demonstration reconciliation data"):
        st.session_state.bank_data = load_csv(None,"bank_statement.csv",["date","description","amount","reference"])
        st.session_state.gl_data = load_csv(None,"gl_export.csv",["date","description","amount","reference"])
        st.session_state.bank_uploaded = False
        st.session_state.gl_uploaded = False
        st.session_state.reconciliation_uploaded = False
        st.rerun()
    matches, exceptions = reconcile(bank2,gl2,days)
    rate = len(matches)/len(bank2)*100 if len(bank2) else 0
    exposure = exceptions.amount.abs().sum() if len(exceptions) else 0
    a,b,c,d,e = st.columns(5)
    with a: kpi_card("Bank transactions",len(bank2),"Rows in bank statement","<b>Bank transactions</b><br>Total valid rows read from the uploaded bank file.")
    with b: kpi_card("Matched",len(matches),"Linked to a GL entry","<b>Matched transactions</b><br>Bank items connected to one unused GL entry using reference or amount-plus-date logic.",f"{len(matches)} cleared","good")
    with c: kpi_card("Match rate",f"{rate:.1f}%",f"{len(matches)} of {len(bank2)} transactions",f"<b>Match rate</b><br>Matched bank transactions ÷ total bank transactions × 100.<br><br>{len(matches)} ÷ {len(bank2)} × 100 = {rate:.1f}%",f"Target 98%","bad" if rate<98 else "good")
    with d: kpi_card("Open exceptions",len(exceptions),"Bank and GL-side items","<b>Open exceptions</b><br>Unmatched bank items plus unmatched GL entries requiring investigation.","Action required" if len(exceptions) else "Clear","bad" if len(exceptions) else "good")
    with e: kpi_card("Gross exposure",money(exposure),"Not confirmed financial loss",f"<b>Gross exposure</b><br>Sum of absolute unresolved amounts.<br><br><b>Formula</b><br>Σ |exception amount| = {money(exposure)}","Review required" if exposure else "Clear","bad" if exposure else "good")
    st.progress(min(rate/100,1.0),text=f"Reconciliation progress · {rate:.1f}% matched")
    tab1,tab2 = st.tabs(["Exceptions","Matched transactions"])
    with tab1:
        if exceptions.empty: st.success("No exceptions found.")
        else:
            risk_counts = exceptions.groupby("risk",as_index=False).size()
            fig = px.bar(risk_counts,x="risk",y="size",color="risk",color_discrete_map={"High":"#d94841","Medium":"#e3a008"},title="Exceptions by risk")
            st.plotly_chart(fig,width="stretch")
            st.dataframe(exceptions,width="stretch",hide_index=True,column_config={"amount":st.column_config.NumberColumn("Amount",format="$%.2f")})
            st.download_button("Download exceptions",exceptions.to_csv(index=False),"reconciliation_exceptions.csv","text/csv")
    with tab2:
        st.dataframe(matches,width="stretch",hide_index=True,column_config={"amount":st.column_config.NumberColumn("Amount",format="$%.2f")})
    if st.button("Analyze exceptions with Claude",type="primary",disabled=exceptions.empty):
        result = claude_text(f"Act as a controller. For every reconciliation exception below, explain the likely issue without inventing facts, prescribe the accounting action, assign urgency, and mention evidence to request. Keep each item concise.\n\n{exceptions.to_csv(index=False)}")
        if result: st.markdown(f'<div class="brief">{result}</div>',unsafe_allow_html=True)
