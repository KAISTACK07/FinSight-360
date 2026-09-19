# FinSight 360 — Power BI Dashboard Architecture

> **3 Executive Dashboards · 22 DAX Measures · Zero KPI Duplication**
>
> Every visual answers a business question. Every KPI traces to SQL or ML. Every page concludes with actionable Key Insights.

---

## 1. Data Model & Connection Architecture

### Connection

| Parameter | Value |
|---|---|
| **Server** | `localhost:5432` |
| **Database** | `postgres` |
| **Schema** | `customer360` |
| **Mode** | Import (all tables) |

### Tables

| Table | Type | Key | Source |
|---|---|---|---|
| `dim_customer` | Dimension | `customer_id` PK | PostgreSQL |
| `dim_date` | Dimension | `date_key` PK | PostgreSQL |
| `dim_product` | Dimension | `product_id` PK | PostgreSQL |
| `dim_campaign` | Dimension | `campaign_id` PK | PostgreSQL |
| `fact_transactions` | Fact | `transaction_id` PK | PostgreSQL |
| `fact_service_logs` | Fact | `service_id` PK | PostgreSQL |
| `fact_campaign_responses` | Fact | `response_id` PK | PostgreSQL |
| `ml_churn_predictions` | ML Output | `customer_id` FK | `data/output/churn_predictions.csv` |
| `ml_customer_segments` | ML Output | `customer_id` FK | `data/output/customer_segments.csv` |
| `shap_feature_importance` | ML Output | `importance_rank` | `data/output/shap_feature_importance.csv` |

### Relationships (Star Schema — All Single Direction, 1:Many)

```
dim_customer ──1:*──► fact_transactions
dim_date     ──1:*──► fact_transactions
dim_product  ──1:*──► fact_transactions
dim_customer ──1:*──► fact_service_logs
dim_date     ──1:*──► fact_service_logs
dim_customer ──1:*──► fact_campaign_responses
dim_campaign ──1:*──► fact_campaign_responses
dim_date     ──1:*──► fact_campaign_responses
dim_customer ──1:1──► ml_churn_predictions
dim_customer ──1:1──► ml_customer_segments
```

### Power Query Transformations

Apply transformations from `powerbi/power_query_transforms.m`:

1. **ml_customer_segments**: Rename generic cluster labels → business-friendly names (Premium Customers, Loyal Customers, Growth Customers, Value Seekers). Strip numbered prefixes.
2. **ml_churn_predictions**: Add `risk_tier_sort` column. Translate technical feature names in risk driver columns to human-readable labels.
3. **shap_feature_importance**: Type casting only (auto-exported from Python).
4. **dim_customer**: Add `age_band` and `card_sort` computed columns.

---

## 2. Theme & Design System

**Theme file**: `powerbi/FinSight360-Executive.json` — import via View → Themes → Browse for Themes.

| Role | Hex | Usage |
|---|---|---|
| Canvas Background | `#0F0F1A` | All page backgrounds |
| Card / Panel Background | `#1A1A2E` | KPI cards, chart containers |
| Card Border | `#2A2A40` | Subtle panel separation |
| Primary Accent (Growth) | `#00E396` | Positive KPIs, revenue, active |
| Secondary Accent (Caution) | `#FEB019` | Medium risk, warnings |
| Danger (Risk) | `#FF4560` | Churn, high risk, decline |
| Info / Neutral | `#775DD0` | Segments, demographics |
| Text Primary | `#FFFFFF` | Titles, KPI values |
| Text Secondary | `#8B8BA7` | Subtitles, labels |

**Card Tier Colors**: Blue `#5B8FF9` · Silver `#C0C0C0` · Gold `#FFD700` · Platinum `#E5E4E2`

**Typography**: Segoe UI across all elements. KPI values 28pt Bold. Chart titles 11pt Semibold. Labels 8pt Regular.

---

## 3. DAX Measures (22 Total)

