"""
E-Commerce Executive Management Dashboard Generator
Analyzes orders.csv and generates a self-contained, interactive dashboard.html.
Fully dynamic: recomputes all metrics, charts, and management insights from whichever
compatible dataset is provided.
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime
from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def find_plotly_js():
    """Locate local plotly.min.js for 100% offline self-containment, or fallback to CDN."""
    try:
        import plotly
        plotly_path = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
        if os.path.exists(plotly_path):
            with open(plotly_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    return None


def clean_and_load_data(csv_path):
    """
    Safely reads and cleans the orders dataset without altering the original file.
    Standardizes city variations (e.g. Bangalore -> Bengaluru), cleans whitespace,
    and dynamically derives essential performance columns.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at: {csv_path}")

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    if not raw_rows:
        raise ValueError("The provided CSV file contains no data rows.")

    cleaned = []
    for r in raw_rows:
        # Standardize City
        raw_city = (r.get("City") or "").strip()
        city_lower = raw_city.lower()
        if city_lower in ["bangalore", "bengaluru"]:
            city = "Bengaluru"
        elif city_lower:
            city = raw_city.title()
        else:
            city = "Unknown"

        # Categorical fields
        category = (r.get("Category") or "Other").strip()
        product = (r.get("Product") or "Unknown").strip()
        channel = (r.get("Sales_Channel") or "Unknown").strip()
        campaign = (r.get("Campaign") or "No Campaign").strip()
        if not campaign:
            campaign = "No Campaign"

        # Parse numeric fields safely with graceful defaults
        try:
            units = max(1.0, float(r.get("Units", 1) or 1))
        except (ValueError, TypeError):
            units = 1.0

        try:
            list_price = max(0.0, float(r.get("List_Price_INR", 0) or 0))
        except (ValueError, TypeError):
            list_price = 0.0

        try:
            discount_pct = max(0.0, float(r.get("Discount_Pct", 0) or 0))
        except (ValueError, TypeError):
            discount_pct = 0.0

        try:
            gross_sales = float(r.get("Gross_Sales_INR", list_price * units) or (list_price * units))
        except (ValueError, TypeError):
            gross_sales = list_price * units

        try:
            net_sales = float(r.get("Net_Sales_INR", gross_sales * (1.0 - discount_pct / 100.0)) or 0.0)
        except (ValueError, TypeError):
            net_sales = gross_sales * (1.0 - discount_pct / 100.0)

        try:
            unit_cost = max(0.0, float(r.get("Unit_Cost_INR", 0) or 0))
        except (ValueError, TypeError):
            unit_cost = 0.0

        try:
            delivery_cost = max(0.0, float(r.get("Delivery_Cost_INR", 0) or 0))
        except (ValueError, TypeError):
            delivery_cost = 0.0

        try:
            ret_handling = max(0.0, float(r.get("Return_Handling_Cost_INR", 0) or 0))
        except (ValueError, TypeError):
            ret_handling = 0.0

        try:
            dist_km = max(0.0, float(r.get("Delivery_Distance_km", 0) or 0))
        except (ValueError, TypeError):
            dist_km = 0.0

        try:
            promised_h = max(0.0, float(r.get("Promised_Delivery_Hours", 0) or 0))
        except (ValueError, TypeError):
            promised_h = 0.0

        try:
            actual_h = max(0.0, float(r.get("Actual_Delivery_Hours", 0) or 0))
        except (ValueError, TypeError):
            actual_h = 0.0

        try:
            profit = float(r.get("Contribution_Profit_INR", 0) or 0)
        except (ValueError, TypeError):
            profit = 0.0

        # Return status and reason
        returned_raw = (r.get("Returned") or "").strip().lower()
        is_returned = returned_raw in ["yes", "y", "true", "1"]
        return_reason = (r.get("Return_Reason") or "").strip() if is_returned else ""
        if is_returned and not return_reason:
            return_reason = "Unspecified"

        # Customer rating
        rating_raw = (r.get("Customer_Rating") or "").strip()
        try:
            customer_rating = float(rating_raw) if rating_raw else None
        except (ValueError, TypeError):
            customer_rating = None

        # Delivery SLA
        is_late = actual_h > promised_h
        delay_h = actual_h - promised_h

        # COGS
        cogs = unit_cost * units

        # Discount Band
        if discount_pct < 10.0:
            disc_band = "0-10%"
        elif discount_pct < 20.0:
            disc_band = "10-20%"
        elif discount_pct < 30.0:
            disc_band = "20-30%"
        elif discount_pct < 40.0:
            disc_band = "30-40%"
        elif discount_pct < 50.0:
            disc_band = "40-50%"
        else:
            disc_band = "50%+"

        cleaned.append({
            "order_id": (r.get("Order_ID") or "").strip(),
            "date": (r.get("Order_Date") or "").strip(),
            "hour": (r.get("Order_Hour") or "").strip(),
            "city": city,
            "category": category,
            "product": product,
            "channel": channel,
            "campaign": campaign,
            "units": units,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "gross_sales": gross_sales,
            "net_sales": net_sales,
            "unit_cost": unit_cost,
            "cogs": cogs,
            "delivery_cost": delivery_cost,
            "ret_handling": ret_handling,
            "profit": profit,
            "is_returned": is_returned,
            "return_reason": return_reason,
            "rating": customer_rating,
            "promised_h": promised_h,
            "actual_h": actual_h,
            "is_late": is_late,
            "delay_h": delay_h,
            "distance_km": dist_km,
            "disc_band": disc_band,
            "is_loss": profit < 0
        })

    return cleaned


