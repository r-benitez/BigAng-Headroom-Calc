import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

st.set_page_config(layout="wide")
st.title('📈 Performance Headroom Calculator')

st.header("Step 1: Upload Your Data")
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        # Determine the file type and read it into a pandas DataFrame
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        st.write("---")
        st.subheader("Analysis Results")
        
        # --- Analysis Code ---
        required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
        if not all(col in df.columns for col in required_cols):
            st.error(f"ERROR: Your file is missing one or more required columns. Please ensure your file contains: {', '.join(required_cols)}")
        else:
            df_raw = df[required_cols].copy()
            df_raw.loc[:, 'Date'] = pd.to_datetime(df_raw['Date'])
            df_daily = df_raw.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            
            # Calculate eCPA and handle division by zero
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)

            # Outlier Detection
            q1 = df_daily['eCPA'].quantile(0.25)
            q3 = df_daily['eCPA'].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            df_daily['is_outlier'] = (df_daily['eCPA'].isna()) | (df_daily['eCPA'] < lower_bound) | (df_daily['eCPA'] > upper_bound)
            df_cleaned = df_daily[~df_daily['is_outlier']].copy()

            st.session_state.model = None
            if len(df_cleaned.dropna(subset=['eCPA'])) > 1:
                x_cleaned, y_cleaned = df_cleaned['Revenue (USD)'], df_cleaned['eCPA']
                slope, intercept, r_value, _, _ = stats.linregress(x_cleaned, y_cleaned)
                st.session_state.model = {'slope': slope, 'intercept': intercept}
                st.write(f"**Model Fit (R-squared):** `{r_value**2:.4f}` (A value closer to 1.0 indicates a better fit)")


            # Display the analysis graph
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=df_daily['is_outlier'], cmap='coolwarm', alpha=0.7)
            if st.session_state.model:
                x_vals = np.array(ax.get_xlim())
                y_vals = intercept + slope * x_vals
                ax.plot(x_vals, y_vals, '--', color='green', label='Regression Line')
            ax.set_title('Spend vs. CPA (Red dots are outliers)', fontweight='bold')
            ax.set_xlabel('Daily Spend (USD)')
            ax.set_ylabel('Daily CPA (USD)')
            ax.grid(True)
            st.pyplot(fig)

    except Exception as e:
        st.error(f"An error occurred during analysis: {e}")

st.write("---")
st.subheader("Step 2: Calculate Spend Goal")
if 'model' in st.session_state and st.session_state.model:
    goal_cpa = st.number_input("Enter your client's Goal CPA:", min_value=0.0, format="%.2f")
    if st.button("Calculate Recommended Spend"):
        model = st.session_state.model
        slope, intercept = model.get('slope', 0), model.get('intercept', 0)
        if slope > 1e-6:
            recommended_spend = (goal_cpa - intercept) / slope
            if recommended_spend < 0:
                st.warning(f"💡 This Goal CPA is below the model's effective baseline of ~${intercept:,.2f} and is likely unachievable.")
            else:
                st.success(f"✅ For a Goal CPA of ${goal_cpa:,.2f}, the recommended daily spend is **${recommended_spend:,.2f}**")
        else:
            st.error("The relationship in your data is flat or negative, so spend cannot be predicted from CPA.")
else:
    st.info("Upload a file to run the analysis and activate the calculator.")

