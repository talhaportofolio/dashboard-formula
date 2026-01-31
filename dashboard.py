import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Analisis Downtime Pro", layout="wide", page_icon="🏭")

# CSS Kustom (Diperbarui untuk Layout Rapat/One Screen)
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    h1 { color: #2c3e50; font-size: 2rem !important; margin-bottom: 0 !important; }
    .stDataFrame { border: 1px solid #ddd; background-color: white; }
    div[data-testid="stMetricValue"] { font-size: 20px; color: #e74c3c; }
    div[data-testid="stMetricLabel"] { font-size: 14px; }
    
    /* --- COMPACT LAYOUT CSS --- */
    .block-container {
        padding-top: 1rem !important; /* Mengurangi jarak atas */
        padding-bottom: 1rem !important;
    }
    
    /* --- SEMBUNYIKAN ELEMENT STREAMLIT ASLI --- */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Styling untuk Halaman Depan */
    .landing-box {
        background-color: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'landing'
if 'df_main' not in st.session_state:
    st.session_state.df_main = None
if 'selected_machine_type' not in st.session_state:
    st.session_state.selected_machine_type = None
# State untuk menyimpan filter agar tidak reset saat pindah halaman
if 'saved_filter_area' not in st.session_state:
    st.session_state.saved_filter_area = None

# --- 1. FUNGSI PEMBERSIH & FORMATTER ---
def clean_downtime_value(val):
    if pd.isna(val) or val == '' or val == '-': return 0
    if isinstance(val, (int, float)): return val
    if isinstance(val, datetime.time): return (val.hour * 60) + val.minute + (val.second / 60)
    if isinstance(val, pd.Timedelta): return val.total_seconds() / 60
    try: return float(str(val).strip())
    except: return 0

def format_time(val):
    if pd.isna(val): return "-"
    if isinstance(val, datetime.time): return val.strftime("%H:%M")
    if isinstance(val, datetime.datetime): return val.strftime("%H:%M")
    return str(val)

def format_date(val):
    if pd.isna(val): return "-"
    try:
        if isinstance(val, datetime.datetime): return val.strftime("%d-%b-%y")
        return str(val)
    except: return str(val)

def clean_shift(val):
    if pd.isna(val): return "Unknown"
    s = str(val).strip().replace('.0', '')
    if s in ['1', '2', '3']: return f"Shift {s}"
    return s

# --- 2. LOAD DATA FUNCTION ---
@st.cache_data(ttl=600) 
def load_data(file_path):
    target_sheets = ['Injection', 'Filling', 'Cutting', 'Packing']
    all_data = []
    
    try:
        xls = pd.ExcelFile(file_path)
        
        for sheet_name in xls.sheet_names:
            matched_target = next((t for t in target_sheets if t.lower() in sheet_name.lower()), None)
            
            if matched_target:
                success = False
                potential_headers = [3, 4] 
                
                for header_row in potential_headers:
                    try:
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
                        
                        clean_columns = {}
                        for col in df.columns:
                            clean_col = str(col).lower().replace('\n', ' ').replace('\r', '').replace('  ', ' ').strip()
                            clean_columns[col] = clean_col
                        
                        has_machine = any(("machine name" in c or "kode mesin" in c) for c in clean_columns.values())
                        has_downtime = any(("total" in c and "downtime" in c) for c in clean_columns.values())
                        
                        if has_machine and has_downtime:
                            col_map = {}
                            for original_col, clean_col in clean_columns.items():
                                if "machine name" in clean_col or "kode mesin" in clean_col: col_map['Machine'] = original_col
                                elif "total" in clean_col and "downtime" in clean_col: col_map['Downtime'] = original_col     
                                elif "start date" in clean_col: col_map['Date'] = original_col
                                elif "start downtime" in clean_col: col_map['Time'] = original_col
                                elif "level 2" in clean_col: col_map['Category'] = original_col   
                                elif "level 3" in clean_col: col_map['Cause'] = original_col      
                                elif "tindakan" in clean_col: col_map['Action'] = original_col
                                elif "shift" in clean_col: col_map['Shift'] = original_col
                                elif "machine type" in clean_col: col_map['Type'] = original_col
                                elif "brand" in clean_col: col_map['Brand'] = original_col
                                elif "stop date" in clean_col: col_map['StopDate'] = original_col
                                elif "start repair" in clean_col: col_map['StartRepair'] = original_col
                                elif "stop repair" in clean_col: col_map['StopRepair'] = original_col
                                elif "start production" in clean_col: col_map['StartProduction'] = original_col
                                elif "respon time" in clean_col: col_map['ResponTime'] = original_col
                                elif "technical downtime" in clean_col: col_map['TechDowntime'] = original_col

                            temp_data = pd.DataFrame()
                            temp_data['Area'] = [matched_target] * len(df)
                            temp_data['Tanggal'] = df[col_map['Date']] if 'Date' in col_map else "-"
                            temp_data['Jam'] = df[col_map['Time']] if 'Time' in col_map else "-"
                            temp_data['Nama Mesin'] = df[col_map['Machine']]
                            
                            temp_data['Machine Type'] = df[col_map['Type']] if 'Type' in col_map else "-"
                            temp_data['Machine Brand'] = df[col_map['Brand']] if 'Brand' in col_map else "-"
                            temp_data['Shift'] = df[col_map['Shift']].apply(clean_shift) if 'Shift' in col_map else "Unknown"
                            
                            l2 = df[col_map['Category']].fillna('') if 'Category' in col_map else ""
                            l3 = df[col_map['Cause']].fillna('') if 'Cause' in col_map else ""
                            temp_data['Penyebab'] = l2.astype(str) + " - " + l3.astype(str)
                            temp_data['Tindakan'] = df[col_map['Action']] if 'Action' in col_map else "-"
                            temp_data['Total Downtime (Menit)'] = df[col_map['Downtime']].apply(clean_downtime_value)
                            
                            temp_data['Stop Date'] = df[col_map['StopDate']].apply(format_date) if 'StopDate' in col_map else "-"
                            temp_data['Start Repair'] = df[col_map['StartRepair']].apply(format_time) if 'StartRepair' in col_map else "-"
                            temp_data['Stop Repair'] = df[col_map['StopRepair']].apply(format_time) if 'StopRepair' in col_map else "-"
                            temp_data['Start Production'] = df[col_map['StartProduction']].apply(format_time) if 'StartProduction' in col_map else "-"
                            temp_data['Level 3'] = l3
                            temp_data['Respon Time'] = df[col_map['ResponTime']].apply(clean_downtime_value) if 'ResponTime' in col_map else 0
                            temp_data['Technical Downtime'] = df[col_map['TechDowntime']].apply(clean_downtime_value) if 'TechDowntime' in col_map else 0

                            temp_data['Tanggal'] = temp_data['Tanggal'].apply(format_date)
                            temp_data['Jam'] = temp_data['Jam'].apply(format_time)

                            temp_data = temp_data.dropna(subset=['Nama Mesin'])
                            if not temp_data.empty:
                                all_data.append(temp_data)
                            
                            success = True
                            break 
                            
                    except Exception as e:
                        continue 
                
                if not success:
                    st.warning(f"⚠️ Sheet '{sheet_name}' gagal dibaca (Cek Header Baris 4 atau 5).")

    except Exception as e:
        if "401" in str(e):
            st.error("🔒 **Error 401: Akses Ditolak.**")
        else:
            st.error(f"Gagal membaca sumber data: {e}")
        return pd.DataFrame()

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# ==========================================
# PAGE 1: LANDING PAGE (INPUT DATA)
# ==========================================
if st.session_state.current_page == 'landing':
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏭 Dashboard Formula")
        st.markdown("### Selamat Datang")
        st.markdown("Silakan pilih sumber data untuk memulai analisis downtime.")
        st.markdown("---")
        
        source_option = st.radio("Pilih Metode Input:", ["Upload File Excel", "Link Google Sheet"], horizontal=True)
        
        final_file_path = None
        
        if source_option == "Upload File Excel":
            uploaded_file = st.file_uploader("📂 Upload File LKM (.xlsx)", type=["xlsx"])
            if uploaded_file:
                final_file_path = uploaded_file

        else:
            st.info("💡 Pastikan Google Sheet diatur ke **'Anyone with the link'**.")
            sheet_url = st.text_input("🔗 Paste Link Google Sheet:", placeholder="https://docs.google.com/spreadsheets/d/...")
            
            if sheet_url:
                match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
                if match:
                    sheet_id = match.group(1)
                    final_file_path = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
                else:
                    st.error("Link tidak valid.")

        if final_file_path:
            if st.button("🚀 Proses Data", type="primary", use_container_width=True):
                with st.spinner("Sedang memproses data..."):
                    df_loaded = load_data(final_file_path)
                    if not df_loaded.empty:
                        st.session_state.df_main = df_loaded
                        # Reset filter saat data baru masuk
                        st.session_state.saved_filter_area = None
                        st.session_state.current_page = 'dashboard'
                        st.rerun()
                    else:
                        st.error("Data kosong atau gagal dibaca.")

# ==========================================
# PAGE 2: DASHBOARD (VISUALISASI 1 LAYAR)
# ==========================================
elif st.session_state.current_page == 'dashboard':
    
    # --- HEADER COMPACT ---
    c1, c2 = st.columns([8, 1])
    with c1:
        st.markdown("### 🏭 Dashboard PT Ultra Prima Abadi - Formula")
    with c2:
        if st.button("🔄 Reset"):
            st.session_state.df_main = None
            st.session_state.saved_filter_area = None
            st.session_state.current_page = 'landing'
            st.cache_data.clear()
            st.rerun()

    df = st.session_state.df_main
    
    if df is not None and not df.empty:
        
        # --- TAB NAVIGASI ---
        tab_dashboard, tab_detail = st.tabs(["📊 Dashboard Visual", "📋 Detail Data Tracking"])

        # === TAB 1: VISUALISASI RAPAT ===
        with tab_dashboard:
            
            # --- LAYOUT METRICS & FILTER SEJAJAR ---
            # c1-c3 untuk Metrics, c4 untuk Filter (Lebih lebar)
            c_metric1, c_metric2, c_metric3, c_filter = st.columns([1, 1, 1, 2])
            
            # 1. FILTER AREA (Di Kolom Paling Kanan)
            with c_filter:
                area_list = sorted(list(df['Area'].unique()))
                if st.session_state.saved_filter_area is None:
                    st.session_state.saved_filter_area = area_list
                
                selected_area = st.pills(
                    "Filter Area:", 
                    options=area_list, 
                    selection_mode="multi", 
                    default=st.session_state.saved_filter_area,
                    key="widget_filter_area"
                )
                st.session_state.saved_filter_area = selected_area
            
            # Terapkan Filter
            if selected_area:
                df_main = df[df['Area'].isin(selected_area)]
            else:
                df_main = df[df['Area'].isin([])] # Kosong jika tidak dipilih

            # 2. METRICS (Di 3 Kolom Pertama)
            df_agg_metrics = df_main.groupby(['Machine Type'])['Total Downtime (Menit)'].sum().reset_index()
            df_agg_metrics = df_agg_metrics.sort_values(by='Total Downtime (Menit)', ascending=False)
            
            total_dt = df_main['Total Downtime (Menit)'].sum()
            top_type = df_agg_metrics.iloc[0]['Machine Type'] if not df_agg_metrics.empty else "-"
            
            with c_metric1:
                st.metric("Total Downtime", f"{total_dt:,.0f} min")
            with c_metric2:
                st.metric("Mesin Kritis", top_type)
            with c_metric3:
                st.metric("Jumlah Tipe", len(df_agg_metrics))
            
            st.divider()

            # 3. VISUALISASI COMPACT (2 Kolom: Bar, Heatmap)
            # Mengatur rasio kolom menjadi 1:1 agar Heatmap punya ruang yang cukup
            row_viz = st.columns([1, 1])
            
            # --- KOLOM KIRI: BAR CHART (INTERAKTIF) ---
            with row_viz[0]:
                st.caption("📊 **Total Downtime per Tipe Mesin** (Klik batang untuk melihat detail)")
                df_agg = df_main.groupby(['Machine Type'])['Total Downtime (Menit)'].sum().reset_index()
                df_agg = df_agg.sort_values(by='Total Downtime (Menit)', ascending=False)
                
                if not df_agg.empty:
                    # Tinggi chart dinamis
                    # User request: 9 bars visible. 
                    # Assuming ~45px per bar row (including gap) -> 9 * 45 = 405px -> ~420px container
                    dynamic_height = max(420, len(df_agg) * 45)
                    
                    # Container scrollable set to 420 to show approx 9 bars
                    with st.container(height=420):
                        fig_bar = px.bar(
                            df_agg, 
                            x='Total Downtime (Menit)', 
                            y='Machine Type', 
                            orientation='h', 
                            text_auto='.0f'
                        )
                        fig_bar.update_layout(
                            yaxis={'categoryorder':'total ascending'}, 
                            height=dynamic_height, 
                            margin=dict(l=0, r=0, t=0, b=0),
                            clickmode='event+select'
                        )
                        # ON SELECT -> PINDAH KE PAGE 3
                        selection = st.plotly_chart(fig_bar, use_container_width=True, on_select="rerun", selection_mode="points")
                        
                        if selection and len(selection.selection['points']) > 0:
                            selected_machine = selection.selection['points'][0]['y']
                            st.session_state.selected_machine_type = selected_machine
                            st.session_state.current_page = 'detail_page' # Pindah Page
                            st.rerun()

            # --- KOLOM KANAN: HEATMAP (PENGGANTI PIE CHART) ---
            with row_viz[1]:
                st.caption("🔥 **Tipe Mesin vs Shift**")
                if 'Shift' in df_main.columns:
                    df_pivot = df_main.pivot_table(index='Machine Type', columns='Shift', values='Total Downtime (Menit)', aggfunc='sum', fill_value=0)
                    df_pivot['Total'] = df_pivot.sum(axis=1)
                    # Ambil Top 15 agar muat di height 420px dan terlihat rapi
                    df_pivot = df_pivot.sort_values('Total', ascending=False).drop(columns='Total').head(15) 
                    
                    fig_heat = px.imshow(df_pivot, text_auto=True, aspect="auto", color_continuous_scale="Reds")
                    # Set height agar sejajar dengan container sebelah (420px)
                    fig_heat.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0)) 
                    st.plotly_chart(fig_heat, use_container_width=True)

        # === TAB 2: TABEL DATA LENGKAP ===
        with tab_detail:
            st.subheader("📋 Detail Data Tracking (Keseluruhan)")
            df_sorted = df_main.sort_values(by='Total Downtime (Menit)', ascending=False).reset_index(drop=True)
            # Menyesuaikan tinggi untuk menampilkan sekitar 14 data (~530px)
            st.dataframe(df_sorted, use_container_width=True, height=530)
            csv = df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "analisis_lkm.csv", "text/csv")

# ==========================================
# PAGE 3: DETAIL PAGE (DRILL DOWN)
# ==========================================
elif st.session_state.current_page == 'detail_page':
    
    # Tombol Kembali
    if st.button("⬅️ Kembali ke Dashboard"):
        st.session_state.current_page = 'dashboard'
        st.session_state.selected_machine_type = None
        st.rerun()
        
    target_machine = st.session_state.selected_machine_type
    df = st.session_state.df_main
    
    st.markdown(f"### 🔎 Analisis Detail: **{target_machine}**")
    
    if df is not None:
        # Filter data hanya untuk mesin yang diklik
        df_detail = df[df['Machine Type'] == target_machine].copy()
        df_detail = df_detail.sort_values(by='Total Downtime (Menit)', ascending=False)
        
        # --- METRICS DETAIL PER TIPE MESIN ---
        # Menghitung Total untuk tipe mesin yang dipilih
        tot_downtime = df_detail['Total Downtime (Menit)'].sum() if 'Total Downtime (Menit)' in df_detail.columns else 0
        tot_respon = df_detail['Respon Time'].sum() if 'Respon Time' in df_detail.columns else 0
        tot_tech = df_detail['Technical Downtime'].sum() if 'Technical Downtime' in df_detail.columns else 0
        
        # Tampilkan Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Downtime", f"{tot_downtime:,.0f} min")
        col2.metric("Total Respon Time", f"{tot_respon:,.0f} min")
        col3.metric("Total Tech Downtime", f"{tot_tech:,.0f} min")
        
        st.divider()

        # Mapping kolom agar user friendly
        cols_to_show = {
            'Tanggal': 'Start Date', 
            'Stop Date': 'Stop Date', 
            'Jam': 'Start Downtime',
            'Start Repair': 'Start Repair', 
            'Stop Repair': 'Stop Repair',
            'Start Production': 'Start Production', 
            'Level 3': 'Level 3',
            'Tindakan': 'Tindakan', 
            'Respon Time': 'Respon Time',
            'Technical Downtime': 'Tech Downtime', 
            'Total Downtime (Menit)': 'Total Downtime'
        }
        
        available_cols = [c for c in cols_to_show.keys() if c in df_detail.columns]
        df_show = df_detail[available_cols].rename(columns=cols_to_show)
        
        # Tampilkan Tabel Detail (Disetel ~500px untuk 13 Data)
        st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True, 
            height=500, # Tinggi disesuaikan untuk menampilkan ~13 baris saja
            column_config={
                "Total Downtime": st.column_config.NumberColumn(format="%d min"),
                "Tech Downtime": st.column_config.NumberColumn(format="%d min"),
                "Respon Time": st.column_config.NumberColumn(format="%d min"),
            }
        )
