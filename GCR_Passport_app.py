import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
# Replace with your actual Google Sheet export link
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1FnHMVgluyCBep93B0X2Hi2tb_dU2O1L1wBbXzLXteO8/export?format=csv"

# Connect to SQL (Carpex Database)
conn = st.connection("my_db", type="sql")

@st.cache_data(ttl=300)
def load_and_merge_data():
    # ---------------------------------------------------------
    # PART 1: GOOGLE SHEET (Non-Carpex Regions)
    # ---------------------------------------------------------
    try:
        df_sheet = pd.read_csv(GSHEET_URL)
        
        # 1. Identify the 'Beatdown' columns from the different form sections
        # Update these strings to match the EXACT headers in your Google Sheet
        col_gl = "Beatdown (Green Level)" 
        col_pc = "Beatdown (Peak City)"
        col_sc = "Beatdown (South Cary)"
        
        # 2. Coalesce them into one 'Beatdown' column
        # This logic says: "Take Green Level; if empty, take Peak City; if empty, take South Cary"
        df_sheet['Beatdown'] = df_sheet[col_gl].fillna(df_sheet[col_pc]).fillna(df_sheet[col_sc])
        
        # 3. Clean up the rest of the columns
        df_sheet = df_sheet.rename(columns={
            "Pax Name": "Name",          # Update to match your form header
            "Region": "Region",          # Update to match your form header
            "Date": "Date"               # Update to match your form header
        })
        
        # 4. Filter for only the columns we need
        df_sheet = df_sheet[["Date", "Name", "Beatdown", "Region"]]
        df_sheet['Date'] = pd.to_datetime(df_sheet['Date'])
        
    except Exception as e:
        st.warning(f"Google Sheet Error: {e}")
        df_sheet = pd.DataFrame(columns=["Date", "Name", "Beatdown", "Region"])

    # ---------------------------------------------------------
    # PART 2: SQL DATABASE (Carpex Region)
    # ---------------------------------------------------------
    try:
        # We only pull Carpex data from here
        query = """
        SELECT 
            Date as Date,
            PAX as Name,
            AO as Beatdown,
            'Carpex' as Region
        FROM attendance_view
        WHERE Date >= '2025-01-01' 
        """
        df_sql = conn.query(query)
        df_sql['Date'] = pd.to_datetime(df_sql['Date'])
        
    except Exception as e:
        st.error(f"Here is the exact error: {e}") # <--- This will tell us what is wrong
        st.stop() # Stops the app here so you can read it
        df_sql = pd.DataFrame(columns=["Date", "Name", "Beatdown", "Region"])

    # ---------------------------------------------------------
    # PART 3: MERGE
    # ---------------------------------------------------------
    df_master = pd.concat([df_sql, df_sheet], ignore_index=True)
    
    return df_master

# Load the data
df = load_and_merge_data()

st.title("🏆 GCR Tour Tracker (Hybrid)")

# --- METRICS ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Posts", len(df))
col2.metric("Pax Participating", df["Name"].nunique())
col3.metric("Tour Stops Cleared", df["Beatdown"].nunique())

# --- LEADERBOARD TAB ---
st.subheader("Leaderboard")

if not df.empty:
    # Group by Name
    leaderboard = df.groupby("Name")["Beatdown"].nunique().reset_index()
    leaderboard.columns = ["Name", "Unique Stops"]
    leaderboard["Progress"] = leaderboard["Unique Stops"] / 60
    
    leaderboard = leaderboard.sort_values("Unique Stops", ascending=False)
    
    st.dataframe(
        leaderboard,
        column_config={
            "Progress": st.column_config.ProgressColumn(
                "Completion", format="%.0f%%", min_value=0, max_value=1
            )
        },
        use_container_width=True,
        hide_index=True
    )