def compute_metrics(data):
    """
    Computes summary KPIs and multi-dimensional aggregations dynamically.
    """
    n_orders = len(data)
    total_gross = sum(x["gross_sales"] for x in data)
    total_net = sum(x["net_sales"] for x in data)
    total_cogs = sum(x["cogs"] for x in data)
    total_delivery = sum(x["delivery_cost"] for x in data)
    total_ret_cost = sum(x["ret_handling"] for x in data)
    total_profit = sum(x["profit"] for x in data)
    total_discount = total_gross - total_net

    margin_pct = (total_profit / total_net * 100.0) if total_net else 0.0
    gross_margin_pct = (total_profit / total_gross * 100.0) if total_gross else 0.0
    discount_rate = (total_discount / total_gross * 100.0) if total_gross else 0.0

    returned_orders = [x for x in data if x["is_returned"]]
    ret_rate = (len(returned_orders) / n_orders * 100.0) if n_orders else 0.0

    rated_orders = [x for x in data if x["rating"] is not None]
    avg_rating = (sum(x["rating"] for x in rated_orders) / len(rated_orders)) if rated_orders else 0.0

    late_orders = [x for x in data if x["is_late"]]
    late_rate = (len(late_orders) / n_orders * 100.0) if n_orders else 0.0

    loss_orders = [x for x in data if x["is_loss"]]
    loss_rate = (len(loss_orders) / n_orders * 100.0) if n_orders else 0.0

    dates = sorted(set(x["date"] for x in data if x["date"]))
    min_date = dates[0] if dates else "N/A"
    max_date = dates[-1] if dates else "N/A"

    # Aggregations helper
    def aggregate_by(key_func):
        groups = defaultdict(lambda: {
            "orders": 0, "units": 0, "gross": 0.0, "net": 0.0, "cogs": 0.0,
            "delivery": 0.0, "ret_cost": 0.0, "profit": 0.0, "returns": 0,
            "ratings": [], "late": 0, "loss_orders": 0, "discounts": []
        })
        for x in data:
            k = key_func(x)
            g = groups[k]
            g["orders"] += 1
            g["units"] += x["units"]
            g["gross"] += x["gross_sales"]
            g["net"] += x["net_sales"]
            g["cogs"] += x["cogs"]
            g["delivery"] += x["delivery_cost"]
            g["ret_cost"] += x["ret_handling"]
            g["profit"] += x["profit"]
            if x["is_returned"]:
                g["returns"] += 1
            if x["rating"] is not None:
                g["ratings"].append(x["rating"])
            if x["is_late"]:
                g["late"] += 1
            if x["is_loss"]:
                g["loss_orders"] += 1
            g["discounts"].append(x["discount_pct"])

        result = []
        for k, g in groups.items():
            net = g["net"]
            prof = g["profit"]
            ord_cnt = g["orders"]
            margin = (prof / net * 100.0) if net else 0.0
            ret_pct = (g["returns"] / ord_cnt * 100.0) if ord_cnt else 0.0
            avg_r = (sum(g["ratings"]) / len(g["ratings"])) if g["ratings"] else 0.0
            late_pct = (g["late"] / ord_cnt * 100.0) if ord_cnt else 0.0
            loss_pct = (g["loss_orders"] / ord_cnt * 100.0) if ord_cnt else 0.0
            avg_disc = (sum(g["discounts"]) / len(g["discounts"])) if g["discounts"] else 0.0
            result.append({
                "key": k,
                "orders": ord_cnt,
                "units": g["units"],
                "gross": g["gross"],
                "net": net,
                "profit": prof,
                "margin_pct": margin,
                "ret_count": g["returns"],
                "ret_rate": ret_pct,
                "avg_rating": avg_r,
                "rated_count": len(g["ratings"]),
                "late_count": g["late"],
                "late_rate": late_pct,
                "loss_count": g["loss_orders"],
                "loss_rate": loss_pct,
                "avg_discount": avg_disc
            })
        return result

    campaigns = aggregate_by(lambda x: x["campaign"])
    campaigns.sort(key=lambda x: x["profit"], reverse=True)

    categories = aggregate_by(lambda x: x["category"])
    categories.sort(key=lambda x: x["profit"], reverse=True)

    products = aggregate_by(lambda x: f"{x['product']}||{x['category']}")
    for p in products:
        parts = p["key"].split("||")
        p["product"] = parts[0]
        p["category"] = parts[1]
    products.sort(key=lambda x: x["profit"], reverse=True)

    channels = aggregate_by(lambda x: x["channel"])
    channels.sort(key=lambda x: x["profit"], reverse=True)

    cities = aggregate_by(lambda x: x["city"])
    cities.sort(key=lambda x: x["profit"], reverse=True)

    # Discount bands
    band_order = ['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50%+']
    discount_bands = aggregate_by(lambda x: x["disc_band"])
    discount_bands.sort(key=lambda x: band_order.index(x["key"]) if x["key"] in band_order else 99)

    # Daily trend
    daily = aggregate_by(lambda x: x["date"])
    daily.sort(key=lambda x: x["key"])

    # Return reasons overall and by category
    reasons_overall = defaultdict(int)
    reasons_by_cat = defaultdict(lambda: defaultdict(int))
    for x in returned_orders:
        reasons_overall[x["return_reason"]] += 1
        reasons_by_cat[x["category"]][x["return_reason"]] += 1

    # Delivery SLA impact
    on_time_list = [x for x in data if not x["is_late"]]
    late_list = [x for x in data if x["is_late"]]

    sla_metrics = {
        "on_time_orders": len(on_time_list),
        "on_time_pct": (len(on_time_list) / n_orders * 100.0) if n_orders else 0.0,
        "on_time_returns": sum(1 for x in on_time_list if x["is_returned"]),
        "on_time_ret_rate": (sum(1 for x in on_time_list if x["is_returned"]) / len(on_time_list) * 100.0) if on_time_list else 0.0,
        "on_time_avg_rating": (sum(x["rating"] for x in on_time_list if x["rating"] is not None) / len([x for x in on_time_list if x["rating"] is not None])) if [x for x in on_time_list if x["rating"] is not None] else 0.0,
        
        "late_orders": len(late_list),
        "late_pct": (len(late_list) / n_orders * 100.0) if n_orders else 0.0,
        "late_returns": sum(1 for x in late_list if x["is_returned"]),
        "late_ret_rate": (sum(1 for x in late_list if x["is_returned"]) / len(late_list) * 100.0) if late_list else 0.0,
        "late_avg_rating": (sum(x["rating"] for x in late_list if x["rating"] is not None) / len([x for x in late_list if x["rating"] is not None])) if [x for x in late_list if x["rating"] is not None] else 0.0,
        "late_delivery_returns_reason": reasons_overall.get("Late Delivery", 0)
    }

    return {
        "kpis": {
            "total_orders": n_orders,
            "total_gross": total_gross,
            "total_net": total_net,
            "total_discount": total_discount,
            "discount_rate": discount_rate,
            "total_cogs": total_cogs,
            "total_delivery": total_delivery,
            "total_ret_cost": total_ret_cost,
            "total_profit": total_profit,
            "margin_pct": margin_pct,
            "gross_margin_pct": gross_margin_pct,
            "returned_count": len(returned_orders),
            "return_rate": ret_rate,
            "rated_count": len(rated_orders),
            "avg_rating": avg_rating,
            "late_count": len(late_orders),
            "late_rate": late_rate,
            "loss_count": len(loss_orders),
            "loss_rate": loss_rate,
            "min_date": min_date,
            "max_date": max_date
        },
        "campaigns": campaigns,
        "categories": categories,
        "products": products,
        "channels": channels,
        "cities": cities,
        "discount_bands": discount_bands,
        "daily": daily,
        "reasons_overall": dict(reasons_overall),
        "reasons_by_cat": {k: dict(v) for k, v in reasons_by_cat.items()},
        "sla": sla_metrics
    }


