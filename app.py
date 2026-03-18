import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

st.set_page_config(layout="wide", page_title="Performance Headroom Calculator")
st.title('📈 Performance Headroom Calculator')

# --- Step 1: Campaign Information ---
st.header("Step 1: Campaign Information")
col_meta1, col_meta2 = st.columns(2)
with col_meta1:
    client_name = st.text_input("Client Name", placeholder="e.g., IHG, State Farm")
with col_meta2:
    vertical_name = st.text_input("Vertical", placeholder="e.g., Fin CW, Telecom")

st.write("---")

# --- Step 2: Data Upload ---
st.header("Step 2: Upload Your Data")
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        st.write("---")
        st.subheader("Analysis Results")
        
        required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
        if not all(col in df.columns for col in required_cols):
            st.error(f"ERROR: Your file is missing required columns: {', '.join(required_cols)}")
        else:
            df_raw = df[required_cols].copy()
            df_raw.loc[:, 'Date'] = pd.to_datetime(df_raw['Date'])
            df_daily = df_raw.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()
            
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
                st.write(f"**Model Fit (R-squared):** `{r_value**2:.4f}`")

            # Display the analysis graph
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=df_daily['is_outlier'], cmap='coolwarm', alpha=0.7)
            if st.session_state.model:
                x_vals = np.array(ax.get_xlim())
                y_vals = intercept + slope * x_vals
                ax.plot(x_vals, y_vals, '--', color='green', label='Regression Line')
            ax.set_title(f'Spend vs. CPA Analysis: {client_name if client_name else "Unknown Client"}', fontweight='bold')
            ax.set_xlabel('Daily Spend (USD)')
            ax.set_ylabel('Daily CPA (USD)')
            ax.grid(True)
            st.pyplot(fig)

    except Exception as e:
        st.error(f"An error occurred: {e}")

# --- Step 3: Calculation & Budgeting ---
st.write("---")
st.subheader("Step 3: Spend & Budget Calculator")

if 'model' in st.session_state and st.session_state.model:
    col_calc1, col_calc2 = st.columns(2)
    
    with col_calc1:
        goal_cpa = st.number_input(f"Goal CPA ($):", min_value=0.0, value=50.0, format="%.2f")
    
    with col_calc2:
        num_days = st.number_input("Number of days to calculate for:", min_value=1, value=30, step=1)

    if st.button("Generate Recommendation"):
        model = st.session_state.model
        slope, intercept = model.get('slope', 0), model.get('intercept', 0)
        
        if slope > 1e-6:
            daily_spend = (goal_cpa - intercept) / slope
            
            if daily_spend < 0:
                st.warning(f"💡 This Goal CPA is below the model's effective baseline (~${intercept:,.2f}) and is likely unachievable.")
            else:
                total_budget = daily_spend * num_days
                
                # Metadata display
                st.markdown(f"### Results for **{client_name if client_name else 'Client'}**")
                if vertical_name:
                    st.caption(f"Vertical: {vertical_name}")
                
                # Metrics boxes for a professional feel
                m_col1, m_col2 = st.columns(2)
                m_col1.metric("Recommended Daily Spend", f"${daily_spend:,.2f}")
                m_col2.metric(f"Total Budget ({num_days} Days)", f"${total_budget:,.2f}")
                
                st.success(f"To maintain a **${goal_cpa:,.2f} CPA**, you should target a daily spend of **${daily_spend:,.2f}**, totaling **${total_budget:,.2f}** over {num_days} days.")
        else:
            st.error("The relationship in your data is flat or negative, so spend cannot be predicted from CPA.")
else:
    st.info("Please upload data in Step 2 to enable the calculator.")
    
