import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- NAME NORMALIZATION MAP ---
# Left Side = Your Database Name
# Right Side = The "Clean" Name (Must match ALL_REGIONS exactly)
DB_TO_CLEAN_MAP = {
    "ao-mon-ateam": "A-Team",
    "ao-mon-dollywood": "Dollywood",
    "ao-mon-wolverine": "Wolverine",
    "ao-tues-claymore": "Claymore",
    "ao-tues-fmj": "FMJ",
    "ao-tues-smoke-n-mirrors": "S&M",
    "ao-tues-ovaltime": "Oval Time",
    "ao-wed-005": "OO5",             # Database uses Zeros, Clean list uses Letter Os
    "ao-wed-sns": "SNS",
    "ao-wed-full-throttle": "Full Throttle",
    "ao-thurs-bo": "BO",
    "ao-thurs-moab": "MOAB",
    "ao-fri-dangerzone": "Danger Zone",
    "ao-fri-gt": "Gran Torino"
}

# --- MASTER LIST OF ALL STOPS ---
# This is the "Passport" checklist
ALL_REGIONS = {
    "Carpex": [
        "A-Team", "Dollywood", "Wolverine", "Claymore", "FMJ", "S&M", "Oval Time", 
        "OO5", "SNS", "Die Another Day", "Full Throttle", "BO", "MOAB", 
        "Danger Zone", "Gran Torino", "Phoenix"
    ],
    "Green Level": [
        "Alpha", "Measure Twice", "Winterfell", "Epcot", "FOD", "Whereville", 
        "Flying Circus", "Omega", "Alderaan"
    ],
    "Peak City": [
        "Beaver Chase", "Hell's Bells", "Off the Rails", "Cougar Town", 
        "Disturbing the Peace", "Pump Fiction", "Ruck This Way", "7th Inning Stretch", 
        "The Foundry", "Lion's Den", "Tortoises", "Bounty Hunters", "Half Dome", 
        "Hot For Teacher", "Board Meeting", "Dante's Peak", "Moon Tower", "Tin 2 Iron", "Das Boot"
    ],
    "South Cary": [
        "99MPH", "Kryptonite", "Jack It Up", "Flirtin' With Disaster", "Just Dough It", 
        "Just Ruck It", "MDCH", "Hulkamania", "Point Break", "Back in Black", 
        "Stonecutters", "Thunderstruck", "Shepherd's Watch", "Slippery When Wet", 
        "Swwingers", "Loch n Load"
    ]
}

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
        # 1. Define the specific list of Carpex AOs that count
        # (Make sure these match the spelling in your database exactly!)
        valid_carpex_aos = [
            "ao-mon-ateam", "ao-mon-dollywood", "ao-mon-wolverine", 
            "ao-tues-claymore", "ao-tues-fmj", "ao-tues-smoke-n-mirrors", "ao-tues-ovaltime", 
            "ao-wed-005", "ao-wed-sns", "ao-wed-full-throttle", 
            "ao-thurs-bo", "ao-thurs-moab", 
            "ao-fri-dangerzone", "ao-fri-gt"
        ]
        
        # 2. Format the list for SQL (Turns it into: "'A-Team', 'Dollywood', ...")
        # We use a Python trick to join them with quotes
        aos_sql_string = "', '".join(valid_carpex_aos)
        aos_sql_string = f"('{aos_sql_string}')"

        # 3. The Query
        query = f"""
        SELECT 
            Date as Date,
            PAX as Name,
            AO as Beatdown,
            'Carpex' as Region
        FROM attendance_view
        WHERE Date >= '2025-01-01' 
        AND AO IN {aos_sql_string} 
        """
        # ^ The "IN" clause filters out any AO not in your list
        
        df_sql = conn.query(query)
        df_sql['Date'] = pd.to_datetime(df_sql['Date'])
        
    except Exception as e:
        st.error(f"Here is the exact error: {e}")
        st.stop()
        df_sql = pd.DataFrame(columns=["Date", "Name", "Beatdown", "Region"])

    # ---------------------------------------------------------
    # PART 3: MERGE & CLEAN
    # ---------------------------------------------------------
    df_master = pd.concat([df_sql, df_sheet], ignore_index=True)
    
    # 1. Apply the translation map
    # This replaces the messy DB names with the clean ones defined above
    df_master["Beatdown"] = df_master["Beatdown"].replace(DB_TO_CLEAN_MAP)
    
    # 2. OPTIONAL: Debugging Helper
    # This will print any names from the DB that don't match your Master List.
    # Check your Streamlit app "Logs" to see these.
    all_valid_stops = [item for sublist in ALL_REGIONS.values() for item in sublist]
    unknown_stops = df_master[~df_master["Beatdown"].isin(all_valid_stops)]["Beatdown"].unique()
    
    if len(unknown_stops) > 0:
        print("⚠️ Warning: These DB names need to be added to your Map:", unknown_stops)

    return df_master