**File**: `powerbi/dax_measures.dax` — every measure maps to a specific visual.

| Domain | Count | Measures |
|---|---|---|
| Revenue | 5 | Total Revenue, Total Transactions, Avg Transaction Value, Revenue MoM %, Revenue Trend Arrow |
| Customer | 5 | Total Customers, Active Customers, Churn Rate %, Retention Rate %, Avg Tenure Months |
| CLV | 3 | Avg CLV, Total Portfolio CLV, Customer CLV Rank |
| Churn / ML | 3 | Avg Churn Probability, High Risk Customers, Revenue at Risk |
| Campaign | 3 + funnel | Campaign Acceptance Rate %, Campaign ROI %, Funnel Targeted/Contacted/Opened/Accepted |
| Service | 1 | Avg CSAT |
| Formatting | 1 | Churn Rate Color |
| **Calculated Column** | 1 | Recommended Action (on ml_churn_predictions) |

---

## 4. Navigation Framework

### Left Sidebar (60px wide, all pages)

| Icon | Label | Action |
|---|---|---|
| 📊 | Executive Overview | Navigate → Page 1 |
| 👥 | Customer Intelligence | Navigate → Page 2 |
| 💰 | Revenue & Churn | Navigate → Page 3 |

Active page: Vertical `#00E396` accent bar (3px left border).

### Page Header (top bar, all pages)

- **Left**: Page title (22pt) + subtitle (11pt `#8B8BA7`)
- **Right**: Fiscal Year slicer (dropdown) + "Data as of" timestamp

### Canvas: 1320 × 720 px (16:9 widescreen)

---

## 5. Page 1 — Executive Overview

**Audience**: C-Suite, Regional Managers
**Objective**: Single-glance answer to *"How is the bank performing?"*

### Layout

```
┌──────┬────────────────────────────────────────────────────────────────────────────────┐
│      │  HEADER: "Executive Overview" + FY Slicer                            [50px]   │
│  NAV │──────────────────────────────────────────────────────────────────────────────── │
│      │  KPI-1         │  KPI-2         │  KPI-3         │  KPI-4         │  KPI-5    │
│ [60] │  Total         │  Active        │  Total         │  Churn         │  Avg      │
│  px  │  Customers     │  Customers     │  Revenue       │  Rate          │  CLV      │
│      │──────────────────────────────────────────────────────────────────────[100px]── │
│      │                                          │                         [300px]    │
│      │   AREA CHART                             │  DONUT CHART                       │
│      │   Monthly Revenue Trend                  │  Revenue by Card Tier              │
│      │   (MoM% in tooltip)                      │                                    │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │                                                                     [200px]   │
│      │   HORIZONTAL BAR: Top 10 States by Revenue                                    │
│      │   (sorted descending, with conditional formatting)                             │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │   📌 KEY INSIGHTS                                                     [70px]  │
│      │   • Revenue grew X% MoM. Top state: Maharashtra (₹X Cr)                      │
│      │   • Churn at X%. Blue-tier customers account for X% of attrition              │
│      │   • Recommendation: Activate re-engagement for high-risk segments             │
└──────┴────────────────────────────────────────────────────────────────────────────────┘
```

### Visuals (5 KPI Cards + 3 Charts + Insight Panel)

#### KPI Cards (Row of 5)
Position: `x:70, y:55, w:1240, h:95` — Background `#1A1A2E`, border `#2A2A40`, rounded 8px

Each card has 3 rows: **Label** (9pt `#8B8BA7`) → **Value** (28pt `#FFFFFF`) → **Trend** (9pt `#00E396` or `#FF4560`)