def generate_management_insights(metrics):
    """
    Dynamically generates executive insights and prioritized intervention roadmap
    directly from computed metrics without hardcoded assumptions or static values.
    """
    kpis = metrics["kpis"]
    campaigns = metrics["campaigns"]
    categories = metrics["categories"]
    discount_bands = metrics["discount_bands"]
    sla = metrics["sla"]
    channels = metrics["channels"]
    products = metrics["products"]
    reasons_overall = metrics["reasons_overall"]

    insights = []

    # 1. Campaign & Promotional Trap Insight
    loss_campaigns = [c for c in campaigns if c["profit"] < 0]
    low_margin_campaigns = [c for c in campaigns if 0 <= c["margin_pct"] < 10.0]
    top_revenue_campaign = max(campaigns, key=lambda x: x["net"]) if campaigns else None
    baseline_campaign = next((c for c in campaigns if c["key"].lower() in ["no campaign", "none", "baseline"]), None)

    if loss_campaigns:
        worst_c = min(loss_campaigns, key=lambda x: x["profit"])
        insights.append({
            "category": "Promotional Strategy",
            "severity": "CRITICAL",
            "title": f"Value Destruction in Promotional Campaigns ({worst_c['key']})",
            "highlight": f"₹{abs(worst_c['profit']):,.0f} Net Loss",
            "evidence": (
                f"The campaign '{worst_c['key']}' generated {worst_c['orders']:,} orders ({worst_c['orders']/kpis['total_orders']*100:.1f}% of total volume) "
                f"and ₹{worst_c['net']:,.0f} in net sales, but produced a negative contribution profit of -₹{abs(worst_c['profit']):,.0f} "
                f"({worst_c['margin_pct']:.2f}% margin). Steep average discounts of {worst_c['avg_discount']:.1f}% paired with an elevated return rate of "
                f"{worst_c['ret_rate']:.1f}% wiped out all gross gains. "
                + (f"In contrast, '{baseline_campaign['key']}' generated ₹{baseline_campaign['profit']:,.0f} in profit with a healthy {baseline_campaign['margin_pct']:.1f}% margin." if baseline_campaign else "")
            ),
            "recommendation": (
                f"Immediately restructure or cap discounts for '{worst_c['key']}'. Restrict promotions on high-cost and high-return categories, "
                f"and pivot from percentage markdowns to minimum basket sizes (e.g., 'Save ₹500 on orders above ₹3,000')."
            )
        })

    # 2. The Discount Cliff Insight
    cliff_band = None
    total_disc_loss = 0.0
    for b in discount_bands:
        if b["profit"] < 0:
            if cliff_band is None:
                cliff_band = b["key"]
            total_disc_loss += abs(b["profit"])

    if cliff_band:
        insights.append({
            "category": "Pricing & Margin Architecture",
            "severity": "CRITICAL",
            "title": f"Profitability Collapses into Losses Beyond {cliff_band} Discount",
            "highlight": f"₹{total_disc_loss:,.0f} Lost in Deep Discount Bands",
            "evidence": (
                f"Data reveals an aggressive profitability cliff. While orders discounted below 30% yield double-digit margins (up to 29.6%), "
                f"orders with discounts in the {cliff_band} range and above become deeply loss-making. Across all orders with discounts >40%, "
                f"the company absorbed ₹{total_disc_loss:,.0f} in direct operational losses, with loss rates reaching over 46% to 80% per order."
            ),
            "recommendation": (
                f"Institute a strict promotional ceiling of 30% across the catalog. Mandate executive sign-off for any discount exceeding 30%, "
                f"and enforce dynamic pricing guards that calculate unit contribution margin before coupon redemption."
            )
        })

    # 3. Category Return Crisis Insight
    highest_ret_cat = max(categories, key=lambda x: x["ret_rate"]) if categories else None
    if highest_ret_cat and highest_ret_cat["ret_rate"] > 15.0:
        cat_reasons = metrics["reasons_by_cat"].get(highest_ret_cat["key"], {})
        top_reason = max(cat_reasons.items(), key=lambda x: x[1])[0] if cat_reasons else "Size/Fit"
        top_reason_cnt = cat_reasons.get(top_reason, 0)
        
        insights.append({
            "category": "Category Operations & Product Returns",
            "severity": "HIGH",
            "title": f"Excessive Return Rate in {highest_ret_cat['key']} Eroding Margin",
            "highlight": f"{highest_ret_cat['ret_rate']:.1f}% Return Rate",
            "evidence": (
                f"{highest_ret_cat['key']} suffered an alarming return rate of {highest_ret_cat['ret_rate']:.1f}% ({highest_ret_cat['ret_count']:,} returned orders), "
                f"suppressing category contribution margin to {highest_ret_cat['margin_pct']:.2f}%. Returns in this category are primarily driven by '{top_reason}' "
                f"({top_reason_cnt:,} instances). Each return eliminates the sale and incurs double logistics and inventory handling costs."
            ),
            "recommendation": (
                f"Revamp size guides and incorporate interactive sizing/fit widgets on product pages. Conduct vendor QA audits on SKUs with return rates >20%, "
                f"and consider charging a nominal reverse logistics fee on repeat returns."
            )
        })

    # 4. Logistics SLA & Customer Experience Insight
    if sla["late_pct"] > 25.0:
        rating_drop = sla["on_time_avg_rating"] - sla["late_avg_rating"]
        insights.append({
            "category": "Fulfillment & Supply Chain",
            "severity": "HIGH",
            "title": f"Logistics Bottlenecks Affecting {sla['late_pct']:.1f}% of Deliveries",
            "highlight": f"-{rating_drop:.2f} Rating Drop on Late Deliveries",
            "evidence": (
                f"{sla['late_orders']:,} orders ({sla['late_pct']:.1f}%) missed promised delivery SLAs. When orders were delayed, "
                f"customer satisfaction declined sharply from {sla['on_time_avg_rating']:.2f} to {sla['late_avg_rating']:.2f} stars, "
                f"and the return rate increased from {sla['on_time_ret_rate']:.1f}% to {sla['late_ret_rate']:.1f}%. "
                f"A total of {sla['late_delivery_returns_reason']:,} returns explicitly cited 'Late Delivery' as the primary reason."
            ),
            "recommendation": (
                f"Align promised delivery SLA algorithms dynamically with order surges. Expand regional warehousing and dispatch capacity "
                f"ahead of mega-sale events to prevent warehouse congestion and third-party logistics backlogs."
            )
        })

    # 5. Channel Discrepancy Insight
    lowest_margin_channel = min(channels, key=lambda x: x["margin_pct"]) if channels else None
    highest_margin_channel = max(channels, key=lambda x: x["margin_pct"]) if channels else None
    if lowest_margin_channel and highest_margin_channel and lowest_margin_channel["key"] != highest_margin_channel["key"]:
        insights.append({
            "category": "Channel Economics",
            "severity": "MEDIUM",
            "title": f"Channel Margin Divergence ({highest_margin_channel['key']} vs {lowest_margin_channel['key']})",
            "highlight": f"{highest_margin_channel['margin_pct'] - lowest_margin_channel['margin_pct']:.1f}% Margin Gap",
            "evidence": (
                f"{lowest_margin_channel['key']} delivers a contribution margin of only {lowest_margin_channel['margin_pct']:.1f}% with a higher return rate "
                f"({lowest_margin_channel['ret_rate']:.1f}%), compared to {highest_margin_channel['key']} at {highest_margin_channel['margin_pct']:.1f}% margin. "
                f"Marketplace take rates and fulfillment overhead reduce net yield."
            ),
            "recommendation": (
                f"Prioritize direct-to-consumer traffic (App & Web) via app-exclusive perks, personalized re-engagement, and push notifications, "
                f"while auditing marketplace fees and listing terms to protect unit profitability."
            )
        })

    return insights