# Load the data
df = load_and_merge_data()

st.title("🏆 GCR Tour Tracker (Hybrid)")

# --- METRICS ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Posts", len(df))
col2.metric("Pax Participating", df["Name"].nunique())
col3.metric("Tour Stops Cleared", df["Beatdown"].nunique())

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["👤 My Progress", "📊 Leaderboard", "🔥 Heatmap"])

# --- TAB 1: INDIVIDUAL PROGRESS ---
with tab1:
    st.subheader("Pax Passport Check")
    
    # Get unique list of names for the dropdown
    all_names = sorted(df["Name"].unique().tolist())
    
    # 1. Select Pax
    selected_pax = st.selectbox("Find your name:", all_names)
    
    if selected_pax:
        # Filter data for this person
        pax_data = df[df["Name"] == selected_pax]
        
        # Get set of beatdowns they have done
        completed_set = set(pax_data["Beatdown"].unique())
        
        # Calculate Stats
        total_stops = sum(len(v) for v in ALL_REGIONS.values())
        my_count = len(completed_set)
        progress = my_count / total_stops
        
        # Display Progress Bar
        st.progress(progress, text=f"{my_count} of {total_stops} Stops Completed ({progress:.0%})")
        
        # Display Checklist by Region
        col1, col2 = st.columns(2)
        
        # Iterate through regions to show what is done/missing
        # We split the 4 regions into two columns for layout
        regions_list = list(ALL_REGIONS.items())
        
        # Left Column (First 2 regions)
        with col1:
            for region, beatdowns in regions_list[:2]:
                with st.expander(f"**{region}**", expanded=True):
                    for bd in beatdowns:
                        if bd in completed_set:
                            st.write(f"✅ ~~{bd}~~") # Strikethrough for done
                        else:
                            st.write(f"⬜ {bd}") # Empty box for to-do

        # Right Column (Last 2 regions)
        with col2:
            for region, beatdowns in regions_list[2:]:
                with st.expander(f"**{region}**", expanded=True):
                    for bd in beatdowns:
                        if bd in completed_set:
                            st.write(f"✅ ~~{bd}~~")
                        else:
                            st.write(f"⬜ {bd}")

# --- TAB 2: LEADERBOARD ---
with tab2:
    # (Your existing Leaderboard code goes here)
    if not df.empty:
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

# --- TAB 3: HEATMAP ---
with tab3:
    st.subheader("🔥 Beatdown Activity")
    
    if not df.empty:
        import plotly.express as px
        
        # --- CHART 1: TREEMAP (Region > Beatdown Popularity) ---
        # Group by Region and Beatdown to get the count
        heatmap_data = df.groupby(['Region', 'Beatdown']).size().reset_index(name='Attendance')
        
        fig_tree = px.treemap(
            heatmap_data,
            path=[px.Constant("Greater Carpex"), 'Region', 'Beatdown'],
            values='Attendance',
            color='Region',
            title="Beatdown Popularity (Size = Total Posts)",
            hover_data=['Attendance']
        )
        st.plotly_chart(fig_tree, use_container_width=True)
        
        st.divider()
        
        # --- CHART 2: DAY OF WEEK GRID ---
        # Extract Day Name from the Date column
        df['Day'] = df['Date'].dt.day_name()
        
        # Group by Day and Region
        day_counts = df.groupby(['Day', 'Region']).size().reset_index(name='Posts')
        
        # Sort Days correctly (Mon -> Sun) instead of Alphabetical
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        fig_grid = px.density_heatmap(
            day_counts,
            x='Day',
            y='Region',
            z='Posts',
            title="Attendance Intensity by Day",
            text_auto=True,
            color_continuous_scale="Viridis",
            category_orders={"Day": day_order}
        )
        st.plotly_chart(fig_grid, use_container_width=True)

    else:
        st.info("No data available yet to generate heatmaps.")