| # | KPI | Measure | Format | Trend Indicator | Conditional |
|---|---|---|---|---|---|
| 1 | Total Customers | `[Total Customers]` | `#,0` | `[Customer Trend]` — *"▲ 2.1% vs Prev Qtr"* | — |
| 2 | Active Customers | `[Active Customers]` | `#,0` | `[Customer Trend]` — *reused* | Green `#00E396` |
| 3 | Total Revenue | `[Total Revenue]` | `₹#,0,,.0 Cr` | `[Revenue Trend]` — *"▲ 8.2% vs Prev Qtr"* | — |
| 4 | Churn Rate | `[Churn Rate %]` | `0.0%` | `[Churn Rate Trend]` — *"▲ 1.3 pp above target"* | Background via `[Churn Rate Color]` |
| 5 | Avg CLV | `[Avg CLV]` | `₹#,0,.0 L` | — | — |

**Trend color rule**: `▲` in `#00E396` if positive (except Churn Rate, where lower is better → invert colors).

**Tables**: `dim_customer`, `fact_transactions`, `ml_churn_predictions`

#### Monthly Revenue Trend (Area Chart)
Position: `x:70, y:160, w:750, h:300`

- **X-Axis**: `dim_date[full_date]` (Year → Quarter → Month)
- **Y-Axis**: `[Total Revenue]` — Format `₹#,0,,.0 Cr`
- **Fill**: Gradient `#00E396` 30% opacity
- **Line**: `#00E396`, 2px
- **Tooltip**: `[Revenue MoM %]`, `[Total Transactions]`, `[Avg Transaction Value]`
- **SQL Source**: `03_revenue_kpis.sql` KPI 1

#### Revenue by Card Tier (Donut Chart)
Position: `x:830, y:160, w:480, h:300`

- **Legend**: `dim_customer[card_category]`
- **Values**: `[Total Revenue]`
- **Colors**: Blue `#5B8FF9`, Silver `#C0C0C0`, Gold `#FFD700`, Platinum `#E5E4E2`
- **Inner radius**: 60%, center label shows total
- **SQL Source**: `03_revenue_kpis.sql` KPI 4

#### Top 10 States by Revenue (Horizontal Bar Chart)
Position: `x:70, y:470, w:1240, h:185`

- **Y-Axis**: `dim_customer[state]`
- **X-Axis**: `[Total Revenue]` — Format `₹#,0,,.0 Cr`
- **Sort**: Descending by revenue
- **Top N filter**: Top 10 by `[Total Revenue]`
- **Data labels**: ON, `₹#,0,,.0 Cr` at bar end
- **Tooltips**: `[Total Customers]`, `[Churn Rate %]`, `[Avg Transaction Value]`
- **Bar color**: Gradient from `#00E396` (top state) fading to `#2A2A40`
- **Conditional formatting**: Bar color by `[Total Revenue]` (darker = less revenue)
- **Cross-filter**: Click state → filters all visuals on page
- **Title**: "Top 10 States by Revenue"
- **SQL Source**: `03_revenue_kpis.sql` KPI 7

> **Why bar chart over filled map**: Filled maps in Power BI are often inaccurate for Indian states and can be slow to render. A ranked bar chart communicates geographic revenue distribution more precisely and is faster to read.

### 📌 Key Insights Panel
Position: `x:70, y:660, w:1240, h:55` — Background `#1A1A2E`, border-top `2px #00E396`

**Visual Type**: Multi-row card or text box with dynamic DAX narrative

**Content Pattern** (update with actual data after first load):

> **Key Insights**
> - Revenue grew **X.X% MoM**. Top contributing state: **Maharashtra** (₹X.X Cr, XX% share)
> - Churn rate: **X.X%**. Blue-tier customers represent **XX%** of all churn
> - Avg CLV: **₹X.X L**. Platinum-tier customers generate **X.Xx** more CLV than Blue-tier
>
> **Recommendation**: Launch targeted re-engagement for **X,XXX** high-risk customers. Expected revenue loss: **₹XX.X L**

### Filters
- `dim_date[fiscal_year]` — Header dropdown slicer
- `dim_customer[state]` — Cross-filter from bar click
- `dim_customer[card_category]` — Filter pane only

