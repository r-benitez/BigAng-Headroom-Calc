import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Performance Headroom Calculator")
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
        # File Reading
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Standardize column search (looking for "Insertion Order")
        # This handles "Insertion Order", "insertion order", or "Insertion order"
        io_col = next((c for c in df.columns if "insertion order" in c.lower()), None)
        
        if io_col:
            st.subheader("Filter by Insertion Order")
            io_options = ["ALL IOs"] + sorted(df[io_col].dropna().unique().tolist())
            selected_io = st.selectbox("Select an Insertion Order to analyze:", options=io_options)
            
            if selected_io != "ALL IOs":
                df = df[df[io_col] == selected_io].copy()
                st.info(f"Analysis filtered to: **{selected_io}**")
            else:
                st.info("Analyzing aggregate performance across **ALL Insertion Orders**.")
        else:
            st.warning("No 'Insertion Order' column detected. Analyzing full dataset.")

        required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
        
        if not all(col in df.columns for col in required_cols):
            st.error(f"Missing required columns: {required_cols}")
        else:
            # Data Preprocessing
            df['Date'] = pd.to_datetime(df['Date'])
            # We group by Date to get daily performance regardless of IO splits
            df_daily = df.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            
            # Calculate eCPA
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)

            # Outlier Detection (Matches Source 15 logic)
            q1, q3 = df_daily['eCPA'].quantile(0.25), df_daily['eCPA'].quantile(0.75)
            iqr = q3 - q1
            df_daily['is_outlier'] = (df_daily['eCPA'] < (q1 - 1.5*iqr)) | (df_daily['eCPA'] > (q3 + 1.5*iqr))
            df_cleaned = df_daily[~df_daily['is_outlier']].dropna(subset=['eCPA', 'Revenue (USD)'])

            # Regression Model
            if len(df_cleaned) > 1:
                slope, intercept, r_val, _, _ = stats.linregress(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'])
                st.session_state.model = {'slope': slope, 'intercept': intercept}
                
                st.subheader("Analysis Results")
                st.write(f"**Model R-Squared:** `{r_val**2:.4f}`")

                # Visualization (Mimics the chart in Source 15)
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=df_daily['is_outlier'], cmap='coolwarm', alpha=0.5, label='Daily Data Points')
                
                # Plot Trendline
                x_range = np.array(ax.get_xlim())
                ax.plot(x_range, intercept + slope * x_range, color='red', linestyle='--', label='Regression Trendline')
                
                ax.set_title(f"Spend vs CPA Analysis: {client_name if client_name else 'Campaign'}")
                ax.set_xlabel("Daily Spend (USD)")
                ax.set_ylabel("CPA (USD)")
                ax.legend()
                st.pyplot(fig)
            else:
                st.error("Not enough data points after filtering/outlier removal to run regression.")

    except Exception as e:
        st.error(f"Analysis Error: {e}")

# Step 3: Calculation
st.write("---")
st.subheader("Step 3: Spend Goal Calculator")

if 'model' in st.session_state:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        # Default Goal CPA set to $1,000 per the Viking example 
        goal_cpa = st.number_input("Enter Target Goal CPA ($):", min_value=0.0, value=1000.0, format="%.2f")
    with col_c2:
        forecast_days = st.number_input("Forecast Period (Days):", min_value=1, value=30, step=1)

    if st.button("Calculate Recommended Spend"):
        m = st.session_state.model
        
        if abs(m['slope']) > 1e-9:
            daily_spend = (goal_cpa - m['intercept']) / m['slope']
            total_budget = daily_spend * forecast_days

            if daily_spend < 0:
                st.warning(f"💡 Target CPA of ${goal_cpa:,.2f} is likely unachievable with current performance trends.")
            else:
                st.success(f"### Results for {client_name if client_name else 'Campaign'}:")
                
                res_col1, res_col2 = st.columns(2)
                res_col1.metric("Recommended Daily Spend", f"${daily_spend:,.2f}")
                res_col2.metric(f"Total Period Budget (${forecast_days} Days)", f"${total_budget:,.2f}")
                
                # Final recommendation sentence similar to Source 4
                st.info(f"**Recommendation:** To maintain a ${goal_cpa:,.2f} CPA, target a total budget of **${total_budget:,.2f}** over {forecast_days} days.")
        else:
            st.error("The relationship in the data is too flat to provide a recommendation.")
else:
    st.info("Upload data in Step 2 to activate the calculator.")
