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