---

## 6. Page 2 — Customer Intelligence

**Audience**: Product Managers, CRM Teams
**Objective**: Understand *who the customers are* and which segments deserve investment

### Layout

```
┌──────┬────────────────────────────────────────────────────────────────────────────────┐
│      │  HEADER: "Customer Intelligence" + Segment Slicer                    [50px]   │
│  NAV │──────────────────────────────────────────────────────────────────────────────── │
│      │  KPI-1           │  KPI-2           │  KPI-3           │  KPI-4              │
│ [60] │  Avg CLV         │  Avg Products    │  Avg Tenure      │  Portfolio CLV      │
│  px  │──────────────────────────────────────────────────────────────────────[90px]── │
│      │                                        │                             [260px]  │
│      │  100% STACKED BAR                      │  TREEMAP                             │
│      │  Segment Distribution by                │  Revenue by Income Bracket           │
│      │  Card Tier (% of customers)             │                                      │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │                            │                                         [230px]  │
│      │  RIBBON CHART              │  TABLE                                           │
│      │  Revenue Contribution      │  Top 10 High-Value Customers                     │
│      │  by Segment over Time      │  (CLV, Segment, Churn Risk, Action)              │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │   📌 KEY INSIGHTS                                                     [70px]  │
│      │   • Elite Spenders = X% of base, XX% of revenue                               │
│      │   • X customers hold < 2 products — cross-sell opportunity                    │
│      │   • Recommendation: Upgrade high-CLV Blue-card customers                      │
└──────┴────────────────────────────────────────────────────────────────────────────────┘
```

### Visuals (4 KPI Cards + 4 Charts + Insight Panel)

#### KPI Cards (Row of 4)
Position: `x:70, y:55, w:1240, h:85`

| # | KPI | Measure | Format |
|---|---|---|---|
| 1 | Avg CLV | `[Avg CLV]` | `₹#,0,.0 L` |
| 2 | Avg Products Held | `AVERAGE(dim_customer[total_products_held])` | `0.0` |
| 3 | Avg Tenure | `[Avg Tenure Months]` | `0 months` |
| 4 | Total Portfolio CLV | `[Total Portfolio CLV]` | `₹#,0,,.0 Cr` |

#### Customer Segment Distribution (100% Stacked Bar Chart)
Position: `x:70, y:150, w:640, h:260`

- **Y-Axis**: `dim_customer[card_category]` (sorted by `card_sort`)
- **X-Axis**: `[Total Customers]`
- **Legend**: `ml_customer_segments[behavioral_segment]`
- **Chart subtype**: 100% Stacked (shows % composition)
- **Colors**: Elite/Premium `#00E396`, Credit Dependent `#FF4560`, Engaged/Growth `#FEB019`, Passive/Value Seekers `#775DD0`, Loyal `#26A0FC`
- **Data labels**: Percentage inside each segment bar
- **Title**: "Customer Segment Mix by Card Tier"
- **Subtitle**: "K-Means Behavioral Segments (ML Pipeline)"
- **ML Source**: `segmentation_model.py`

> **Why 100% Stacked Bar over PCA Scatter**: A stacked bar is immediately understandable by non-technical stakeholders (product managers, CRM teams). It answers "which card tier has the most at-risk or passive customers?" without requiring knowledge of PCA or clustering.

#### Revenue by Income Bracket (Treemap)
Position: `x:720, y:150, w:590, h:260`

- **Category**: `dim_customer[income_bracket]`
- **Values**: `[Total Revenue]`
- **Tooltips**: `[Total Customers]`, `[Churn Rate %]`
- **Color**: Sequential gradient `#775DD0` → `#00E396`
- **Data labels**: Bracket name + `₹X.X Cr` + percentage
- **SQL Source**: `03_revenue_kpis.sql` KPI 3

