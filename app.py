import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RealtorOS - Sales Report App",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR VISUAL APPEAL ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a8a;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(to right, #667eea, #764ba2);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- GEMINI API CONFIGURATION ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- DATABASE MANAGEMENT ---
EXCEL_FILE = "realtor_sales_database.xlsx"

def load_database():
    """Load or create Excel database"""
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE)
    else:
        df = pd.DataFrame(columns=['Date', 'Agent', 'Location', 'Price', 'Status', 'Client_Name', 'Phone', 'Notes'])
        df.to_excel(EXCEL_FILE, index=False)
        return df

def save_database(df):
    """Save dataframe to Excel"""
    df.to_excel(EXCEL_FILE, index=False)

# Initialize session state
if 'sales_data' not in st.session_state:
    st.session_state.sales_data = load_database()

# --- TARGETS & CONSTANTS ---
QUARTERLY_TARGETS = {
    "Q1 2026": 100,
    "Q2 2026": 120,
    "Q3 2026": 60,
    "Q4 2026": 60
}

AGENTS = ["Agent 1", "Agent 2", "Agent 3", "Agent 4"]
LOCATIONS = ["Malaa", "Joska", "Kamulu", "Matuu", "Makutano"]

def get_current_quarter():
    """Determine current quarter"""
    month = datetime.datetime.now().month
    if month <= 3:
        return "Q1 2026"
    elif month <= 6:
        return "Q2 2026"
    elif month <= 9:
        return "Q3 2026"
    else:
        return "Q4 2026"

CURRENT_Q = get_current_quarter()

# --- SIDEBAR NAVIGATION ---
st.sidebar.image("https://via.placeholder.com/150x100/667eea/ffffff?text=RealtorOS", use_container_width=True)
st.sidebar.title("🏘️ RealtorOS Manager")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "📝 Log Sales", "👥 Team Performance", "🤖 AI Coach", "📑 Reports"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.info(f"**Current Quarter:** {CURRENT_Q}\n\n**Target:** {QUARTERLY_TARGETS[CURRENT_Q]} plots")

