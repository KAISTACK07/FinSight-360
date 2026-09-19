# FinSight 360 – Power BI Build Guide

## Page 1 – Executive Overview

### KPI Cards
1. **Total Customers**: Format `#,0`, Measure: `[Total Customers]`, Trend Indicator: `[Customer Trend]`
2. **Active Customers**: Format `#,0`, Measure: `[Active Customers]`, Trend Indicator: `[Customer Trend]`, Conditional: Green `#00E396` text
3. **Total Revenue**: Format `₹#,0,,.0 Cr`, Measure: `[Total Revenue]`, Trend Indicator: `[Revenue Trend]`
4. **Churn Rate**: Format `0.0%`, Measure: `[Churn Rate %]`, Trend Indicator: `[Churn Rate Trend]`, Conditional: Background via `[Churn Rate Color]` measure
5. **Avg CLV**: Format `₹#,0,.0 L`, Measure: `[Avg CLV]`

### Slicers
- **Fiscal Year**: `dim_date[fiscal_year]` (Header dropdown)
- **Card Category**: `dim_customer[card_category]` (Filter pane)

### Visuals
**1. Monthly Revenue Trend**
- **Visual Type**: Area Chart
- **Purpose**: Show revenue trend and momentum
- **Required Tables**: `dim_date`, `_Measures`
- **Required Columns**: `dim_date[full_date]`
- **Required DAX Measures**: `[Total Revenue]`
- **Required Filters**: None
- **Tooltip**: `[Revenue MoM %]`, `[Total Transactions]`, `[Avg Transaction Value]`
- **Drill-through**: None
- **Formatting Notes**: Y-Axis `₹#,0,,.0 Cr`. Fill: Gradient `#00E396` 30% opacity. Line: `#00E396`, 2px.

**2. Revenue by Card Tier**
- **Visual Type**: Donut Chart
- **Purpose**: Show composition of revenue by tier
- **Required Tables**: `dim_customer`, `_Measures`
- **Required Columns**: `dim_customer[card_category]`
- **Required DAX Measures**: `[Total Revenue]`
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Colors: Blue `#5B8FF9`, Silver `#C0C0C0`, Gold `#FFD700`, Platinum `#E5E4E2`. Inner radius 60%.

**3. Top 10 States by Revenue**
- **Visual Type**: Horizontal Bar Chart
- **Purpose**: Ranked geographic revenue distribution
- **Required Tables**: `dim_customer`, `_Measures`
- **Required Columns**: `dim_customer[state]`
- **Required DAX Measures**: `[Total Revenue]`
- **Required Filters**: Top N: Top 10 by `[Total Revenue]`
- **Tooltip**: `[Total Customers]`, `[Churn Rate %]`, `[Avg Transaction Value]`
- **Drill-through**: None
- **Formatting Notes**: Data labels `₹#,0,,.0 Cr`. Bar color gradient from `#00E396` to `#2A2A40` (by `[Total Revenue]`).

**4. Key Insights Panel**
- **Visual Type**: Multi-row card or Text box
- **Purpose**: Dynamic DAX narrative
- **Required Tables**: None
- **Required Columns**: None
- **Required DAX Measures**: None
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Background `#1A1A2E`, top border `2px #00E396`.

### Visual Build Order
1. Create KPI cards
2. Create slicers
3. Create charts (Area Chart, Donut Chart, Horizontal Bar Chart)
4. Create tables (N/A)
5. Add tooltips
6. Configure interactions (State bar click filters page)
7. Final formatting

---

## Page 2 – Customer Intelligence

### KPI Cards
1. **Avg CLV**: Format `₹#,0,.0 L`, Measure: `[Avg CLV]`
2. **Avg Products Held**: Format `0.0`, Measure: `AVERAGE(dim_customer[total_products_held])` (inline measure)
3. **Avg Tenure**: Format `0 months`, Measure: `[Avg Tenure Months]`
4. **Total Portfolio CLV**: Format `₹#,0,,.0 Cr`, Measure: `[Total Portfolio CLV]`

### Slicers
- **Segment**: `ml_customer_segments[behavioral_segment]` (Header dropdown)
- **Card Category**: `dim_customer[card_category]` (Horizontal chip slicer)