#### Revenue by Segment over Time (Ribbon Chart)
Position: `x:70, y:420, w:470, h:230`

- **X-Axis**: `dim_date[fiscal_quarter_name]` within `dim_date[fiscal_year]`
- **Y-Axis**: `[Total Revenue]`
- **Legend**: `ml_customer_segments[behavioral_segment]`
- **Colors**: Same as segment distribution chart (consistent palette)
- **Ribbon transitions**: Show rank changes between quarters
- **Title**: "Revenue Contribution by Segment over Time"
- **Subtitle**: "Ribbon width = revenue share · Rank shifts show segment momentum"
- **SQL Source**: `03_revenue_kpis.sql` via segments + `dim_date`

> **Why Ribbon Chart over Grouped Bar (CLV × Status)**: The ribbon chart reveals temporal trends — which segments are gaining or losing revenue share over quarters. This is more actionable than a static CLV comparison because it shows *direction*, not just current state.

#### Top 10 High-Value Customers (Table)
Position: `x:550, y:420, w:760, h:230`

| Column | Source | Format | Conditional |
|---|---|---|---|
| Rank | `[Customer CLV Rank]` | `#` | — |
| Customer | `first_name & " " & last_name` | Text | — |
| Location | `city & ", " & state` | Text | — |
| Card | `card_category` | Text | Font color by tier |
| Annual Revenue | `total_trans_amt_12m` | `₹#,0` | — |
| Segment | `behavioral_segment` | Text | — |
| Churn Risk | `churn_risk_tier` | Text | Background: High `#FF4560`, Med `#FEB019`, Low `#00E396` (25% opacity) |
| CLV | Row-level CLV calc | `₹#,0,.0 L` | — |

**Top N filter**: Top 10 by `[Customer CLV Rank]` — executives don't scroll through long tables.

### 📌 Key Insights Panel
Position: `x:70, y:655, w:1240, h:65` — Background `#1A1A2E`, border-top `2px #775DD0`

**Content Pattern**:

> **Key Insights**
> - **Elite High-Spenders** represent X% of the customer base but contribute **XX% of total revenue**
> - **X,XXX customers** hold fewer than 2 products — prime cross-sell targets for Insurance and Mutual Fund SIP
> - Revenue share of Passive/Value Seeker segment **declined X% QoQ** — engagement campaigns needed
>
> **Recommendation**: Proactively upgrade high-CLV Blue-card customers to Silver. Target low-product customers with Campaign 4 (Cross-sell Insurance)

### Filters
- `ml_customer_segments[behavioral_segment]` — Header dropdown
- `dim_customer[card_category]` — Horizontal chip slicer
- Income bracket — Cross-filter from treemap click

---

## 7. Page 3 — Revenue, Churn & Retention Intelligence

**Audience**: Retention Team, Revenue Leaders
**Objective**: Understand *where revenue comes from, who will churn, why, and what to do about it*

### Layout

```
┌──────┬────────────────────────────────────────────────────────────────────────────────┐
│      │  HEADER: "Revenue, Churn & Retention Intelligence" + Risk Slicer     [50px]   │
│  NAV │──────────────────────────────────────────────────────────────────────────────── │
│      │  KPI-1         │  KPI-2       │  KPI-3       │  KPI-4       │  KPI-5         │
│ [60] │  Revenue       │  High Risk   │  Avg Churn   │  Campaign    │  Avg           │
│  px  │  at Risk       │  Customers   │  Probability │  ROI         │  CSAT          │
│      │──────────────────────────────────────────────────────────────────────[90px]── │
│      │                                │                              [250px]         │
│      │  COMBO CHART                   │  HORIZONTAL BAR CHART                        │
│      │  Quarterly Revenue +           │  Global Churn Risk Drivers                   │
│      │  Transaction Count (Dual Axis) │  (SHAP Feature Importance)                   │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │                     │                                         [250px]         │
│      │  FUNNEL CHART       │  TABLE: High-Risk Customer Watchlist                    │
│      │  Campaign            │  Churn Prob · Risk Drivers · Revenue ·                 │
│      │  Conversion Funnel  │  Recommended Action                                     │
│      │──────────────────────────────────────────────────────────────────────────────── │
│      │   📌 KEY INSIGHTS                                                    [80px]   │
│      │   • X,XXX high-risk customers. Revenue at risk: ₹XX.X L                      │
│      │   • Top churn driver: Transaction frequency decline (importance: 0.29)        │
│      │   • Recommendation: Retain 20% of high-risk = recover ₹X.X L annually        │
└──────┴────────────────────────────────────────────────────────────────────────────────┘
```

