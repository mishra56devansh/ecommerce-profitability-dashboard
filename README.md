# E-Commerce Executive Profitability & Performance Dashboard

An executive-grade, interactive management dashboard built to diagnose profitability challenges in e-commerce operations.

---

## 🚀 Quick Start: How to Run & Regenerate

Whenever `data/orders.csv` is updated or replaced with new data, regenerate the dashboard with a single command:

### Option 1: 1-Click Batch Runner (Windows)
Double-click `run_dashboard.bat` or run:
```cmd
run_dashboard.bat
```

### Option 2: Command Line (Python)
```cmd
.venv\Scripts\python generate_dashboard.py
```
Or with custom paths:
```cmd
.venv\Scripts\python generate_dashboard.py --data path/to/orders.csv --output custom_dashboard.html
```

Once generated, double-click `dashboard.html` to open it locally in any web browser (Chrome, Edge, Firefox, Safari).

---

## 💼 Executive Business Findings

Analysis of 30,000 orders (₹87.3M gross revenue, ₹67.5M net revenue) uncovered why profitability has been disappointing despite strong sales:

1. **The Promotional Margin Cliff**:
   - Discounts up to 20% generate 22%–30% net margin.
   - Discounts of 30%–40% compress margins to **0.47%** (near breakeven).
   - Discounts above 40% enter a **steep loss zone** (-27% to -50% margin), causing over ₹1.5M in direct losses.

2. **MegaFest Campaign Value Destruction**:
   - Generated 41.5% of total order volume (12,464 orders) and ₹24.2M net sales, but generated a **net loss of -₹201,445** (-0.83% margin).
   - In stark contrast, baseline ("No Campaign") orders delivered **₹7.39M in profit** at a 29.55% margin.
   - Peak operations handled 3.5x package volume for zero additional profit.

3. **Fashion Returns Crisis**:
   - Fashion suffered an alarming **24.15% return rate** (surging to **37.9%** during MegaFest), with size/fit (1,075 orders) and quality (395 orders) being the dominant drivers.
   - Each returned item wiped out the sale while incurring product cost write-down, outbound delivery, and reverse logistics handling fees.

4. **Logistics SLA Failure**:
   - **49.1% of all shipments were delayed** beyond promised SLAs during peak spikes.
   - Delayed deliveries suffered an immediate **-0.46 star drop in customer rating** (3.61 vs 4.07) and higher return rates (13.6% vs 11.7%), with 475 returns explicitly citing "Late Delivery".

5. **Channel & Product Imbalances**:
   - Marketplace channel produced significantly lower margins (10.48%) compared to App (14.91%) and Website (14.98%).
   - Smartwatch generated the highest revenue (₹9.73M) but only ₹645k in profit (6.64% margin) due to aggressive promotional discounts and high COGS.

---

## 🛠️ Prioritized Management Action Roadmap

1. **Promotional Governance**:
   - Enforce an automatic **30% discount ceiling** across all campaigns.
   - Phase out flat percentage markdowns during mega-events; transition to **minimum basket-size thresholds** (e.g., "₹500 off on ₹3,000+").
2. **Fashion Returns Intervention**:
   - Implement interactive sizing/fit widgets and AR sizing on product pages.
   - Conduct QA supplier audits on SKUs with return rates >20%.
   - Introduce nominal reverse logistics fees for chronic returners.
3. **Fulfillment SLA Optimization**:
   - Dynamically expand promised delivery windows during promotional volume surges to prevent customer expectation mismatch.
   - Add temporary flex warehouse capacity and pre-position inventory regionally.
4. **Channel & Assortment Strategy**:
   - Drive traffic to high-margin owned channels (App & Web) with exclusive perks.
   - Bundle low-margin high-ticket electronics (e.g. Smartwatches) with high-margin accessories.

---

## 💻 Technical Architecture & Design

- **100% Standalone & Self-Contained**: Generates a single `dashboard.html` file with embedded Plotly JS. Requires no server, no Streamlit/Dash background process, no database, and no external API.
- **Dynamic Calculation Engine**: Does not hardcode cities, categories, campaigns, dates, row counts, or insights. Every metric and insight is computed directly from whichever compatible dataset is provided.
- **Clean Data Handling**: Automatically standardizes city naming (e.g. "Bangalore" -> "Bengaluru"), trims whitespace, and validates numeric types without modifying the original source CSV.
- **Executive UI**: Clean typography, responsive KPI cards, interactive Plotly visualizations with unified hover tooltips, tabbed navigation, and catalog search tables.

