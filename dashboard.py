import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Analisis Downtime Pro", layout="wide", page_icon="🏭")

# CSS Kustom
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    h1 { color: #2c3e50; }
    .stDataFrame { border: 1px solid #ddd; background-color: white; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #e74c3c; }
    
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
# Kita gunakan ini untuk mengatur navigasi antar halaman
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'landing'
if 'df_main' not in st.session_state:
    st.session_state.df_main = None

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
    
    # Layout Tengah
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏭 Dashboard PT Ultra Prima Abadi - Formula")
        st.markdown("### Selamat Datang")
        st.markdown("Silakan pilih sumber data untuk memulai analisis downtime.")
        st.markdown("---")
        
        # Pilihan Input
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

        # Tombol Proses
        if final_file_path:
            if st.button("🚀 Proses Data & Masuk Dashboard", type="primary", use_container_width=True):
                with st.spinner("Sedang memproses data..."):
                    df_loaded = load_data(final_file_path)
                    if not df_loaded.empty:
                        # Simpan ke session state
                        st.session_state.df_main = df_loaded
                        st.session_state.current_page = 'dashboard'
                        st.rerun() # Refresh untuk pindah halaman
                    else:
                        st.error("Data kosong atau gagal dibaca.")

# ==========================================
# PAGE 2: DASHBOARD (VISUALISASI)
# ==========================================
elif st.session_state.current_page == 'dashboard':
    
    # --- HEADER ---
    c1, c2 = st.columns([6, 1])
    with c1:
        st.title("🏭 Dashboard PT Ultra Prima Abadi - Formula")
    with c2:
        # Tombol Kembali / Ganti Data
        if st.button("🔄 Ganti Data"):
            st.session_state.df_main = None
            st.session_state.current_page = 'landing'
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")
    
    # Ambil data dari session state
    df = st.session_state.df_main
    
    if df is not None and not df.empty:
        # --- SIDEBAR FILTER ---
        st.sidebar.header("Filter Dashboard")
        area_list = sorted(list(df['Area'].unique()))
        selected_area = st.sidebar.multiselect("Pilih Area:", area_list, default=area_list)
        
        # Filter Data
        if selected_area:
            df_main = df[df['Area'].isin(selected_area)]
            
            # --- TABS ---
            tab1, tab2 = st.tabs(["📊 Dashboard", "📋 Data Detail"])

            # ==========================
            # TAB 1: VISUALISASI
            # ==========================
            with tab1:
                # A. METRICS
                df_agg = df_main.groupby(['Machine Type'])['Total Downtime (Menit)'].sum().reset_index()
                df_agg = df_agg.sort_values(by='Total Downtime (Menit)', ascending=False)
                
                total_dt = df_main['Total Downtime (Menit)'].sum()
                top_type = df_agg.iloc[0]['Machine Type'] if not df_agg.empty else "-"
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total Downtime Keseluruhan", f"{total_dt:,.0f} Menit")
                col_m2.metric("Tipe Mesin Paling Kritis", top_type)
                col_m3.metric("Jumlah Tipe Mesin", len(df_agg))
                
                st.markdown("---")

                # B. CHARTS
                col_bar, col_pie = st.columns([2, 1])
                selected_machine_type = None

                with col_bar:
                    st.subheader("📊 Total Downtime per Tipe Mesin")
                    st.caption("Klik batang untuk melihat detail history kerusakan.")
                    
                    if not df_agg.empty:
                        full_height = max(400, len(df_agg) * 30)
                        with st.container(height=500):
                            fig_bar = px.bar(
                                df_agg, 
                                x='Total Downtime (Menit)', 
                                y='Machine Type', 
                                orientation='h', 
                                text_auto='.0f'
                            )
                            fig_bar.update_layout(
                                yaxis={'categoryorder':'total ascending'}, 
                                height=full_height, 
                                margin=dict(l=0, r=0, t=10, b=0),
                                clickmode='event+select'
                            )
                            selection = st.plotly_chart(fig_bar, use_container_width=True, on_select="rerun", selection_mode="points")
                            
                            if selection and len(selection.selection['points']) > 0:
                                selected_machine_type = selection.selection['points'][0]['y']

                with col_pie:
                    st.subheader("🕒 Total Downtime per Shift")
                    if 'Shift' in df_main.columns:
                        df_shift = df_main.groupby('Shift')['Total Downtime (Menit)'].sum().reset_index()
                        fig_pie = px.pie(df_shift, values='Total Downtime (Menit)', names='Shift', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                        st.plotly_chart(fig_pie, use_container_width=True)

                # --- DRILL-DOWN ---
                if selected_machine_type:
                    st.divider()
                    st.markdown(f"### 🔎 Detail Kerusakan: **{selected_machine_type}**")
                    
                    df_detail = df_main[df_main['Machine Type'] == selected_machine_type].copy()
                    df_detail = df_detail.sort_values(by='Total Downtime (Menit)', ascending=False)
                    
                    cols_to_show = {
                        'Tanggal': 'Start Date', 'Stop Date': 'Stop Date', 'Jam': 'Start Downtime',
                        'Start Repair': 'Start Repair', 'Stop Repair': 'Stop Repair',
                        'Start Production': 'Start Production', 'Level 3': 'Level 3',
                        'Tindakan': 'Tindakan', 'Respon Time': 'Respon Time',
                        'Technical Downtime': 'Tech Downtime', 'Total Downtime (Menit)': 'Total Downtime'
                    }
                    available_cols = [c for c in cols_to_show.keys() if c in df_detail.columns]
                    df_show = df_detail[available_cols].rename(columns=cols_to_show)
                    
                    st.dataframe(df_show, use_container_width=True, hide_index=True, column_config={"Total Downtime": st.column_config.NumberColumn(format="%d min")})
                else:
                    st.info("👆 Klik batang pada grafik 'Total Downtime per Tipe Mesin' di atas untuk melihat rincian kerusakan.")

                # C. HEATMAP
                st.markdown("---")
                st.subheader("🔥 Heatmap: Tipe Mesin vs Shift")
                if 'Shift' in df_main.columns:
                    df_pivot = df_main.pivot_table(index='Machine Type', columns='Shift', values='Total Downtime (Menit)', aggfunc='sum', fill_value=0)
                    df_pivot['Total'] = df_pivot.sum(axis=1)
                    df_pivot = df_pivot.sort_values('Total', ascending=False).drop(columns='Total').head(20)
                    fig_heat = px.imshow(df_pivot, text_auto=True, aspect="auto", color_continuous_scale="Reds", title="Sebaran Downtime per Shift")
                    st.plotly_chart(fig_heat, use_container_width=True)

            # ==========================
            # TAB 2: DATA DETAIL
            # ==========================
            with tab2:
                df_sorted = df_main.sort_values(by='Total Downtime (Menit)', ascending=False).reset_index(drop=True)
                st.dataframe(df_sorted, use_container_width=True, height=800)
                csv = df_sorted.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full CSV", csv, "analisis_lkm.csv", "text/csv")
        
        else:
            st.info("Pilih Area di sidebar untuk menampilkan data.")