import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
from io import BytesIO
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import gspread
from google.oauth2.service_account import Credentials

# --- 1. PAGE CONFIGURATION & BEAUTIFICATION ---
st.set_page_config(page_title="RealtorOS Executive", page_icon="🏘️", layout="wide")

# Custom CSS to keep that professional "Blue & Purple" look from your original
st.markdown("""
<style>
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e3a8a; text-align: center; margin-bottom: 2rem; }
    .stMetric { background-color: #f8fafc; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# --- 2. CLOUD CONNECTION (Google Sheets & Gemini) ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
SPREADSHEET_ID = st.secrets.get("SPREADSHEET_ID", "")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@st.cache_resource
def get_gsheet_client():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
        return gspread.authorize(creds)
    return None

def load_data():
    client = get_gsheet_client()
    if client and SPREADSHEET_ID:
        try:
            sh = client.open_by_key(SPREADSHEET_ID)
            ws = sh.sheet1
            data = ws.get_all_values()
            if not data or len(data) == 0:
                headers = ['Date', 'Agent', 'Location', 'Price', 'Status', 'Client_Name', 'Phone', 'Notes']
                ws.append_row(headers)
                return pd.DataFrame(columns=headers)
            df = pd.DataFrame(data[1:], columns=data[0])
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.sidebar.error(f"Spreadsheet Error: {e}")
    return pd.DataFrame()

# --- 3. STATE MANAGEMENT (Agents & Targets) ---
if 'agents' not in st.session_state:
    # Requirement: Manager included by default
    st.session_state.agents = ["Manager", "Agent 1", "Agent 2"]

if 'targets' not in st.session_state:
    # Requirement: Weekly, Monthly, Quarterly, Yearly targets
    st.session_state.targets = {"Week": 0, "Month": 0, "Quarter": 0, "Year": 0}

# Load data into session
st.session_state.sales_data = load_data()

# --- 4. NAVIGATION ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/609/609036.png", width=100)
st.sidebar.title("RealtorOS Menu")
page = st.sidebar.radio("Navigate to:", 
    ["📊 Dashboard & AI Coach", "📝 Log New Sale", "🎯 Revenue Targets", "👥 Team Management", "📑 Reports & PDF"])

# --- PAGE 1: DASHBOARD & AI COACH ---
if page == "📊 Dashboard & AI Coach":
    st.markdown('<p class="main-header">📊 Executive Dashboard</p>', unsafe_allow_html=True)
    df = st.session_state.sales_data
    
    if not df.empty:
        # Top Metrics
        m1, m2, m3, m4 = st.columns(4)
        total_rev = df['Price'].sum()
        m1.metric("Total Revenue", f"KSh {total_rev:,.0f}")
        m2.metric("Sales Count", len(df))
        
        # Target Progress logic
        month_target = st.session_state.targets["Month"]
        if month_target > 0:
            progress = (total_rev / month_target) * 100
            m3.metric("Monthly Target Progress", f"{progress:.1f}%")
            st.progress(min(progress/100, 1.0))
        
        # AI SALES COACH SECTION
        st.markdown("---")
        st.subheader("🤖 AI Sales Coach (Gemini 1.5 Flash)")
        if st.button("🧠 Analyze My Sales Vibe"):
            if not GEMINI_API_KEY:
                st.warning("Please add your GEMINI_API_KEY to secrets.")
            else:
                with st.spinner("Gemini is analyzing your data..."):
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    # Feed summary to AI
                    data_summary = df.groupby(['Location', 'Agent'])['Price'].sum().to_string()
                    prompt = f"""
                    Act as a high-end Real Estate Coach for Kenya. 
                    Analyze this sales data: {data_summary}. 
                    Provide 3 punchy, actionable tips to increase revenue in Malaa, Joska, or Kamulu.
                    Use a professional but encouraging 'boss' vibe.
                    """
                    response = model.generate_content(prompt)
                    st.info(response.text)
        
        # Charts
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            fig_loc = px.pie(df, names='Location', values='Price', title="Revenue by Location", hole=0.5)
            st.plotly_chart(fig_loc, use_container_width=True)
        with c2:
            fig_trend = px.line(df.sort_values('Date'), x='Date', y='Price', title="Sales Trend Over Time")
            st.plotly_chart(fig_trend, use_container_width=True)

# --- PAGE 2: LOG NEW SALE ---
elif page == "📝 Log New Sale":
    st.markdown('<p class="main-header">📝 Record Sale</p>', unsafe_allow_html=True)
    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            # Requirement: Access older sales via date picker
            sale_date = st.date_input("Sale Date", datetime.date.today())
            # Requirement: Manager + Team list
            agent = st.selectbox("Who made the sale?", st.session_state.agents)
            location = st.selectbox("Location", ["Malaa", "Joska", "Kamulu", "Other"])
        with col2:
            price = st.number_input("Sale Price (KSh)", min_value=0, step=50000)
            client = st.text_input("Client Name")
            phone = st.text_input("Phone Number")
        
        notes = st.text_area("Notes (Optional)")
        
        if st.form_submit_button("🚀 Sync to Google Sheets"):
            new_row = [str(sale_date), agent, location, price, "Sold", client, phone, notes]
            client_gs = get_gsheet_client()
            if client_gs:
                sh = client_gs.open_by_key(SPREADSHEET_ID)
                sh.sheet1.append_row(new_row)
                st.success("✅ Sale Saved Successfully!")
                st.balloons()
                st.session_state.sales_data = load_data()

# --- PAGE 3: REVENUE TARGETS ---
elif page == "🎯 Revenue Targets":
    st.markdown('<p class="main-header">🎯 Performance Goals</p>', unsafe_allow_html=True)
    st.write("Enter your revenue expectations to track them on the dashboard.")
    
    with st.form("target_form"):
        c1, c2 = st.columns(2)
        t_w = c1.number_input("Weekly Target (KSh)", value=st.session_state.targets["Week"])
        t_m = c2.number_input("Monthly Target (KSh)", value=st.session_state.targets["Month"])
        t_q = c1.number_input("Quarterly Target (KSh)", value=st.session_state.targets["Quarter"])
        t_y = c2.number_input("Yearly Target (KSh)", value=st.session_state.targets["Year"])
        
        if st.form_submit_button("Update Targets"):
            st.session_state.targets = {"Week": t_w, "Month": t_m, "Quarter": t_q, "Year": t_y}
            st.success("Targets updated for this session!")

# --- PAGE 4: TEAM MANAGEMENT ---
elif page == "👥 Team Management":
    st.markdown('<p class="main-header">👥 Team List</p>', unsafe_allow_html=True)
    
    # Add Agent
    st.subheader("Add New Team Member")
    new_name = st.text_input("Full Name")
    if st.button("Add to Dropdowns"):
        if new_name and new_name not in st.session_state.agents:
            st.session_state.agents.append(new_name)
            st.success(f"{new_name} added!")
            st.rerun()

    st.markdown("---")
    # Remove Agent
    st.subheader("Remove Team Member")
    to_remove = st.selectbox("Select Name to Remove", st.session_state.agents)
    if st.button("Remove Permanently"):
        if to_remove != "Manager": # Protect the manager role
            st.session_state.agents.remove(to_remove)
            st.warning(f"{to_remove} removed.")
            st.rerun()
        else:
            st.error("Cannot remove the primary Manager role.")

# --- PAGE 5: REPORTS & PDF ---
elif page == "📑 Reports & PDF":
    st.markdown('<p class="main-header">📑 Sales Reports</p>', unsafe_allow_html=True)
    df = st.session_state.sales_data
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        # PDF GENERATION (Restored logic)
        if st.button("📄 Generate PDF Summary"):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("RealtorOS - Executive Sales Report", styles['Title']))
            elements.append(Spacer(1, 12))
            
            # Table Data
            data_list = [df.columns.tolist()] + df.values.tolist()
            t = Table(data_list)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            elements.append(t)
            doc.build(elements)
            
            st.download_button(
                label="📥 Download PDF Report",
                data=buffer.getvalue(),
                file_name=f"Sales_Report_{datetime.date.today()}.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("No data found to report.")
