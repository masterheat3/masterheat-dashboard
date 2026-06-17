import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from io import BytesIO
import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

st.set_page_config(
    page_title="ماستر هيت",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');

* { -webkit-text-size-adjust: 100%; touch-action: manipulation; }

html, body, [class*="css"] {
    font-family: 'Tajawal', sans-serif !important;
    direction: rtl !important;
}

.stApp { background: #0a0f1e !important; }

#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarNav"] { display: none !important; }

.block-container {
    padding: 0 10px 90px 10px !important;
    max-width: 100% !important;
}

/* ── شريط علوي ── */
.topbar {
    background: linear-gradient(135deg,#0f172a,#1e3a5f);
    padding: 12px 14px;
    margin: -10px -10px 14px -10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(56,189,248,0.25);
}
.topbar-title { color:#fff; font-size:1.1rem; font-weight:900; }
.topbar-sub   { color:#64748b; font-size:0.68rem; }
.topbar-time  { color:#38bdf8; font-size:0.75rem; }

/* ── بطاقات إحصاء ── */
.stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 14px;
}
.stat-card {
    background: #1e293b;
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 14px 10px;
    text-align: center;
}
.stat-card.full { grid-column: 1 / -1; }
.stat-icon { font-size: 1.3rem; }
.stat-val  { font-size:1.25rem; font-weight:900; color:#38bdf8; margin:4px 0 2px; }
.stat-val.g { color:#22c55e; }
.stat-val.r { color:#ef4444; }
.stat-val.o { color:#f97316; }
.stat-lbl  { color:#64748b; font-size:0.7rem; }

/* ── تنبيهات ── */
.alert {
    border-radius: 10px;
    padding: 10px 12px;
    font-size:0.83rem;
    font-weight:700;
    margin-bottom:12px;
    direction:rtl;
}
.alert-r { background:#7f1d1d; color:#fca5a5; }
.alert-b { background:#1e3a5f; color:#93c5fd; }
.alert-g { background:#064e3b; color:#6ee7b7; }

/* ── عنوان قسم ── */
.sec-hdr {
    color:#e2e8f0; font-size:0.9rem; font-weight:900;
    padding:8px 0 6px; border-bottom:2px solid #1e3a5f;
    margin-bottom:10px; direction:rtl;
}

/* ── جدول HTML مخصص ── */
.rtl-table {
    width:100%;
    border-collapse:collapse;
    font-size:0.78rem;
    direction:rtl;
    margin-bottom:12px;
}
.rtl-table th {
    background:#1e3a5f;
    color:#93c5fd;
    padding:8px 6px;
    text-align:right;
    font-weight:700;
    white-space:nowrap;
    border-bottom:1px solid #334155;
}
.rtl-table td {
    padding:7px 6px;
    border-bottom:1px solid #1e293b;
    color:#cbd5e1;
    text-align:right;
    vertical-align:middle;
    max-width:90px;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.rtl-table tr:nth-child(even) td { background:rgba(30,41,59,0.5); }
.rtl-table tr:hover td { background:rgba(56,189,248,0.07); }

/* ── شريط التنقل السفلي ── */
.bottom-nav-wrap {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #0f172a;
    border-top: 1px solid #1e3a5f;
    display: flex;
    z-index: 9999;
    padding: 6px 0 8px;
    gap: 0;
}
.nav-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 6px 2px;
    cursor: pointer;
    border-radius: 10px;
    text-decoration: none;
    border: none;
    background: none;
    gap: 2px;
}
.nav-btn.active { background: rgba(56,189,248,0.12); }
.nav-ico { font-size: 1.35rem; line-height:1; }
.nav-lbl { font-size: 0.6rem; color: #64748b; font-family:'Tajawal',sans-serif; }
.nav-btn.active .nav-lbl { color: #38bdf8; }

/* إخفاء أزرار Streamlit المستخدمة للتنقل */
div[data-testid="stColumns"] .stButton > button {
    display: none !important;
}

/* ── أزرار عامة ── */
.stButton > button {
    background: linear-gradient(135deg,#0ea5e9,#0284c7) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Tajawal',sans-serif !important;
    font-weight: 700 !important;
    width: 100% !important;
    padding: 11px !important;
    font-size: 0.9rem !important;
    margin-top: 6px !important;
}

/* selectbox */
[data-testid="stSelectbox"] label,
[data-testid="stSelectbox"] div { direction:rtl !important; font-family:'Tajawal',sans-serif !important; }

/* input */
.stTextInput input, .stNumberInput input {
    font-family:'Tajawal',sans-serif !important;
    direction:rtl !important;
    border-radius:10px !important;
    font-size:0.9rem !important;
}
.stTextInput label, .stNumberInput label { font-family:'Tajawal',sans-serif !important; direction:rtl !important; }

/* date input */
[data-testid="stDateInput"] label { font-family:'Tajawal',sans-serif !important; }

/* tabs */
.stTabs [data-baseweb="tab"] {
    font-family:'Tajawal',sans-serif !important;
    font-weight:700 !important;
    font-size:0.82rem !important;
}

/* progress */
.stProgress > div > div { background:#0ea5e9 !important; border-radius:8px !important; }

/* download button */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg,#22c55e,#16a34a) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-family:'Tajawal',sans-serif !important;
    font-weight:700 !important;
    width:100% !important;
    padding:11px !important;
    margin-top:6px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── إعداد ───
load_dotenv()

def _cfg(key):
    # Streamlit Cloud secrets أولاً، ثم .env
    try:    return st.secrets[key]
    except: return os.getenv(key, "")

@st.cache_resource
def get_supabase():
    return create_client(_cfg("SUPABASE_URL"), _cfg("SUPABASE_KEY"))
@st.cache_resource
def get_openai():
    return OpenAI(api_key=_cfg("OPENAI_API_KEY"))

supabase      = get_supabase()
openai_client = get_openai()

@st.cache_data(ttl=60)
def load_invoices():
    try:
        res = supabase.table("invoices").select("*").order("created_at", desc=True).execute()
        if not res.data: return pd.DataFrame()
        df = pd.DataFrame(res.data)
        for c in ["taxable_amount","vat_amount","total_amount"]:
            df[c] = pd.to_numeric(df.get(c,0), errors="coerce").fillna(0)
        df["invoice_date"] = pd.to_datetime(df.get("invoice_date"), errors="coerce")
        df["created_at"]   = pd.to_datetime(df.get("created_at"),   errors="coerce")
        return df
    except Exception as e:
        st.error(f"خطأ: {e}"); return pd.DataFrame()

@st.cache_data(ttl=60)
def load_projects():
    try:
        res = supabase.table("projects").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

def fmt_num(v):
    try: return f"{float(v):,.0f}"
    except: return "-"

def trunc(s, n=16):
    s = str(s or "-")
    return s[:n] + "…" if len(s) > n else s

def html_table(df: pd.DataFrame) -> str:
    rows = ""
    for _, r in df.iterrows():
        cells = "".join(f"<td>{v}</td>" for v in r)
        rows += f"<tr>{cells}</tr>"
    heads = "".join(f"<th>{c}</th>" for c in df.columns)
    return f'<div style="overflow-x:auto"><table class="rtl-table"><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></div>'

# ─── بيانات ───
df_inv  = load_invoices()
df_proj = load_projects()
expenses = df_inv[df_inv["type"]=="expense"] if not df_inv.empty else pd.DataFrame()
revenues = df_inv[df_inv["type"]=="revenue"] if not df_inv.empty else pd.DataFrame()
total_exp = expenses["total_amount"].sum() if not expenses.empty else 0
total_rev = revenues["total_amount"].sum() if not revenues.empty else 0
vat_out   = revenues["vat_amount"].sum()   if not revenues.empty else 0
vat_in    = expenses["vat_amount"].sum()   if not expenses.empty else 0
net_vat   = vat_out - vat_in
profit    = total_rev - total_exp
active_p  = len(df_proj[df_proj["status"]=="نشط"]) if (not df_proj.empty and "status" in df_proj.columns) else len(df_proj)

if "page" not in st.session_state:
    st.session_state.page = "home"

# ─── شريط علوي ───
titles = {"home":("🏗️","ماستر هيت","للمقاولات"),"projects":("📊","المشاريع","التحليل"),"vat":("🧾","الضريبة","VAT"),"invoices":("📋","الفواتير","السجلات")}
ico,ttl,sub = titles.get(st.session_state.page,("🏗️","ماستر هيت",""))
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="topbar-title">{ico} {ttl}</div>
    <div class="topbar-sub">{sub}</div>
  </div>
  <div class="topbar-time">{datetime.now().strftime("%H:%M")}</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════
# 🏠 الرئيسية
# ══════════════════════════════════════
if st.session_state.page == "home":

    today = date.today()
    vat_dl = date(today.year, 7, 28)
    days_l = (vat_dl - today).days
    if today.month in [5,6,7] and days_l <= 30:
        st.markdown(f'<div class="alert alert-r">⚠️ موعد الإقرار الضريبي بعد <b>{days_l} يوم</b></div>', unsafe_allow_html=True)
    elif today.month in [5,6,7]:
        st.markdown(f'<div class="alert alert-b">🏛️ الفترة الضريبية نشطة — صافي VAT: <b>{fmt_num(net_vat)} AED</b></div>', unsafe_allow_html=True)

    pc = "g" if profit >= 0 else "r"
    vc = "r" if net_vat > 0 else "g"
    st.markdown(f"""
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon">📤</div>
        <div class="stat-val">{fmt_num(total_exp)}</div>
        <div class="stat-lbl">المصروفات AED</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📥</div>
        <div class="stat-val g">{fmt_num(total_rev)}</div>
        <div class="stat-lbl">الإيرادات AED</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📈</div>
        <div class="stat-val {pc}">{fmt_num(profit)}</div>
        <div class="stat-lbl">صافي الربح AED</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🏛️</div>
        <div class="stat-val {vc}">{fmt_num(net_vat)}</div>
        <div class="stat-lbl">صافي VAT AED</div>
      </div>
      <div class="stat-card full">
        <div class="stat-icon">🏗️</div>
        <div class="stat-val">{active_p} مشروع نشط &nbsp;|&nbsp; {len(df_inv)} فاتورة</div>
        <div class="stat-lbl">إجمالي السجلات</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if not expenses.empty and "project" in expenses.columns:
        st.markdown('<div class="sec-hdr">📊 المصروفات حسب المشروع</div>', unsafe_allow_html=True)
        pe = expenses.groupby("project")["total_amount"].sum().reset_index()
        fig = px.bar(pe, x="project", y="total_amount",
                     color_discrete_sequence=["#0ea5e9"],
                     template="plotly_dark",
                     labels={"project":"","total_amount":"AED"})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          height=200, margin=dict(l=0,r=0,t=4,b=0),
                          font=dict(family="Tajawal",size=11),
                          dragmode=False)
        fig.update_traces(text=pe["total_amount"].apply(lambda x: f"{x:,.0f}"),
                          textposition="outside", textfont=dict(size=10,family="Tajawal"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False})

    if not df_inv.empty:
        st.markdown('<div class="sec-hdr">📋 آخر الفواتير</div>', unsafe_allow_html=True)
        recent = df_inv.head(10).copy()
        tbl = pd.DataFrame({
            "النوع":    recent["type"].map({"expense":"📤 مصروف","revenue":"📥 إيراد"}),
            "المورد":   recent["vendor_name"].apply(lambda x: trunc(x, 14)),
            "الإجمالي": recent["total_amount"].apply(fmt_num),
            "المشروع":  recent.get("project", pd.Series(["-"]*len(recent))).apply(lambda x: trunc(x, 10)),
        })
        st.markdown(html_table(tbl), unsafe_allow_html=True)

    if st.button("🔄 تحديث البيانات"):
        st.cache_data.clear(); st.rerun()

# ══════════════════════════════════════
# 📊 المشاريع
# ══════════════════════════════════════
elif st.session_state.page == "projects":

    tab1, tab2 = st.tabs(["📈 مقارنة الميزانية", "📦 جدول المواد"])

    with tab1:
        if df_proj.empty:
            st.info("لا توجد مشاريع مسجلة.")
        else:
            plist = df_proj["name"].tolist() if "name" in df_proj.columns else []
            if plist:
                sel    = st.selectbox("اختر المشروع", plist)
                pe     = expenses[expenses["project"]==sel] if not expenses.empty and "project" in expenses.columns else pd.DataFrame()
                actual = pe["total_amount"].sum() if not pe.empty else 0
                budget = st.number_input("الميزانية (AED)", min_value=0.0, value=100000.0, step=5000.0, format="%.0f")
                pct    = (actual/budget*100) if budget > 0 else 0
                remain = budget - actual
                vc2    = "r" if pct>=90 else ("o" if pct>=70 else "g")

                st.markdown(f"""
                <div class="stat-grid">
                  <div class="stat-card">
                    <div class="stat-icon">💰</div>
                    <div class="stat-val">{fmt_num(actual)}</div>
                    <div class="stat-lbl">المصروف الفعلي AED</div>
                  </div>
                  <div class="stat-card">
                    <div class="stat-icon">📉</div>
                    <div class="stat-val {vc2}">{fmt_num(remain)}</div>
                    <div class="stat-lbl">المتبقي AED</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"**{pct:.1f}%** من الميزانية مُنفَق")
                st.progress(min(pct/100, 1.0))

                if pct >= 90:
                    st.markdown('<div class="alert alert-r">⚠️ تحذير: تجاوز 90% من الميزانية!</div>', unsafe_allow_html=True)
                elif pct >= 70:
                    st.markdown('<div class="alert alert-b">🔶 تنبيه: صُرف أكثر من 70%</div>', unsafe_allow_html=True)

                fig2 = go.Figure(data=[go.Bar(
                    x=["الميزانية","الفعلي"], y=[budget,actual],
                    marker_color=["#22c55e","#ef4444" if actual>budget else "#38bdf8"],
                    text=[fmt_num(budget),fmt_num(actual)], textposition="outside",
                    textfont=dict(family="Tajawal",size=11),
                )])
                fig2.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)",height=220,
                                   margin=dict(l=0,r=0,t=4,b=0),
                                   font=dict(family="Tajawal"),dragmode=False)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False})

                if not pe.empty:
                    st.markdown('<div class="sec-hdr">📋 فواتير المشروع</div>', unsafe_allow_html=True)
                    tbl2 = pd.DataFrame({
                        "رقم الفاتورة": pe["invoice_number"].apply(lambda x: trunc(x,14)),
                        "المورد":        pe["vendor_name"].apply(lambda x: trunc(x,14)),
                        "الإجمالي AED":  pe["total_amount"].apply(fmt_num),
                        "الضريبة AED":   pe["vat_amount"].apply(fmt_num),
                    })
                    st.markdown(html_table(tbl2), unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="alert alert-b">📦 ارفع جدول المواد لتقدير التكلفة بالذكاء الاصطناعي</div>', unsafe_allow_html=True)
        proj_name_est = st.text_input("اسم المشروع", placeholder="مثال: الظاهر 6")
        uploaded = st.file_uploader("Excel / CSV", type=["xlsx","xls","csv"])
        if uploaded:
            try:
                df_mat = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
                st.success(f"✅ {len(df_mat)} صف")
                tbl_mat = df_mat.head(8).copy()
                tbl_mat.columns = [str(c)[:12] for c in tbl_mat.columns]
                st.markdown(html_table(tbl_mat), unsafe_allow_html=True)
                if st.button("🤖 تقدير التكلفة"):
                    with st.spinner("جارٍ التحليل..."):
                        res = openai_client.chat.completions.create(
                            model="gpt-4o", temperature=0.2,
                            messages=[{"role":"user","content":
                                f"أنت مهندس تكاليف إماراتي. قدّر تكلفة هذا الجدول بالدرهم مع إجمالي وضريبة 5% وهامش 10%:\n{df_mat.to_string(index=False)[:4000]}"}]
                        )
                    st.markdown(res.choices[0].message.content)
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine="openpyxl") as w:
                        df_mat.to_excel(w, sheet_name="جدول المواد", index=False)
                    out.seek(0)
                    st.download_button("⬇️ تحميل Excel", out,
                        file_name=f"تقدير_{proj_name_est or 'مشروع'}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"❌ {e}")

# ══════════════════════════════════════
# 🧾 الضريبة
# ══════════════════════════════════════
elif st.session_state.page == "vat":

    c1,c2 = st.columns(2)
    with c1: start_date = st.date_input("من", value=date(date.today().year,5,1))
    with c2: end_date   = st.date_input("إلى", value=date(date.today().year,7,31))

    if not df_inv.empty and "invoice_date" in df_inv.columns:
        mask = (df_inv["invoice_date"].dt.date >= start_date) & (df_inv["invoice_date"].dt.date <= end_date)
        dp   = df_inv[mask]
    else:
        dp = df_inv.copy() if not df_inv.empty else pd.DataFrame()

    pr  = dp[dp["type"]=="revenue"] if not dp.empty else pd.DataFrame()
    pe  = dp[dp["type"]=="expense"] if not dp.empty else pd.DataFrame()
    rv  = pr["taxable_amount"].sum() if not pr.empty else 0
    rvv = pr["vat_amount"].sum()     if not pr.empty else 0
    rvt = pr["total_amount"].sum()   if not pr.empty else 0
    ex  = pe["taxable_amount"].sum() if not pe.empty else 0
    exv = pe["vat_amount"].sum()     if not pe.empty else 0
    ext = pe["total_amount"].sum()   if not pe.empty else 0
    pn  = rvv - exv
    nc  = "r" if pn > 0 else "g"
    nl  = "واجب السداد" if pn > 0 else "مستحق الاسترداد"

    st.markdown(f"""
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon">📥</div>
        <div class="stat-val g">{fmt_num(rvv)}</div>
        <div class="stat-lbl">ضريبة المخرجات AED</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📤</div>
        <div class="stat-val o">{fmt_num(exv)}</div>
        <div class="stat-lbl">ضريبة المدخلات AED</div>
      </div>
      <div class="stat-card full">
        <div class="stat-icon">🏛️</div>
        <div class="stat-val {nc}">{fmt_num(abs(pn))} AED</div>
        <div class="stat-lbl">صافي VAT — {nl}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sec-hdr">📋 ملخص الإقرار الضريبي</div>', unsafe_allow_html=True)
    smry = pd.DataFrame({
        "البند": ["الإيرادات الخاضعة","ضريبة المخرجات 5%","إجمالي الإيرادات",
                  "المصروفات الخاضعة","ضريبة المدخلات 5%","إجمالي المصروفات","▶ صافي VAT"],
        "المبلغ AED": [fmt_num(rv),fmt_num(rvv),fmt_num(rvt),
                       fmt_num(ex),fmt_num(exv),fmt_num(ext),fmt_num(pn)],
    })
    st.markdown(html_table(smry), unsafe_allow_html=True)

    fig_v = go.Figure(data=[
        go.Bar(name="مخرجات", x=["VAT"], y=[rvv], marker_color="#22c55e",
               text=[fmt_num(rvv)], textposition="outside", textfont=dict(family="Tajawal")),
        go.Bar(name="مدخلات", x=["VAT"], y=[exv], marker_color="#f97316",
               text=[fmt_num(exv)], textposition="outside", textfont=dict(family="Tajawal")),
        go.Bar(name="صافي",   x=["VAT"], y=[pn],  marker_color="#38bdf8",
               text=[fmt_num(pn)],  textposition="outside", textfont=dict(family="Tajawal")),
    ])
    fig_v.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",height=220,barmode="group",
                        margin=dict(l=0,r=0,t=4,b=0),font=dict(family="Tajawal"),
                        legend=dict(font=dict(family="Tajawal",size=10)),dragmode=False)
    st.plotly_chart(fig_v, use_container_width=True, config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False})

    if st.button("📊 تصدير تقرير VAT — Excel"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            smry.to_excel(w, sheet_name="ملخص VAT", index=False)
            if not pr.empty:
                pr[["invoice_number","vendor_name","invoice_date","taxable_amount","vat_amount","total_amount"]]\
                  .rename(columns={"invoice_number":"رقم","vendor_name":"الجهة","invoice_date":"التاريخ",
                                   "taxable_amount":"خاضع","vat_amount":"ضريبة","total_amount":"إجمالي"})\
                  .to_excel(w, sheet_name="الإيرادات", index=False)
            if not pe.empty:
                pe[["invoice_number","vendor_name","project","invoice_date","taxable_amount","vat_amount","total_amount"]]\
                  .rename(columns={"invoice_number":"رقم","vendor_name":"مورد","project":"مشروع",
                                   "invoice_date":"تاريخ","taxable_amount":"خاضع",
                                   "vat_amount":"ضريبة","total_amount":"إجمالي"})\
                  .to_excel(w, sheet_name="المصروفات", index=False)
        out.seek(0)
        st.download_button("⬇️ تحميل Excel", out,
            file_name=f"VAT_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ══════════════════════════════════════
# 📋 الفواتير
# ══════════════════════════════════════
elif st.session_state.page == "invoices":

    if df_inv.empty:
        st.info("📭 لا توجد فواتير بعد.")
    else:
        type_f  = st.selectbox("النوع", ["الكل","مصروف","إيراد"])
        popts   = ["الكل"] + sorted(df_inv["project"].dropna().unique().tolist()) if "project" in df_inv.columns else ["الكل"]
        proj_f  = st.selectbox("المشروع", popts)
        search  = st.text_input("🔍 بحث", placeholder="اسم المورد أو رقم الفاتورة")

        df_f = df_inv.copy()
        if type_f == "مصروف": df_f = df_f[df_f["type"]=="expense"]
        elif type_f == "إيراد": df_f = df_f[df_f["type"]=="revenue"]
        if proj_f != "الكل": df_f = df_f[df_f["project"]==proj_f]
        if search:
            m = (df_f.get("vendor_name","").astype(str).str.contains(search,case=False,na=False) |
                 df_f.get("invoice_number","").astype(str).str.contains(search,case=False,na=False))
            df_f = df_f[m]

        total_f = df_f["total_amount"].sum()
        st.markdown(f'<div class="alert alert-b">📊 {len(df_f)} فاتورة — إجمالي: <b>{fmt_num(total_f)} AED</b></div>', unsafe_allow_html=True)

        tbl3 = pd.DataFrame({
            "ن":       df_f["type"].map({"expense":"📤","revenue":"📥"}),
            "رقم الفاتورة": df_f["invoice_number"].apply(lambda x: trunc(x,12)),
            "المورد":       df_f["vendor_name"].apply(lambda x: trunc(x,13)),
            "المشروع":      df_f.get("project", pd.Series(["-"]*len(df_f))).apply(lambda x: trunc(x,10)),
            "الإجمالي":     df_f["total_amount"].apply(fmt_num),
        })
        st.markdown(html_table(tbl3), unsafe_allow_html=True)

        out2 = BytesIO()
        with pd.ExcelWriter(out2, engine="openpyxl") as w:
            df_f[["invoice_number","vendor_name","project","type","taxable_amount","vat_amount","total_amount","invoice_date"]]\
              .rename(columns={"invoice_number":"رقم","vendor_name":"مورد","project":"مشروع","type":"نوع",
                               "taxable_amount":"خاضع","vat_amount":"ضريبة","total_amount":"إجمالي","invoice_date":"تاريخ"})\
              .to_excel(w, sheet_name="الفواتير", index=False)
        out2.seek(0)
        st.download_button("⬇️ تصدير Excel", out2, file_name="invoices.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ══════════════════════════════════════
# شريط التنقل السفلي (HTML حقيقي)
# ══════════════════════════════════════
cur = st.session_state.page
nav_html = f"""
<div class="bottom-nav-wrap">
  <button class="nav-btn {'active' if cur=='home' else ''}"
    onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',value:'home'}},'*')"
    style="cursor:pointer">
    <span class="nav-ico">🏠</span>
    <span class="nav-lbl">الرئيسية</span>
  </button>
  <button class="nav-btn {'active' if cur=='projects' else ''}"
    onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',value:'projects'}},'*')"
    style="cursor:pointer">
    <span class="nav-ico">📊</span>
    <span class="nav-lbl">المشاريع</span>
  </button>
  <button class="nav-btn {'active' if cur=='vat' else ''}"
    onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',value:'vat'}},'*')"
    style="cursor:pointer">
    <span class="nav-ico">🧾</span>
    <span class="nav-lbl">الضريبة</span>
  </button>
  <button class="nav-btn {'active' if cur=='invoices' else ''}"
    onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',value:'invoices'}},'*')"
    style="cursor:pointer">
    <span class="nav-ico">📋</span>
    <span class="nav-lbl">الفواتير</span>
  </button>
</div>
"""
st.markdown(nav_html, unsafe_allow_html=True)

# أزرار Streamlit الحقيقية للتنقل (مخفية بصرياً لكن تعمل)
cols = st.columns(4)
pages_nav = ["home","projects","vat","invoices"]
for i, pg in enumerate(pages_nav):
    with cols[i]:
        if st.button("nav", key=f"navbtn_{pg}"):
            st.session_state.page = pg
            st.rerun()
