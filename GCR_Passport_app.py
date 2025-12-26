import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
# 1. Google Sheet Link (Export Format)
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1FnHMVgluyCBep93B0X2Hi2tb_dU2O1L1wBbXzLXteO8/export?format=csv"

# 2. Master List of Requirements (The "Clean" Names)
ALL_REGIONS = {
    "Carpex": [
        "A-Team", "Dollywood", "Wolverine", "Claymore", "FMJ", "S&M", "Oval Time", 
        "OO5", "SNS", "Full Throttle", "BO", "MOAB", 
        "Danger Zone", "Gran Torino"
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

# 3. Translation Map (Database Name -> Clean Name)
DB_TO_CLEAN_MAP = {
    "ao-mon-ateam": "A-Team",
    "ao-mon-dollywood": "Dollywood",
    "ao-mon-wolverine": "Wolverine",
    "ao-tues-claymore": "Claymore",
    "ao-tues-fmj": "FMJ",
    "ao-tues-smoke-n-mirrors": "S&M",
    "ao-tues-ovaltime": "Oval Time",
    "ao-wed-005": "OO5",
    "ao-wed-sns": "SNS",
    "ao-wed-full-throttle": "Full Throttle",
    "ao-thurs-bo": "BO",
    "ao-thurs-moab": "MOAB",
    "ao-fri-dangerzone": "Danger Zone",
    "ao-fri-gt": "Gran Torino"
    # Note: "Phoenix" and "Die Another Day" are assumed to match. If not, add them here.
}

# Connect to SQL
conn = st.connection("my_db", type="sql")

@st.cache_data(ttl=300)
def load_and_merge_data():
    # ---------------------------------------------------------
    # PART 1: GOOGLE SHEET (Non-Carpex Regions)
    # ---------------------------------------------------------
    try:
        df_sheet = pd.read_csv(GSHEET_URL)
        
        # Columns from your Form Sections
        col_gl = "Beatdown (Green Level)" 
        col_pc = "Beatdown (Peak City)"
        col_sc = "Beatdown (South Cary)"
        
        # Coalesce
        df_sheet['Beatdown'] = df_sheet[col_gl].fillna(df_sheet[col_pc]).fillna(df_sheet[col_sc])
        
        # Rename
        df_sheet = df_sheet.rename(columns={
            "Pax Name": "Name",          
            "Region": "Region",          
            "Date": "Date"               
        })
        
        # Filter
        df_sheet = df_sheet[["Date", "Name", "Beatdown", "Region"]]
        df_sheet['Date'] = pd.to_datetime(df_sheet['Date'])
        
    except Exception as e:
        st.error(f"Google Sheet Error: {e}")
        df_sheet = pd.DataFrame(columns=["Date", "Name", "Beatdown", "Region"])

    # ---------------------------------------------------------
    # PART 2: SQL DATABASE (Carpex Region)
    # ---------------------------------------------------------
    try:
        # RAW NAMES list for the SQL Query
        valid_carpex_aos_raw = [
            "ao-mon-ateam", "ao-mon-dollywood", "ao-mon-wolverine", 
            "ao-tues-claymore", "ao-tues-fmj", "ao-tues-smoke-n-mirrors", "ao-tues-ovaltime", 
            "ao-wed-005", "ao-wed-sns", "ao-wed-full-throttle", 
            "ao-thurs-bo", "ao-thurs-moab", 
            "ao-fri-dangerzone", "ao-fri-gt", 
            "Die Another Day", "Phoenix" # Assuming these match raw DB names
        ]
        
        # Format for SQL IN clause
        aos_sql_string = "', '".join(valid_carpex_aos_raw)
        aos_sql_string = f"('{aos_sql_string}')"

        # Query
        # Changed date to 2025-01-01 so you can see data NOW. Change to 2026 later.
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
        
        df_sql = conn.query(query)
        df_sql['Date'] = pd.to_datetime(df_sql['Date'])
        
    except Exception as e:
        st.error(f"SQL Error: {e}")
        st.stop()
        df_sql = pd.DataFrame(columns=["Date", "Name", "Beatdown", "Region"])

    # ---------------------------------------------------------
    # PART 3: MERGE & CLEAN
    # ---------------------------------------------------------
    df_master = pd.concat([df_sql, df_sheet], ignore_index=True)
    
    # Apply the Name Translation Map
    df_master["Beatdown"] = df_master["Beatdown"].replace(DB_TO_CLEAN_MAP)
    
    return df_master

# Load Data
df = load_and_merge_data()

st.title("🏆 GCR Passport Stamp Tracker")

# --- CALCULATE FINISHERS ---
# We need to calculate this before drawing the tabs so we can use the data in multiple places
region_finishers = {region: [] for region in ALL_REGIONS}
tour_finishers = []

if not df.empty:
    # Get a set of visited beatdowns for every single person
    pax_groups = df.groupby("Name")["Beatdown"].apply(set)
    
    for pax, visited_set in pax_groups.items():
        regions_done_count = 0
        
        # Check specific regions
        for region, required_list in ALL_REGIONS.items():
            required_set = set(required_list)
            if required_set.issubset(visited_set):
                region_finishers[region].append(pax)
                regions_done_count += 1
        
        # Check if they finished ALL regions (The Full Tour)
        if regions_done_count == len(ALL_REGIONS):
            tour_finishers.append(pax)

# --- METRICS ROW ---
cols = st.columns(len(ALL_REGIONS) + 1)
# 1. Full Tour Metrics
cols[0].metric("🏆 Tour Champions", f"{len(tour_finishers)} Pax")
# 2. Individual Region Metrics
for i, (region, names_list) in enumerate(region_finishers.items()):
    cols[i+1].metric(f"Completed {region}", f"{len(names_list)} Pax")

# --- TABS ---
# Added "Hall of Fame" as the last tab
tab1, tab2, tab3, tab4 = st.tabs(["👤 My Progress", "📊 Leaderboard", "🔥 Heatmap", "🏅 Hall of Fame"])

# --- TAB 1: INDIVIDUAL PROGRESS ---
with tab1:
    st.subheader("Pax Passport Check")
    if not df.empty:
        all_names = sorted(df["Name"].unique().tolist())
        selected_pax = st.selectbox("Find your name:", all_names)
        
        if selected_pax:
            pax_data = df[df["Name"] == selected_pax]
            completed_set = set(pax_data["Beatdown"].unique())
            
            total_stops = sum(len(v) for v in ALL_REGIONS.values())
            my_count = len(completed_set)
            progress = my_count / total_stops
            
            st.progress(progress, text=f"{my_count} of {total_stops} Stops Completed ({progress:.0%})")
            
            col1, col2 = st.columns(2)
            regions_list = list(ALL_REGIONS.items())
            
            with col1:
                for region, beatdowns in regions_list[:2]:
                    with st.expander(f"**{region}**", expanded=True):
                        for bd in beatdowns:
                            if bd in completed_set:
                                st.write(f"✅ ~~{bd}~~")
                            else:
                                st.write(f"⬜ {bd}")

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
    st.subheader("Overall Standings")
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

# --- TAB 4: HALL OF FAME ---
with tab4:
    st.header("🏅 Hall of Fame")
    st.markdown("These Pax have completed every stop in the specific region.")
    
    # Section 1: The Grand Champions (Full Tour)
    st.subheader(f"🏆 GCR Passport Finishers ({len(tour_finishers)})")
    if tour_finishers:
        st.success(", ".join(tour_finishers))
    else:
        st.info("No one has completed the full tour yet. Will you be the first?")
    
    st.divider()
    
    # Section 2: Regional Finishers
    # Display in 2 columns for better layout
    col_a, col_b = st.columns(2)
    
    # Loop through regions and display them
    region_items = list(region_finishers.items())
    
    # Left Column
    with col_a:
        for region, names in region_items[:2]: # First 2 regions
            st.markdown(f"### {region} ({len(names)})")
            if names:
                st.write(", ".join(names))
            else:
                st.caption("No finishers yet.")
                
    # Right Column
    with col_b:
        for region, names in region_items[2:]: # Last 2 regions
            st.markdown(f"### {region} ({len(names)})")
            if names:
                st.write(", ".join(names))
            else:
                st.caption("No finishers yet.")
