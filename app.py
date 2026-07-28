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
            
            # --- MULTISELECT ---
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
            df_daily = df.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            
            # Calculate eCPA
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)
            df_daily.dropna(subset=['eCPA', 'Revenue (USD)'], inplace=True)

            # --- IQR WITH A BOUND OF 2 ---
            q1, q3 = df_daily['eCPA'].quantile(0.25), df_daily['eCPA'].quantile(0.75)
            iqr = q3 - q1
            df_daily['is_outlier'] = (df_daily['eCPA'] < (q1 - 2 * iqr)) | (df_daily['eCPA'] > (q3 + 2 * iqr))
            df_cleaned = df_daily[~df_daily['is_outlier']].copy()

            # --- CALCULATE BOTH REGRESSIONS INDEPENDENTLY ---
            model_raw = None
            model_clean = None
            if len(df_daily) > 1:
                s_raw, i_raw, r_raw, _, _ = stats.linregress(df_daily['Revenue (USD)'], df_daily['eCPA'])
                model_raw = {'slope': s_raw, 'intercept': i_raw, 'r_squared': r_raw**2}
            if len(df_cleaned) > 1:
                s_clean, i_clean, r_clean, _, _ = stats.linregress(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'])
                model_clean = {'slope': s_clean, 'intercept': i_clean, 'r_squared': r_clean**2}

            # --- SIDE BY SIDE VISUALIZATION ---
            st.write("### Data Comparison View")
            chart_col1, chart_col2 = st.columns(2)
            
            # Chart 1: Daily Data (Outliers Included)
            with chart_col1:
                fig1, ax1 = plt.subplots(figsize=(8, 4.5))
                ax1.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], color='#1f77b4', alpha=0.6, label='All Daily Data')
                if model_raw:
                    x_rng1 = np.array(ax1.get_xlim())
                    ax1.plot(x_rng1, model_raw['intercept'] + model_raw['slope'] * x_rng1, color='#1f77b4', linestyle='-', label='Raw Trendline')
                    ax1.set_title(f"Daily Data (Outliers Included) | R² = {model_raw['r_squared']:.4f}")
                else:
                    ax1.set_title("Daily Data (Outliers Included)")
                ax1.set_xlabel("Daily Spend (USD)")
                ax1.set_ylabel("CPA (USD)")
                ax1.legend()
                st.pyplot(fig1)

            # Chart 2: Daily Data (Outliers Removed)
            with chart_col2:
                fig2, ax2 = plt.subplots(figsize=(8, 4.5))
                ax2.scatter(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'], color='#1f77b4', alpha=0.6, label='Cleaned Daily Data')
                if model_clean:
                    x_rng2 = np.array(ax2.get_xlim())
                    ax2.plot(x_rng2, model_clean['intercept'] + model_clean['slope'] * x_rng2, color='#1f77b4', linestyle='-', label='Cleaned Trendline')
                    ax2.set_title(f"Daily Data (Outliers Removed) | R² = {model_clean['r_squared']:.4f}")
                else:
                    ax2.set_title("Daily Data (Outliers Removed)")
                ax2.set_xlabel("Daily Spend (USD)")
                ax2.set_ylabel("CPA (USD)")
                ax2.legend()
                st.pyplot(fig2)

            # --- Step 3: Dual Calculation Interface ---
            st.write("---")
            st.subheader("Step 3: Spend Goal Calculator")
            col_inputs1, col_inputs2 = st.columns(2)
            with col_inputs1:
                goal_cpa = st.number_input("Enter Target Goal CPA ($):", min_value=0.0, value=1000.0, format="%.2f")
            with col_inputs2:
                forecast_days = st.number_input("Forecast Period (Days):", min_value=1, value=30, step=1)

            if st.button("Calculate Recommended Spend Across Both Models"):
                st.write("### 📊 Calculation Comparison")
                calc_col1, calc_col2 = st.columns(2)

                # --- LEFT COLUMN: OUTLIERS INCLUDED RESULTS ---
                with calc_col1:
                    st.markdown("#### Mode: Outliers Included")
                    if model_raw:
                        if model_raw['r_squared'] < 0.15 or model_raw['slope'] < 0:
                            st.warning("⚠️ Model performance invalid (R² < 0.15 or inverse trend relationship).")
                        else:
                            daily_spend_raw = (goal_cpa - model_raw['intercept']) / model_raw['slope']
                            total_budget_raw = daily_spend_raw * forecast_days
                            
                            if daily_spend_raw < 0:
                                st.error(f"💡 Target CPA of ${goal_cpa:,.2f} is modeled as unachievable.")
                            else:
                                total_conversions_raw = total_budget_raw / goal_cpa if goal_cpa > 0 else 0.0
                                
                                # Dynamic Baselines based on exact days uploaded
                                uploaded_days_raw = len(df_daily)
                                avg_daily_spend_raw = df_daily['Revenue (USD)'].mean()
                                avg_daily_conversions_raw = df_daily['Total Conversions'].mean()
                                
                                # Scale Baselines to target forecast period
                                baseline_spend_forecast_raw = avg_daily_spend_raw * forecast_days
                                baseline_conversions_forecast_raw = avg_daily_conversions_raw * forecast_days
                                
                                # Headroom (Recommended - Baseline Baseline)
                                headroom_spend_raw = total_budget_raw - baseline_spend_forecast_raw
                                headroom_conversions_raw = total_conversions_raw - baseline_conversions_forecast_raw
                                
                                st.metric("Recommended Daily Spend", f"${daily_spend_raw:,.2f}")
                                st.metric(
                                    f"Total Budget ({forecast_days} Days)", 
                                    f"${total_budget_raw:,.2f}",
                                    delta=f"${headroom_spend_raw:,.2f} Headroom"
                                )
                                st.metric(
                                    "Total Projected Conversions", 
                                    f"{total_conversions_raw:,.1f}",
                                    delta=f"{headroom_conversions_raw:,.1f} Headroom"
                                )
                                
                                st.markdown("---")
                                st.markdown(f"**Baseline Baseline ({uploaded_days_raw} Days Uploaded):**")
                                st.write(f"- Avg Daily Spend: `${avg_daily_spend_raw:,.2f}`")
                                st.write(f"- Avg Daily Conversions: `{avg_daily_conversions_raw:,.1f}`")
                                st.write(f"- Baseline Expected Spend over {forecast_days} days: `${baseline_spend_forecast_raw:,.2f}`")
                                st.write(f"- Baseline Expected Conversions over {forecast_days} days: `{baseline_conversions_forecast_raw:,.1f}`")
                    else:
                        st.error("Insufficient raw data to run metrics.")

                # --- RIGHT COLUMN: OUTLIERS REMOVED RESULTS ---
                with calc_col2:
                    st.markdown("#### Mode: Outliers Removed")
                    if model_clean:
                        if model_clean['r_squared'] < 0.15 or model_clean['slope'] < 0:
                            st.warning("⚠️ Model performance invalid (R² < 0.15 or inverse trend relationship).")
                        else:
                            daily_spend_clean = (goal_cpa - model_clean['intercept']) / model_clean['slope']
                            total_budget_clean = daily_spend_clean * forecast_days
                            
                            if daily_spend_clean < 0:
                                st.error(f"💡 Target CPA of ${goal_cpa:,.2f} is modeled as unachievable.")
                            else:
                                total_conversions_clean = total_budget_clean / goal_cpa if goal_cpa > 0 else 0.0
                                
                                # Dynamic Baselines based on exact days uploaded
                                uploaded_days_clean = len(df_cleaned)
                                avg_daily_spend_clean = df_cleaned['Revenue (USD)'].mean()
                                avg_daily_conversions_clean = df_cleaned['Total Conversions'].mean()
                                
                                # Scale Baselines to target forecast period
                                baseline_spend_forecast_clean = avg_daily_spend_clean * forecast_days
                                baseline_conversions_forecast_clean = avg_daily_conversions_clean * forecast_days
                                
                                # Headroom (Recommended - Baseline Baseline)
                                headroom_spend_clean = total_budget_clean - baseline_spend_forecast_clean
                                headroom_conversions_clean = total_conversions_clean - baseline_conversions_forecast_clean
                                
                                st.metric("Recommended Daily Spend", f"${daily_spend_clean:,.2f}")
                                st.metric(
                                    f"Total Budget ({forecast_days} Days)", 
                                    f"${total_budget_clean:,.2f}",
                                    delta=f"${headroom_spend_clean:,.2f} Headroom"
                                )
                                st.metric(
                                    "Total Projected Conversions", 
                                    f"{total_conversions_clean:,.1f}",
                                    delta=f"{headroom_conversions_clean:,.1f} Headroom"
                                )
                                
                                st.markdown("---")
                                st.markdown(f"**Baseline Baseline ({uploaded_days_clean} Days Uploaded):**")
                                st.write(f"- Avg Daily Spend: `${avg_daily_spend_clean:,.2f}`")
                                st.write(f"- Avg Daily Conversions: `{avg_daily_conversions_clean:,.1f}`")
                                st.write(f"- Baseline Expected Spend over {forecast_days} days: `${baseline_spend_forecast_clean:,.2f}`")
                                st.write(f"- Baseline Expected Conversions over {forecast_days} days: `{baseline_conversions_forecast_clean:,.1f}`")
                    else:
                        st.error("Insufficient cleaned data to run metrics.")
                        
    except Exception as e:
        st.error(f"Analysis Error: {e}")
else:
    st.write("---")
    st.subheader("Step 3: Spend Goal Calculator")
    st.info("Upload data and ensure models are generated to activate the calculator.")
