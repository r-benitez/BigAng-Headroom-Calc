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

# Initialize df to None
df = None

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
    except Exception as e:
        st.error(f"Error reading file: {e}")

# This block will only run if the file was successfully uploaded and read into a dataframe
if df is not None:
    
    # --- START of EDIT: IO Dropdown ---
    # Assumption: Your dataframe has a column named 'IO' for the insertion orders.
    io_column_name = 'IO'
    
    df_selection = df # By default, the selection is the entire dataframe

    if io_column_name in df.columns:
        # Get unique IOs and add "All IOs" option
        io_options = df[io_column_name].unique().tolist()
        io_options.insert(0, "All IOs")
        
        # Create the dropdown
        selected_io = st.selectbox("Select IO", io_options)
        
        # Filter the dataframe based on the selection
        if selected_io != "All IOs":
            df_selection = df[df[io_column_name] == selected_io]
        else:
            # If "All IOs" is selected, use the entire dataframe
            df_selection = df
    else:
        st.warning(f"Warning: Column '{io_column_name}' not found. Processing data for all IOs.")
    # --- END of EDIT ---

    required_cols = ['Date', 'Revenue (USD)', 'Total Conversions']
    if not all(col in df_selection.columns for col in required_cols):
        st.error(f"Missing required columns in the selected data: {required_cols}")
    else:
        try:
            # Data Preprocessing
            df_processed = df_selection.copy()
            df_processed['Date'] = pd.to_datetime(df_processed['Date'])
            df_daily = df_processed.groupby('Date').agg({'Revenue (USD)': 'sum', 'Total Conversions': 'sum'}).reset_index()

            # Calculate eCPA (Revenue / Conversions)
            df_daily['eCPA'] = df_daily['Revenue (USD)'] / df_daily['Total Conversions']
            df_daily.replace([np.inf, -np.inf], np.nan, inplace=True)

            # Outlier Detection (IQR Method)
            q1, q3 = df_daily['eCPA'].quantile(0.25), df_daily['eCPA'].quantile(0.75)
            iqr = q3 - q1
            df_daily['is_outlier'] = (df_daily['eCPA'] < (q1 - 1.5 * iqr)) | (df_daily['eCPA'] > (q3 + 1.5 * iqr))
            df_cleaned = df_daily[~df_daily['is_outlier']].dropna(subset=['eCPA', 'Revenue (USD)'])

            # Regression Model
            if len(df_cleaned) > 1:
                slope, intercept, r_val, _, _ = stats.linregress(df_cleaned['Revenue (USD)'], df_cleaned['eCPA'])
                st.session_state.model = {'slope': slope, 'intercept': intercept}

                st.subheader("Analysis Results")
                st.write(f"**Model R-Squared:** `{r_val**2:.4f}`")

                # Visualization
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.scatter(df_daily['Revenue (USD)'], df_daily['eCPA'], c=df_daily['is_outlier'], cmap='coolwarm', alpha=0.5, label='Data Points')
                x_range = np.array(ax.get_xlim())
                ax.plot(x_range, intercept + slope * x_range, color='red', linestyle='--', label='Regression Trendline')

                ax.set_title(f"Spend vs CPA Analysis: {client_name if client_name else 'Campaign'}")
                ax.set_xlabel("Daily Spend (USD)")
                ax.set_ylabel("CPA (USD)")
                ax.legend()
                st.pyplot(fig)
            else:
                st.error("Not enough data points after outlier removal to run regression.")
        except Exception as e:
            st.error(f"Analysis Error: {e}")

# Step 3: Calculation
st.write("---")
st.subheader("Step 3: Spend Goal Calculator")
if 'model' in st.session_state and df is not None:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        goal_cpa = st.number_input("Enter Target Goal CPA ($):", min_value=0.0, value=1000.0, format="%.2f")
    with col_c2:
        forecast_days = st.number_input("Forecast Period (Number of Days):", min_value=1, value=30, step=1)
    
    if st.button("Calculate Recommended Spend"):
        m = st.session_state.model

        # Check for flat slope to avoid division by zero
        if abs(m['slope']) > 1e-9:
            # Formula: Spend = (Target CPA - Intercept) / Slope
            daily_spend = (goal_cpa - m['intercept']) / m['slope']
            total_budget = daily_spend * forecast_days
            if daily_spend < 0:
                st.warning(f"💡 The Goal CPA of ${goal_cpa:,.2f} is likely unachievable based on current data trends.")
            else:
                st.success(f"### Results for {client_name if client_name else 'your campaign'}:")
                
                res_col1, res_col2 = st.columns(2)
                res_col1.metric("Recommended Daily Spend", f"${daily_spend:,.2f}")
                res_col2.metric(f"Total Budget ({forecast_days} Days)", f"${total_budget:,.2f}")

                st.info(f"To maintain a **${goal_cpa:,.2f} CPA** in the **{vertical_name if vertical_name else 'selected'}** vertical, target a daily spend of **${daily_spend:,.2f}**.")
        else:
            st.error("The relationship in your data is too flat to predict a spend recommendation.")
else:
    st.info("Upload data in Step 2 to activate the calculator.")

