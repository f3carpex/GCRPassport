import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

st.set_page_config(page_title="GCR Tour Tracker", page_icon="💪", layout="wide")

# --- 1. SETUP CONNECTION ---
# This looks for the [connections.my_db] section in your secrets.toml
conn = st.connection("my_db", type="sql")

st.title("🏆 Greater Carpex Region Tour 2026")

# --- 2. LOAD DATA (CACHE IT) ---
# We use st.cache_data so we don't hammer your DB with a query every time a user clicks a button.
# ttl=300 means "refresh data every 5 minutes"
@st.cache_data(ttl=300)
def get_tour_data():
    # QUERY 1: RAW LOGS (For Heatmap & Recent Activity)
    # Replace 'attendance_table' with your actual table name
    query_logs = """
    SELECT 
        date_attended,
        pax_name,
        beatdown_name,
        region_name
    FROM attendance_table
    WHERE date_attended >= '2026-01-01'
    """
    df_logs = conn.query(query_logs)
    
    # QUERY 2: LEADERBOARD
    # Doing the heavy lifting in SQL is faster than Pandas for large datasets
    query_leaderboard = """
    SELECT 
        pax_name, 
        COUNT(DISTINCT beatdown_name) as unique_stops
    FROM attendance_table
    WHERE date_attended >= '2026-01-01'
    GROUP BY pax_name
    ORDER BY unique_stops DESC
    """
    df_leaderboard = conn.query(query_leaderboard)
    
    return df_logs, df_leaderboard

# Load the data
try:
    df_logs, df_leaderboard = get_tour_data()
except Exception as e:
    st.error("Error connecting to database. Check your secrets.toml settings.")
    st.stop()

# --- 3. DASHBOARD METRICS ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Posts (2026)", len(df_logs))
col2.metric("Active Pax", df_logs['pax_name'].nunique())
col3.metric("Stops Visited", df_logs['beatdown_name'].nunique())

# --- 4. TABS & VISUALIZATIONS ---
tab1, tab2 = st.tabs(["📊 Leaderboard", "🔥 Heatmap"])

with tab1:
    st.subheader("Tour Standings")
    
    # Calculate Percentage (Assuming 60 total stops)
    df_leaderboard['Progress'] = df_leaderboard['unique_stops'] / 60
    
    st.dataframe(
        df_leaderboard,
        column_config={
            "pax_name": "Pax Name",
            "unique_stops": "Unique Stops",
            "Progress": st.column_config.ProgressColumn(
                "Tour Completion",
                format="%.0f%%",
                min_value=0,
                max_value=1
            )
        },
        hide_index=True,
        use_container_width=True
    )

with tab2:
    st.subheader("Beatdown Activity Heatmap")
    
    # Group data for the Heatmap: Region -> Beatdown -> Count
    heatmap_data = df_logs.groupby(['region_name', 'beatdown_name']).size().reset_index(name='attendance_count')
    
    # A Tree Map is perfect for this "Region > Beatdown" hierarchy
    fig = px.treemap(
        heatmap_data,
        path=[px.Constant("Greater Carpex"), 'region_name', 'beatdown_name'],
        values='attendance_count',
        color='region_name', # Different color for each region
        title="Size of box = Total Attendance",
        hover_data=['attendance_count']
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # The "Ratio" / Day of Week Heatmap (If you have Day of Week data)
    # If your SQL date column is actually a date object, we can extract the day name
    if not df_logs.empty:
        df_logs['day_of_week'] = pd.to_datetime(df_logs['date_attended']).dt.day_name()
        
        day_heatmap = df_logs.groupby(['day_of_week', 'region_name']).size().reset_index(name='posts')
        
        # Sort days correctly
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        fig2 = px.density_heatmap(
            day_heatmap,
            x='day_of_week',
            y='region_name',
            z='posts',
            text_auto=True,
            title="Attendance Density by Day",
            category_orders={"day_of_week": day_order}
        )
        st.plotly_chart(fig2, use_container_width=True)
