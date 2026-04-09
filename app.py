import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Inventory Management — Peta Stock",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0f172a; color: #f1f5f9; }

/* Header */
.dash-header {
    background: rgba(15,23,42,0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid #1e293b;
    padding: 16px 24px;
    border-radius: 12px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.dash-title { font-size: 1.25rem; font-weight: 700; color: #f1f5f9; }
.dash-sub { font-size: 0.75rem; color: #64748b; margin-top: 2px; }

/* Stat Cards */
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
}
.stat-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.stat-value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
.stat-sub { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
.stat-card.warning .stat-value { color: #f59e0b; }
.stat-card.danger .stat-value { color: #ef4444; }
.stat-card.success .stat-value { color: #22c55e; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
.badge-ok { background: #166534; color: #86efac; }
.badge-low { background: #713f12; color: #fcd34d; }
.badge-critical { background: #7f1d1d; color: #fca5a5; }
.badge-out { background: #1e1b4b; color: #a5b4fc; }

/* Alert card */
.alert-card {
    background: #1e293b;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.alert-card.warning { border-left-color: #f59e0b; }
.alert-title { font-weight: 600; font-size: 0.9rem; color: #f1f5f9; }
.alert-sub { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }

/* Warning banner */
.warn-banner {
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.85rem;
    color: #fcd34d;
    margin-bottom: 16px;
}

/* Buttons */
.stButton > button {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
.stButton > button:hover {
    background: #334155 !important;
    border-color: #475569 !important;
}

/* Selectbox & Input */
.stSelectbox > div > div, .stTextInput > div > div > input {
    background: #1e293b !important;
    border-color: #334155 !important;
    color: #f1f5f9 !important;
    border-radius: 8px !important;
}
.stSelectbox label, .stTextInput label { color: #94a3b8 !important; font-size: 0.8rem !important; }

div[data-testid="stDataFrame"] { border: 1px solid #334155; border-radius: 12px; overflow: hidden; }

.stTabs [data-baseweb="tab-list"] { background: #1e293b; border-radius: 8px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #94a3b8; border-radius: 6px; font-size: 0.85rem; }
.stTabs [aria-selected="true"] { background: #0f172a !important; color: #f1f5f9 !important; }

section[data-testid="stSidebar"] { background: #0f172a; border-right: 1px solid #1e293b; }

/* Last updated */
.last-updated { font-size: 0.75rem; color: #475569; text-align: right; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)


# ─── Zoho API ─────────────────────────────────────────────────────────────────

def get_access_token(client_id, client_secret, refresh_token):
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token"
    }
    try:
        r = requests.post(url, params=params, timeout=15)
        d = r.json()
        return d.get("access_token"), d.get("error")
    except Exception as e:
        return None, str(e)


def fetch_all_items(token, org_id):
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    all_items = []
    page = 1
    while True:
        r = requests.get(
            "https://www.zohoapis.com/inventory/v1/items",
            headers=headers,
            params={"organization_id": org_id, "page": page, "per_page": 200},
            timeout=20
        )
        d = r.json()
        if d.get("code") != 0:
            return None, d.get("message", "API Error")
        items = d.get("items", [])
        all_items.extend(items)
        if not d.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return all_items, None


def fetch_warehouse_details(token, org_id, item_ids):
    """Fetch warehouse breakdown in batches of 200. Returns (details_map, wh_names)."""
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    details_map = {}   # item_id -> {wh_name: {avail, committed}}
    wh_names = set()
    batch_size = 200   # increased batch size — fewer API calls
    for i in range(0, len(item_ids), batch_size):
        batch = item_ids[i:i + batch_size]
        try:
            r = requests.get(
                "https://www.zohoapis.com/inventory/v1/itemdetails",
                headers=headers,
                params={"organization_id": org_id, "item_ids": ",".join(batch)},
                timeout=30
            )
            d = r.json()
            if d.get("code") == 0:
                for item in d.get("items", []):
                    iid = str(item.get("item_id", ""))
                    wh_map = {}
                    for wh in item.get("warehouses", []):
                        name = wh.get("warehouse_name", "Unknown")
                        wh_map[name] = {
                            "avail":     wh.get("warehouse_actual_available_stock", 0) or 0,
                            "committed": wh.get("warehouse_actual_committed_stock", 0) or 0,
                        }
                        wh_names.add(name)
                    details_map[iid] = wh_map
        except Exception:
            pass
    return details_map, sorted(wh_names)


def build_dataframe(items, details_map=None, wh_names=None):
    """Build lean core dataframe — NO per-warehouse columns (those stay in details_map)."""
    if details_map is None:
        details_map = {}
    rows = []

    for item in items:
        item_id = str(item.get("item_id", ""))
        wh_map  = details_map.get(item_id, {})

        total     = item.get("actual_available_stock", 0) or 0
        # Sum actual_committed from warehouse data (more accurate than /items field)
        committed = sum(v["committed"] for v in wh_map.values()) if wh_map else (item.get("committed_stock", 0) or 0)
        reorder   = safe_int(item.get("reorder_level", 0))

        if total == 0:
            status = "out"
        elif reorder and total <= reorder:
            status = "critical"
        elif reorder and total <= reorder * 1.5:
            status = "low"
        else:
            status = "ok"

        rows.append({
            "item_id":        item_id,
            "SKU":            item.get("sku", "—") or "—",
            "Name":           item.get("name", ""),
            "Brand":          item.get("brand", "—") or "—",
            "Category":       item.get("category_name", "—") or "—",
            "Total Stock":    total,
            "Committed":      committed,
            "Reorder Point":  reorder,
            "Unit":           item.get("unit", ""),
            "Status":         status,
        })

    df = pd.DataFrame(rows)
    return df



def safe_int(val, default=0):
    try:
        v = float(val)
        return int(v) if v == v else default
    except (TypeError, ValueError):
        return default


def status_badge(status):
    labels = {"ok": ("ok", "In Stock"), "low": ("low", "Low"), "critical": ("critical", "Critical"), "out": ("out", "Out")}
    cls, text = labels.get(status, ("ok", status))
    return f'<span class="badge badge-{cls}">{text}</span>'


@st.cache_data(ttl=1800, show_spinner=False)  # cache 30 minutes
def load_inventory(client_id, client_secret, refresh_token, org_id):
    """Full fetch: token → items → warehouse details → dataframe. Cached 30 min."""
    token, err = get_access_token(client_id, client_secret, refresh_token)
    if err or not token:
        return None, {}, [], f"Token error: {err}"

    items, err = fetch_all_items(token, org_id)
    if err:
        return None, {}, [], f"API error: {err}"

    item_ids = [str(i.get("item_id", "")) for i in items if i.get("item_id")]
    details_map, wh_names = fetch_warehouse_details(token, org_id, item_ids)
    df = build_dataframe(items, details_map, wh_names)
    return df, details_map, wh_names, None


# ─── Session State ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:           st.session_state.df = None
if "details_map" not in st.session_state:  st.session_state.details_map = {}
if "warehouses" not in st.session_state:   st.session_state.warehouses = []
if "last_updated" not in st.session_state: st.session_state.last_updated = None
if "error" not in st.session_state:        st.session_state.error = False


# ─── Credentials from Streamlit Secrets ──────────────────────────────────────
try:
    default_client_id     = st.secrets["CLIENT_ID"]
    default_client_secret = st.secrets["CLIENT_SECRET"]
    default_refresh_token = st.secrets["REFRESH_TOKEN"]
    default_org_id        = st.secrets["ORG_ID"]
    secrets_loaded = True
except:
    default_client_id = default_client_secret = default_refresh_token = ""
    default_org_id = "771975372"
    secrets_loaded = False


def apply_loaded(df, details_map, wh_names):
    st.session_state.df = df
    st.session_state.details_map = details_map
    st.session_state.warehouses = wh_names
    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.error = False


# ─── Auto-fetch when secrets are present and no data yet ─────────────────────
if secrets_loaded and st.session_state.df is None:
    with st.spinner("⏳ Loading inventory data..."):
        df_l, dm_l, wh_l, err = load_inventory(
            default_client_id, default_client_secret,
            default_refresh_token, default_org_id
        )
    if err:
        st.session_state.error = True
    else:
        apply_loaded(df_l, dm_l, wh_l)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if secrets_loaded:
        st.success("✅ Credentials loaded from Secrets")
        client_id     = default_client_id
        client_secret = default_client_secret
        refresh_token = default_refresh_token
        org_id        = default_org_id
    else:
        st.info("Enter your Zoho credentials")
        client_id     = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        refresh_token = st.text_input("Refresh Token", type="password")
        org_id        = st.text_input("Organization ID", value="771975372")

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        load_inventory.clear()
        with st.spinner("Refreshing..."):
            df_l, dm_l, wh_l, err = load_inventory(
                client_id, client_secret, refresh_token, org_id
            )
        if err:
            st.error(err)
            st.session_state.error = True
        else:
            apply_loaded(df_l, dm_l, wh_l)
            st.success(f"✅ {len(df_l):,} items | {len(wh_l)} warehouses")

    if st.session_state.last_updated:
        st.markdown(f"<div style='font-size:0.75rem; color:#475569; margin-top:8px;'>🕐 Next auto-refresh in ~30 min</div>", unsafe_allow_html=True)


# ─── Header ───────────────────────────────────────────────────────────────────
df_all = st.session_state.df

critical_count = 0
if df_all is not None:
    critical_count = len(df_all[df_all["Status"].isin(["critical", "out"])])

st.markdown(f"""
<div class="dash-header">
    <div style="display:flex; align-items:center; gap:12px;">
        <div style="background:#1e3a5f; padding:8px; border-radius:10px; font-size:1.4rem;">📦</div>
        <div>
            <div class="dash-title">Inventory Management</div>
            <div class="dash-sub">Peta Stock — Dashboard</div>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:8px;">
        {"<span style='background:#7f1d1d; color:#fca5a5; padding:6px 14px; border-radius:8px; font-size:0.8rem; font-weight:600;'>🔔 " + str(critical_count) + " Critical</span>" if critical_count > 0 else ""}
        {"<span style='color:#475569; font-size:0.75rem;'>Last sync: " + st.session_state.last_updated + "</span>" if st.session_state.last_updated else ""}
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Error Banner ─────────────────────────────────────────────────────────────
if st.session_state.error:
    st.markdown('<div class="warn-banner">⚠️ Could not connect to Zoho API — please check your credentials and try again.</div>', unsafe_allow_html=True)

# ─── Empty State ──────────────────────────────────────────────────────────────
if df_all is None:
    st.markdown("""
    <div style="text-align:center; padding:80px 20px; color:#475569;">
        <div style="font-size:4rem; margin-bottom:16px;">📦</div>
        <div style="font-size:1.4rem; font-weight:600; color:#64748b; margin-bottom:8px;">No Data Loaded</div>
        <div style="font-size:0.9rem;">Open the sidebar (←) and click <strong style="color:#94a3b8;">Fetch / Refresh Data</strong></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ─── Filters ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1.5])
with col1:
    search = st.text_input("", placeholder="🔍 Search by name or SKU...", label_visibility="collapsed")
with col2:
    wh_options = ["All Warehouses"] + st.session_state.warehouses
    selected_wh = st.selectbox("", wh_options, label_visibility="collapsed")
with col3:
    brands = ["All Brands"] + sorted(df_all["Brand"].dropna().unique().tolist())
    selected_brand = st.selectbox("", brands, label_visibility="collapsed")
with col4:
    cats = ["All Categories"] + sorted(df_all["Category"].dropna().unique().tolist())
    selected_cat = st.selectbox("", cats, label_visibility="collapsed")
with col5:
    export_btn = st.button("⬇️ Export", use_container_width=True)


# ─── Filter Logic ─────────────────────────────────────────────────────────────
df = df_all.copy()
if search:
    df = df[df["Name"].str.contains(search, case=False, na=False) |
            df["SKU"].astype(str).str.contains(search, case=False, na=False)]
if selected_brand != "All Brands":
    df = df[df["Brand"] == selected_brand]
if selected_cat != "All Categories":
    df = df[df["Category"] == selected_cat]

# Filter by warehouse: keep only items that have stock in selected warehouse
details_map = st.session_state.details_map
if selected_wh != "All Warehouses":
    def has_wh_stock(item_id):
        return details_map.get(item_id, {}).get(selected_wh, {}).get("avail", 0) > 0
    df = df[df["item_id"].apply(has_wh_stock)]


# ─── Stats Cards (reactive to filters) ────────────────────────────────────────
total_items   = len(df)
total_brands  = df["Brand"].nunique()
low_stock     = len(df[df["Status"] == "low"])
critical      = len(df[df["Status"].isin(["critical", "out"])])
out_of_stock  = len(df[df["Status"] == "out"])
total_stock   = safe_int(df["Total Stock"].sum())
total_commit  = safe_int(df["Committed"].sum())

filter_label = ""
if selected_wh != "All Warehouses":       filter_label = f" · {selected_wh}"
elif selected_brand != "All Brands":      filter_label = f" · {selected_brand}"
elif selected_cat != "All Categories":    filter_label = f" · {selected_cat}"
elif search:                              filter_label = f" · \"{search}\""

st.markdown(f"""
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-label">Items{filter_label}</div>
        <div class="stat-value">{total_items:,}</div>
        <div class="stat-sub">{total_brands} brands · {len(df_all):,} total</div>
    </div>
    <div class="stat-card success">
        <div class="stat-label">Available Units</div>
        <div class="stat-value">{total_stock:,}</div>
        <div class="stat-sub">actual available stock</div>
    </div>
    <div class="stat-card warning">
        <div class="stat-label">Committed</div>
        <div class="stat-value">{total_commit:,}</div>
        <div class="stat-sub">reserved / pending orders</div>
    </div>
    <div class="stat-card danger">
        <div class="stat-label">Critical / Out</div>
        <div class="stat-value">{critical}</div>
        <div class="stat-sub">{out_of_stock} completely out</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Warehouse Summary Cards (from details_map, reactive to filters) ──────────
if st.session_state.warehouses:
    show_warehouses = [selected_wh] if selected_wh != "All Warehouses" else st.session_state.warehouses
    filtered_ids = set(df["item_id"].tolist())
    wh_cards_html = "<div style='display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px;'>"
    for wh in show_warehouses:
        avail_total = 0
        comm_total  = 0
        for iid in filtered_ids:
            wh_data = details_map.get(iid, {}).get(wh, {})
            avail_total += wh_data.get("avail", 0)
            comm_total  += wh_data.get("committed", 0)
        wh_cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:14px 18px;min-width:160px;flex:1;">
            <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">🏭 {wh}</div>
            <div style="display:flex;gap:16px;align-items:flex-end;">
                <div>
                    <div style="font-size:1.4rem;font-weight:700;color:#22c55e;">{safe_int(avail_total):,}</div>
                    <div style="font-size:0.65rem;color:#64748b;">Available</div>
                </div>
                <div>
                    <div style="font-size:1.4rem;font-weight:700;color:#f59e0b;">{safe_int(comm_total):,}</div>
                    <div style="font-size:0.65rem;color:#64748b;">Committed</div>
                </div>
            </div>
        </div>"""
    wh_cards_html += "</div>"
    st.markdown(wh_cards_html, unsafe_allow_html=True)


# ─── Tabs ─────────────────────────────────────────────────────────────────────
alerts_label = f"🚨 Alerts ({critical})" if critical > 0 else "✅ Alerts"
tab1, tab2, tab3 = st.tabs(["📋 Inventory Table", "📊 Stock Chart", alerts_label])


# ── Tab 1: Inventory Table ────────────────────────────────────────────────────
with tab1:
    st.markdown(f"<div style='color:#64748b;font-size:0.8rem;margin-bottom:8px;'>Showing {len(df):,} of {len(df_all):,} items</div>", unsafe_allow_html=True)

    # Base columns always shown
    base_cols = ["SKU", "Name", "Brand", "Category", "Total Stock", "Committed", "Reorder Point", "Status"]

    # If a specific warehouse is selected, add its Available + Committed inline
    if selected_wh != "All Warehouses":
        # Build a display df with the warehouse columns added on the fly
        show_df = df[base_cols].copy()
        show_df.insert(4, f"{selected_wh} Avail",
            df["item_id"].map(lambda i: safe_int(details_map.get(i, {}).get(selected_wh, {}).get("avail", 0))))
        show_df.insert(5, f"{selected_wh} Comm",
            df["item_id"].map(lambda i: safe_int(details_map.get(i, {}).get(selected_wh, {}).get("committed", 0))))
    else:
        show_df = df[base_cols].copy()

    def highlight_row(row):
        s = row.get("Status", "")
        if s == "out":      return ["background-color:rgba(127,29,29,0.3)"]  * len(row)
        if s == "critical": return ["background-color:rgba(127,29,29,0.15)"] * len(row)
        if s == "low":      return ["background-color:rgba(113,63,18,0.2)"]  * len(row)
        return [""] * len(row)

    styled = show_df.style.apply(highlight_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=520)

    if export_btn:
        csv = show_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", data=csv,
            file_name=f"inventory_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")


# ── Tab 2: Stock Chart ────────────────────────────────────────────────────────
with tab2:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Stock Status Distribution")
        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        status_map = {"ok": "In Stock", "low": "Low", "critical": "Critical", "out": "Out of Stock"}
        status_counts["Status"] = status_counts["Status"].map(status_map)
        st.bar_chart(status_counts.set_index("Status"), use_container_width=True, color="#3b82f6")

    with col_b:
        st.markdown("#### Top 15 Items by Stock")
        top_items = df.nlargest(15, "Total Stock")[["Name", "Total Stock"]].copy()
        top_items["Name"] = top_items["Name"].str[:30]
        st.bar_chart(top_items.set_index("Name"), use_container_width=True, color="#22c55e")

    # Warehouse breakdown from details_map
    if st.session_state.warehouses:
        st.markdown("#### Available Stock by Warehouse")
        filtered_ids = set(df["item_id"].tolist())
        wh_rows = []
        for wh in st.session_state.warehouses:
            avail = sum(details_map.get(iid, {}).get(wh, {}).get("avail", 0) for iid in filtered_ids)
            comm  = sum(details_map.get(iid, {}).get(wh, {}).get("committed", 0) for iid in filtered_ids)
            wh_rows.append({"Warehouse": wh, "Available": safe_int(avail), "Committed": safe_int(comm)})
        wh_df = pd.DataFrame(wh_rows).set_index("Warehouse")
        st.bar_chart(wh_df, use_container_width=True)


# ── Tab 3: Alerts ─────────────────────────────────────────────────────────────
with tab3:
    out_items  = df[df["Status"] == "out"]
    crit_items = df[df["Status"] == "critical"]
    low_items  = df[df["Status"] == "low"]

    if len(out_items) == 0 and len(crit_items) == 0 and len(low_items) == 0:
        st.markdown("<div style='text-align:center;padding:40px;color:#64748b;'>✅ All items are well-stocked!</div>", unsafe_allow_html=True)
    else:
        def wh_line(item_id):
            wh_map = details_map.get(item_id, {})
            if not wh_map:
                return ""
            parts = [
                f"{wh}: <b>{safe_int(v['avail'])}</b> avail / <b>{safe_int(v['committed'])}</b> comm"
                for wh, v in wh_map.items() if v.get("avail", 0) > 0 or v.get("committed", 0) > 0
            ]
            return " &nbsp;|&nbsp; ".join(parts)

        if len(out_items) > 0:
            st.markdown(f"##### 🔴 Out of Stock ({len(out_items)} items)")
            for _, row in out_items.iterrows():
                whl = wh_line(row["item_id"])
                st.markdown(f"""
                <div class="alert-card">
                    <div class="alert-title">{row['Name']}</div>
                    <div class="alert-sub">SKU: {row['SKU']} · Brand: {row['Brand']} · Reorder: {safe_int(row['Reorder Point'])}</div>
                    {f'<div class="alert-sub" style="margin-top:4px;font-size:0.75rem;">{whl}</div>' if whl else ''}
                </div>""", unsafe_allow_html=True)

        if len(crit_items) > 0:
            st.markdown(f"##### 🟠 Critical Stock ({len(crit_items)} items)")
            for _, row in crit_items.iterrows():
                whl = wh_line(row["item_id"])
                st.markdown(f"""
                <div class="alert-card warning">
                    <div class="alert-title">{row['Name']}</div>
                    <div class="alert-sub">SKU: {row['SKU']} · Stock: {safe_int(row['Total Stock'])} · Committed: {safe_int(row['Committed'])} · Reorder: {safe_int(row['Reorder Point'])}</div>
                    {f'<div class="alert-sub" style="margin-top:4px;font-size:0.75rem;">{whl}</div>' if whl else ''}
                </div>""", unsafe_allow_html=True)

        if len(low_items) > 0:
            st.markdown(f"##### 🟡 Low Stock ({len(low_items)} items)")
            for _, row in low_items.iterrows():
                whl = wh_line(row["item_id"])
                st.markdown(f"""
                <div class="alert-card warning">
                    <div class="alert-title">{row['Name']}</div>
                    <div class="alert-sub">SKU: {row['SKU']} · Stock: {safe_int(row['Total Stock'])} · Committed: {safe_int(row['Committed'])} · Reorder: {safe_int(row['Reorder Point'])}</div>
                    {f'<div class="alert-sub" style="margin-top:4px;font-size:0.75rem;">{whl}</div>' if whl else ''}
                </div>""", unsafe_allow_html=True)
