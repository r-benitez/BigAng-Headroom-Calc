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
    client_name = st.text_input("Client Name", placeholder="e.g., State Farm, IHG, etc.")
with col_m2:
    vertical_name = st.text_input("Vertical", placeholder="e.g., Fin CW, Telecom, etc.")

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
        io_col = next((c for c in df.columns if "insertion order" in c.lower()), None)
        
        if io_col:
            st.subheader("Filter by Insertion Order")
            unique_ios = sorted(df[io_col].dropna().unique().tolist())
            io_options = ["ALL IOs"] + unique_ios
            
            # --- UPDATED TO MULTISELECT ---
            selected_ios = st.multiselect(
                "Select one or more Insertion Orders to analyze:", 
                options=io_options,
                default=["ALL IOs"]
            )
            
            # Logic to handle filtering
            if not selected_ios or "ALL IOs" in selected_ios:
                st.info("Analyzing aggregate performance across **ALL Insertion Orders**.")
            else:
                df = df[df[io_col].isin(selected_ios)].copy()
                st.info(f"Analysis filtered to **{len(selected_ios)}** selected IO(s).")
        else:
            st.warning("No 'Insertion Order' column detected. Analyzing full dataset.")

        required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
        
        if not all(col in df.columns for col in required_cols):
            st.error(f"Missing required columns: {required_cols}")
        else:
            # Data Preprocessing
            df['Date'] = pd.to_datetime(df['Date'])
            # Group by Date to get daily performance for the selection
            df_daily = df.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            
            # Calculate eCPA
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)
            df_daily.dropna(subset=['eCPA', 'Revenue (USD)'], inplace=True)

            # --- MODIFIED Z-SCORE OUTLIER DETECTION ---
            if len(df_daily) > 0:
                median_ecpa = df_daily['eCPA'].median()
                mad = np.median(np.abs(df_daily['eCPA'] - median_ecpa))
                
                # Default to false if we can't compute a valid MAD (e.g., all values identical)
                if mad == 0:
                    df_daily['is_outlier'] = False
                else:
                    # Calculate Modified Z-score for each day
                    df_daily['mod_z_score'] = 0.6745 * (df_daily['eCPA'] - median_ecpa) / mad
                    # Flag outliers beyond the standard 3.5 threshold
                    df_daily['is_outlier'] = df_daily['mod_z_score'].abs() > 3.5
                
                df_cleaned = df_daily[~df_daily['is_outlier']].copy()
            else:
                df_cleaned = df_daily.copy()

            # Regression Model
            if len(df_cleaned) > 1:
                slope, intercept, r_val, _, _ = stats.linregress(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'])
                
                # Safety Check per your previous requirement
                r_squared = r_val**2
                if r_squared < 0.2 or slope < 0:
                    st.error("⚠️ Analysis Not Possible due to insufficient data or inverse relationship")
                    st.session_state.model = None
                else:
                    st.session_state.model = {'slope': slope, 'intercept': intercept}
                    st.subheader("Analysis Results")
                    st.write(f"**Model R-Squared:** `{r_squared:.4f}`")

                    # Visualization
                    fig, ax = plt.subplots(figsize=(10, 5))
                    
                    # Colors: Map Outliers clearly in the scatter plot
                    colors = df_daily['is_outlier'].map({True: 'red', False: 'blue'})
                    ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=colors, alpha=0.5, label='Daily Data Points')
                    
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

if st.session_state.get('model'):
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        goal_cpa = st.number_input("Enter Target Goal CPA ($):", min_value=0.0, value=1000.0, format="%.2f")
    with col_c2:
        forecast_days = st.number_input("Forecast Period (Days):", min_value=1, value=30, step=1)

    if st.button("Calculate Recommended Spend"):
        m = st.session_state.model
        daily_spend = (goal_cpa - m['intercept']) / m['slope']
        total_budget = daily_spend * forecast_days

        if daily_spend < 0:
            st.warning(f"💡 Target CPA of ${goal_cpa:,.2f} is likely unachievable with current performance trends.")
        else:
            st.success(f"### Results for {client_name if client_name else 'Campaign'}:")
            res_col1, res_col2 = st.columns(2)
            res_col1.metric("Recommended Daily Spend", f"${daily_spend:,.2f}")
            res_col2.metric(f"Total Period Budget ({forecast_days} Days)", f"${total_budget:,.2f}")
            st.info(f"**Recommendation:** To maintain a ${goal_cpa:,.2f} CPA, target a total budget of **${total_budget:,.2f}** over {forecast_days} days.")
else:
    st.info("Upload data and ensure a valid model is generated to activate the calculator.")
