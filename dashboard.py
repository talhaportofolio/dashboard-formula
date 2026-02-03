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
# State untuk menyimpan pilihan Level 3 di Page 3
if 'selected_level3' not in st.session_state:
    st.session_state.selected_level3 = None

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
                                elif "regu" in clean_col: col_map['Regu'] = original_col # GANTI SHIFT -> REGU
                                elif "machine type" in clean_col: col_map['Type'] = original_col
                                elif "brand" in clean_col: col_map['Brand'] = original_col
                                elif "stop date" in clean_col: col_map['StopDate'] = original_col
                                elif "start repair" in clean_col: col_map['StartRepair'] = original_col
                                elif "stop repair" in clean_col: col_map['StopRepair'] = original_col
                                elif "start production" in clean_col: col_map['StartProduction'] = original_col
                                elif "respon time" in clean_col: col_map['ResponTime'] = original_col
                                elif "technical downtime" in clean_col: col_map['TechDowntime'] = original_col
                                elif "pic" in clean_col: col_map['PIC'] = original_col

                            temp_data = pd.DataFrame()
                            temp_data['Area'] = [matched_target] * len(df)
                            
                            # Simpan Raw Date untuk Filtering
                            if 'Date' in col_map:
                                temp_data['Date_Raw'] = pd.to_datetime(df[col_map['Date']], errors='coerce')
                            else:
                                temp_data['Date_Raw'] = pd.NaT

                            temp_data['Tanggal'] = df[col_map['Date']] if 'Date' in col_map else "-"
                            temp_data['Jam'] = df[col_map['Time']] if 'Time' in col_map else "-"
                            temp_data['Nama Mesin'] = df[col_map['Machine']]
                            
                            temp_data['Machine Type'] = df[col_map['Type']] if 'Type' in col_map else "-"
                            temp_data['Machine Brand'] = df[col_map['Brand']] if 'Brand' in col_map else "-"
                            
                            # AMBIL REGU
                            temp_data['Regu'] = df[col_map['Regu']].astype(str) if 'Regu' in col_map else "-"
                            
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
                            temp_data['PIC'] = df[col_map['PIC']] if 'PIC' in col_map else "-"

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
        st.title("🏭 Dashboard PT Ultra Prima Abadi - Formula")
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
                        # Simpan path file/link untuk keperluan Refresh di Page 2
                        st.session_state.file_path = final_file_path
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
    c1, c2, c3 = st.columns([6, 1, 1]) # Layout Header: Judul | Refresh | Ganti File
    with c1:
        st.markdown("### 🏭 Dashboard PT Ultra Prima Abadi - Formula")
    with c2:
        # Tombol REFRESH (Fitur Baru)
        if st.button("🔄 Refresh"):
            st.cache_data.clear() # Hapus cache lama
            if st.session_state.file_path:
                with st.spinner("Mengambil data terbaru..."):
                    df_new = load_data(st.session_state.file_path)
                    st.session_state.df_main = df_new
            st.rerun()
            
    with c3:
        if st.button("⬅️ Ganti File"): # Tombol Back ke Landing Page
            st.session_state.df_main = None
            st.session_state.saved_filter_area = None
            st.session_state.selected_level3 = None # Reset selected level 3
            st.session_state.current_page = 'landing'
            st.cache_data.clear()
            st.rerun()

    df = st.session_state.df_main
    
    if df is not None and not df.empty:
        
        # === VISUALISASI RAPAT (TANPA TAB) ===
        
        # --- LAYOUT METRICS & FILTER SEJAJAR ---
        # c1-c3 untuk Metrics, c4 untuk Filter (Lebih lebar)
        c_metric1, c_metric2, c_metric3, c_filter = st.columns([1, 1, 1, 2])
        
        # 1. FILTER AREA (Di Kolom Paling Kanan)
        with c_filter:
            # Custom Order: Injection -> Filling -> Cutting -> Packing
            custom_order = ['Injection', 'Filling', 'Cutting', 'Packing']
            available_areas = df['Area'].unique()
            
            # Urutkan berdasarkan custom order, sisanya taruh di belakang
            area_list = [area for area in custom_order if area in available_areas]
            area_list += [area for area in available_areas if area not in custom_order]
            
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
            # Ganti Label: Mesin Kritis -> Downtime Tertinggi
            st.metric("Downtime Tertinggi", top_type)
        with c_metric3:
            # Ganti Label: Jml Tipe -> Jumlah Mesin
            st.metric("Jumlah Mesin", len(df_agg_metrics))
        
        st.divider()

        # 3. VISUALISASI COMPACT (2 Kolom: Bar, Heatmap)
        row_viz = st.columns([1, 1])
        
        # --- KOLOM KIRI: BAR CHART (INTERAKTIF) ---
        with row_viz[0]:
            # Ganti Caption
            st.caption("📊 **Total Downtime per Mesin** (Klik batang untuk melihat detail)")
            df_agg = df_main.groupby(['Machine Type'])['Total Downtime (Menit)'].sum().reset_index()
            df_agg = df_agg.sort_values(by='Total Downtime (Menit)', ascending=False)
            
            if not df_agg.empty:
                # Tinggi chart dinamis agar batang besar-besar (3 batang per layar)
                # ~120px per bar agar 3 bar muat di 400px container
                dynamic_height = max(420, len(df_agg) * 45)
                
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
                    selection = st.plotly_chart(fig_bar, use_container_width=True, on_select="rerun", selection_mode="points")
                    
                    if selection and len(selection.selection['points']) > 0:
                        selected_machine = selection.selection['points'][0]['y']
                        st.session_state.selected_machine_type = selected_machine
                        st.session_state.current_page = 'detail_page' 
                        st.rerun()

        # --- KOLOM KANAN: HEATMAP REGU ---
        with row_viz[1]:
            st.caption("🔥 **Jumlah Downtime Mesin berdasarkan Regu**")
            if 'Regu' in df_main.columns:
                df_pivot = df_main.pivot_table(index='Machine Type', columns='Regu', values='Total Downtime (Menit)', aggfunc='sum', fill_value=0)
                df_pivot['Total'] = df_pivot.sum(axis=1)
                # Restore Top 15 Limit for neatness like before
                df_pivot = df_pivot.sort_values('Total', ascending=False).drop(columns='Total').head(15) 
                
                fig_heat = px.imshow(df_pivot, text_auto=True, aspect="auto", color_continuous_scale="Reds")
                # Fixed Height matching the container of Bar Chart
                fig_heat.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0)) 
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("Kolom 'Regu' tidak ditemukan dalam data.")