### Visuals

#### KPI Cards (Row of 5)
Position: `x:70, y:55, w:1240, h:85`

Each card: **Label** → **Value** → **Trend** (same pattern as Page 1)

| # | KPI | Measure | Format | Trend Indicator | Conditional |
|---|---|---|---|---|---|
| 1 | Revenue at Risk | `[Revenue at Risk]` | `₹#,0,.0 L` | `[Risk Exposure Trend]` — *"▲ 4.2% of portfolio revenue"* | Red background `#FF4560` 20% |
| 2 | High Risk Customers | `[High Risk Customers]` | `#,0` | — | Red text if > 1000 |
| 3 | Avg Churn Probability | `[Avg Churn Probability]` | `0.0%` | — | Color scale Green→Amber→Red |
| 4 | Campaign ROI | `[Campaign ROI %]` | `0.0%` | `[Campaign ROI Trend]` — *"▲ 3.2 pp vs Prev Qtr"* | Green if positive |
| 5 | Avg CSAT | `[Avg CSAT]` | `0.0 / 5` | `[CSAT Trend]` — *"▲ 0.3 pts vs Prev Qtr"* | Green >3.5, Amber 2.5-3.5, Red <2.5 |

#### Quarterly Revenue + Transactions (Combo Chart)
Position: `x:70, y:150, w:620, h:250`

- **X-Axis**: `dim_date[fiscal_quarter_name]` within `dim_date[fiscal_year]`
- **Column Y-Axis**: `[Total Revenue]` — gradient `#775DD0` → `#5B8FF9`
- **Line Y-Axis**: `[Total Transactions]` — `#00E396`, 2.5px, with markers
- **Tooltips**: `[Avg Transaction Value]`, `[Revenue QoQ %]`
- **Dual Y-axis**: Left = Revenue (`₹Cr`), Right = Count (`#,0`)
- **Title**: "Quarterly Revenue & Transaction Volume"
- **SQL Source**: `03_revenue_kpis.sql` KPI 2 + `04_transaction_kpis.sql` KPI 4

#### Global Churn Risk Drivers (Horizontal Bar)
Position: `x:700, y:150, w:610, h:250`

- **Y-Axis**: `shap_feature_importance[display_name]`
- **X-Axis**: `shap_feature_importance[importance_score]`
- **Sort**: Descending by importance
- **Bar color**: Gradient `#FF4560` (highest) → `#FEB019` → `#775DD0` (lowest)
- **Data labels**: ON, 4 decimal places
- **Title**: "Global Churn Risk Drivers"
- **Subtitle**: "Random Forest Feature Importance · Auto-exported from ML Pipeline"
- **Data Source**: `data/output/shap_feature_importance.csv` (auto-generated by `export_shap_importance.py`)

#### Campaign Conversion Funnel
Position: `x:70, y:410, w:360, h:250`

- **Category**: Funnel stages (Targeted → Contacted → Opened → Accepted)
- **Values**: `[Funnel Targeted]`, `[Funnel Contacted]`, `[Funnel Opened]`, `[Funnel Accepted]`
- **Colors**: Stage gradient `#5B8FF9` → `#775DD0` → `#FEB019` → `#00E396`
- **Data labels**: Count + drop-off %
- **Title**: "Campaign Conversion Funnel"
- **SQL Source**: `06_campaign_kpis.sql` KPI 1, `v_campaign_funnel` view

