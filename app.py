import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
from io import BytesIO
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import gspread
from google.oauth2.service_account import Credentials
import uuid
from datetime import timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="RealtorOS Executive", page_icon="🏘️", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e3a8a; text-align: center; margin-bottom: 2rem; }
    .stMetric { background-color: #f8fafc; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# --- CLOUD CONNECTION ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    GEMINI_API_KEY = ""
    
try:
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
except KeyError:
    SPREADSHEET_ID = ""

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = genai.GenerativeModel('gemini-2.5-flash-lite')
    except Exception as e:
        st.sidebar.error(f"Gemini error: {e}")
        GEMINI_MODEL = None
else:
    GEMINI_MODEL = None

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
            return None
    except Exception as e:
        st.sidebar.error(f"Auth error: {e}")
        return None

# --- SHEET INITIALIZATION FUNCTIONS ---
def initialize_sheets():
    """Initialize all three sheets with proper headers"""
    client = get_gsheet_client()
    if not client or not SPREADSHEET_ID:
        return False
    
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        
        # SHEET 1: Transactions (All Payments)
        try:
            transactions_ws = sh.worksheet("Transactions")
        except gspread.exceptions.WorksheetNotFound:
            transactions_ws = sh.add_worksheet(title="Transactions", rows="1000", cols="10")
        
        trans_headers = ['Transaction_ID', 'Date', 'Agent', 'Location', 'Client_ID', 
                        'Amount', 'Payment_Type', 'Phone', 'Sale_ID', 'Notes']
        if not transactions_ws.get_all_values():
            transactions_ws.append_row(trans_headers)
        
        # SHEET 2: Targets
        try:
            targets_ws = sh.worksheet("Targets")
        except gspread.exceptions.WorksheetNotFound:
            targets_ws = sh.add_worksheet(title="Targets", rows="100", cols="6")
        
        target_headers = ['Year', 'Period_Type', 'Period_Number', 'Target_Amount', 'Last_Updated', 'Notes']
        if not targets_ws.get_all_values():
            targets_ws.append_row(target_headers)
        
        # SHEET 3: Sales Ledger (Master Sales List)
        try:
            ledger_ws = sh.worksheet("Sales_Ledger")
        except gspread.exceptions.WorksheetNotFound:
            ledger_ws = sh.add_worksheet(title="Sales_Ledger", rows="1000", cols="12")
        
        ledger_headers = ['Sale_ID', 'Client_ID', 'Client_Name', 'Phone', 'Agent', 
                         'Location', 'Total_Sale_Price', 'Amount_Paid', 'Balance', 
                         'Sale_Date', 'Status', 'Notes']
        if not ledger_ws.get_all_values():
            ledger_ws.append_row(ledger_headers)
        
        return True
        
    except Exception as e:
        st.error(f"Sheet initialization error: {e}")
        return False

# --- DATA LOADING FUNCTIONS ---
def load_transactions():
    """Load all transactions"""
    client = get_gsheet_client()
    if not client or not SPREADSHEET_ID:
        return pd.DataFrame()
    
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("Transactions")
        data = ws.get_all_values()
        
        if len(data) <= 1:
            return pd.DataFrame(columns=['Transaction_ID', 'Date', 'Agent', 'Location', 'Client_ID', 
                                        'Amount', 'Payment_Type', 'Phone', 'Sale_ID', 'Notes'])
        
        df = pd.DataFrame(data[1:], columns=data[0])
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return df
    except Exception as e:
        st.sidebar.error(f"Error loading transactions: {e}")
        return pd.DataFrame()

def load_sales_ledger():
    """Load sales ledger"""
    client = get_gsheet_client()
    if not client or not SPREADSHEET_ID:
        return pd.DataFrame()
    
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("Sales_Ledger")
        data = ws.get_all_values()
        
        if len(data) <= 1:
            return pd.DataFrame(columns=['Sale_ID', 'Client_ID', 'Client_Name', 'Phone', 'Agent', 
                                        'Location', 'Total_Sale_Price', 'Amount_Paid', 'Balance', 
                                        'Sale_Date', 'Status', 'Notes'])
        
        df = pd.DataFrame(data[1:], columns=data[0])
        df['Total_Sale_Price'] = pd.to_numeric(df['Total_Sale_Price'], errors='coerce').fillna(0)
        df['Amount_Paid'] = pd.to_numeric(df['Amount_Paid'], errors='coerce').fillna(0)
        df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
        df['Sale_Date'] = pd.to_datetime(df['Sale_Date'], errors='coerce')
        return df
    except Exception as e:
        st.sidebar.error(f"Error loading ledger: {e}")
        return pd.DataFrame()

def load_targets():
    """Load revenue targets"""
    client = get_gsheet_client()
    if not client or not SPREADSHEET_ID:
        return pd.DataFrame()
    
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("Targets")
        data = ws.get_all_values()
        
        if len(data) <= 1:
            return pd.DataFrame(columns=['Year', 'Period_Type', 'Period_Number', 'Target_Amount', 'Last_Updated', 'Notes'])
        
        df = pd.DataFrame(data[1:], columns=data[0])
        df['Target_Amount'] = pd.to_numeric(df['Target_Amount'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.sidebar.error(f"Error loading targets: {e}")
        return pd.DataFrame()

# --- HELPER FUNCTIONS ---
def get_week_number(date):
    """Get week number for a date"""
    return date.isocalendar()[1]

def get_quarter(date):
    """Get quarter for a date"""
    return (date.month - 1) // 3 + 1

def calculate_suggested_targets(transactions_df):
    """Calculate suggested targets based on historical data"""
    if transactions_df.empty:
        return {"Week": 500000, "Month": 2000000, "Quarter": 6000000, "Year": 25000000}
    
    # Get last 3 months of data
    three_months_ago = datetime.datetime.now() - timedelta(days=90)
    recent_data = transactions_df[transactions_df['Date'] >= three_months_ago]
    
    if recent_data.empty:
        avg_monthly = transactions_df['Amount'].sum() / 3 if len(transactions_df) > 0 else 2000000
    else:
        avg_monthly = recent_data['Amount'].sum() / 3
    
    return {
        "Week": avg_monthly / 4,
        "Month": avg_monthly * 1.1,  # 10% growth
        "Quarter": avg_monthly * 3 * 1.1,
        "Year": avg_monthly * 12 * 1.1
    }

# --- STATE MANAGEMENT ---
if 'agents' not in st.session_state:
    st.session_state.agents = ["Manager", "Agent 1", "Agent 2"]

if 'initialized' not in st.session_state:
    st.session_state.initialized = initialize_sheets()

# Load all data
if 'transactions_data' not in st.session_state or st.sidebar.button("🔄 Refresh Data"):
    st.session_state.transactions_data = load_transactions()
    st.session_state.ledger_data = load_sales_ledger()
    st.session_state.targets_data = load_targets()

# --- NAVIGATION ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/609/609036.png", width=100)
st.sidebar.title("RealtorOS Menu")

# Connection status
if get_gsheet_client() and SPREADSHEET_ID:
    st.sidebar.success("✅ Connected to Google Sheets")
    trans_count = len(st.session_state.transactions_data)
    ledger_count = len(st.session_state.ledger_data)
    st.sidebar.info(f"📊 {trans_count} transactions | {ledger_count} sales")
else:
    st.sidebar.error("❌ Not connected")

page = st.sidebar.radio("Navigate to:", 
    ["📊 Dashboard", "💰 New Sale", "💳 Payment Entry", "📋 Sales Ledger", 
     "🎯 Targets", "✏️ Edit/Delete", "👥 Team", "📑 Reports"])

# --- PAGE 1: DASHBOARD ---
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">📊 Executive Dashboard</p>', unsafe_allow_html=True)
    
    trans_df = st.session_state.transactions_data
    ledger_df = st.session_state.ledger_data
    targets_df = st.session_state.targets_data
    
    if not trans_df.empty and 'Amount' in trans_df.columns:
        # Current period calculations
        today = datetime.datetime.now()
        current_week = get_week_number(today)
        current_month = today.month
        current_quarter = get_quarter(today)
        current_year = today.year
        
        # Filter data for current periods
        week_data = trans_df[(trans_df['Date'].dt.isocalendar().week == current_week) & 
                            (trans_df['Date'].dt.year == current_year)]
        month_data = trans_df[(trans_df['Date'].dt.month == current_month) & 
                             (trans_df['Date'].dt.year == current_year)]
        quarter_data = trans_df[(trans_df['Date'].apply(get_quarter) == current_quarter) & 
                               (trans_df['Date'].dt.year == current_year)]
        year_data = trans_df[trans_df['Date'].dt.year == current_year]
        
        # Calculate actuals
        week_actual = week_data['Amount'].sum()
        month_actual = month_data['Amount'].sum()
        quarter_actual = quarter_data['Amount'].sum()
        year_actual = year_data['Amount'].sum()
        
        # Get targets
        week_target = targets_df[(targets_df['Year'] == str(current_year)) & 
                                (targets_df['Period_Type'] == 'Week') & 
                                (targets_df['Period_Number'] == str(current_week))]
        week_target = float(week_target['Target_Amount'].iloc[0]) if not week_target.empty else 0
        
        month_target = targets_df[(targets_df['Year'] == str(current_year)) & 
                                 (targets_df['Period_Type'] == 'Month') & 
                                 (targets_df['Period_Number'] == str(current_month))]
        month_target = float(month_target['Target_Amount'].iloc[0]) if not month_target.empty else 0
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Week", f"KSh {week_actual:,.0f}", 
                     f"Target: KSh {week_target:,.0f}" if week_target > 0 else "No target")
            if week_target > 0:
                progress = (week_actual / week_target) * 100
                st.progress(min(progress/100, 1.0))
                st.caption(f"{progress:.1f}% achieved")
        
        with col2:
            st.metric("Month", f"KSh {month_actual:,.0f}",
                     f"Target: KSh {month_target:,.0f}" if month_target > 0 else "No target")
            if month_target > 0:
                progress = (month_actual / month_target) * 100
                st.progress(min(progress/100, 1.0))
                st.caption(f"{progress:.1f}% achieved")
        
        with col3:
            st.metric("Quarter", f"KSh {quarter_actual:,.0f}")
        
        with col4:
            st.metric("Year", f"KSh {year_actual:,.0f}")
        
        # Revenue breakdown
        st.markdown("---")
        st.subheader("💰 Revenue Breakdown")
        
        col1, col2 = st.columns(2)
        with col1:
            new_sales = trans_df[trans_df['Payment_Type'] == 'New Sale']['Amount'].sum()
            installments = trans_df[trans_df['Payment_Type'] == 'Installment']['Amount'].sum()
            st.metric("New Business", f"KSh {new_sales:,.0f}")
            st.metric("Installments", f"KSh {installments:,.0f}")
        
        with col2:
            if 'Payment_Type' in trans_df.columns:
                fig = px.pie(trans_df, names='Payment_Type', values='Amount',
                           title="Revenue by Type", hole=0.5)
                st.plotly_chart(fig, use_container_width=True)
        
        # Outstanding balances
        st.markdown("---")
        st.subheader("📊 Sales Status")
        if not ledger_df.empty:
            outstanding = ledger_df[ledger_df['Status'] != 'Fully Paid']
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Sales", len(ledger_df))
            col2.metric("Outstanding", len(outstanding))
            col3.metric("Total Outstanding", f"KSh {outstanding['Balance'].sum():,.0f}")
    else:
        st.info("📊 No transaction data yet. Start by recording a new sale!")

# --- PAGE 2: NEW SALE ---
elif page == "💰 New Sale":
    st.markdown('<p class="main-header">💰 Record New Sale</p>', unsafe_allow_html=True)
    
    with st.form("new_sale_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sale_date = st.date_input("Sale Date", datetime.date.today())
            client_name = st.text_input("Client Name*", placeholder="e.g., John Doe")
            phone = st.text_input("Phone Number*", placeholder="0712345678")
            agent = st.selectbox("Sales Agent*", st.session_state.agents)
        
        with col2:
            location = st.selectbox("Location*", ["Malaa", "Joska", "Kamulu", "Other"])
            total_price = st.number_input("Total Sale Price (KSh)*", min_value=0, step=100000, value=2500000)
            initial_payment = st.number_input("Initial Payment (KSh)*", min_value=0, step=50000, value=0)
        
        notes = st.text_area("Notes", placeholder="Any special terms or details...")
        
        submitted = st.form_submit_button("💾 Record Sale", use_container_width=True)
        
        if submitted:
            if not client_name or not phone:
                st.error("❌ Please fill in all required fields (*)")
            elif initial_payment > total_price:
                st.error("❌ Initial payment cannot exceed total price")
            else:
                client = get_gsheet_client()
                if client and SPREADSHEET_ID:
                    try:
                        sh = client.open_by_key(SPREADSHEET_ID)
                        
                        # Generate unique IDs
                        sale_id = f"SALE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                        client_id = f"CLIENT-{uuid.uuid4().hex[:8].upper()}"
                        transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
                        
                        # Add to Sales Ledger
                        balance = total_price - initial_payment
                        status = "Fully Paid" if balance == 0 else "Installment Plan"
                        
                        ledger_row = [sale_id, client_id, client_name, phone, agent, location,
                                     str(total_price), str(initial_payment), str(balance),
                                     str(sale_date), status, notes]
                        
                        ledger_ws = sh.worksheet("Sales_Ledger")
                        ledger_ws.append_row(ledger_row)
                        
                        # Add to Transactions (if initial payment > 0)
                        if initial_payment > 0:
                            trans_row = [transaction_id, str(sale_date), agent, location, client_id,
                                       str(initial_payment), "New Sale", phone, sale_id, notes]
                            trans_ws = sh.worksheet("Transactions")
                            trans_ws.append_row(trans_row)
                        
                        st.success(f"✅ Sale recorded! Sale ID: {sale_id}")
                        st.balloons()
                        st.info(f"💰 Total: KSh {total_price:,} | Paid: KSh {initial_payment:,} | Balance: KSh {balance:,}")
                        
                        # Refresh data
                        st.session_state.transactions_data = load_transactions()
                        st.session_state.ledger_data = load_sales_ledger()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# --- PAGE 3: PAYMENT ENTRY ---
elif page == "💳 Payment Entry":
    st.markdown('<p class="main-header">💳 Log Payment (Installment)</p>', unsafe_allow_html=True)
    
    ledger_df = st.session_state.ledger_data
    
    if ledger_df.empty:
        st.warning("No sales in ledger. Create a sale first!")
    else:
        # Filter only sales with outstanding balance
        outstanding = ledger_df[ledger_df['Status'] != 'Fully Paid'].copy()
        
        if outstanding.empty:
            st.info("🎉 All sales are fully paid!")
        else:
            st.subheader("Select Sale to Add Payment")
            
            # Create display format with unique identifiers
            outstanding['Display'] = outstanding.apply(
                lambda row: f"{row['Client_Name']} ({row['Sale_ID']}) - Balance: KSh {float(row['Balance']):,.0f}",
                axis=1
            )
            
            # IMPORTANT: Display selection OUTSIDE the form so it updates dynamically
            st.subheader("Step 1: Select Sale")
            selected_display = st.selectbox("Select Sale*", outstanding['Display'].tolist(), key="sale_selector")
            
            # Get selected sale details
            selected_sale = outstanding[outstanding['Display'] == selected_display].iloc[0]
            
            # Show current sale details
            st.info(f"""
            **Selected Sale Details:**
            - Client: {selected_sale['Client_Name']}
            - Sale ID: {selected_sale['Sale_ID']}
            - Total Price: KSh {float(selected_sale['Total_Sale_Price']):,.0f}
            - Amount Paid: KSh {float(selected_sale['Amount_Paid']):,.0f}
            - **Current Balance: KSh {float(selected_sale['Balance']):,.0f}**
            """)
            
            st.markdown("---")
            st.subheader("Step 2: Enter Payment Details")
            
            with st.form("payment_form"):
                col1, col2 = st.columns(2)
                with col1:
                    payment_date = st.date_input("Payment Date", datetime.date.today())
                    payment_amount = st.number_input("Payment Amount (KSh)*", 
                                                    min_value=0.0, 
                                                    max_value=float(selected_sale['Balance']),
                                                    step=10000.0,
                                                    value=min(float(selected_sale['Balance']), 100000.0),
                                                    help=f"Maximum: KSh {float(selected_sale['Balance']):,.0f}")
                
                with col2:
                    # Show calculated values
                    new_balance = float(selected_sale['Balance']) - payment_amount
                    new_amount_paid = float(selected_sale['Amount_Paid']) + payment_amount
                    
                    st.metric("Current Balance", f"KSh {float(selected_sale['Balance']):,.0f}")
                    st.metric("New Balance After Payment", f"KSh {new_balance:,.0f}", 
                             delta=f"-{payment_amount:,.0f}", delta_color="normal")
                    
                    if new_balance == 0:
                        st.success("✅ This payment will fully settle the account!")
                
                notes = st.text_area("Payment Notes")
                
                submitted = st.form_submit_button("💰 Record Payment", use_container_width=True)
                
                if submitted:
                    if payment_amount <= 0:
                        st.error("❌ Payment amount must be greater than 0")
                    else:
                        client = get_gsheet_client()
                        if client and SPREADSHEET_ID:
                            try:
                                sh = client.open_by_key(SPREADSHEET_ID)
                                
                                # Add transaction
                                transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
                                trans_row = [transaction_id, str(payment_date), 
                                           selected_sale['Agent'], selected_sale['Location'],
                                           selected_sale['Client_ID'], str(payment_amount),
                                           "Installment", selected_sale['Phone'],
                                           selected_sale['Sale_ID'], notes]
                                
                                trans_ws = sh.worksheet("Transactions")
                                trans_ws.append_row(trans_row)
                                
                                # Update ledger
                                ledger_ws = sh.worksheet("Sales_Ledger")
                                all_ledger = ledger_ws.get_all_values()
                                
                                for i, row in enumerate(all_ledger[1:], start=2):
                                    if row[0] == selected_sale['Sale_ID']:
                                        new_amount_paid = float(selected_sale['Amount_Paid']) + payment_amount
                                        new_balance = float(selected_sale['Total_Sale_Price']) - new_amount_paid
                                        new_status = "Fully Paid" if new_balance == 0 else "Installment Plan"
                                        
                                        ledger_ws.update_cell(i, 8, str(new_amount_paid))
                                        ledger_ws.update_cell(i, 9, str(new_balance))
                                        ledger_ws.update_cell(i, 11, new_status)
                                        break
                                
                                st.success(f"✅ Payment recorded! Transaction ID: {transaction_id}")
                                st.balloons()
                                
                                # Refresh
                                st.session_state.transactions_data = load_transactions()
                                st.session_state.ledger_data = load_sales_ledger()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error: {e}")

# --- PAGE 4: SALES LEDGER ---
elif page == "📋 Sales Ledger":
    st.markdown('<p class="main-header">📋 Sales Ledger</p>', unsafe_allow_html=True)
    
    ledger_df = st.session_state.ledger_data
    
    if not ledger_df.empty:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Sales", len(ledger_df))
        col2.metric("Total Value", f"KSh {ledger_df['Total_Sale_Price'].sum():,.0f}")
        col3.metric("Total Collected", f"KSh {ledger_df['Amount_Paid'].sum():,.0f}")
        col4.metric("Outstanding", f"KSh {ledger_df['Balance'].sum():,.0f}")
        
        st.markdown("---")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect("Filter by Status", 
                                          ledger_df['Status'].unique(),
                                          default=ledger_df['Status'].unique())
        with col2:
            agent_filter = st.multiselect("Filter by Agent",
                                         ledger_df['Agent'].unique(),
                                         default=ledger_df['Agent'].unique())
        
        # Apply filters
        filtered = ledger_df[
            (ledger_df['Status'].isin(status_filter)) &
            (ledger_df['Agent'].isin(agent_filter))
        ]
        
        st.dataframe(filtered, use_container_width=True, height=400)
        
        # Download
        csv = filtered.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Ledger CSV", csv, 
                          f"Sales_Ledger_{datetime.date.today()}.csv", "text/csv")
    else:
        st.info("No sales recorded yet")

# --- PAGE 5: TARGETS ---
elif page == "🎯 Targets":
    st.markdown('<p class="main-header">🎯 Revenue Targets</p>', unsafe_allow_html=True)
    
    trans_df = st.session_state.transactions_data
    targets_df = st.session_state.targets_data
    
    # Show suggested targets
    suggested = calculate_suggested_targets(trans_df)
    
    st.info("💡 **Auto-Calculated Targets** (based on last 3 months)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Weekly", f"KSh {suggested['Week']:,.0f}")
    col2.metric("Monthly", f"KSh {suggested['Month']:,.0f}")
    col3.metric("Quarter", f"KSh {suggested['Quarter']:,.0f}")
    col4.metric("Yearly", f"KSh {suggested['Year']:,.0f}")
    
    st.markdown("---")
    st.subheader("Set Custom Targets")
    
    today = datetime.datetime.now()
    
    with st.form("target_form"):
        target_year = st.number_input("Year", min_value=2024, max_value=2030, value=today.year)
        
        col1, col2 = st.columns(2)
        with col1:
            period_type = st.selectbox("Period Type", ["Week", "Month", "Quarter", "Year"])
        with col2:
            if period_type == "Week":
                period_num = st.number_input("Week Number", min_value=1, max_value=53, value=get_week_number(today))
            elif period_type == "Month":
                period_num = st.number_input("Month Number", min_value=1, max_value=12, value=today.month)
            elif period_type == "Quarter":
                period_num = st.number_input("Quarter", min_value=1, max_value=4, value=get_quarter(today))
            else:
                period_num = 1
        
        target_amount = st.number_input("Target Amount (KSh)", min_value=0, step=100000, value=int(suggested.get(period_type, 0)))
        notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("💾 Save Target")
        
        if submitted:
            client = get_gsheet_client()
            if client and SPREADSHEET_ID:
                try:
                    sh = client.open_by_key(SPREADSHEET_ID)
                    ws = sh.worksheet("Targets")
                    
                    row = [str(target_year), period_type, str(period_num), 
                          str(target_amount), str(datetime.date.today()), notes]
                    ws.append_row(row)
                    
                    st.success("✅ Target saved!")
                    st.session_state.targets_data = load_targets()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    
    # Display existing targets
    if not targets_df.empty:
        st.markdown("---")
        st.subheader("Current Targets")
        st.dataframe(targets_df, use_container_width=True)

# --- PAGE 6: EDIT/DELETE ---
elif page == "✏️ Edit/Delete":
    st.markdown('<p class="main-header">✏️ Edit/Delete Records</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Transactions", "Sales Ledger"])
    
    with tab1:
        st.subheader("Delete Transaction")
        trans_df = st.session_state.transactions_data
        
        if not trans_df.empty:
            st.warning("⚠️ Deleting a transaction does NOT update the Sales Ledger automatically. Use with caution!")
            
            trans_df['Display'] = trans_df.apply(
                lambda row: f"{row['Transaction_ID']} | {row['Date']} | {row['Client_ID']} | KSh {row['Amount']:,.0f}",
                axis=1
            )
            
            to_delete = st.selectbox("Select Transaction to Delete", trans_df['Display'].tolist())
            
            if st.button("🗑️ Delete Transaction", type="primary"):
                selected = trans_df[trans_df['Display'] == to_delete].iloc[0]
                
                client = get_gsheet_client()
                if