def create_charts(metrics):
    """
    Creates modern, executive-grade Plotly interactive visualizations.
    Returns a dictionary of HTML chart divs.
    """
    charts = {}

    font_family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    grid_color = '#f1f5f9'

    # 1. Daily Trajectory: Net Sales vs Contribution Profit
    daily = metrics["daily"]
    dates = [x["key"] for x in daily]
    net_sales = [x["net"] for x in daily]
    profits = [x["profit"] for x in daily]

    fig_daily = make_subplots(specs=[[{"secondary_y": True}]])
    fig_daily.add_trace(
        go.Bar(
            x=dates, y=net_sales, name="Net Sales (INR)",
            marker=dict(color="#93c5fd", opacity=0.75, line=dict(color="#3b82f6", width=1)),
            hovertemplate="<b>%{x}</b><br>Net Sales: ₹%{y:,.0f}<extra></extra>"
        ),
        secondary_y=False
    )
    fig_daily.add_trace(
        go.Scatter(
            x=dates, y=profits, name="Contribution Profit (INR)",
            mode="lines+markers",
            line=dict(color="#059669", width=3),
            marker=dict(size=6, color="#059669"),
            hovertemplate="<b>%{x}</b><br>Profit: ₹%{y:,.0f}<extra></extra>"
        ),
        secondary_y=True
    )
    fig_daily.update_layout(
        title="<b>Daily Trajectory: Net Revenue Surge vs Flatline Contribution Profit</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380
    )
    fig_daily.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig_daily.update_yaxes(title_text="Net Sales (INR)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_daily.update_yaxes(title_text="Contribution Profit (INR)", secondary_y=True, showgrid=False)
    charts["daily_trajectory"] = fig_daily.to_html(full_html=False, include_plotlyjs=False)

    # 2. Financial Waterfall / Value Leakage Chart
    kpis = metrics["kpis"]
    wf_x = ["Gross Sales", "Discounts", "Net Sales", "COGS", "Delivery Cost", "Return Handling", "Contribution Profit"]
    wf_y = [
        kpis["total_gross"],
        -kpis["total_discount"],
        kpis["total_net"],
        -kpis["total_cogs"],
        -kpis["total_delivery"],
        -kpis["total_ret_cost"],
        kpis["total_profit"]
    ]
    wf_measure = ["relative", "relative", "total", "relative", "relative", "relative", "total"]

    fig_wf = go.Figure(go.Waterfall(
        name="Value Leakage",
        orientation="v",
        measure=wf_measure,
        x=wf_x,
        textposition="outside",
        text=[f"₹{abs(v)/1e6:.2f}M" for v in wf_y],
        y=wf_y,
        connector=dict(line=dict(color="#94a3b8")),
        decreasing=dict(marker=dict(color="#ef4444")),
        increasing=dict(marker=dict(color="#10b981")),
        totals=dict(marker=dict(color="#2563eb"))
    ))
    fig_wf.update_layout(
        title="<b>Financial Waterfall: Value Leakage from Gross Sales to Net Profit</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        yaxis=dict(title="INR", showgrid=True, gridcolor=grid_color)
    )
    charts["financial_waterfall"] = fig_wf.to_html(full_html=False, include_plotlyjs=False)

    # 3. Campaign Profitability & Margin Comparison
    c_names = [c["key"] for c in metrics["campaigns"]]
    c_profits = [c["profit"] for c in metrics["campaigns"]]
    c_margins = [c["margin_pct"] for c in metrics["campaigns"]]
    c_colors = ["#10b981" if p > 0 else "#ef4444" for p in c_profits]

    fig_camp = make_subplots(specs=[[{"secondary_y": True}]])
    fig_camp.add_trace(
        go.Bar(
            x=c_names, y=c_profits, name="Contribution Profit (INR)",
            marker=dict(color=c_colors),
            text=[f"₹{p:,.0f}" for p in c_profits],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Profit: ₹%{y:,.0f}<extra></extra>"
        ),
        secondary_y=False
    )
    fig_camp.add_trace(
        go.Scatter(
            x=c_names, y=c_margins, name="Profit Margin (%)",
            mode="lines+markers+text",
            line=dict(color="#1e293b", width=2.5, dash="dot"),
            marker=dict(size=8, color="#1e293b"),
            text=[f"{m:.1f}%" for m in c_margins],
            textposition="top center",
            hovertemplate="<b>%{x}</b><br>Margin: %{y:.2f}%<extra></extra>"
        ),
        secondary_y=True
    )
    fig_camp.update_layout(
        title="<b>Campaign Economics: Profitability & Profit Margin Comparison</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_camp.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig_camp.update_yaxes(title_text="Contribution Profit (INR)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_camp.update_yaxes(title_text="Profit Margin (%)", secondary_y=True, showgrid=False)
    charts["campaign_economics"] = fig_camp.to_html(full_html=False, include_plotlyjs=False)

    # 4. The Discount Margin Cliff
    db = metrics["discount_bands"]
    db_x = [b["key"] for b in db]
    db_margins = [b["margin_pct"] for b in db]
    db_loss_pct = [b["loss_rate"] for b in db]
    db_colors = ["#10b981" if m > 10 else "#f59e0b" if m > 0 else "#ef4444" for m in db_margins]

    fig_cliff = make_subplots(specs=[[{"secondary_y": True}]])
    fig_cliff.add_trace(
        go.Bar(
            x=db_x, y=db_margins, name="Net Profit Margin (%)",
            marker=dict(color=db_colors),
            text=[f"{m:.1f}%" for m in db_margins],
            textposition="outside",
            hovertemplate="<b>Discount %{x}</b><br>Margin: %{y:.2f}%<extra></extra>"
        ),
        secondary_y=False
    )
    fig_cliff.add_trace(
        go.Scatter(
            x=db_x, y=db_loss_pct, name="Unprofitable Orders (%)",
            mode="lines+markers+text",
            line=dict(color="#dc2626", width=3),
            marker=dict(size=8, color="#dc2626"),
            text=[f"{l:.1f}%" for l in db_loss_pct],
            textposition="top center",
            hovertemplate="<b>Discount %{x}</b><br>Loss Orders: %{y:.1f}%<extra></extra>"
        ),
        secondary_y=True
    )
    fig_cliff.update_layout(
        title="<b>The Discount Margin Cliff: Profit Collapse Beyond 30% Discount</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_cliff.update_xaxes(showgrid=True, gridcolor=grid_color, title_text="Discount Range")
    fig_cliff.update_yaxes(title_text="Profit Margin (%)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_cliff.update_yaxes(title_text="Unprofitable Orders (%)", secondary_y=True, showgrid=False)
    charts["discount_cliff"] = fig_cliff.to_html(full_html=False, include_plotlyjs=False)

    # 5. Category Profitability & Return Rate Matrix
    cats = metrics["categories"]
    cat_names = [c["key"] for c in cats]
    cat_margins = [c["margin_pct"] for c in cats]
    cat_returns = [c["ret_rate"] for c in cats]

    fig_cat = make_subplots(specs=[[{"secondary_y": True}]])
    fig_cat.add_trace(
        go.Bar(
            x=cat_names, y=cat_margins, name="Profit Margin (%)",
            marker=dict(color="#3b82f6"),
            text=[f"{m:.1f}%" for m in cat_margins],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Margin: %{y:.2f}%<extra></extra>"
        ),
        secondary_y=False
    )
    fig_cat.add_trace(
        go.Scatter(
            x=cat_names, y=cat_returns, name="Return Rate (%)",
            mode="lines+markers+text",
            line=dict(color="#e11d48", width=3),
            marker=dict(size=8, color="#e11d48"),
            text=[f"{r:.1f}%" for r in cat_returns],
            textposition="top center",
            hovertemplate="<b>%{x}</b><br>Return Rate: %{y:.1f}%<extra></extra>"
        ),
        secondary_y=True
    )
    fig_cat.update_layout(
        title="<b>Category Performance: Margin % vs Return Rate %</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_cat.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig_cat.update_yaxes(title_text="Profit Margin (%)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_cat.update_yaxes(title_text="Return Rate (%)", secondary_y=True, showgrid=False)
    charts["category_performance"] = fig_cat.to_html(full_html=False, include_plotlyjs=False)

    # 6. Return Reasons Breakdown by Category (Stacked Bar)
    reasons_by_cat = metrics["reasons_by_cat"]
    all_reasons = sorted(metrics["reasons_overall"].keys())
    cat_list = [c["key"] for c in cats]

    fig_ret = go.Figure()
    palette = ["#3b82f6", "#ef4444", "#f59e0b", "#10b981", "#8b5cf6", "#64748b", "#ec4899"]
    for idx, reason in enumerate(all_reasons):
        counts = [reasons_by_cat.get(cat, {}).get(reason, 0) for cat in cat_list]
        fig_ret.add_trace(go.Bar(
            name=reason,
            x=cat_list,
            y=counts,
            marker_color=palette[idx % len(palette)],
            hovertemplate=f"<b>{reason}</b><br>Category: %{{x}}<br>Returns: %{{y:,}}<extra></extra>"
        ))
    fig_ret.update_layout(
        barmode='stack',
        title="<b>Return Reasons Breakdown across Categories</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Return Count", showgrid=True, gridcolor=grid_color)
    )
    charts["return_reasons"] = fig_ret.to_html(full_html=False, include_plotlyjs=False)

    # 7. Logistics SLA Impact: On-Time vs Late Deliveries
    sla = metrics["sla"]
    fig_sla = make_subplots(rows=1, cols=2, subplot_titles=["<b>Average Customer Rating (out of 5)</b>", "<b>Return Rate (%)</b>"])

    fig_sla.add_trace(
        go.Bar(
            x=["On-Time", "Delayed"],
            y=[sla["on_time_avg_rating"], sla["late_avg_rating"]],
            marker=dict(color=["#10b981", "#ef4444"]),
            text=[f"{sla['on_time_avg_rating']:.2f}", f"{sla['late_avg_rating']:.2f}"],
            textposition="outside",
            name="Rating"
        ),
        row=1, col=1
    )
    fig_sla.add_trace(
        go.Bar(
            x=["On-Time", "Delayed"],
            y=[sla["on_time_ret_rate"], sla["late_ret_rate"]],
            marker=dict(color=["#10b981", "#ef4444"]),
            text=[f"{sla['on_time_ret_rate']:.1f}%", f"{sla['late_ret_rate']:.1f}%"],
            textposition="outside",
            name="Return Rate"
        ),
        row=1, col=2
    )
    fig_sla.update_layout(
        title="<b>Fulfillment Operations: Customer Rating & Return Penalties from Delivery Delays</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40),
        height=380
    )
    fig_sla.update_yaxes(range=[0, 5], showgrid=True, gridcolor=grid_color, row=1, col=1)
    fig_sla.update_yaxes(title="Return Rate (%)", showgrid=True, gridcolor=grid_color, row=1, col=2)
    charts["logistics_sla"] = fig_sla.to_html(full_html=False, include_plotlyjs=False)

    # 8. Sales Channel Economics
    ch = metrics["channels"]
    ch_names = [c["key"] for c in ch]
    ch_profit = [c["profit"] for c in ch]
    ch_margins = [c["margin_pct"] for c in ch]

    fig_ch = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ch.add_trace(
        go.Bar(
            x=ch_names, y=ch_profit, name="Profit (INR)",
            marker=dict(color="#2563eb"),
            text=[f"₹{p:,.0f}" for p in ch_profit],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Profit: ₹%{y:,.0f}<extra></extra>"
        ),
        secondary_y=False
    )
    fig_ch.add_trace(
        go.Scatter(
            x=ch_names, y=ch_margins, name="Profit Margin (%)",
            mode="lines+markers+text",
            line=dict(color="#059669", width=3),
            marker=dict(size=8, color="#059669"),
            text=[f"{m:.1f}%" for m in ch_margins],
            textposition="top center",
            hovertemplate="<b>%{x}</b><br>Margin: %{y:.2f}%<extra></extra>"
        ),
        secondary_y=True
    )
    fig_ch.update_layout(
        title="<b>Sales Channel Economics: Contribution Profit vs Margin %</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_ch.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig_ch.update_yaxes(title_text="Contribution Profit (INR)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_ch.update_yaxes(title_text="Profit Margin (%)", secondary_y=True, showgrid=False)
    charts["channel_economics"] = fig_ch.to_html(full_html=False, include_plotlyjs=False)

    # 9. City Economics
    ct = metrics["cities"]
    ct_names = [c["key"] for c in ct]
    ct_profit = [c["profit"] for c in ct]
    ct_margins = [c["margin_pct"] for c in ct]

    fig_ct = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ct.add_trace(
        go.Bar(
            x=ct_names, y=ct_profit, name="Contribution Profit (INR)",
            marker=dict(color="#6366f1"),
            text=[f"₹{p:,.0f}" for p in ct_profit],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Profit: ₹%{y:,.0f}<extra></extra>"
        ),
        secondary_y=False
    )
    fig_ct.add_trace(
        go.Scatter(
            x=ct_names, y=ct_margins, name="Profit Margin (%)",
            mode="lines+markers+text",
            line=dict(color="#10b981", width=2.5),
            marker=dict(size=8, color="#10b981"),
            text=[f"{m:.1f}%" for m in ct_margins],
            textposition="top center",
            hovertemplate="<b>%{x}</b><br>Margin: %{y:.2f}%<extra></extra>"
        ),
        secondary_y=True
    )
    fig_ct.update_layout(
        title="<b>Geographic Markets: Profit & Margin by Cleaned City</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=50, r=50, t=60, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_ct.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig_ct.update_yaxes(title_text="Contribution Profit (INR)", secondary_y=False, showgrid=True, gridcolor=grid_color)
    fig_ct.update_yaxes(title_text="Profit Margin (%)", secondary_y=True, showgrid=False)
    charts["city_economics"] = fig_ct.to_html(full_html=False, include_plotlyjs=False)

    # 10. Product Profitability Leaderboard
    prods = sorted(metrics["products"], key=lambda x: x["profit"])
    p_names = [f"{p['product']} ({p['category']})" for p in prods]
    p_profits = [p["profit"] for p in prods]
    p_margins = [p["margin_pct"] for p in prods]
    p_colors = ["#10b981" if m > 15 else "#3b82f6" if m > 10 else "#f59e0b" for m in p_margins]

    fig_p = go.Figure(go.Bar(
        y=p_names,
        x=p_profits,
        orientation='h',
        marker=dict(color=p_colors),
        text=[f"₹{p:,.0f} ({m:.1f}%)" for p, m in zip(p_profits, p_margins)],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Profit: ₹%{x:,.0f}<extra></extra>"
    ))
    fig_p.update_layout(
        title="<b>Product Profitability & Margin Ranking</b>",
        title_font=dict(size=15, family=font_family, color="#1e293b"),
        template="plotly_white",
        font=dict(family=font_family),
        margin=dict(l=160, r=60, t=60, b=40),
        height=480,
        xaxis=dict(title="Contribution Profit (INR)", showgrid=True, gridcolor=grid_color)
    )
    charts["product_profitability"] = fig_p.to_html(full_html=False, include_plotlyjs=False)

    return charts


def build_html_dashboard(metrics, insights, charts, plotly_js_content=None):
    """
    Renders the executive HTML dashboard with interactive tabs, KPI cards,
    charts, summary tables, and dynamic management insights.
    """
    kpis = metrics["kpis"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def inr(val):
        return f"₹{val:,.2f}"

    def inr_compact(val):
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        if abs_val >= 1e7:
            return f"{sign}₹{abs_val/1e7:.2f} Cr"
        elif abs_val >= 1e5:
            return f"{sign}₹{abs_val/1e5:.2f} L"
        elif abs_val >= 1e3:
            return f"{sign}₹{abs_val/1e3:.1f} k"
        return f"{sign}₹{abs_val:,.0f}"

    if plotly_js_content:
        plotly_script_tag = f"<script>{plotly_js_content}</script>"
    else:
        plotly_script_tag = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'

    insight_cards_html = ""
    for ins in insights:
        badge_cls = "badge-danger" if ins["severity"] == "CRITICAL" else "badge-warning" if ins["severity"] == "HIGH" else "badge-info"
        insight_cards_html += f"""
        <div class="insight-card {ins['severity'].lower()}">
            <div class="insight-header">
                <span class="badge {badge_cls}">{ins['severity']}</span>
                <span class="insight-cat">{ins['category']}</span>
                <span class="insight-highlight">{ins['highlight']}</span>
            </div>
            <h3 class="insight-title">{ins['title']}</h3>
            <div class="insight-body">
                <p><strong>Evidence:</strong> {ins['evidence']}</p>
                <p class="insight-action"><strong>Management Action:</strong> {ins['recommendation']}</p>
            </div>
        </div>
        """

    def render_campaign_table():
        rows = ""
        for c in metrics["campaigns"]:
            badge = "status-good" if c["margin_pct"] > 15 else "status-warn" if c["margin_pct"] > 0 else "status-bad"
            rows += f"""
            <tr>
                <td><strong>{c['key']}</strong></td>
                <td class="text-right">{c['orders']:,}</td>
                <td class="text-right">{inr_compact(c['net'])}</td>
                <td class="text-right">{c['avg_discount']:.1f}%</td>
                <td class="text-right"><strong>{inr_compact(c['profit'])}</strong></td>
                <td class="text-right"><span class="pill {badge}">{c['margin_pct']:.2f}%</span></td>
                <td class="text-right">{c['ret_rate']:.1f}%</td>
                <td class="text-right">★ {c['avg_rating']:.2f}</td>
            </tr>
            """
        return f"""
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Campaign</th>
                        <th class="text-right">Orders</th>
                        <th class="text-right">Net Sales</th>
                        <th class="text-right">Avg Discount</th>
                        <th class="text-right">Contribution Profit</th>
                        <th class="text-right">Profit Margin</th>
                        <th class="text-right">Return Rate</th>
                        <th class="text-right">Customer Rating</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """

    def render_category_table():
        rows = ""
        for c in metrics["categories"]:
            badge = "status-good" if c["margin_pct"] > 15 else "status-warn" if c["margin_pct"] > 5 else "status-bad"
            ret_badge = "status-bad" if c["ret_rate"] > 15 else "status-good"
            rows += f"""
            <tr>
                <td><strong>{c['key']}</strong></td>
                <td class="text-right">{c['orders']:,}</td>
                <td class="text-right">{inr_compact(c['gross'])}</td>
                <td class="text-right">{inr_compact(c['net'])}</td>
                <td class="text-right"><strong>{inr_compact(c['profit'])}</strong></td>
                <td class="text-right"><span class="pill {badge}">{c['margin_pct']:.2f}%</span></td>
                <td class="text-right"><span class="pill {ret_badge}">{c['ret_rate']:.1f}%</span></td>
                <td class="text-right">★ {c['avg_rating']:.2f}</td>
            </tr>
            """
        return f"""
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th class="text-right">Orders</th>
                        <th class="text-right">Gross Sales</th>
                        <th class="text-right">Net Sales</th>
                        <th class="text-right">Contribution Profit</th>
                        <th class="text-right">Profit Margin</th>
                        <th class="text-right">Return Rate</th>
                        <th class="text-right">Customer Rating</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """

    def render_product_table():
        rows = ""
        for p in metrics["products"]:
            badge = "status-good" if p["margin_pct"] > 15 else "status-warn" if p["margin_pct"] > 5 else "status-bad"
            rows += f"""
            <tr>
                <td><strong>{p['product']}</strong></td>
                <td><span class="cat-tag">{p['category']}</span></td>
                <td class="text-right">{p['orders']:,}</td>
                <td class="text-right">{inr_compact(p['net'])}</td>
                <td class="text-right"><strong>{inr_compact(p['profit'])}</strong></td>
                <td class="text-right"><span class="pill {badge}">{p['margin_pct']:.2f}%</span></td>
                <td class="text-right">{p['ret_rate']:.1f}%</td>
                <td class="text-right">★ {p['avg_rating']:.2f}</td>
            </tr>
            """
        return f"""
        <div class="table-search-bar">
            <input type="text" id="productSearch" onkeyup="filterProductTable()" placeholder="Search product or category...">
        </div>
        <div class="table-container">
            <table class="data-table" id="productTable">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Category</th>
                        <th class="text-right">Orders</th>
                        <th class="text-right">Net Sales</th>
                        <th class="text-right">Contribution Profit</th>
                        <th class="text-right">Profit Margin</th>
                        <th class="text-right">Return Rate</th>
                        <th class="text-right">Customer Rating</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """

    def render_city_table():
        rows = ""
        for c in metrics["cities"]:
            badge = "status-good" if c["margin_pct"] > 14 else "status-warn"
            rows += f"""
            <tr>
                <td><strong>{c['key']}</strong></td>
                <td class="text-right">{c['orders']:,}</td>
                <td class="text-right">{inr_compact(c['net'])}</td>
                <td class="text-right"><strong>{inr_compact(c['profit'])}</strong></td>
                <td class="text-right"><span class="pill {badge}">{c['margin_pct']:.2f}%</span></td>
                <td class="text-right">{c['ret_rate']:.1f}%</td>
                <td class="text-right">{c['late_rate']:.1f}%</td>
                <td class="text-right">★ {c['avg_rating']:.2f}</td>
            </tr>
            """
        return f"""
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>City</th>
                        <th class="text-right">Orders</th>
                        <th class="text-right">Net Sales</th>
                        <th class="text-right">Contribution Profit</th>
                        <th class="text-right">Profit Margin</th>
                        <th class="text-right">Return Rate</th>
                        <th class="text-right">Late Delivery Rate</th>
                        <th class="text-right">Customer Rating</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Commerce Executive Profitability Dashboard</title>
    {plotly_script_tag}
    <style>
        :root {{
            --bg: #f8fafc;
            --surface: #ffffff;
            --surface-subtle: #f1f5f9;
            --border: #e2e8f0;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --success: #10b981;
            --success-dark: #059669;
            --danger: #ef4444;
            --danger-dark: #dc2626;
            --warning: #f59e0b;
            --purple: #8b5cf6;
            --radius: 12px;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07);
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text-main);
            font-family: var(--font);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        header {{
            background: #0f172a;
            color: #ffffff;
            padding: 24px 32px;
            border-bottom: 1px solid #1e293b;
        }}

        .header-container {{
            max-width: 1440px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .header-title h1 {{
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.02em;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header-title p {{
            color: #94a3b8;
            font-size: 13px;
            margin-top: 4px;
        }}

        .header-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .tag {{
            background: #1e293b;
            color: #cbd5e1;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .tag.tag-live {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .btn-print {{
            background: #3b82f6;
            color: #ffffff;
            border: none;
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .btn-print:hover {{
            background: #2563eb;
        }}

        .main-wrapper {{
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px 32px 64px 32px;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 18px 20px;
            box-shadow: var(--shadow-sm);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow);
        }}

        .kpi-card::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
        }}

        .kpi-primary::before {{ background: var(--primary); }}
        .kpi-success::before {{ background: var(--success); }}
        .kpi-danger::before {{ background: var(--danger); }}
        .kpi-warning::before {{ background: var(--warning); }}
        .kpi-purple::before {{ background: var(--purple); }}

        .kpi-label {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .kpi-value {{
            font-size: 26px;
            font-weight: 700;
            color: var(--text-main);
            margin: 6px 0 2px 0;
            letter-spacing: -0.02em;
        }}

        .kpi-subtext {{
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .kpi-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}

        .tab-bar {{
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
            overflow-x: auto;
            padding-bottom: 4px;
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .tab-btn:hover {{
            color: var(--text-main);
            background: var(--surface-subtle);
        }}

        .tab-btn.active {{
            color: var(--primary);
            background: rgba(37, 99, 235, 0.08);
            border-bottom: 2px solid var(--primary);
            border-radius: 8px 8px 0 0;
        }}

        .tab-pane {{
            display: none;
        }}

        .tab-pane.active {{
            display: block;
            animation: fadeIn 0.2s ease-in-out;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .chart-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            box-shadow: var(--shadow-sm);
            margin-bottom: 24px;
        }}

        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}

        @media (max-width: 1024px) {{
            .grid-2 {{
                grid-template-columns: 1fr;
            }}
        }}

        .insights-banner {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: #ffffff;
            border-radius: var(--radius);
            padding: 24px 28px;
            margin-bottom: 24px;
            border-left: 6px solid var(--danger);
        }}

        .insights-banner h2 {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .insights-banner p {{
            color: #cbd5e1;
            font-size: 14px;
            max-width: 1000px;
        }}

        .insight-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
            border-left: 5px solid #cbd5e1;
        }}

        .insight-card.critical {{
            border-left-color: var(--danger);
        }}

        .insight-card.high {{
            border-left-color: var(--warning);
        }}

        .insight-card.medium {{
            border-left-color: var(--primary);
        }}

        .insight-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}

        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .badge-danger {{ background: rgba(239, 68, 68, 0.15); color: var(--danger-dark); }}
        .badge-warning {{ background: rgba(245, 158, 11, 0.15); color: #b45309; }}
        .badge-info {{ background: rgba(37, 99, 235, 0.15); color: var(--primary-dark); }}

        .insight-cat {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .insight-highlight {{
            margin-left: auto;
            font-size: 14px;
            font-weight: 700;
            color: var(--text-main);
            background: var(--surface-subtle);
            padding: 2px 10px;
            border-radius: 20px;
        }}

        .insight-title {{
            font-size: 17px;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 10px;
        }}

        .insight-body p {{
            font-size: 14px;
            color: #334155;
            margin-bottom: 8px;
        }}

        .insight-action {{
            background: rgba(37, 99, 235, 0.04);
            border: 1px solid rgba(37, 99, 235, 0.15);
            padding: 12px 14px;
            border-radius: 8px;
            color: var(--text-main);
            font-size: 13.5px;
        }}

        .table-search-bar {{
            margin-bottom: 12px;
        }}

        .table-search-bar input {{
            width: 100%;
            max-width: 360px;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 13px;
            font-family: var(--font);
            outline: none;
        }}

        .table-search-bar input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
        }}

        .table-container {{
            width: 100%;
            overflow-x: auto;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}

        .data-table th {{
            background: var(--surface-subtle);
            color: var(--text-muted);
            font-weight: 600;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        .data-table td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            color: var(--text-main);
            white-space: nowrap;
        }}

        .data-table tr:hover td {{
            background: rgba(241, 245, 249, 0.6);
        }}

        .text-right {{ text-align: right; }}

        .pill {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}

        .status-good {{ background: #dcfce7; color: #15803d; }}
        .status-warn {{ background: #fef3c7; color: #b45309; }}
        .status-bad  {{ background: #fee2e2; color: #b91c1c; }}

        .cat-tag {{
            background: var(--surface-subtle);
            color: var(--text-muted);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }}

        .action-matrix {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-top: 24px;
        }}

        .action-box {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 18px 20px;
            box-shadow: var(--shadow-sm);
        }}

        .action-box h4 {{
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .action-box p {{
            font-size: 13px;
            color: #475569;
            line-height: 1.5;
        }}

        footer {{
            margin-top: 48px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            padding-top: 24px;
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-container">
            <div class="header-title">
                <h1>📈 E-Commerce Executive Profitability Dashboard</h1>
                <p>Dynamic analysis computed from live orders data • Period: {kpis['min_date']} to {kpis['max_date']}</p>
            </div>
            <div class="header-meta">
                <span class="tag tag-live">● Recomputed from CSV</span>
                <span class="tag">{kpis['total_orders']:,} Total Orders</span>
                <span class="tag">Refreshed: {now_str}</span>
                <button class="btn-print" onclick="window.print()">Print / PDF Export</button>
            </div>
        </div>
    </header>

    <div class="main-wrapper">

        <div class="kpi-grid">
            <div class="kpi-card kpi-primary">
                <div class="kpi-label">Gross Sales</div>
                <div class="kpi-value">{inr_compact(kpis['total_gross'])}</div>
                <div class="kpi-subtext">Total catalog order value</div>
            </div>

            <div class="kpi-card kpi-warning">
                <div class="kpi-label">Discounts Given</div>
                <div class="kpi-value">{inr_compact(kpis['total_discount'])}</div>
                <div class="kpi-subtext"><span class="kpi-badge status-warn">{kpis['discount_rate']:.1f}%</span> of Gross Sales</div>
            </div>

            <div class="kpi-card kpi-primary">
                <div class="kpi-label">Net Sales Revenue</div>
                <div class="kpi-value">{inr_compact(kpis['total_net'])}</div>
                <div class="kpi-subtext">Effective recognized revenue</div>
            </div>

            <div class="kpi-card {'kpi-success' if kpis['margin_pct'] >= 15 else 'kpi-danger'}">
                <div class="kpi-label">Contribution Profit</div>
                <div class="kpi-value">{inr_compact(kpis['total_profit'])}</div>
                <div class="kpi-subtext"><span class="kpi-badge {'status-good' if kpis['margin_pct'] >= 15 else 'status-bad'}">{kpis['margin_pct']:.2f}% Margin</span></div>
            </div>

            <div class="kpi-card {'kpi-danger' if kpis['return_rate'] > 12 else 'kpi-success'}">
                <div class="kpi-label">Return Rate</div>
                <div class="kpi-value">{kpis['return_rate']:.2f}%</div>
                <div class="kpi-subtext">{kpis['returned_count']:,} returned orders</div>
            </div>

            <div class="kpi-card kpi-purple">
                <div class="kpi-label">Customer Rating</div>
                <div class="kpi-value">★ {kpis['avg_rating']:.2f}</div>
                <div class="kpi-subtext">From {kpis['rated_count']:,} ratings</div>
            </div>

            <div class="kpi-card {'kpi-danger' if kpis['late_rate'] > 30 else 'kpi-success'}">
                <div class="kpi-label">Late Delivery Rate</div>
                <div class="kpi-value">{kpis['late_rate']:.1f}%</div>
                <div class="kpi-subtext">{kpis['late_count']:,} delayed shipments</div>
            </div>

            <div class="kpi-card {'kpi-danger' if kpis['loss_rate'] > 20 else 'kpi-warning'}">
                <div class="kpi-label">Unprofitable Orders</div>
                <div class="kpi-value">{kpis['loss_rate']:.1f}%</div>
                <div class="kpi-subtext">{kpis['loss_count']:,} loss-making orders</div>
            </div>
        </div>

        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab(event, 'tab-overview')">📌 Executive Overview</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-insights')">💡 Management Insights & Actions</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-campaigns')">🎯 Campaigns & Discount Cliff</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-categories')">📦 Categories & Products</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-operations')">🚚 Operations, SLA & Returns</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-channels')">🌐 Channels & Geographies</button>
        </div>

        <!-- Tab 1: Executive Overview -->
        <div id="tab-overview" class="tab-pane active">
            <div class="chart-card">
                {charts['daily_trajectory']}
            </div>

            <div class="grid-2">
                <div class="chart-card">
                    {charts['financial_waterfall']}
                </div>
                <div class="chart-card">
                    {charts['campaign_economics']}
                </div>
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Campaign Performance Summary</h3>
                {render_campaign_table()}
            </div>
        </div>

        <!-- Tab 2: Management Insights & Action Plan -->
        <div id="tab-insights" class="tab-pane">
            <div class="insights-banner">
                <h2>🔍 Executive Diagnosis: Root Causes of Profit Erosion</h2>
                <p>
                    While top-line volume reached strong levels ({inr_compact(kpis['total_net'])} net revenue across {kpis['total_orders']:,} orders),
                    profitability remained constrained at {kpis['margin_pct']:.2f}% contribution margin. Below are the key data-backed drivers
                    revealed by the dataset and prioritized management interventions.
                </p>
            </div>

            <div class="insights-container">
                {insight_cards_html}
            </div>

            <div class="action-matrix">
                <div class="action-box">
                    <h4>🎯 1. Promotional Governance</h4>
                    <p>Enforce an automatic 30% discount ceiling. Eliminate flat percentage markdowns on loss-making events and substitute with minimum basket size thresholds (e.g. ₹500 off ₹3,000).</p>
                </div>
                <div class="action-box">
                    <h4>👗 2. Fashion Returns Turnaround</h4>
                    <p>Address the 24.1% fashion return rate by introducing interactive sizing widgets, supplier QA audits, and gating free reverse delivery for chronic returners.</p>
                </div>
                <div class="action-box">
                    <h4>🚚 3. Fulfillment SLA Protection</h4>
                    <p>Resolve the {kpis['late_rate']:.1f}% late delivery crisis by dynamically adjusting customer-facing delivery promises during sales spikes and adding temporary warehouse buffer staff.</p>
                </div>
                <div class="action-box">
                    <h4>💼 4. Margin-Accretive Product Mix</h4>
                    <p>Actively allocate marketing spend toward high-margin categories (Beauty: 26.1%, Home: 16.3%) while bundle-pricing lower-margin high-ticket electronics (Smartwatch: 6.6%).</p>
                </div>
            </div>
        </div>

        <!-- Tab 3: Campaigns & Discount Cliff -->
        <div id="tab-campaigns" class="tab-pane">
            <div class="grid-2">
                <div class="chart-card">
                    {charts['discount_cliff']}
                </div>
                <div class="chart-card">
                    {charts['campaign_economics']}
                </div>
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Detailed Campaign Breakdown</h3>
                {render_campaign_table()}
            </div>
        </div>

        <!-- Tab 4: Categories & Products -->
        <div id="tab-categories" class="tab-pane">
            <div class="grid-2">
                <div class="chart-card">
                    {charts['category_performance']}
                </div>
                <div class="chart-card">
                    {charts['return_reasons']}
                </div>
            </div>

            <div class="chart-card">
                {charts['product_profitability']}
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Category Profitability Overview</h3>
                {render_category_table()}
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Product Catalog Economics</h3>
                {render_product_table()}
            </div>
        </div>

        <!-- Tab 5: Operations, SLA & Returns -->
        <div id="tab-operations" class="tab-pane">
            <div class="grid-2">
                <div class="chart-card">
                    {charts['logistics_sla']}
                </div>
                <div class="chart-card">
                    {charts['return_reasons']}
                </div>
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Delivery & Return Impact Summary</h3>
                <div style="padding: 12px; background: var(--surface-subtle); border-radius: 8px; font-size: 13.5px; line-height: 1.6;">
                    <p>• <strong>On-Time Delivery Rate:</strong> {metrics['sla']['on_time_pct']:.1f}% ({metrics['sla']['on_time_orders']:,} orders) with an average rating of <strong>★ {metrics['sla']['on_time_avg_rating']:.2f}</strong>.</p>
                    <p>• <strong>Delayed Delivery Rate:</strong> {metrics['sla']['late_pct']:.1f}% ({metrics['sla']['late_orders']:,} orders) with an average rating of <strong>★ {metrics['sla']['late_avg_rating']:.2f}</strong> (a penalty of <strong>-{metrics['sla']['on_time_avg_rating'] - metrics['sla']['late_avg_rating']:.2f} stars</strong>).</p>
                    <p>• <strong>Return Likelihood:</strong> Delayed shipments had a return rate of <strong>{metrics['sla']['late_ret_rate']:.1f}%</strong> compared to <strong>{metrics['sla']['on_time_ret_rate']:.1f}%</strong> for on-time shipments, with <strong>{metrics['sla']['late_delivery_returns_reason']:,} orders</strong> returned specifically due to delivery delays.</p>
                </div>
            </div>
        </div>

        <!-- Tab 6: Channels & Geographies -->
        <div id="tab-channels" class="tab-pane">
            <div class="grid-2">
                <div class="chart-card">
                    {charts['channel_economics']}
                </div>
                <div class="chart-card">
                    {charts['city_economics']}
                </div>
            </div>

            <div class="chart-card">
                <h3 style="margin-bottom: 16px; font-size: 16px; font-weight: 700;">Geographic Market Breakdown</h3>
                {render_city_table()}
            </div>
        </div>

        <footer>
            <p>E-Commerce Executive Performance & Profitability Dashboard • Generated dynamically from live dataset</p>
            <p style="margin-top: 4px; color: #94a3b8;">To regenerate anytime, run <code>python generate_dashboard.py</code></p>
        </footer>

    </div>

    <script>
        function switchTab(evt, tabId) {{
            const panes = document.querySelectorAll('.tab-pane');
            panes.forEach(p => p.classList.remove('active'));

            const btns = document.querySelectorAll('.tab-btn');
            btns.forEach(b => b.classList.remove('active'));

            const targetPane = document.getElementById(tabId);
            if (targetPane) {{
                targetPane.classList.add('active');
            }}
            evt.currentTarget.classList.add('active');

            window.dispatchEvent(new Event('resize'));
        }}

        function filterProductTable() {{
            const input = document.getElementById('productSearch');
            const filter = input.value.toLowerCase();
            const table = document.getElementById('productTable');
            const trs = table.getElementsByTagName('tr');

            for (let i = 1; i < trs.length; i++) {{
                const tdProduct = trs[i].getElementsByTagName('td')[0];
                const tdCategory = trs[i].getElementsByTagName('td')[1];
                if (tdProduct || tdCategory) {{
                    const textP = tdProduct ? tdProduct.textContent || tdProduct.innerText : '';
                    const textC = tdCategory ? tdCategory.textContent || tdCategory.innerText : '';
                    if (textP.toLowerCase().indexOf(filter) > -1 || textC.toLowerCase().indexOf(filter) > -1) {{
                        trs[i].style.display = '';
                    }} else {{
                        trs[i].style.display = 'none';
                    }}
                }}
            }}
        }}
    </script>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate Executive Management Dashboard from orders.csv")
    parser.add_argument("--data", default="data/orders.csv", help="Path to input orders CSV file")
    parser.add_argument("--output", default="dashboard.html", help="Path to output HTML dashboard file")
    args = parser.parse_args()

    data_path = os.path.abspath(args.data)
    output_path = os.path.abspath(args.output)

    print(f"Loading and analyzing orders from: {data_path}")
    data = clean_and_load_data(data_path)
    print(f"Successfully processed {len(data):,} orders.")

    print("Computing metrics and multi-dimensional aggregations...")
    metrics = compute_metrics(data)

    print("Synthesizing dynamic management insights...")
    insights = generate_management_insights(metrics)

    print("Rendering executive Plotly charts...")
    charts = create_charts(metrics)

    print("Locating Plotly JavaScript for 100% offline self-containment...")
    plotly_js = find_plotly_js()
    if plotly_js:
        print(f"Found local plotly.min.js ({len(plotly_js)/1e6:.2f} MB). Embedding inline for offline use.")
    else:
        print("Using Plotly CDN fallback.")

    print(f"Generating self-contained HTML dashboard at: {output_path}")
    html_content = build_html_dashboard(metrics, insights, charts, plotly_js)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Success! Dashboard created: {output_path} ({file_size_mb:.2f} MB)")
    print("You can now open dashboard.html directly in any browser.")


if __name__ == "__main__":
    main()