#### Top 10 High-Risk Customers (Table)
Position: `x:440, y:410, w:870, h:250`

| Column | Source | Format | Conditional |
|---|---|---|---|
| Risk Rank | `RANKX` by churn_probability | `#` | — |
| Customer | Name concatenation | Text | — |
| Churn Prob. | `churn_probability` | `0.0%` | Data bars `#FF4560` |
| Risk Tier | `churn_risk_tier` | Text | Background by tier |
| Annual Revenue | `total_trans_amt_12m` | `₹#,0` | Bold + color scale |
| Top Risk Driver | `top_risk_driver_1` (human-readable) | Text | — |
| 2nd Driver | `top_risk_driver_2` | Text | — |
| Recommended Action | Calculated column | Text | — |

**Top N filter**: Top 10 by `churn_probability` — concise enough for executive review
**Default filter**: `churn_risk_tier = "High Risk"` (togglable via slicer)
**Sort**: Descending by churn_probability

### 📌 Key Insights Panel
Position: `x:70, y:665, w:1240, h:55` — Background `#1A1A2E`, border-top `2px #FF4560`

**Content Pattern**:

> **Key Insights**
> - **X,XXX high-risk customers** identified by ML model. Expected revenue loss (probability-weighted): **₹XX.X L/year**
> - Top churn driver: **Transaction frequency decline** (importance: 0.2940), followed by transaction amount and spending change
> - Campaign 3 (Re-engagement) shows **highest ROI** — outperforms others by XX%
> - Churned customers averaged **1.7/5 CSAT** vs 2.4 for active — poor service accelerates churn
>
> **Recommendation**: Retaining even **20% of high-risk customers** recovers **₹X.X L annually**. Prioritize automated engagement offers for customers with declining transaction frequency. Route high-risk tickets to senior agents.

### Filters
- `ml_churn_predictions[churn_risk_tier]` — Button slicer (All / High / Medium / Low)
- `dim_campaign[campaign_name]` — Dropdown near funnel
- `dim_customer[card_category]` — Filter pane

---

## 8. Drill-through & Tooltip Pages

### Drill-through: Customer 360 Detail

**Trigger**: Right-click any customer in Page 2 or Page 3 tables
**Field**: `dim_customer[customer_id]`

| Section | Visuals |
|---|---|
| Header | Name, Age, Gender, City/State, Card Category, Tenure |
| Financial | Annual Revenue (card), CLV (card), Credit Utilization (card) |
| Risk | Churn Probability (gauge), Risk Tier (text) |
| History | Monthly transaction trend (line chart) |
| SHAP | Top 3 risk drivers with human-readable labels (bar chart) |
| Action | Recommended Action text |
| Navigation | Back button → returns to originating page |

### Tooltip: Customer Risk (320 × 240 px)

**Trigger**: Hover over segment bars (Page 2) or customer data points
**Content**: Name, Segment, Risk Tier (colored), Churn Probability (mini gauge), Top Risk Driver

### Tooltip: Revenue Trend (320 × 180 px)

**Trigger**: Hover over revenue area chart (Page 1)
**Content**: Month/Year, Revenue (`₹Cr`), MoM Growth (arrow), Transaction Count, Avg Txn Value

---

## 9. Zero-Duplication KPI Matrix