### Visuals
**1. Segment Distribution by Card Tier**
- **Visual Type**: 100% Stacked Bar Chart
- **Purpose**: Segment composition per tier
- **Required Tables**: `dim_customer`, `ml_customer_segments`, `_Measures`
- **Required Columns**: `dim_customer[card_category]` (Y-Axis), `ml_customer_segments[behavioral_segment]` (Legend)
- **Required DAX Measures**: `[Total Customers]` (X-Axis)
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Sorted by `card_sort`. Percentage data labels. Segment colors from theme (Elite `#00E396`, etc).

**2. Revenue by Income Bracket**
- **Visual Type**: Treemap
- **Purpose**: Distribution of revenue
- **Required Tables**: `dim_customer`, `_Measures`
- **Required Columns**: `dim_customer[income_bracket]`
- **Required DAX Measures**: `[Total Revenue]`
- **Required Filters**: None
- **Tooltip**: `[Total Customers]`, `[Churn Rate %]`
- **Drill-through**: None
- **Formatting Notes**: Color sequential gradient `#775DD0` → `#00E396`.

**3. Revenue Contribution by Segment over Time**
- **Visual Type**: Ribbon Chart
- **Purpose**: Track segment revenue rank shifts
- **Required Tables**: `dim_date`, `ml_customer_segments`, `_Measures`
- **Required Columns**: `dim_date[fiscal_quarter_name]` (X-Axis), `ml_customer_segments[behavioral_segment]` (Legend)
- **Required DAX Measures**: `[Total Revenue]` (Y-Axis)
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Colors consistent with stacked bar chart.

**4. Top 10 High-Value Customers**
- **Visual Type**: Table
- **Purpose**: Identify top individuals
- **Required Tables**: `dim_customer`, `ml_customer_segments`, `ml_churn_predictions`, `_Measures`
- **Required Columns**: Name (first+last), Location (city+state), `dim_customer[card_category]`, `dim_customer[total_trans_amt_12m]`, `ml_customer_segments[behavioral_segment]`, `ml_churn_predictions[churn_risk_tier]`, CLV (inline)
- **Required DAX Measures**: `[Customer CLV Rank]`, `[Avg CLV]`
- **Required Filters**: Top 10 by `[Customer CLV Rank]`
- **Tooltip**: None
- **Drill-through**: Customer 360 Detail
- **Formatting Notes**: Card tier font color. Churn Risk conditional background (High `#FF4560`, Med `#FEB019`, Low `#00E396`).

**5. Key Insights Panel**
- **Visual Type**: Multi-row card or Text box
- **Purpose**: Segment & CLV insights
- **Required Tables**: None
- **Required Columns**: None
- **Required DAX Measures**: None
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Background `#1A1A2E`, top border `2px #775DD0`.

### Visual Build Order
1. Create KPI cards
2. Create slicers
3. Create charts (Stacked Bar, Treemap, Ribbon)
4. Create tables (Top 10 High-Value Table)
5. Add tooltips
6. Configure interactions (Treemap cross-filters)
7. Final formatting

---

## Page 3 – Revenue, Churn & Retention Intelligence

### KPI Cards
1. **Revenue at Risk**: Format `₹#,0,.0 L`, Measure: `[Revenue at Risk]`, Trend: `[Risk Exposure Trend]`, Conditional: Red `#FF4560` 20% bg
2. **High Risk Customers**: Format `#,0`, Measure: `[High Risk Customers]`, Conditional: Red text if > 1000
3. **Avg Churn Probability**: Format `0.0%`, Measure: `[Avg Churn Probability]`, Conditional: Green→Amber→Red text
4. **Campaign ROI**: Format `0.0%`, Measure: `[Campaign ROI %]`, Trend: `[Campaign ROI Trend]`, Conditional: Green if positive
5. **Avg CSAT**: Format `0.0 / 5`, Measure: `[Avg CSAT]`, Trend: `[CSAT Trend]`, Conditional: Green >3.5, Amber 2.5-3.5, Red <2.5

### Slicers
- **Risk Tier**: `ml_churn_predictions[churn_risk_tier]` (Button slicer)
- **Campaign**: `dim_campaign[campaign_name]` (Dropdown)
- **Card Category**: `dim_customer[card_category]` (Filter pane)

