# ============================================================================= 
# SLT1: Imports and Page Setup
# Imports the libraries and sets the page title, icon, and wide layout.
# =============================================================================
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title = "Delivery & Returns Analytics", page_icon = "📦", layout = "wide")


# ============================================================================= 
# SLT2: Theme Placeholders
# Defines the THEME color placeholders, the card and header CSS, and the style_chart() helper.
# =============================================================================
THEME = {
    "accent": "#6065C7",
    "header": "#0F136D",
    "button": "#F38989",
    "stripe": "#F85606",
    "ink": "#111111",
    "text_secondary": "#4f5170",
    "muted": "#dfe0ea",
    "page": "#f0f1f6",
    "card": "#ffffff",
}

DELIVERY_REASONS = ["Late delivery", "Damaged item"]
CHART_HEIGHT = 262
CARD_RADIUS = "18px"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {THEME["page"]}; }}
    [data-testid = "stHeader"]{{background: transparent; }}
    [data-testid = "stMainBlockContainer"]{{padding-top: 1.75rem; padding-bottom: 2rem; }}
    div[class*="st-key-card"]{{
        background-color: {THEME["card"]};
        border-radius: {CARD_RADIUS};
        padding: 1.1rem 1.4rem;
        box-shadow: 0 1px 2px rgba(17, 17, 17, 0.04), 0 6px 16px rgba(17, 17, 17, 0.04);
    }}
    .st-key-card_header h1 {{font-size: 2.1rem; padding: 0;}}
    div[class*="st-key-card"] h5 {{padding: 0.1rem 0 0 0; }}
    [data-testid = "stMetricLabel"] p {{color: {THEME["text_secondary"]}; font-size: 0.95rem; }}
    [data-testid = "stMetricValue"] {{font-weight: 700; color: {THEME["ink"]}; }}
    [data-testid = "stExpander"] details {{
        background-color: {THEME["card"]};
        border: none;
        border-radius: {CARD_RADIUS};
    }}
    div.st-key-card_header {{background-color: {THEME["header"]}; position: relative; overflow: hidden; }}
    div.st-key-card_header::before{{
        content: ""; position: absolute; left: 0; right: 0; top: 0; height: 6px;
        background: linear-gradient(90deg, {THEME["stripe"]}, {THEME["button"]});
    }}
    div.st-key-card_header h1, div.st-key-card_header label p {{color: #ffffff;}}
    div.st-key-card_header [data-testid="stCaptionContainer"] {{opacity: 1;}}
    div.st-key-card_header [data-testid="stCaptionContainer"] p {{color: #ffffff; opacity: 0.88;}}
    div.st-key-card_header [data-baseweb="select"] > div {{background-color: #ffffff;}}
    div.st-key-card_header [data-testid = "stBaseButton-primary"] {{background-color: {THEME["button"]}; border: none;}}
    div.st-key-card_header [data-testid = "stBaseButton-primary"] p {{color: {THEME["header"]}; font-weight: 600;}}
    </style>
""", unsafe_allow_html = True)


def style_chart(fig, title, subtitle=""):
    """Card header (title plus a one-line takeaway), then the same look for every Plotly chart."""
    st.markdown(f"##### {title}")
    st.caption(subtitle)
    fig.update_layout(
        height=CHART_HEIGHT, 
        margin=dict(l=10, r=40, t=10, b=10),
        paper_bgcolor=THEME["card"],
        plot_bgcolor=THEME["card"],
        font=dict(color=THEME["text_secondary"]),
        showlegend=False,
    )
    fig.update_traces(textfont_color=THEME["ink"], cliponaxis=False, selector=dict(type="bar"))
    fig.update_layout(bargap=0.38, barcornerradius=4)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig



# ============================================================================= 
# SLT3: Cached Data Load
# Loads the cleaned CSVs once and rebuilds the PC12 fact table and the PC15 order categories.
# =============================================================================
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cleaned"

@st.cache_data
def load_data():
    orders = pd.read_csv(DATA_DIR / "orders_clean.csv", parse_dates = ["order_datetime"])
    shipments = pd.read_csv(DATA_DIR / "shipments_clean.csv", parse_dates = ["ship_date", "delivered_date"])
    returns = pd.read_csv(DATA_DIR / "returns_clean.csv", parse_dates = ["return_request_date"])
    items = pd.read_csv(DATA_DIR / "order_items_clean.csv")
    products = pd.read_csv(DATA_DIR / "products_clean.csv")

    order_cols = ["order_id", "order_datetime", "order_status", "shipping_method", "shipping_fee"]
    fact = shipments.merge(orders[order_cols], on="order_id", how="left", validate="one_to_one")
    fact["in_lead_time_scope"] = fact["shipment_status"].eq("Delivered") & fact["delivered_date"].notna()
    lead_days = (fact["delivered_date"] - fact["ship_date"]).dt.days
    fact["lead_time_days"] = lead_days.where(fact["in_lead_time_scope"])
    fact["has_return"] = fact["order_id"].isin(returns["order_id"])
    fact["ship_month"] = fact["ship_date"].dt.to_period("M").astype("string")

    valid_lines = items[~items["invalid_order_line"] & ~items["orphan_product"]]
    order_category = (
        valid_lines[["order_id", "product_id"]]
        .merge(products[["product_id", "category"]], on = "product_id", how = "left")
        [["order_id", "category"]]
        .drop_duplicates()
    )
    return fact, returns, order_category

try: 
    fact, returns, order_category = load_data()
except FileNotFoundError as error: 
    st.error("A cleaned CSV file was not found. Run the notebook (PC1 to PC11) first.")
    st.code("Expected files in data/cleaned:\norders_clean.csv\nshipments_clean.csv\n"
           "returns_clean.csv\norder_items_clean.csv\nproducts_clean.csv")
    st.exception(error)
    st.stop()


def overview_page():
    # ============================================================================= 
    # SLT4: Header and Filters
    # Builds the header with the title, the three filters, and the Clear All button.
    # =============================================================================
    FILTER_KEYS = ["month", "courier", "method"] 
    
    def clear_filters():
        """Clear All button: set every filter back to All."""
        for key in FILTER_KEYS:
            st.session_state[key] = "All"
    
    month_options = ["All"] + sorted(fact["ship_month"].dropna().unique().tolist())
    courier_options = ["All"] + sorted(fact["courier"].dropna().unique().tolist())
    method_options = ["All"] + sorted(fact["shipping_method"].dropna().unique().tolist())
    
    with st.container(key="card_header"):
        title_col, filter_col = st.columns([1.15, 1], vertical_alignment = "center")
        with title_col:
            st.title("Delivery & Returns Analytics")
            period_slot = st.empty()
        with filter_col:
            f1, f2, f3, f4 = st.columns([1, 1, 1, 0.7], vertical_alignment = "bottom")
            selected_month = f1.selectbox("Ship Month", month_options, key = "month")
            selected_courier = f2.selectbox("Courier", courier_options, key = "courier")
            selected_method = f3.selectbox("Shipping Method", method_options, key = "method")
            f4.button("Clear All", on_click = clear_filters, type = "primary", width = "stretch")
    
    
    
    # ============================================================================= 
    # SLT5: Apply Filters and Empty Check
    # Applies the filters and stops the page with a warning when no shipments match.
    # =============================================================================
    filtered = fact.copy()
    if selected_month != "All":
        filtered = filtered[filtered["ship_month"] == selected_month]
    if selected_method != "All":
        filtered = filtered[filtered["shipping_method"] == selected_method]
    courier_scope = filtered
    if selected_courier != "All":
        filtered = filtered[filtered["courier"] == selected_courier]
    
    
    if filtered.empty:
        st.warning("No shipments match the selected filters. Please change one or more filters.")
        st.stop()
    
    period_slot.caption(f"How well are we delivering, and what causes returns? | Ship dates: "
                       f"{filtered['ship_date'].min():%b %d, %Y} to {filtered['ship_date'].max():%b %d, %Y}")
    
    delivered = filtered[filtered["in_lead_time_scope"]]
    filtered_returns = returns[returns["order_id"].isin(filtered["order_id"])]
    
    
    
    # ============================================================================= 
    # SLT6: KPI Cards
    # Shows the KPI Cards and compares each filtered value with the overall value.
    # =============================================================================
    shipment_count = len(filtered)
    delivered_pct = filtered["shipment_status"].eq("Delivered").mean()
    lost_pct = filtered["shipment_status"].eq("Lost").mean()
    avg_lead_time = delivered["lead_time_days"].mean()
    return_rate = filtered["has_return"].mean()
    
    overall_delivered = fact["shipment_status"].eq("Delivered").mean()
    overall_lost = fact["shipment_status"].eq("Lost").mean()
    overall_lead_time = fact["lead_time_days"].mean()
    overall_return_rate = fact["has_return"].mean()
    
    def pts_vs_overall(value, overall):
        """Difference in percentage points, written for the KPI Card."""
        diff = round((value - overall) * 100, 1)
        if diff == 0:
            diff = 0.0
        return f"{diff:+.1f} pts vs overall"
    
    lead_diff = round(avg_lead_time - overall_lead_time, 2)
    if lead_diff == 0:
        lead_diff = 0.0
    
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.container(key="card_kpi1").metric(
        ":material/local_shipping: Shipments", f"{shipment_count:,}",
        delta=f"{shipment_count / len(fact):.1%} of all shipments", delta_color = "off"
    )
    k2.container(key="card_kpi2").metric(
        ":material/task_alt: Delivered", f"{delivered_pct:.1%}",
        delta=pts_vs_overall(delivered_pct, overall_delivered), delta_color = "off",
        help = "Share of shipments with status Delivered"
    )
    k3.container(key="card_kpi3").metric(
        ":material/schedule: Average Lead Time",
        f"{avg_lead_time:.2f} days" if pd.notna(avg_lead_time) else "No data",
        delta = f"{lead_diff:+.2f} days vs overall" if pd.notna(avg_lead_time) else None,
        delta_color = "off",
        help = "Days from ship date to delivered date. Delivered shipments with a delivered_date only."
    )
    k4.container(key="card_kpi4").metric(
        ":material/report: Lost", f"{lost_pct:.1%}",
        delta = pts_vs_overall(lost_pct, overall_lost), delta_color="off",
        help = "Share of shipments with status Lost"
    )
    k5.container(key="card_kpi5").metric(
        ":material/assignment_return: Return Rate", f"{return_rate:.1%}",
        delta = pts_vs_overall(return_rate, overall_return_rate), delta_color = "off",
        help = "Orders with a row in returns.csv divided by all orders"
    )
    
    left1, right1 = st.columns(2)
    left1, right1 = left1.container(key="card_lead"), right1.container(key="card_status")
    
    
    
    
    # ============================================================================= 
    # SLT7: Lead Time Distribution
    # Draws the lead time distribution for the filtered shipments (same chart as PC17).
    # =============================================================================
    with left1:
        if delivered.empty:
            st.info("No delivered shipments in this selection, so lead time cannot be shown.")
        else: 
            lead_counts = (delivered["lead_time_days"].astype(int).value_counts().sort_index()
                          .rename_axis("lead_time_days").reset_index(name="shipments"))
            lead_counts["label"] = (lead_counts["shipments"] / lead_counts["shipments"].sum()).map("{:.1%}".format)
            fig_lead = px.bar(lead_counts, x="lead_time_days", y="shipments", text="label",
                             color_discrete_sequence = [THEME["accent"]],
                             labels={"lead_time_days": "Lead time (days from ship date to delivered date)",
                                    "shipments": "Delivered shipments"})
            fig_lead.update_xaxes(dtick=1)
            fig_lead.update_yaxes(tickformat=",")
            fig_lead.update_traces(textposition="outside")
            style_chart(fig_lead, "Lead Time Distribution",
                       f"Average {avg_lead_time:.1f} days | {(delivered['lead_time_days']<=2).mean():.1%} within 2 days | "
                       f"{(delivered['lead_time_days']>=6).mean():.1%} take 6 to 7 days")
            st.plotly_chart(fig_lead, width="stretch")
    
    
    
    # ============================================================================= 
    # SLT8: Shipment Status Breakdown
    # Draws the shipment status breakdown (same chart as PC21).
    # =============================================================================
    with right1:
        status = (filtered["shipment_status"].value_counts()
                 .rename_axis("shipment_status").reset_index(name="shipments"))
        status["label"] = [f"{n:,} ({n / shipment_count:.1%})" for n in status["shipments"]]
        fig_status = px.bar(status, x="shipments", y="shipment_status", orientation="h", text="label",
                           color_discrete_sequence=[THEME["accent"]],
                           labels={"shipments": "Shipments", "shipment_status": ""})
        fig_status.update_yaxes(categoryorder="total ascending")
        fig_status.update_traces(textposition="outside")
        fig_status.update_xaxes(tickformat=",", range=[0, status["shipments"].max() * 1.3])
        style_chart(fig_status, "Shipment Status Breakdown",
                    f"{delivered_pct:.1%} delivered | {filtered['shipment_status'].eq('In Transit').mean():.1%} in transit | "
                    f"{lost_pct:.1%} lost")
        st.plotly_chart(fig_status, width="stretch")
    
    
    
    
    # ============================================================================= 
    # SLT9: Courier Comparison
    # Draws lead time and return rate by courier and highlights the selected courier (same chart as PC18).
    # =============================================================================
    courier = courier_scope.groupby("courier").agg(
        shipments = ("shipment_id", "count"),
        returns = ("has_return", "sum"),
        return_rate = ("has_return", "mean"),
    )
    scope_delivered = courier_scope[courier_scope["in_lead_time_scope"]]
    courier = (courier.join(scope_delivered.groupby("courier")["lead_time_days"].mean().rename("avg_lead_time_days"))
                .reset_index().sort_values("return_rate"))
    courier_colors = [THEME["accent"] if selected_courier in ("All", c) else THEME["muted"]
                     for c in courier["courier"]]
    
    left2, right2 = st.columns(2)
    left2, right2 = left2.container(key="card_courier_lead"), right2.container(key="card_courier_returns")
    with left2:
        fig_courier_lead = px.bar(courier, x="avg_lead_time_days", y="courier", orientation="h",
                                 text=courier["avg_lead_time_days"].map("{:.2f} days".format),
                                 color_discrete_sequence=[THEME["accent"]],
                                 labels={"avg_lead_time_days": "Average lead time (days)", "courier": ""})
        fig_courier_lead.update_traces(textposition="outside", marker_color=courier_colors)
        fig_courier_lead.update_xaxes(range=[0,5.5])
        lead_gap = courier["avg_lead_time_days"].max() - courier["avg_lead_time_days"].min()
        style_chart(fig_courier_lead, "Average Lead Time by Courier",
                   f"Fastest to slowest gap: {lead_gap:.2f} days ({lead_gap * 24:.1f} hours)")
        st.plotly_chart(fig_courier_lead, width = "stretch")
    
    with right2:
        fig_courier_returns = px.bar(courier, x="return_rate", y="courier", orientation="h",
                                    text=courier["return_rate"].map("{:.1%}".format),
                                    color_discrete_sequence=[THEME["accent"]],
                                    labels={"return_rate": "Return rate (% of shipments)", "courier": ""})
        fig_courier_returns.update_traces(textposition="outside", marker_color=courier_colors)
        fig_courier_returns.update_xaxes(tickformat=".0%", range = [0, 0.11])
        lowest, highest = courier.iloc[0], courier.iloc[-1]
        style_chart(fig_courier_returns, "Return Rate by Courier",
                   f"Lowest {lowest['return_rate']:.1%} ({lowest['courier']}) | "
                   f"highest {highest['return_rate']:.1%} ({highest['courier']})")
        st.plotly_chart(fig_courier_returns, width="stretch")
    
    
    
    
    # ============================================================================= 
    # SLT10: Returns Charts
    # Draws the return reasons and the return rate by category (same charts as PC19 and PC20).
    # =============================================================================
    left3, right3 = st.columns(2)
    left3, right3 = left3.container(key="card_reasons"), right3.container(key="card_category")
    
    with left3:
        if filtered_returns.empty:
            st.info("No returns in the selection.")
        else:
            reasons = (filtered_returns["reason"].value_counts()
                      .rename_axis("reason").reset_index(name="returns"))
            reasons["group"] = reasons["reason"].isin(DELIVERY_REASONS).map(
                {True: "Delivery-related", False: "Product or order"}
            )
            reasons["label"] = [f"{n} ({n / len(filtered_returns):.1%})" for n in reasons["returns"]]
            fig_reasons = px.bar(reasons, x="returns", y="reason", orientation="h", text="label",
                                color="group",
                                color_discrete_map = {"Delivery-related": THEME["accent"], 
                                                     "Product or order": THEME["muted"]},
                                category_orders={"group": ["Delivery-related", "Product or order"]},
                                labels={"returns": "Returns", "reason": "", "group": ""})
            fig_reasons.update_yaxes(categoryorder="total ascending")
            fig_reasons.update_traces(textposition="outside")
            delivery_share = reasons.loc[reasons["group"] == "Delivery-related", "returns"].sum() / len(filtered_returns)
            style_chart(fig_reasons, "Return Reasons",
                       f"Highlighted bars are delivery-related reasons: {delivery_share:.1%} of {len(filtered_returns):,} returns")
            st.plotly_chart(fig_reasons, width="stretch")
    
    with right3:
        cat = order_category[order_category["order_id"].isin(filtered["order_id"])].copy()
        cat["has_return"] = cat["order_id"].isin(filtered_returns["order_id"])
        category = (cat.groupby("category").agg(orders=("order_id", "count"), return_rate=("has_return", "mean"))
                   .reset_index().sort_values("return_rate"))
        fig_category = px.bar(category, x="return_rate", y= "category", orientation="h",
                             text=category["return_rate"].map("{:.1%}".format),
                             color_discrete_sequence=[THEME["accent"]],
                             labels={"return_rate": "Return rate (% of orders that include the category)",
                                    "category": ""})
        fig_category.update_traces(textposition="outside")
        fig_category.update_xaxes(tickformat=".0%", range=[0, max(0.11, category["return_rate"].max() * 1.25)])
        style_chart(fig_category, "Return Rate by Category",
                   f"Overall {return_rate:.1%} | An order with two categories counts in both")
        st.plotly_chart(fig_category, width="stretch")
        
    
    
    
    # ============================================================================= 
    # SLT11: Detail Table
    # Shows the filtered shipment records in an expandable table.
    # =============================================================================
    with st.expander("View filtered shipment records"):
        detail_cols = ["shipment_id", "order_id", "courier", "shipping_method", "shipment_status",
                      "ship_date", "delivered_date", "lead_time_days", "has_return"]
        detail = filtered[detail_cols].sort_values("ship_date", ascending=False).copy()
        detail["ship_date"] = detail["ship_date"].dt.date
        detail["delivered_date"] = detail["delivered_date"].dt.date
        st.dataframe(detail, width="stretch", hide_index=True)
        st.caption(f"{len(filtered):,} shipments | {len(delivered):,} in the lead time scope | "
                  f"{len(filtered_returns):,} returns")
    
    
    
    
    # ============================================================================= 
    # SLT12: About This Dashboard
    # Shows the About section with the data source, metric definitions, and limitations.
    # =============================================================================
    with st.expander("About this dashboard"):
        st.markdown(
            """
    **Business question:** How well are we delivering, and what causes returns?
    
    **Data:** Training dataset from the DataSense Analytics Python Programming Data Analyst Professional Certificate.
    The app reads the cleaned CSVs exported by the notebook (PC11). No rows were deleted for missing values or conflicts. Problem rows carry a True / False flag column instead. 
    
    **Metric definitions**
    - **Lead time:** delivered_date minus ship_date, in days. Only Delivered shipments with a delivered_date are used.
    - **Return rate:** orders with a row in returns.csv divided by all orders. The order_status value "Returned" is not used. Only 6.9% of the 578 "Returned" orders also appear in returns.csv.
    - **Return rate by category:** a return is linked to an order, not a product. An order with items from two categories counts once in each category.
    - **Delivery-related reasons:** Late delivery and Damaged item.
    
    **Limitations:** The no-difference findings are possibly because the dataset is synthetic.
    
    **Theme:** Color theme inspired by Lazada.
            """
        )
    
    st.caption("by David Alilio | Training dataset from the DataSense Analytics Python Programming Data Analyst Professional Certificate")




# ============================================================================= 
# SLT13: Statistical Tests (Cached)
# Runs the seven statistical tests once and caches the results (same tests as PC15, PC22, PC23, and PC24).
# =============================================================================
@st.cache_data
def run_tests(_fact, _returns):
    fact, returns = _fact, _returns
    from scipy import stats
    delivered = fact[fact["in_lead_time_scope"]]
    rows = []

    def groups(col):
        return [g["lead_time_days"] for _, g in delivered.groupby(col)]

    w, p = stats.levene(*groups("courier"))
    sd = delivered.groupby("courier")["lead_time_days"].std()
    rows.append(("Levene", "Does any courier deliver more consistently?", f"W = {w:.2f}, p = {p:.3f}",
                f"SD {sd.min():.2f} to {sd.max():.2f} days", "No. Every courier is equally predictable."))

    grand = delivered["lead_time_days"].mean()
    ss_total = ((delivered["lead_time_days"] - grand) ** 2).sum()
    for col, question, answer in [
        ("courier", "Is any courier faster?", "No. Every courier averages about 4 days."),
        ("shipping_method", "Is Express faster than Standard?", "No. The gap is under 1 hour."),
    ]:
        g = groups(col)
        f, p = stats.f_oneway(*g)
        r2 = sum(len(x) * (x.mean() - grand) ** 2 for x in g) / ss_total
        rows.append((f"One-way ANOVA ({col.replace('_', ' ')})", question, f"F = {f:.2f}, p = {p:.3f}",
                    f"R\u00b2 = {r2:.3%}", answer))
    
    def chi(table, name, question, answer):
        c2, p, dof, exp = stats.chi2_contingency(table)
        v = (c2 / (table.to_numpy().sum() * (min(table.shape) - 1))) ** 0.5
        rows.append((name, question, f"\u03c7\u00b2 = {c2:.2f}, p = {p:.3f}", f"Cram\u00e9r's V = {v:.3f}", answer))

    chi(pd.crosstab(fact["courier"], fact["shipment_status"]), "Chi-square (status x courier)",
       "Do lost or returned-to-sender rates differ by courier?", "No. The status mix is the same.")
    chi(pd.crosstab(fact["courier"], fact["has_return"]), "Chi-square (returned x courier)",
       "Do return rates differ by courier?", "Yes, but the gap is very weak.")
    return_courier = returns["order_id"].map(fact.set_index("order_id")["courier"])
    chi(pd.crosstab(return_courier, returns["reason"]), "Chi-square (reason x courier)",
       "Do return reasons differ by courier?", "No. Every courier has the same mix.")
    
    lead_by_order = delivered.set_index("order_id")["lead_time_days"]
    return_lead = returns["order_id"].map(lead_by_order)
    is_late = returns["reason"].eq("Late delivery")
    late, other = return_lead[is_late].dropna(), return_lead[~is_late].dropna()
    u, p = stats.mannwhitneyu(late, other, alternative="two-sided")
    rows.append(("Mann-Whitney", "Did 'Late delivery' returns come from slower deliveries?", f"p = {p:.2f}",
                f"Median {late.median():.0f} vs {other.median():.0f} days", "No. Both took a median of 4 days."))

    summary = pd.DataFrame(rows, columns=["Test", "Business question", "Result", "Effect size", "Answer"])
    late_vs_other = pd.DataFrame({"lead_time_days": pd.concat([late, other]),
                                 "group": ["Late delivery"] * len(late) + ["Other reasons"] * len(other)})

    return summary, late_vs_other




# ============================================================================= 
# SLT14: Statistical Analysis Page
# Builds the Statistical Analysis page with the KPI cards, the test summary table, and four charts.
# =============================================================================
def stats_page():
    summary, late_vs_other = run_tests(fact, returns)
    delivered_all = fact[fact["in_lead_time_scope"]]
    courier_order = {"courier": sorted(fact["courier"].dropna().unique())}

    with st.container(key="card_header"):
        st.title("Statistical Analysis")
        st.caption("Are the gaps between couriers and shipping methods real, or just noise? | "
                  f"All {len(fact):,} shipments, no filters")

    significant = (summary["Result"].str.extract(r"p = ([0-9.]+)")[0].astype(float) < 0.05).sum()
    k1, k2, k3 = st.columns(3)
    k1.container(key="card_kpi_t1").metric(":material/science: Tests Run", f"{len(summary)}")
    k2.container(key="card_kpi_t2").metric(":material/check_circle: Significant (p < 0.05)",
                                          f"{significant} of {len(summary)}")
    k3.container(key="card_kpi_t3").metric(":material/straighten: Effect Size of the Significant Test",
                                          summary.loc[4, "Effect size"].replace("Cram\u00e9r's ", ""),
                                          help="Cram\u00e9r's V for return rate x courier, the only test with "
                                          "p < 0.05. Values below 0.10 are very weak.")

    with st.container(key="card_summary"):
        st.markdown("##### Test Summary")
        st.caption("Each test answers one business question from the Executive Overview page")
        st.dataframe(summary, width="stretch", hide_index=True)


    ci = delivered_all.groupby("courier")["lead_time_days"].agg(["mean", "sem", "count"]).reset_index()
    ci["ci95"] = 1.96 * ci["sem"]
    rate = fact.groupby("courier")["has_return"].agg(["mean", "count"]).reset_index()
    rate["ci95"] = 1.96 * (rate["mean"] * (1 - rate["mean"]) / rate["count"]) ** 0.5

    left, right = st.columns(2)
    left, right = left.container(key="card_anova"), right.container(key="card_levene")
    with left: 
        fig = px.scatter(ci, x="mean", y="courier", error_x="ci95", color_discrete_sequence=[THEME["accent"]],
                        category_orders=courier_order,
                        labels={"mean": "Average lead time (days), with 95% confidence interval", "courier": ""})
        fig.update_traces(marker_size=12)
        fig.update_xaxes(range=[3.7, 4.3])
        style_chart(fig, "Is Any Courier Faster?",
                   f"{summary.loc[1, 'Result']} | {summary.loc[1, 'Effect size']} | All intervals overlap")
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.box(delivered_all, x="lead_time_days", y="courier", color_discrete_sequence=[THEME["accent"]],
                    category_orders=courier_order,
                    labels={"lead_time_days": "Lead time (days)", "courier": ""})
        style_chart(fig, "Does Any Courier Deliver More Consistently?",
                   f"Levene {summary.loc[0, 'Result']} | {summary.loc[0, 'Effect size']}")
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    left, right = left.container(key="card_chi"), right.container(key="card_mw")
    with left:
        fig = px.scatter(rate, x="mean", y="courier", error_x="ci95", color_discrete_sequence=[THEME["accent"]],
                        category_orders=courier_order,
                        labels={"mean": "Return rate, with 95% confidence interval", "courier": ""})
        fig.update_traces(marker_size=12)
        fig.update_xaxes(tickformat=".0%", range=[0.05, 0.11])
        style_chart(fig, "Do Return Rates Differ by Courier?", 
                   f"{summary.loc[4, 'Result']} | {summary.loc[4, 'Effect size']} | Real but very weak")
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.box(late_vs_other, x="lead_time_days", y="group", color_discrete_sequence=[THEME["accent"]],
                    labels={"lead_time_days": "Lead time of the returned parcel (days)", "group": ""})
        style_chart(fig, "Did 'Late Delivery' Returns Come From Slower Deliveries?",
                   f"Mann-Whitney {summary.loc[6, 'Result']} | {summary.loc[6, 'Effect size']}")
        st.plotly_chart(fig, width="stretch")

    st.caption("by David Alilio | Training dataset from the DataSense Analytics Python Programming "
                  "Data Analyst Professional Certificate")
            



# ============================================================================= 
# SLT15: Page Navigation
# Adds the top navigation between the two pages and centers the page links.
# =============================================================================
st.markdown(
    """
    <style>
    [data-testid="stToolbar"] div:has(> .rc-overflow){flex:1}
    [data-testid="stToolbar"] .rc-overflow{flex: 1; justify-content: center;}
    [data-testid="stTopNavLink"] p {font-size: 0.95rem; font-weight: 500;}
    </style>
    """, unsafe_allow_html=True
)

nav = st.navigation(
    [st.Page(overview_page, title="Executive Overview", default=True),
    st.Page(stats_page, title="Statistical Analysis", url_path="statistics")],
    position="top",
)
nav.run()