| KPI | Page 1 | Page 2 | Page 3 |
|---|---|---|---|
| Total Customers | ✅ Card | — | — |
| Active Customers | ✅ Card | — | — |
| Total Revenue | ✅ Card + Charts | — | — |
| Churn Rate | ✅ Card | — | — |
| Avg CLV | ✅ Card | ✅ Card | — |
| Portfolio CLV | — | ✅ Card | — |
| Avg Products | — | ✅ Card | — |
| Avg Tenure | — | ✅ Card | — |
| Segment Distribution | — | ✅ Stacked Bar | — |
| Revenue by Segment (time) | — | ✅ Ribbon | — |
| Revenue at Risk (expected loss) | — | — | ✅ Card |
| High Risk Count | — | — | ✅ Card |
| Churn Probability | — | — | ✅ Card |
| Campaign ROI | — | — | ✅ Card |
| Avg CSAT | — | — | ✅ Card |
| SHAP Drivers | — | — | ✅ Bar Chart |
| Campaign Funnel | — | — | ✅ Funnel |

---

## 10. SQL-to-Dashboard Traceability

| Dashboard Visual | SQL Source | SQL KPI # |
|---|---|---|
| Revenue Area Chart (P1) | `03_revenue_kpis.sql` | KPI 1: Monthly Revenue Trend |
| Revenue by Card Donut (P1) | `03_revenue_kpis.sql` | KPI 4: Revenue by Card Category |
| Top 10 States Bar (P1) | `03_revenue_kpis.sql` | KPI 7: Revenue by Geography |
| Segment Distribution (P2) | `segmentation_model.py` + `dim_customer` | K-Means clusters × card_category |
| Revenue by Income Treemap (P2) | `03_revenue_kpis.sql` | KPI 3: Revenue by Income Bracket |
| Revenue by Segment Ribbon (P2) | `segmentation_model.py` + `03_revenue_kpis.sql` | Segment revenue over fiscal quarters |
| Top 10 Customers Table (P2) | `02_customer_kpis.sql` | KPI 10: Top Customers by Value |
| Quarterly Revenue Combo (P3) | `03_revenue_kpis.sql` | KPI 2: Quarterly Revenue |
| SHAP Bar Chart (P3) | `churn_model.py` → `export_shap_importance.py` | Feature Importances |
| Campaign Funnel (P3) | `06_campaign_kpis.sql` | KPI 1: Campaign Funnel |
| Top 10 Risk Customers (P3) | `churn_model.py` | SHAP top drivers |

---

## 11. Verification Checklist

| Test | Method | Expected |
|---|---|---|
| Total Revenue | Compare card vs `SELECT SUM(amount) FROM fact_transactions` | Match ± ₹1 |
| Customer Count | Compare card vs `SELECT COUNT(*) FROM dim_customer` | Exact: 10,127 |
| Churn Rate | Compare vs SQL KPI 1 | Match ± 0.1% |
| SHAP CSV rows | `shap_feature_importance` row count | Exact: 10 |
| ML row parity | `ml_churn_predictions` rows = `dim_customer` rows | Exact match |
| Funnel integrity | Targeted ≥ Contacted ≥ Opened ≥ Accepted | Monotonic decrease |
| Relationships | Model View — all 9 active, no ambiguity | ✅ |
| Cross-filters | Click state (P1) → all visuals filter | ✅ |
| Cluster labels | No "Cluster X (General)" in any visual | ✅ |
| Risk driver labels | No technical feature names visible | ✅ |

---

## 12. File Manifest

| File | Purpose |
|---|---|
| `powerbi/FinSight360-Executive.json` | Power BI theme (import via View → Themes) |
| `powerbi/dax_measures.dax` | 22 DAX measures reference (copy into _Measures table) |
| `powerbi/power_query_transforms.m` | Power Query M scripts for all CSV imports and computed columns |
| `src/ml/export_shap_importance.py` | Python script to auto-export SHAP feature importance CSV |
| `data/output/shap_feature_importance.csv` | Auto-generated SHAP data for Power BI (10 features, ranked) |
| `data/output/churn_predictions.csv` | ML churn predictions (loaded by Power Query) |
| `data/output/customer_segments.csv` | ML segments (renamed by Power Query) |
| `docs/dashboard_specs/powerbi_build.md` | Practical build guide for the Power BI report |