### Visuals
**1. Quarterly Revenue + Transactions**
- **Visual Type**: Combo Chart (Line and Clustered Column)
- **Purpose**: Revenue vs transaction volume trend
- **Required Tables**: `dim_date`, `_Measures`
- **Required Columns**: `dim_date[fiscal_quarter_name]`
- **Required DAX Measures**: `[Total Revenue]` (Y-Axis Left), `[Total Transactions]` (Y-Axis Right)
- **Required Filters**: None
- **Tooltip**: `[Avg Transaction Value]`, `[Revenue QoQ %]`
- **Drill-through**: None
- **Formatting Notes**: Column: `#775DD0` → `#5B8FF9`. Line: `#00E396` 2.5px with markers.

**2. Global Churn Risk Drivers**
- **Visual Type**: Horizontal Bar Chart
- **Purpose**: Highest impact factors for churn
- **Required Tables**: `shap_feature_importance`
- **Required Columns**: `shap_feature_importance[display_name]`
- **Required DAX Measures**: None (uses `shap_feature_importance[importance_score]`)
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Bar gradient `#FF4560` → `#FEB019` → `#775DD0`. Sorted descending.

**3. Campaign Conversion Funnel**
- **Visual Type**: Funnel Chart
- **Purpose**: Campaign progression
- **Required Tables**: `_Measures`
- **Required Columns**: Funnel Categories (Targeted, Contacted, Opened, Accepted)
- **Required DAX Measures**: `[Funnel Targeted]`, `[Funnel Contacted]`, `[Funnel Opened]`, `[Funnel Accepted]`
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Colors `#5B8FF9` → `#775DD0` → `#FEB019` → `#00E396`. Data labels: Count + drop-off %.

**4. Top 10 High-Risk Customers**
- **Visual Type**: Table
- **Purpose**: Actionable watchlist
- **Required Tables**: `dim_customer`, `ml_churn_predictions`
- **Required Columns**: Customer Name, `ml_churn_predictions[churn_probability]`, `ml_churn_predictions[churn_risk_tier]`, `dim_customer[total_trans_amt_12m]`, `ml_churn_predictions[top_risk_driver_1]`, `ml_churn_predictions[top_risk_driver_2]`, `ml_churn_predictions[Recommended Action]`
- **Required DAX Measures**: `RANKX` by churn_probability
- **Required Filters**: Default filter: `churn_risk_tier = "High Risk"`. Top N: 10 by `churn_probability`.
- **Tooltip**: None
- **Drill-through**: Customer 360 Detail
- **Formatting Notes**: `churn_probability` data bars `#FF4560`. `churn_risk_tier` background color.

**5. Key Insights Panel**
- **Visual Type**: Multi-row card or Text box
- **Purpose**: Narrative overview
- **Required Tables**: None
- **Required Columns**: None
- **Required DAX Measures**: None
- **Required Filters**: None
- **Tooltip**: None
- **Drill-through**: None
- **Formatting Notes**: Background `#1A1A2E`, top border `2px #FF4560`.

### Visual Build Order
1. Create KPI cards
2. Create slicers
3. Create charts (Combo Chart, Bar Chart, Funnel)
4. Create tables (Top 10 High-Risk Table)
5. Add tooltips
6. Configure interactions
7. Final formatting

---

## Page 4 – Churn & Retention Intelligence
*(Note: Combined with Page 3 in architecture as "Revenue, Churn & Retention Intelligence". Drill-through acts as the 4th view)*

### Drill-through: Customer 360 Detail
**Visual Build Order**:
1. Set page type to Drill-through
2. Add back button
3. Create profile header
4. Create financial and risk cards
5. Create history and SHAP charts
6. Test drill-through from Page 2 and 3 tables
7. Final formatting

---

## DAX Mapping

