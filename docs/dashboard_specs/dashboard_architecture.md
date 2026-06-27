# Customer Finance 360° — Power BI Dashboard Architecture

This document serves as the blueprint for building the 5-page Power BI dashboard suite on top of the PostgreSQL data warehouse and Machine Learning outputs.

## 1. Data Model (Star Schema)

Connect Power BI to your local PostgreSQL instance (`localhost:5432`, db: `postgres`, schema: `customer360`).

### Import Mode vs DirectQuery
- **Import Mode**: Recommended for dimensions (`dim_customer`, `dim_date`, `dim_product`, `dim_campaign`) and ML outputs.
- **DirectQuery**: Recommended for `fact_transactions` if scaling beyond 10M rows. For this project's 1.5M rows, **Import Mode** is perfectly fine and will yield the best performance.

### Table Relationships
Set up the following relationships in the Power BI Model View (all Single direction, 1-to-Many):
- `dim_customer[customer_id]` -> `fact_transactions[customer_id]`
- `dim_date[date_key]` -> `fact_transactions[date_key]`
- `dim_product[product_id]` -> `fact_transactions[product_id]`
- `dim_customer[customer_id]` -> `fact_service_logs[customer_id]`
- `dim_customer[customer_id]` -> `fact_campaign_responses[customer_id]`
- `dim_campaign[campaign_id]` -> `fact_campaign_responses[campaign_id]`

**Machine Learning Integration**:
Load the two CSVs from `data/output/`:
- `churn_predictions.csv` -> Link `[customer_id]` to `dim_customer[customer_id]` (1-to-1)
- `customer_segments.csv` -> Link `[customer_id]` to `dim_customer[customer_id]` (1-to-1)

---

## 2. Core DAX Measures

Create a dedicated `_Measures` table to organize these calculations.

### Revenue & Transactions
```dax
Total Revenue = SUM(fact_transactions[amount])
Total Transactions = COUNTROWS(fact_transactions)
Avg Transaction Value = DIVIDE([Total Revenue], [Total Transactions], 0)
Revenue YoY% = DIVIDE([Total Revenue] - CALCULATE([Total Revenue], SAMEPERIODLASTYEAR(dim_date[full_date])), CALCULATE([Total Revenue], SAMEPERIODLASTYEAR(dim_date[full_date])))
```

### Customers & Churn
```dax
Total Customers = DISTINCTCOUNT(dim_customer[customer_id])
Active Customers = CALCULATE([Total Customers], dim_customer[customer_status] = "Active")
Churned Customers = CALCULATE([Total Customers], dim_customer[customer_status] = "Churned")
Churn Rate % = DIVIDE([Churned Customers], [Total Customers], 0)
Avg Customer Tenure (Months) = AVERAGE(dim_customer[customer_tenure_months])
```

### Service & Campaigns
```dax
Avg CSAT = AVERAGE(fact_service_logs[csat_score])
Escalation Rate % = DIVIDE(CALCULATE(COUNTROWS(fact_service_logs), fact_service_logs[escalation_flag] = TRUE), COUNTROWS(fact_service_logs), 0)
Campaign Conversion Rate % = DIVIDE(CALCULATE(COUNTROWS(fact_campaign_responses), fact_campaign_responses[was_accepted] = TRUE), COUNTROWS(fact_campaign_responses), 0)
```

---

## 3. The 5-Page Dashboard Layout

### Page 1: Executive Overview
*Audience: C-Suite, Regional Managers*
* **KPI Cards (Top)**: Total Customers, Churn Rate %, Total Revenue, Avg CSAT.
* **Line Chart**: Monthly Revenue Trend (Indian Fiscal Year) with MoM Growth tooltip.
* **Donut Chart**: Revenue by Card Category (Blue, Silver, Gold, Platinum).
* **Map**: Revenue hot-spots by State (using `dim_customer[state]`).

### Page 2: Customer Portfolio & Segmentation
*Audience: Product Managers*
* **Scatter Plot**: Customer Segments using `pca_x` and `pca_y` from ML output, colored by `behavioral_segment` (Elite High-Spenders, Credit Dependent, etc.).
* **Bar Chart**: Customers by Income Bracket.
* **Histogram**: Distribution of Credit Utilization Ratios.
* **Matrix**: RFM Tier (from `09_segmentation_kpis.sql`) vs Average Annual Spend.

### Page 3: Transaction Analytics
*Audience: Merchant Relations, Risk Teams*
* **KPI Cards**: Avg Transaction Value, High-Value Transaction %.
* **Bar Chart**: Total Volume by Merchant Category (Food, Retail, Travel, etc.).
* **Heatmap**: Day of Week vs Time of Day (proxy: transaction hour if available) spending intensity.
* **Waterfall Chart**: Revenue growth from Q1 to Q4.

### Page 4: Predictive Churn Intelligence
*Audience: Retention Team*
* **Gauge**: Overall Portfolio Risk (Average `churn_probability`).
* **Bar Chart**: Customers by Risk Tier (High/Medium/Low) from `churn_predictions.csv`.
* **Word Cloud / Bar Chart**: Top Global Risk Drivers (e.g., "Inactive for 3 months").
* **Detailed Table**: High-Risk Customers list featuring `customer_id`, `churn_probability`, and their specific `top_risk_driver_1` (from SHAP values) for targeted intervention.

### Page 5: Service & Campaign ROI
*Audience: Marketing & Support Leads*
* **Funnel Chart**: Campaign Drop-off (Targeted -> Contacted -> Opened -> Clicked -> Accepted).
* **Bar Chart**: Campaign ROI % by Campaign Type.
* **Line Chart**: CSAT Score vs Resolution Time over months.
* **Donut Chart**: Complaints by Priority (Critical, High, Medium, Low) vs Escalation %.

---

## 4. Theme & Aesthetics
To make this portfolio-grade:
1. **Color Palette**: Use a modern FinTech dark theme. 
   - Background: `#121212` or `#1E1E2D`
   - Primary Accent (Good): `#00E396` (Mint Green)
   - Secondary Accent (Warning): `#FEB019` (Amber)
   - Danger (Churn/Risk): `#FF4560` (Coral Red)
   - Neutral/Text: `#FFFFFF` and `#888899`
2. **Typography**: Segoe UI or DIN (if available). Keep titles clean and bold.
3. **Interactivity**: Add drill-throughs (e.g., click a State on the map to drill down to Cities). Use custom tooltips to show Top 3 SHAP drivers when hovering over a customer in the risk table.
