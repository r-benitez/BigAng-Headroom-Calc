import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from fpdf import FPDF
from io import BytesIO

# --- Theme Configuration ---
V_BLUE = (0, 107, 230)  # Viking Blue
T_GREY = (89, 89, 89)   # Text Grey
L_GREY = (166, 166, 166) # Light Grey for source

class VikingPDF(FPDF):
    def draw_viking_layout(self, client, vertical, cpa, daily, total, days, chart_buf):
        self.add_page(orientation='L') # Landscape mode
        
        # 1. Top Left: Source
        self.set_font("Helvetica", size=8)
        self.set_text_color(*L_GREY)
        self.text(10, 10, "Source: Performance Headroom Tool Analysis")

        # 2. Main Headline
        self.set_xy(10, 15)
        self.set_font("Helvetica", style='B', size=22)
        self.set_text_color(0, 0, 0)
        headline = f"{client if client else 'Client'} can support a {days}-day budget of ${total:,.0f} at a ${cpa:,.0f} CPA."
        self.multi_cell(260, 10, headline)

        # 3. Headroom + Blue Arrow
        # Draw the Blue Arrow (Triangle + Rectangle)
        self.set_fill_color(*V_BLUE)
        self.polygon([(10, 42), (14, 35), (18, 42)], fill=True) 
        self.rect(13, 42, 2, 4, fill=True)
        
        self.set_xy(20, 36)
        self.set_font("Helvetica", size=18)
        self.set_text_color(*V_BLUE)
        self.cell(0, 10, "Headroom")

        # 4. Insert Chart (Positioned center-left)
        chart_buf.seek(0)
        self.image(chart_buf, x=10, y=50, w=170)

        # 5. Right Side Labels
        self.set_xy(190, 55)
        self.set_font("Helvetica", style='B', size=12)
        self.set_text_color(*T_GREY)
        self.cell(0, 10, "Headroom Regression Analysis (Linear)")
        
        self.set_xy(190, 62)
        self.set_font("Helvetica", size=11)
        self.set_text_color(*V_BLUE)
        self.cell(0, 10, vertical.upper() if vertical else "CAMPAIGN_STRATEGY")

        # 6. Bottom Takeaway
        self.set_xy(10, 185)
        self.set_font("Helvetica", style='B', size=14)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, f"Takeaway: Target daily spend is ${daily:,.2f} to maintain efficiency goal.")

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Headroom Calculator")
st.title('📈 Performance Headroom Calculator')

# Step 1: Campaign Metadata
st.header("Step 1: Campaign Information")
col_m1, col_m2 = st.columns(2)
with col_m1:
    client_name = st.text_input("Client Name", placeholder="e.g., Viking River Cruises")
with col_m2:
    vertical_name = st.text_input("Vertical", placeholder="e.g., River Cruises")

st.write("---")

# Step 2: Data Upload
st.header("Step 2: Upload Your Data")
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Missing required columns: {required_cols}")
        else:
            df['Date'] = pd.to_datetime(df['Date'])
            df_daily = df.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)

            # Outlier Cleaning
            q1, q3 = df_daily['eCPA'].quantile(0.25), df_daily['eCPA'].quantile(0.75)
            iqr = q3 - q1
            df_daily['is_outlier'] = (df_daily['eCPA'] < (q1 - 1.5*iqr)) | (df_daily['eCPA'] > (q3 + 1.5*iqr))
            df_cleaned = df_daily[~df_daily['is_outlier']].dropna()

            # Regression
            slope, intercept, r_val, _, _ = stats.linregress(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'])
            st.session_state.model = {'slope': slope, 'intercept': intercept}

            # Plotting
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=df_daily['is_outlier'], cmap='coolwarm', alpha=0.5)
            x_range = np.array(ax.get_xlim())
            ax.plot(x_range, intercept + slope * x_range, color='red', linestyle='--', label='Trendline')
            ax.set_title(f"Spend vs CPA Analysis: {client_name}")
            ax.set_xlabel("Daily Spend (USD)")
            ax.set_ylabel("CPA (USD)")
            st.pyplot(fig)

            # Save chart to memory for PDF
            chart_buf = BytesIO()
            fig.savefig(chart_buf, format='png', dpi=300, bbox_inches='tight')
            st.session_state.chart_buf = chart_buf

    except Exception as e:
        st.error(f"Analysis Error: {e}")

# Step 3: Calculation and PDF Export
st.write("---")
st.subheader("Step 3: Spend Goal & PDF Export")

if 'model' in st.session_state:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        goal_cpa = st.number_input("Enter Goal CPA ($):", min_value=0.0, value=1000.0)
    with col_c2:
        forecast_days = st.number_input("Forecast Period (Days):", min_value=1, value=30)

    if st.button("Calculate & Prepare PDF"):
        m = st.session_state.model
        daily_spend = (goal_cpa - m['intercept']) / m['slope']
        total_budget = daily_spend * forecast_days

        if daily_spend < 0:
            st.warning("Target CPA is likely unachievable based on current data trends.")
        else:
            st.success(f"Recommended Daily Spend: ${daily_spend:,.2f} | Total Budget: ${total_budget:,.2f}")
            
            # PDF Generation
            pdf = VikingPDF()
            pdf.draw_viking_layout(client_name, vertical_name, goal_cpa, daily_spend, total_budget, forecast_days, st.session_state.chart_buf)
            
            pdf_output = pdf.output()
            st.download_button(
                label="📥 Download Viking-Style PDF Report",
                data=pdf_output,
                file_name=f"{client_name}_Headroom_Report.pdf",
                mime="application/pdf"
            )
else:
    st.info("Please upload data in Step 2 to generate calculations.")