| Visual | Required DAX Measures |
|---|---|
| P1: Card Total Customers | `[Total Customers]`, `[Customer Trend]` |
| P1: Card Active Customers | `[Active Customers]`, `[Customer Trend]` |
| P1: Card Total Revenue | `[Total Revenue]`, `[Revenue Trend]` |
| P1: Card Churn Rate | `[Churn Rate %]`, `[Churn Rate Trend]`, `[Churn Rate Color]` |
| P1: Card Avg CLV | `[Avg CLV]` |
| P1: Area Chart | `[Total Revenue]`, `[Revenue MoM %]`, `[Total Transactions]`, `[Avg Transaction Value]` |
| P1: Donut Chart | `[Total Revenue]` |
| P1: Bar Chart | `[Total Revenue]`, `[Total Customers]`, `[Churn Rate %]`, `[Avg Transaction Value]` |
| P2: Card Avg CLV | `[Avg CLV]` |
| P2: Card Avg Products Held | `AVERAGE(dim_customer[total_products_held])` |
| P2: Card Avg Tenure | `[Avg Tenure Months]` |
| P2: Card Total Portfolio CLV| `[Total Portfolio CLV]` |
| P2: Stacked Bar | `[Total Customers]` |
| P2: Treemap | `[Total Revenue]`, `[Total Customers]`, `[Churn Rate %]` |
| P2: Ribbon Chart | `[Total Revenue]` |
| P2: Top 10 Value Table | `[Avg CLV]`, `[Customer CLV Rank]` |
| P3: Card Revenue at Risk | `[Revenue at Risk]`, `[Risk Exposure Trend]` |
| P3: Card High Risk | `[High Risk Customers]` |
| P3: Card Avg Churn Prob | `[Avg Churn Probability]` |
| P3: Card Campaign ROI | `[Campaign ROI %]`, `[Campaign ROI Trend]` |
| P3: Card Avg CSAT | `[Avg CSAT]`, `[CSAT Trend]` |
| P3: Combo Chart | `[Total Revenue]`, `[Total Transactions]`, `[Avg Transaction Value]`, `[Revenue QoQ %]` |
| P3: Funnel Chart | `[Funnel Targeted]`, `[Funnel Contacted]`, `[Funnel Opened]`, `[Funnel Accepted]` |

---

## Visual Mapping

| Visual | Table | Columns |
|---|---|---|
| P1: Area Chart | `dim_date` | `full_date` |
| P1: Donut Chart | `dim_customer` | `card_category` |
| P1: Bar Chart | `dim_customer` | `state` |
| P2: Stacked Bar | `dim_customer`, `ml_customer_segments` | `card_category`, `behavioral_segment` |
| P2: Treemap | `dim_customer` | `income_bracket` |
| P2: Ribbon Chart | `dim_date`, `ml_customer_segments` | `fiscal_quarter_name`, `behavioral_segment` |
| P2: Top 10 Value Table | `dim_customer`, `ml_customer_segments`, `ml_churn_predictions` | Name, `city`, `state`, `card_category`, `total_trans_amt_12m`, `behavioral_segment`, `churn_risk_tier` |
| P3: Combo Chart | `dim_date` | `fiscal_quarter_name` |
| P3: Churn Risk Drivers | `shap_feature_importance` | `display_name`, `importance_score` |
| P3: Top 10 Risk Table | `dim_customer`, `ml_churn_predictions` | Name, `total_trans_amt_12m`, `churn_probability`, `churn_risk_tier`, `top_risk_driver_1`, `top_risk_driver_2`, `Recommended Action` |

---

## Slicer Mapping

### Page 1 – Executive Overview
- **Page Slicers**: `dim_date[fiscal_year]` (Header dropdown)
- **Filter Pane**: `dim_customer[card_category]`
- **Synced Slicers**: None
- **Visual Interactions**: Bar chart (State) cross-filters all visuals on page

### Page 2 – Customer Intelligence
- **Page Slicers**: `ml_customer_segments[behavioral_segment]` (Header dropdown), `dim_customer[card_category]` (Horizontal chip slicer)
- **Synced Slicers**: None
- **Visual Interactions**: Treemap (Income Bracket) cross-filters all visuals on page

### Page 3 – Revenue, Churn & Retention Intelligence
- **Page Slicers**: `ml_churn_predictions[churn_risk_tier]` (Button slicer), `dim_campaign[campaign_name]` (Dropdown)
- **Filter Pane**: `dim_customer[card_category]`
- **Synced Slicers**: None
- **Visual Interactions**: Global Drivers Bar Chart filters table, Funnel stages filter by campaign

### Drill-through Page
- **Page Slicers**: `dim_customer[customer_id]` (Drill-through filter from P2 and P3)