# --- HELPER FUNCTIONS ---
def get_ai_advice(sales_data, current_performance, target):
    """Get AI-powered sales advice using Gemini"""
    if not GEMINI_API_KEY:
        return "⚠️ Please add your GEMINI_API_KEY to Streamlit secrets to enable AI Coach."
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Prepare context
        total_sales = len(sales_data)
        revenue = sales_data['Price'].sum() if not sales_data.empty else 0
        top_location = sales_data['Location'].mode()[0] if not sales_data.empty else "N/A"
        top_agent = sales_data['Agent'].mode()[0] if not sales_data.empty else "N/A"
        
        prompt = f"""
        You are an expert real estate sales coach for Kangundo Road (Malaa, Joska, Kamulu area) in Kenya.
        
        Current Performance:
        - Plots Sold: {total_sales} / Target: {target}
        - Revenue: KSh {revenue:,}
        - Top Location: {top_location}
        - Top Performer: {top_agent}
        - Gap: {target - total_sales} plots behind target
        
        Provide specific, actionable advice for this real estate team including:
        1. Immediate recovery actions (outdoor events, marketing tactics)
        2. Training focus areas
        3. Location-specific strategies for Kangundo Road area
        4. Team motivation tips
        
        Format your response in clear sections with emojis.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Error generating AI advice: {str(e)}"

def create_pdf_report(sales_data, analysis_text):
    """Generate PDF report with analysis"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=30,
        alignment=1
    )
    elements.append(Paragraph("RealtorOS Sales Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary Statistics
    total_sales = len(sales_data)
    revenue = sales_data['Price'].sum() if not sales_data.empty else 0
    target = QUARTERLY_TARGETS[CURRENT_Q]
    
    summary_data = [
        ['Metric', 'Value'],
        ['Quarter', CURRENT_Q],
        ['Plots Sold', f"{total_sales} / {target}"],
        ['Total Revenue', f"KSh {revenue:,}"],
        ['Achievement Rate', f"{(total_sales/target*100):.1f}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # AI Analysis Section
    elements.append(Paragraph("AI-Powered Analysis & Recommendations", styles['Heading2']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Clean and format analysis text
    for line in analysis_text.split('\n'):
        if line.strip():
            elements.append(Paragraph(line, styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- PAGE 1: DASHBOARD ---
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">📊 Sales Dashboard - Kangundo Road</p>', unsafe_allow_html=True)
    
    # Key Metrics
    total_sales = len(st.session_state.sales_data)
    target = QUARTERLY_TARGETS[CURRENT_Q]
    revenue = st.session_state.sales_data['Price'].sum() if not st.session_state.sales_data.empty else 0
    progress = total_sales / target if target > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Current Quarter", CURRENT_Q)
    with col2:
        st.metric("📈 Plots Sold", f"{total_sales} / {target}", delta=f"{total_sales - target}")
    with col3:
        st.metric("💰 Revenue", f"KSh {revenue:,.0f}")
    with col4:
        achievement = (progress * 100)
        st.metric("✅ Achievement", f"{achievement:.1f}%")
    
    # Progress Bar
    st.markdown("### Quarterly Progress")
    st.progress(min(progress, 1.0))
    
    if progress < 0.25:
        st.error("⚠️ **Alert:** Below 25% of quarterly target. Immediate action needed!")
    elif progress < 0.5:
        st.warning("📊 **Moderate Progress:** Keep pushing to reach the halfway mark.")
    elif progress < 0.75:
        st.info("🚀 **Good Progress:** You're on track. Maintain momentum!")
    else:
        st.success("🎉 **Excellent!** Exceeding expectations!")
    
    # Visualizations
    if not st.session_state.sales_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📍 Sales by Location")
            location_data = st.session_state.sales_data['Location'].value_counts().reset_index()
            location_data.columns = ['Location', 'Count']
            fig1 = px.bar(location_data, x='Location', y='Count', 
                         color='Count', color_continuous_scale='Viridis')
            fig1.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.markdown("### 👥 Agent Performance")
            agent_data = st.session_state.sales_data['Agent'].value_counts().reset_index()
            agent_data.columns = ['Agent', 'Sales']
            fig2 = px.pie(agent_data, names='Agent', values='Sales', hole=0.4)
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Revenue Trend
        st.markdown("### 💹 Revenue Trend Over Time")
        revenue_data = st.session_state.sales_data.copy()
        revenue_data['Date'] = pd.to_datetime(revenue_data['Date'])
        revenue_trend = revenue_data.groupby('Date')['Price'].sum().reset_index()
        fig3 = px.line(revenue_trend, x='Date', y='Price', markers=True)
        fig3.update_layout(yaxis_title="Revenue (KSh)", height=400)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("📊 No sales data yet. Start logging sales to see analytics!")

# --- PAGE 2: LOG SALES ---
elif page == "📝 Log Sales":
    st.markdown('<p class="main-header">📝 Log New Sale</p>', unsafe_allow_html=True)
    
    with st.form("sales_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            agent = st.selectbox("👤 Agent Name", AGENTS)
            location = st.selectbox("📍 Location", LOCATIONS)
            price = st.number_input("💰 Amount Collected (KES)", min_value=0, step=1000)
        
        with col2:
            date = st.date_input("📅 Date of Sale", datetime.date.today())
            client_name = st.text_input("👨‍💼 Client Name")
            phone = st.text_input("📱 Phone Number")
        
        notes = st.text_area("📝 Additional Notes")
        
        submitted = st.form_submit_button("✅ Log Sale", use_container_width=True)
        
        if submitted:
            new_entry = {
                'Date': date,
                'Agent': agent,
                'Location': location,
                'Price': price,
                'Status': 'Sold',
                'Client_Name': client_name,
                'Phone': phone,
                'Notes': notes
            }
            st.session_state.sales_data = pd.concat(
                [st.session_state.sales_data, pd.DataFrame([new_entry])],
                ignore_index=True
            )
            save_database(st.session_state.sales_data)
            st.success(f"✅ Sale recorded for **{agent}** at **{location}** - KSh {price:,}")
            st.balloons()
    
    # Recent Sales Table
    st.markdown("### 📋 Recent Sales")
    if not st.session_state.sales_data.empty:
        recent_sales = st.session_state.sales_data.tail(10).sort_values('Date', ascending=False)
        st.dataframe(recent_sales, use_container_width=True, hide_index=True)
    else:
        st.info("No sales recorded yet.")

# --- PAGE 3: TEAM PERFORMANCE ---
elif page == "👥 Team Performance":
    st.markdown('<p class="main-header">👥 Team Performance Analysis</p>', unsafe_allow_html=True)
    
    if not st.session_state.sales_data.empty:
        # Agent Statistics
        for agent in AGENTS:
            agent_data = st.session_state.sales_data[st.session_state.sales_data['Agent'] == agent]
            agent_sales = len(agent_data)
            agent_revenue = agent_data['Price'].sum()
            
            with st.expander(f"**{agent}** - {agent_sales} Sales | KSh {agent_revenue:,}", expanded=False):
                col1, col2, col3 = st.columns(3)
                col1.metric("Plots Sold", agent_sales)
                col2.metric("Total Revenue", f"KSh {agent_revenue:,}")
                col3.metric("Avg Deal Size", f"KSh {agent_revenue/agent_sales:,.0f}" if agent_sales > 0 else "N/A")
                
                if not agent_data.empty:
                    st.dataframe(agent_data[['Date', 'Location', 'Price', 'Client_Name']], use_container_width=True)
    else:
        st.info("No team performance data available yet.")

# --- PAGE 4: AI COACH ---
elif page == "🤖 AI Coach":
    st.markdown('<p class="main-header">🤖 AI Sales Strategy Coach</p>', unsafe_allow_html=True)
    
    st.markdown("""
    Get personalized, AI-powered recommendations based on your current performance.
    The AI analyzes your sales data and provides actionable strategies specific to the Kangundo Road market.
    """)
    
    total_sales = len(st.session_state.sales_data)
    target = QUARTERLY_TARGETS[CURRENT_Q]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Current Sales", total_sales)
    col2.metric("🎯 Target", target)
    col3.metric("📉 Gap", target - total_sales)
    
    st.markdown("---")
    
    if st.button("🚀 Generate AI Strategy", use_container_width=True, type="primary"):
        with st.spinner("🤖 AI is analyzing your performance..."):
            advice = get_ai_advice(st.session_state.sales_data, total_sales, target)
            st.markdown("### 💡 AI-Powered Recommendations")
            st.markdown(advice)
            
            # Store advice for report generation
            st.session_state['last_ai_advice'] = advice

# --- PAGE 5: REPORTS ---
elif page == "📑 Reports":
    st.markdown('<p class="main-header">📑 Reports & Analytics</p>', unsafe_allow_html=True)
    
    # Weekly Report
    st.markdown("### 📅 Weekly Sales Report")
    
    total_sales = len(st.session_state.sales_data)
    revenue = st.session_state.sales_data['Price'].sum() if not st.session_state.sales_data.empty else 0
    top_location = st.session_state.sales_data['Location'].mode()[0] if not st.session_state.sales_data.empty else 'N/A'
    top_agent = st.session_state.sales_data['Agent'].mode()[0] if not st.session_state.sales_data.empty else 'N/A'
    
    report_text = f"""
**Weekly Sales Report - Kangundo Road**
📅 Period: {datetime.date.today().strftime('%B %d, %Y')}
🎯 Quarter: {CURRENT_Q}

**Performance Summary:**
📈 Plots Sold: {total_sales} / {QUARTERLY_TARGETS[CURRENT_Q]}
💰 Total Revenue: KSh {revenue:,}
📍 Top Location: {top_location}
🏆 Top Performer: {top_agent}
✅ Achievement Rate: {(total_sales/QUARTERLY_TARGETS[CURRENT_Q]*100):.1f}%

**Analysis:**
{f"Gap to Target: {QUARTERLY_TARGETS[CURRENT_Q] - total_sales} plots remaining" if total_sales < QUARTERLY_TARGETS[CURRENT_Q] else "🎉 Target exceeded!"}
    """
    
    st.text_area("Report Preview", report_text, height=300)
    
    # Download Buttons
    st.markdown("### 📥 Download Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Excel Download
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            st.session_state.sales_data.to_excel(writer, sheet_name='Sales Data', index=False)
            
            # Summary Sheet
            summary_df = pd.DataFrame({
                'Metric': ['Total Sales', 'Revenue', 'Target', 'Achievement'],
                'Value': [total_sales, revenue, QUARTERLY_TARGETS[CURRENT_Q], f"{(total_sales/QUARTERLY_TARGETS[CURRENT_Q]*100):.1f}%"]
            })
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        excel_buffer.seek(0)
        st.download_button(
            label="📊 Download Excel Report",
            data=excel_buffer,
            file_name=f"RealtorOS_Report_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col2:
        # CSV Download
        csv = st.session_state.sales_data.to_csv(index=False)
        st.download_button(
            label="📄 Download CSV Data",
            data=csv,
            file_name=f"sales_data_{datetime.date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col3:
        # PDF Download with AI Analysis
        if st.button("🤖 Generate AI + PDF Report", use_container_width=True):
            with st.spinner("Generating comprehensive report..."):
                # Generate AI advice if not already done
                if 'last_ai_advice' not in st.session_state:
                    st.session_state['last_ai_advice'] = get_ai_advice(
                        st.session_state.sales_data, 
                        total_sales, 
                        QUARTERLY_TARGETS[CURRENT_Q]
                    )
                
                pdf_buffer = create_pdf_report(
                    st.session_state.sales_data,
                    st.session_state['last_ai_advice']
                )
                
                st.download_button(
                    label="📕 Download PDF Report",
                    data=pdf_buffer,
                    file_name=f"RealtorOS_AI_Report_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# --- FOOTER ---
st.sidebar.markdown("---")
st.sidebar.caption("RealtorOS v1.0 | Powered by Gemini AI")
st.sidebar.caption("© 2026 Kangundo Road Sales")
