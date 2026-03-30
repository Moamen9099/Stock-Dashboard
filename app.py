import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Premium Line - Stock Dashboard",
    page_icon="📦",
    layout="wide"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
}

.stApp {
    background: #0d0d0d;
    color: #f0ede6;
}

.metric-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}

.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #c8ff00;
}

.metric-label {
    font-size: 0.8rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 4px;
}

.header-bar {
    background: linear-gradient(135deg, #1a1a1a 0%, #111 100%);
    border-bottom: 1px solid #2a2a2a;
    padding: 16px 24px;
    margin-bottom: 24px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.brand-tag {
    background: #c8ff00;
    color: #0d0d0d;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'Syne', sans-serif;
    letter-spacing: 1px;
}

.low-stock {
    color: #ff4d4d !important;
    font-weight: 600;
}

.ok-stock {
    color: #c8ff00 !important;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    overflow: hidden;
}

.stButton > button {
    background: #c8ff00;
    color: #0d0d0d;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    letter-spacing: 0.5px;
}

.stButton > button:hover {
    background: #d4ff33;
    color: #0d0d0d;
}

.stSelectbox label, .stTextInput label, .stMultiSelect label {
    color: #888 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.stAlert {
    border-radius: 10px;
}

section[data-testid="stSidebar"] {
    background: #111;
    border-right: 1px solid #2a2a2a;
}

section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ─── 1. Initialize Session State (MODIFIED: Moved here to avoid AttributeError) ───
if "items_df" not in st.session_state:
    st.session_state.items_df = None
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None


# ─── Zoho API Functions ───────────────────────────────────────────────────────

def get_access_token(client_id, client_secret, refresh_token):
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token"
    }
    try:
        response = requests.post(url, params=params, timeout=15)
        data = response.json()
        if "access_token" in data:
            return data["access_token"], None
        else:
            return None, data.get("error", "Unknown error getting token")
    except Exception as e:
        return None, str(e)


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
            if data.get("code") != 0:
                return None, data.get("message", "API Error")
            items = data.get("items", [])
            all_items.extend(items)
            page_context = data.get("page_context", {})
            if not page_context.get("has_more_page", False):
                break
            page += 1
        except Exception as e:
            return None, str(e)
    return all_items, None


def build_dataframe(items):
    rows = []
    for item in items:
        row = {
            "SKU": item.get("sku", ""),
            "Item Name": item.get("name", ""),
            "Brand": item.get("brand", "") or "—",
            "Category": item.get("category_name", "") or "—",
            "Status": item.get("status", ""),
            "Total Stock": item.get("actual_available_stock", 0) or 0,
            "Available Stock": item.get("available_stock", 0) or 0,
            "Reorder Point": item.get("reorder_level", 0) or 0,
            "Unit": item.get("unit", ""),
            "Rate": item.get("rate", 0) or 0,
            "Item ID": item.get("item_id", ""),
        }
        warehouse_stocks = item.get("warehouse_details", [])
        for wh in warehouse_stocks:
            wh_name = wh.get("warehouse_name", "Unknown")
            wh_stock = wh.get("warehouse_actual_available_stock", 0) or 0
            row[f"📦 {wh_name}"] = wh_stock
        rows.append(row)
    return pd.DataFrame(rows)


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.markdown("---")

    client_id = st.text_input("Client ID", type="password", placeholder="1000.XXXXXX")
    client_secret = st.text_input("Client Secret", type="password", placeholder="your secret")
    refresh_token = st.text_input("Refresh Token", type="password", placeholder="1000.XXXXXX")
    org_id = st.text_input("Organization ID", value="771975372")

    st.markdown("---")
    fetch_btn = st.button("🔄 Fetch Data from Zoho")

    st.markdown("---")
    st.markdown("**Filters**")
    show_low_stock = st.checkbox("⚠️ Low Stock Only", value=False)
    search_query = st.text_input("🔍 Search by name or SKU", placeholder="Type to search...")

    # Now this won't crash because items_df is initialized at the top
    if st.session_state.items_df is not None:
        df_all = st.session_state.items_df
        brands = ["All Brands"] + sorted(df_all["Brand"].dropna().unique().tolist())
        selected_brand = st.selectbox("🏷️ Brand", brands)
        categories = ["All Categories"] + sorted(df_all["Category"].dropna().unique().tolist())
        selected_category = st.selectbox("📂 Category", categories)
    else:
        selected_brand = "All Brands"
        selected_category = "All Categories"

    st.markdown("---")
    st.markdown("<div style='color:#555; font-size:0.75rem;'>Premium Line Dashboard<br>Powered by Zoho Inventory API</div>", unsafe_allow_html=True)


# ─── Main Area ────────────────────────────────────────────────────────────────

st.markdown("""
<div class="header-bar">
    <div>
        <span style="font-family:'Syne',sans-serif; font-size:1.5rem; font-weight:800; color:#f0ede6;">
            📦 Stock Dashboard
        </span>
        <span style="color:#555; font-size:0.85rem; margin-left:12px;">Premium Line</span>
    </div>
    <span class="brand-tag">LIVE DATA</span>
</div>
""", unsafe_allow_html=True)


# Fetch data logic
if fetch_btn:
    if not all([client_id, client_secret, refresh_token, org_id]):
        st.error("⚠️ Please fill in all credentials in the sidebar first.")
    else:
        with st.spinner("🔐 Getting access token..."):
            token, err = get_access_token(client_id, client_secret, refresh_token)
        if err:
            st.error(f"❌ Token Error: {err}")
        else:
            with st.spinner("📦 Fetching items from Zoho Inventory..."):
                items, err = get_all_items(token, org_id)
            if err:
                st.error(f"❌ API Error: {err}")
            else:
                df = build_dataframe(items)
                st.session_state.items_df = df
                st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun() # Refresh to update filters and metrics


# Display data
if st.session_state.items_df is not None:
    df = st.session_state.items_df.copy()

    st.markdown(f"<div style='color:#555; font-size:0.8rem; margin-bottom:16px;'>Last updated: {st.session_state.last_updated}</div>", unsafe_allow_html=True)

    # ── Metrics ──
    col1, col2, col3, col4 = st.columns(4)
    total_items = len(df)
    total_brands = df["Brand"].nunique()
    low_stock_items = len(df[df["Total Stock"] <= df["Reorder Point"]])
    out_of_stock = len(df[df["Total Stock"] == 0])

    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_items}</div><div class="metric-label">Total Items</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_brands}</div><div class="metric-label">Brands</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#ff4d4d">{low_stock_items}</div><div class="metric-label">Low Stock</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#ff4d4d">{out_of_stock}</div><div class="metric-label">Out of Stock</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Applying Filters ──
    if search_query:
        mask = (df["Item Name"].str.contains(search_query, case=False, na=False) | 
                df["SKU"].astype(str).str.contains(search_query, case=False, na=False))
        df = df[mask]
    if selected_brand != "All Brands":
        df = df[df["Brand"] == selected_brand]
    if selected_category != "All Categories":
        df = df[df["Category"] == selected_category]
    if show_low_stock:
        df = df[df["Total Stock"] <= df["Reorder Point"]]

    # ── Table ──
    st.markdown(f"### Showing {len(df)} items")

    def highlight_low_stock(row):
        if row["Total Stock"] == 0: return ["background-color: #2a0000"] * len(row)
        elif row["Total Stock"] <= row["Reorder Point"]: return ["background-color: #1a1500"] * len(row)
        return [""] * len(row)

    display_cols = ["SKU", "Item Name", "Brand", "Category", "Total Stock", "Reorder Point", "Available Stock", "Unit"]
    warehouse_cols = [c for c in df.columns if c.startswith("📦")]
    display_cols = [c for c in (display_cols + warehouse_cols) if c in df.columns]

    st.dataframe(df[display_cols].style.apply(highlight_low_stock, axis=1), use_container_width=True, height=500)

    # ── Export ──
    csv = df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(label="⬇️ Export to CSV", data=csv, file_name=f"stock_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

else:
    st.markdown("""
    <div style="text-align: center; padding: 80px 20px; color: #444;">
        <div style="font-size: 4rem; margin-bottom: 16px;">📦</div>
        <div style="font-family: 'Syne', sans-serif; font-size: 1.5rem; color: #666;">No Data Loaded Yet</div>
        <div style="font-size: 0.9rem; color: #444;">Fill in credentials and click <strong style="color:#c8ff00;">Fetch Data</strong></div>
    </div>
    """, unsafe_allow_html=True)
