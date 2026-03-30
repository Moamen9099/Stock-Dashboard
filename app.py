import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io  # لإدارة ملفات الإكسيل في الذاكرة

st.set_page_config(
    page_title="Stock Dashboard",
    page_icon="📦",
    layout="wide"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
.stApp { background: #0d0d0d; color: #f0ede6; }
.metric-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; text-align: center; }
.metric-value { font-family: 'Syne', sans-serif; font-size: 2.2rem; font-weight: 800; color: #c8ff00; }
.metric-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 2px; margin-top: 4px; }
.header-bar { background: linear-gradient(135deg, #1a1a1a 0%, #111 100%); border-bottom: 1px solid #2a2a2a; padding: 16px 24px; margin-bottom: 24px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; }
.brand-tag { background: #c8ff00; color: #0d0d0d; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; font-family: 'Syne', sans-serif; letter-spacing: 1px; }
.stButton > button { background: #c8ff00; color: #0d0d0d; font-family: 'Syne', sans-serif; font-weight: 700; border: none; border-radius: 8px; }
section[data-testid="stSidebar"] { background: #111; border-right: 1px solid #2a2a2a; }
</style>
""", unsafe_allow_html=True)

# ─── 1. Initialize Session State ───
if "items_df" not in st.session_state:
    st.session_state.items_df = None
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

# ─── Zoho API Functions ───────────────────────────────────────────────────────
def get_access_token(client_id, client_secret, refresh_token):
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token"}
    try:
        response = requests.post(url, params=params, timeout=15)
        data = response.json()
        return data.get("access_token"), None if "access_token" in data else data.get("error")
    except Exception as e: return None, str(e)

def get_all_items(access_token, org_id):
    all_items = []
    page = 1
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    while True:
        url = f"https://www.zohoapis.com/inventory/v1/items"
        params = {"organization_id": org_id, "page": page, "per_page": 200}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            data = response.json()
            if data.get("code") != 0: return None, data.get("message")
            items = data.get("items", [])
            all_items.extend(items)
            if not data.get("page_context", {}).get("has_more_page", False): break
            page += 1
        except Exception as e: return None, str(e)
    return all_items, None

def build_dataframe(items):
    rows = []
    for item in items:
        row = {
            "SKU": item.get("sku", ""),
            "Item Name": item.get("name", ""),
            "Brand": item.get("brand", "") or "—",
            "Category": item.get("category_name", "") or "—",
            "Total Stock": item.get("actual_available_stock", 0) or 0,
            "Reorder Point": item.get("reorder_level", 0) or 0,
            "Available Stock": item.get("available_stock", 0) or 0,
            "Unit": item.get("unit", ""),
        }
        for wh in item.get("warehouse_details", []):
            row[f"📦 {wh.get('warehouse_name', 'Unknown')}"] = wh.get("warehouse_actual_available_stock", 0) or 0
        rows.append(row)
    return pd.DataFrame(rows)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Client Secret", type="password")
    refresh_token = st.text_input("Refresh Token", type="password")
    org_id = st.text_input("Organization ID", value="771975372")
    
    fetch_btn = st.button("🔄 Fetch Data from Zoho")
    st.markdown("---")
    st.markdown("**Filters**")
    show_low_stock = st.checkbox("⚠️ Low Stock Only", value=False)
    search_query = st.text_input("🔍 Search SKU/Name")

    if st.session_state.items_df is not None:
        df_all = st.session_state.items_df
        # Warehouse Filter
        wh_cols = [c for c in df_all.columns if c.startswith("📦")]
        selected_wh = st.selectbox("🏬 Warehouse", ["All Warehouses"] + wh_cols)
        # Brand & Category
        brands = ["All Brands"] + sorted(df_all["Brand"].unique().tolist())
        selected_brand = st.selectbox("🏷️ Brand", brands)
        categories = ["All Categories"] + sorted(df_all["Category"].unique().tolist())
        selected_category = st.selectbox("📂 Category", categories)
    else:
        selected_wh = "All Warehouses"
        selected_brand = "All Brands"
        selected_category = "All Categories"

# ─── Main Area ────────────────────────────────────────────────────────────────
st.markdown('<div class="header-bar"><div><span style="font-size:1.5rem; font-weight:800; color:#f0ede6;">📦 Stock Dashboard</span></div><span class="brand-tag">LIVE DATA</span></div>', unsafe_allow_html=True)

if fetch_btn:
    if not all([client_id, client_secret, refresh_token, org_id]):
        st.error("⚠️ Fill all credentials!")
    else:
        with st.spinner("Fetching..."):
            token, err = get_access_token(client_id, client_secret, refresh_token)
            if not err:
                items, err = get_all_items(token, org_id)
                if not err:
                    st.session_state.items_df = build_dataframe(items)
                    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.rerun()
            if err: st.error(f"❌ Error: {err}")

if st.session_state.items_df is not None:
    df = st.session_state.items_df.copy()

    # Apply Filters
    if search_query:
        df = df[df["Item Name"].str.contains(search_query, case=False, na=False) | df["SKU"].astype(str).str.contains(search_query, case=False, na=False)]
    if selected_brand != "All Brands": df = df[df["Brand"] == selected_brand]
    if selected_category != "All Categories": df = df[df["Category"] == selected_category]
    if show_low_stock: df = df[df["Total Stock"] <= df["Reorder Point"]]
    # Warehouse Filter Logic (if specific WH selected, maybe you want to see items that have stock in it)
    if selected_wh != "All Warehouses":
        df = df[df[selected_wh] > 0]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Items", len(df))
    col2.metric("Low Stock", len(df[df["Total Stock"] <= df["Reorder Point"]]))
    
    # Table Display
    def highlight_low(row):
        return ['background-color: #2a0000' if row["Total Stock"] <= row["Reorder Point"] else '' for _ in row]
    
    st.dataframe(df.style.apply(highlight_low, axis=1), use_container_width=True, height=500)

    # ── Excel Export Logic ──
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock_Report')
        # التنسيق التلقائي لعرض الأعمدة في الإكسيل
        workbook = writer.book
        worksheet = writer.sheets['Stock_Report']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)
    
    st.download_button(
        label="📥 Export to Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"Stock_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Please fetch data from the sidebar.")
