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

# Custom CSS to keep that professional "Blue & Purple" look
st.markdown("""
<style>
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e3a8a; text-align: center; margin-bottom: 2rem; }
    .stMetric { background-color: #f8fafc; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# --- 2. CLOUD CONNECTION (Google Sheets & Gemini) ---
# Validate secrets
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    GEMINI_API_KEY = ""
    st.sidebar.warning("⚠️ GEMINI_API_KEY not found in secrets")

try:
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
except KeyError:
    SPREADSHEET_ID = ""
    st.sidebar.warning("⚠️ SPREADSHEET_ID not found in secrets")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Configure Gemini if API key exists
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.sidebar.error(f"Gemini configuration error: {e}")

@st.cache_resource
def get_gsheet_client():
    """Establish connection to Google Sheets"""
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), 
                scopes=SCOPES
            )
            return gspread.authorize(creds)
        else:
            st.sidebar.error("❌ gcp_service_account not found in secrets")
            return None
    except Exception as e:
        st.sidebar.error(f"Google Sheets auth error: {e}")
        return None

def load_data():
    """Load data from Google Sheets"""
    client = get_gsheet_client()
    if not client:
        st.sidebar.warning("Google Sheets client not initialized")
        return pd.DataFrame()
    
    if not SPREADSHEET_ID:
        st.sidebar.warning("SPREADSHEET_ID not configured")
        return pd.DataFrame()
    
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.sheet1
        data = ws.get_all_values()
        
        # Define expected headers
        expected_headers = ['Date', 'Agent', 'Location', 'Price', 'Status', 'Client_Name', 'Phone', 'Notes']
        
        # Initialize headers if sheet is empty
        if not data or len(data) == 0:
            ws.append_row(expected_headers)
            st.sidebar.info("✅ Initialized Google Sheet with headers")
            return pd.DataFrame(columns=expected_headers)
        
        # Check if first row matches expected headers
        if data[0] != expected_headers:
            st.sidebar.warning("⚠️ Sheet headers don't match expected format. Fixing...")
            # Clear sheet and add correct headers
            ws.clear()
            ws.append_row(expected_headers)
            return pd.DataFrame(columns=expected_headers)
        
        # If only headers exist (no data rows)
        if len(data) == 1:
            return pd.DataFrame(columns=expected_headers)
        
        # Create DataFrame with data
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Clean and convert data types
        if 'Price' in df.columns:
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.sidebar.error(f"❌ Spreadsheet not found. Check SPREADSHEET_ID: {SPREADSHEET_ID}")
        st.sidebar.info("💡 Make sure you've shared the sheet with the service account email")
        return pd.DataFrame()
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f"❌ Google Sheets API error: {e}")
        st.sidebar.info("💡 Check if Google Sheets API is enabled in GCP Console")
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.error(f"❌ Error loading data: {e}")
        return pd.DataFrame()

# --- 3. STATE MANAGEMENT (Agents & Targets) ---
if 'agents' not in st.session_state:
    st.session_state.agents = ["Manager", "Agent 1", "Agent 2"]

if 'targets' not in st.session_state:
    st.session_state.targets = {"Week": 0, "Month": 0, "Quarter": 0, "Year": 0}

# Load data into session
if 'sales_data' not in st.session_state or st.sidebar.button("🔄 Refresh Data"):
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
    
    if not df.empty and 'Price' in df.columns and len(df) > 0:
        # Top Metrics
        m1, m2, m3, m4 = st.columns(4)
        total_rev = df['Price'].sum()
        m1.metric("Total Revenue", f"KSh {total_rev:,.0f}")
        m2.metric("Sales Count", len(df))
        
        # Calculate average sale price
        avg_price = df['Price'].mean() if len(df) > 0 else 0
        m3.metric("Average Sale", f"KSh {avg_price:,.0f}")
        
        # Target Progress logic
        month_target = st.session_state.targets["Month"]
        if month_target > 0:
            progress = (total_rev / month_target) * 100
            m4.metric("Monthly Target Progress", f"{progress:.1f}%")
            st.progress(min(progress/100, 1.0))
        
        # AI SALES COACH SECTION
        st.markdown("---")
        st.subheader("🤖 AI Sales Coach (Gemini 2.0 Flash)")
        
        if st.button("🧠 Analyze My Sales Performance"):
            if not GEMINI_API_KEY:
                st.warning("⚠️ Please add your GEMINI_API_KEY to Streamlit secrets to use AI Coach.")
            else:
                try:
                    with st.spinner("🔮 Gemini is analyzing your data..."):
                        # Use Gemini 2.0 Flash (latest available model)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        # Prepare comprehensive data summary
                        location_summary = df.groupby('Location')['Price'].agg(['sum', 'count']).to_string()
                        agent_summary = df.groupby('Agent')['Price'].agg(['sum', 'count']).to_string()
                        
                        prompt = f"""
                        You are an elite Real Estate Sales Coach for the Kenyan market, specializing in Nairobi's eastern suburbs.
                        
                        Analyze this sales performance data:
                        
                        LOCATION BREAKDOWN:
                        {location_summary}
                        
                        AGENT PERFORMANCE:
                        {agent_summary}
                        
                        TOTAL REVENUE: KSh {total_rev:,.0f}
                        AVERAGE SALE: KSh {avg_price:,.0f}
                        TOTAL TRANSACTIONS: {len(df)}
                        
                        Provide:
                        1. Three specific, actionable strategies to increase revenue in Malaa, Joska, and Kamulu
                        2. One key insight about agent performance
                        3. One market opportunity based on the data
                        
                        Use a professional, encouraging tone - like a trusted business advisor.
                        """
                        
                        response = model.generate_content(prompt)
                        st.success("✨ AI Insights Generated!")
                        st.info(response.text)
                        
                except Exception as e:
                    st.error(f"❌ AI Coach error: {e}")
                    st.info("💡 Tip: Make sure you're using a valid Gemini API key")
        
        # Charts
        st.markdown("---")
        st.subheader("📈 Visual Analytics")
        c1, c2 = st.columns(2)
        
        with c1:
            if 'Location' in df.columns and 'Price' in df.columns and len(df) > 0:
                fig_loc = px.pie(df, names='Location', values='Price', 
                               title="Revenue Distribution by Location", 
                               hole=0.5,
                               color_discrete_sequence=px.colors.qualitative.Set3)
                st.plotly_chart(fig_loc, use_container_width=True)
        
        with c2:
            if 'Agent' in df.columns and 'Price' in df.columns and len(df) > 0:
                agent_perf = df.groupby('Agent')['Price'].sum().reset_index()
                fig_agent = px.bar(agent_perf, x='Agent', y='Price',
                                  title="Revenue by Agent",
                                  color='Price',
                                  color_continuous_scale='Blues')
                st.plotly_chart(fig_agent, use_container_width=True)
        
        # Sales trend over time
        if 'Date' in df.columns and not df['Date'].isna().all() and len(df) > 0:
            df_sorted = df.sort_values('Date')
            fig_trend = px.line(df_sorted, x='Date', y='Price', 
                              title="Sales Trend Over Time",
                              markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("📊 No sales data available yet. Start by logging your first sale!")
        
        # Connection troubleshooting
        if not SPREADSHEET_ID:
            st.error("❌ SPREADSHEET_ID not configured in secrets")
        elif not get_gsheet_client():
            st.error("❌ Google Sheets connection failed")
            st.markdown("""
            ### 🔧 Troubleshooting Steps:
            1. **Share your Google Sheet** with: `my-sheet-robot@realtoros-483209.iam.gserviceaccount.com`
            2. **Enable APIs** in Google Cloud Console:
               - Google Sheets API
               - Google Drive API
            3. **Check secrets** formatting in Streamlit Cloud
            4. Click **🔄 Refresh Data** in the sidebar after fixing
            """)
        else:
            st.markdown("### Quick Start Guide:")
            st.markdown("1. Go to **📝 Log New Sale** to record transactions")
            st.markdown("2. Set your **🎯 Revenue Targets**")
            st.markdown("3. Return here to view analytics and AI insights")

# --- PAGE 2: LOG NEW SALE ---
elif page == "📝 Log New Sale":
    st.markdown('<p class="main-header">📝 Record New Sale</p>', unsafe_allow_html=True)
    
    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            sale_date = st.date_input("Sale Date", datetime.date.today())
            agent = st.selectbox("Sales Agent", st.session_state.agents)
            location = st.selectbox("Location", ["Malaa", "Joska", "Kamulu", "Other"])
        
        with col2:
            price = st.number_input("Sale Price (KSh)", min_value=0, step=50000, value=0)
            client = st.text_input("Client Name")
            phone = st.text_input("Phone Number")
        
        notes = st.text_area("Additional Notes (Optional)")
        
        submitted = st.form_submit_button("🚀 Save to Google Sheets")
        
        if submitted:
            # Validation
            if price <= 0:
                st.error("❌ Please enter a valid sale price")
            elif not client:
                st.error("❌ Please enter client name")
            else:
                client_gs = get_gsheet_client()
                
                if not client_gs:
                    st.error("❌ Cannot connect to Google Sheets. Check your credentials.")
                elif not SPREADSHEET_ID:
                    st.error("❌ SPREADSHEET_ID not configured in secrets")
                else:
                    try:
                        new_row = [
                            str(sale_date), 
                            agent, 
                            location, 
                            str(price), 
                            "Sold", 
                            client, 
                            phone, 
                            notes
                        ]
                        
                        sh = client_gs.open_by_key(SPREADSHEET_ID)
                        sh.sheet1.append_row(new_row)
                        
                        st.success("✅ Sale recorded successfully!")
                        st.balloons()
                        
                        # Refresh data
                        st.session_state.sales_data = load_data()
                        
                        # Show success details
                        st.info(f"💰 **{agent}** sold property in **{location}** for **KSh {price:,}**")
                        
                    except Exception as e:
                        st.error(f"❌ Error saving to Google Sheets: {e}")
                        st.info("Please check your SPREADSHEET_ID and permissions")

# --- PAGE 3: REVENUE TARGETS ---
elif page == "🎯 Revenue Targets":
    st.markdown('<p class="main-header">🎯 Performance Goals</p>', unsafe_allow_html=True)
    st.write("Set revenue targets to track progress on your dashboard.")
    
    with st.form("target_form"):
        c1, c2 = st.columns(2)
        
        t_w = c1.number_input("Weekly Target (KSh)", 
                              value=int(st.session_state.targets["Week"]), 
                              step=100000,
                              min_value=0)
        t_m = c2.number_input("Monthly Target (KSh)", 
                              value=int(st.session_state.targets["Month"]), 
                              step=500000,
                              min_value=0)
        t_q = c1.number_input("Quarterly Target (KSh)", 
                              value=int(st.session_state.targets["Quarter"]), 
                              step=1000000,
                              min_value=0)
        t_y = c2.number_input("Yearly Target (KSh)", 
                              value=int(st.session_state.targets["Year"]), 
                              step=5000000,
                              min_value=0)
        
        if st.form_submit_button("💾 Update Targets"):
            st.session_state.targets = {
                "Week": t_w, 
                "Month": t_m, 
                "Quarter": t_q, 
                "Year": t_y
            }
            st.success("✅ Targets updated successfully!")
            st.info("Go to the Dashboard to see your progress!")

# --- PAGE 4: TEAM MANAGEMENT ---
elif page == "👥 Team Management":
    st.markdown('<p class="main-header">👥 Team Management</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("➕ Add Team Member")
        new_name = st.text_input("Full Name")
        
        if st.button("Add to Team"):
            if not new_name:
                st.error("Please enter a name")
            elif new_name in st.session_state.agents:
                st.warning(f"{new_name} already exists in the team")
            else:
                st.session_state.agents.append(new_name)
                st.success(f"✅ {new_name} added to team!")
                st.rerun()
    
    with col2:
        st.subheader("➖ Remove Team Member")
        to_remove = st.selectbox("Select Member", st.session_state.agents)
        
        if st.button("Remove from Team"):
            if to_remove == "Manager":
                st.error("❌ Cannot remove the Manager role")
            else:
                st.session_state.agents.remove(to_remove)
                st.success(f"✅ {to_remove} removed from team")
                st.rerun()
    
    st.markdown("---")
    st.subheader("👥 Current Team")
    for i, agent in enumerate(st.session_state.agents, 1):
        st.write(f"{i}. **{agent}**")

# --- PAGE 5: REPORTS & PDF ---
elif page == "📑 Reports & PDF":
    st.markdown('<p class="main-header">📑 Sales Reports & Export</p>', unsafe_allow_html=True)
    df = st.session_state.sales_data
    
    if not df.empty and 'Price' in df.columns and len(df) > 0:
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sales", len(df))
        col2.metric("Total Revenue", f"KSh {df['Price'].sum():,.0f}")
        col3.metric("Average Sale", f"KSh {df['Price'].mean():,.0f}")
        
        st.markdown("---")
        st.subheader("📊 Full Sales Data")
        st.dataframe(df, use_container_width=True)
        
        # EXPORT OPTIONS
        st.markdown("---")
        st.subheader("💾 Export Options")
        
        col_export1, col_export2 = st.columns(2)
        
        # EXCEL EXPORT
        with col_export1:
            st.markdown("### 📗 Excel Format")
            st.write("Download as Excel spreadsheet (.xlsx)")
            
            try:
                # Create Excel file in memory
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    # Write main data
                    df.to_excel(writer, sheet_name='Sales Data', index=False)
                    
                    # Create summary sheet
                    summary_data = {
                        'Metric': ['Total Sales', 'Total Revenue (KSh)', 'Average Sale (KSh)', 'Report Date'],
                        'Value': [
                            len(df),
                            f"{df['Price'].sum():,.0f}",
                            f"{df['Price'].mean():,.0f}",
                            str(datetime.date.today())
                        ]
                    }
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Create location breakdown sheet
                    if 'Location' in df.columns:
                        location_summary = df.groupby('Location').agg({
                            'Price': ['sum', 'count', 'mean']
                        }).round(0)
                        location_summary.columns = ['Total Revenue', 'Number of Sales', 'Average Price']
                        location_summary.to_excel(writer, sheet_name='By Location')
                    
                    # Create agent performance sheet
                    if 'Agent' in df.columns:
                        agent_summary = df.groupby('Agent').agg({
                            'Price': ['sum', 'count', 'mean']
                        }).round(0)
                        agent_summary.columns = ['Total Revenue', 'Number of Sales', 'Average Price']
                        agent_summary.to_excel(writer, sheet_name='By Agent')
                
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Excel Report",
                    data=excel_buffer.getvalue(),
                    file_name=f"RealtorOS_Sales_Report_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"❌ Error generating Excel: {e}")
        
        # PDF EXPORT
        with col_export2:
            st.markdown("### 📕 PDF Format")
            st.write("Download as PDF document (.pdf)")
            
            if st.button("📄 Generate PDF Report", use_container_width=True):
                try:
                    pdf_buffer = BytesIO()
                    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    # Title
                    elements.append(Paragraph("RealtorOS - Executive Sales Report", styles['Title']))
                    elements.append(Spacer(1, 12))
                    elements.append(Paragraph(f"Generated: {datetime.date.today()}", styles['Normal']))
                    elements.append(Spacer(1, 24))
                    
                    # Summary stats
                    summary_text = f"""
                    <b>Summary Statistics:</b><br/>
                    Total Sales: {len(df)}<br/>
                    Total Revenue: KSh {df['Price'].sum():,.0f}<br/>
                    Average Sale: KSh {df['Price'].mean():,.0f}
                    """
                    elements.append(Paragraph(summary_text, styles['Normal']))
                    elements.append(Spacer(1, 24))
                    
                    # Sales Data Table
                    elements.append(Paragraph("<b>Detailed Sales Data:</b>", styles['Heading2']))
                    elements.append(Spacer(1, 12))
                    
                    # Prepare table data (limit columns for PDF width)
                    display_cols = ['Date', 'Agent', 'Location', 'Price', 'Client_Name']
                    df_display = df[display_cols].copy()
                    df_display['Price'] = df_display['Price'].apply(lambda x: f"KSh {x:,.0f}")
                    
                    data_list = [display_cols] + df_display.values.tolist()
                    t = Table(data_list)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                    ]))
                    elements.append(t)
                    
                    doc.build(elements)
                    pdf_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_buffer.getvalue(),
                        file_name=f"RealtorOS_Sales_Report_{datetime.date.today()}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                    st.success("✅ PDF generated successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Error generating PDF: {e}")
        
        # CSV EXPORT (Bonus)
        st.markdown("---")
        st.markdown("### 📄 Quick CSV Export")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"RealtorOS_Sales_Data_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        
    else:
        st.warning("📊 No sales data available to generate report")
        st.info("Add some sales first to generate reports!")

# --- FOOTER ---
st.sidebar.markdown("---")
st.sidebar.markdown("**RealtorOS Executive v2.0**")
st.sidebar.markdown("Powered by Gemini 2.0 Flash")