# ==========================================
# PAGE 3: DETAIL PAGE (DRILL DOWN)
# ==========================================
elif st.session_state.current_page == 'detail_page':
    
    if st.button("⬅️ Kembali ke Dashboard"):
        st.session_state.current_page = 'dashboard'
        st.session_state.selected_machine_type = None
        st.session_state.selected_level3 = None # Reset selected level 3 saat kembali
        st.rerun()
        
    target_machine = st.session_state.selected_machine_type
    df = st.session_state.df_main
    
    st.markdown(f"### 🔎 Analisis Detail: **{target_machine}**")
    
    if df is not None:
        df_detail = df[df['Machine Type'] == target_machine].copy()
        
        c1, c2, c3, c_filter = st.columns([1, 1, 1, 1.5])
        
        with c_filter:
            min_date = df_detail['Date_Raw'].min()
            max_date = df_detail['Date_Raw'].max()
            
            if pd.notnull(min_date) and pd.notnull(max_date):
                date_range = st.date_input(
                    "Filter Tanggal (Start Date):",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
                
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start_date, end_date = date_range
                    df_detail = df_detail[
                        (df_detail['Date_Raw'].dt.date >= start_date) & 
                        (df_detail['Date_Raw'].dt.date <= end_date)
                    ]
            else:
                st.warning("Data tanggal tidak tersedia.")

        df_detail = df_detail.sort_values(by='Total Downtime (Menit)', ascending=False)
        
        tot_downtime = df_detail['Total Downtime (Menit)'].sum() if 'Total Downtime (Menit)' in df_detail.columns else 0
        tot_respon = df_detail['Respon Time'].sum() if 'Respon Time' in df_detail.columns else 0
        tot_tech = df_detail['Technical Downtime'].sum() if 'Technical Downtime' in df_detail.columns else 0
        
        with c1: st.metric("Total Downtime", f"{tot_downtime:,.0f} min")
        with c2: st.metric("Total Tech Downtime", f"{tot_tech:,.0f} min")
        with c3: st.metric("Total Respon Time", f"{tot_respon:,.0f} min")
        
        st.divider()

        # --- DUA GRAFIK BERDAMPINGAN ---
        c_chart_left, c_chart_right = st.columns(2)

        # 1. KIRI: GRAFIK TREN DOWNTIME HARIAN
        with c_chart_left:
            st.caption("📈 **Grafik Downtime Harian**")
            
            if not df_detail.empty:
                df_trend = df_detail.copy()
                df_trend['Tanggal_Plot'] = df_trend['Date_Raw'].dt.date
                
                df_trend_agg = df_trend.groupby('Tanggal_Plot')['Total Downtime (Menit)'].sum().reset_index()
                
                fig_line = px.line(
                    df_trend_agg, 
                    x='Tanggal_Plot', 
                    y='Total Downtime (Menit)',
                    markers=True,
                )
                fig_line.update_layout(
                    xaxis_title="Tanggal", 
                    yaxis_title="Total Downtime (Menit)", 
                    height=350,
                    margin=dict(l=0, r=0, t=10, b=0)
                )
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Tidak ada data tren.")

        # 2. KANAN: BAR CHART (Proporsi Masalah Level 3) - WITH SCROLLABLE CONTAINER & INTERACTIVE
        with c_chart_right:
            st.caption("📊 **Total Proporsi Masalah Level 3** (Klik batang untuk melihat detail)")
            
            if not df_detail.empty and 'Level 3' in df_detail.columns:
                # 1. Hitung frekuensi awal
                df_level3 = df_detail['Level 3'].value_counts().reset_index()
                df_level3.columns = ['Level 3', 'Jumlah Kejadian']
                
                # 2. Potong nama menjadi 2 kata saja (Truncate)
                df_level3['Level 3'] = df_level3['Level 3'].astype(str).apply(lambda x: ' '.join(x.split()[:2]))
                
                # 3. Group by lagi
                df_level3 = df_level3.groupby('Level 3')['Jumlah Kejadian'].sum().reset_index()
                
                # 4. Sort descending (untuk data processing)
                df_level3 = df_level3.sort_values(by='Jumlah Kejadian', ascending=False)
                
                # 5. Sort ascending agar saat di-plot, bar terbesar ada di ATAS (Plotly default inverted)
                df_level3 = df_level3.sort_values(by='Jumlah Kejadian', ascending=True) 
                
                # Highlight Selected Bar with Strict State Logic
                colors = []
                if st.session_state.selected_level3:
                    for l3 in df_level3['Level 3']:
                        if l3 == st.session_state.selected_level3:
                            colors.append('#ff7f0e') # Orange
                        else:
                            colors.append('#1f77b4') # Blue
                else:
                    colors = ['#1f77b4'] * len(df_level3) # Default Blue

                # Hitung tinggi dinamis berdasarkan jumlah data (agar bisa discroll)
                # Adjust to 60px/bar so ~5 bars fit in 350px
                dynamic_height_l3 = max(350, len(df_level3) * 60)

                with st.container(height=350):
                    fig_bar_l3 = go.Figure(go.Bar(
                        x=df_level3['Jumlah Kejadian'],
                        y=df_level3['Level 3'],
                        orientation='h',
                        text=df_level3['Jumlah Kejadian'],
                        textposition='auto',
                        marker_color=colors # Apply conditional colors
                    ))
                    
                    fig_bar_l3.update_layout(
                        height=dynamic_height_l3,
                        margin=dict(l=0, r=0, t=10, b=0),
                        yaxis={'categoryorder':'total ascending'},
                        clickmode='event+select'
                    )
                    
                    # INTERAKTIVITAS: ON SELECT
                    selection_l3 = st.plotly_chart(
                        fig_bar_l3, 
                        use_container_width=True, 
                        on_select="rerun", 
                        selection_mode="points",
                        key="bar_l3"
                    )
                    
                    if selection_l3 and len(selection_l3.selection['points']) > 0:
                        new_selection = selection_l3.selection['points'][0]['y']
                        # LOGIKA UPDATE STATE + RERUN (Agar warna langsung berubah saat 1x klik)
                        if st.session_state.selected_level3 != new_selection:
                            st.session_state.selected_level3 = new_selection
                            st.rerun()

            else:
                st.info("Data Level 3 tidak tersedia.")

        st.divider()

        # --- SECTION DETAIL PER LEVEL 3 (JIKA DIPILIH) ---
        if st.session_state.selected_level3:
            sel_l3 = st.session_state.selected_level3
            st.markdown(f"#### 🛠️ Detail Masalah: **{sel_l3}**")
            
            # Filter Data berdasarkan Level 3 yang dipilih
            df_detail['Level 3 Short'] = df_detail['Level 3'].astype(str).apply(lambda x: ' '.join(x.split()[:2]))
            df_l3_specific = df_detail[df_detail['Level 3 Short'] == sel_l3].copy()
            
            # Metrics Khusus Level 3
            l3_dt = df_l3_specific['Total Downtime (Menit)'].sum() if 'Total Downtime (Menit)' in df_l3_specific.columns else 0
            l3_tech = df_l3_specific['Technical Downtime'].sum() if 'Technical Downtime' in df_l3_specific.columns else 0
            l3_resp = df_l3_specific['Respon Time'].sum() if 'Respon Time' in df_l3_specific.columns else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Downtime ({sel_l3})", f"{l3_dt:,.0f} min")
            m2.metric(f"Tech Downtime ({sel_l3})", f"{l3_tech:,.0f} min")
            m3.metric(f"Respon Time ({sel_l3})", f"{l3_resp:,.0f} min")
            
            # Tabel Khusus Level 3
            cols_l3_show = {
                'Tanggal': 'Start Date', # Add Start Date
                'Stop Date': 'Stop Date', # Add Stop Date
                'Regu': 'Regu',
                'Level 3': 'Level 3 Full', # Tampilkan nama asli yang panjang
                'Tindakan': 'Tindakan',
                'PIC': 'PIC',
                'Respon Time': 'Respon Time',
                'Technical Downtime': 'Tech Downtime',
                'Total Downtime (Menit)': 'Total Downtime'
            }
            available_cols_l3 = [c for c in cols_l3_show.keys() if c in df_l3_specific.columns]
            df_show_l3 = df_l3_specific[available_cols_l3].rename(columns=cols_l3_show)
            
            st.dataframe(
                df_show_l3, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Total Downtime": st.column_config.NumberColumn(format="%d min"),
                    "Tech Downtime": st.column_config.NumberColumn(format="%d min"),
                    "Respon Time": st.column_config.NumberColumn(format="%d min"),
                }
            )
            st.divider()

        st.caption("📋 **Tabel Downtime Harian**")

        cols_to_show = {
            'Tanggal': 'Start Date', 
            'Stop Date': 'Stop Date',
            'Regu': 'Regu', 
            'Level 3': 'Level 3 Full', # Update: Rename to 'Level 3 Full' for clarity
            'Tindakan': 'Tindakan',
            'PIC': 'PIC',
            'Respon Time': 'Respon Time',
            'Technical Downtime': 'Tech Downtime', 
            'Total Downtime (Menit)': 'Total Downtime'
        }
        
        available_cols = [c for c in cols_to_show.keys() if c in df_detail.columns]
        df_show = df_detail[available_cols].rename(columns=cols_to_show)
        
        st.dataframe(
            df_show, 
            use_container_width=True, 
            hide_index=True, 
            height=500, 
            column_config={
                "Total Downtime": st.column_config.NumberColumn(format="%d min"),
                "Tech Downtime": st.column_config.NumberColumn(format="%d min"),
                "Respon Time": st.column_config.NumberColumn(format="%d min"),
            }
        )
