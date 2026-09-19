# Advanced Data Generation Specification
> **For future data generation pipeline runs only.** Do not execute unless a full data refresh is required.

## Overview
To improve the portfolio-grade quality of the dataset, the next iteration of the data generation pipeline must enforce macroeconomic realism, strict seasonality, and nuanced customer lifecycles.

## 1. Macroeconomic Cycles
The synthetic transactions currently lack temporal macroeconomic variation. Update the pipeline to include:
- **Inflation Simulation:** Increase average transaction value by 4.5% year-over-year.
- **Interest Rate Sensitivity:** For loan and credit products, simulate higher default rates and lower originations during simulated "high-interest" periods (e.g., Q2-Q3).

## 2. Realistic Seasonality (Indian Context)
- **Festival Spikes:** Transaction volume and frequency must spike by 30-40% during October-November (Diwali) and 15% in late December.
- **Salary Cycles:** Increase high-value transactions (investments, bill payments) within 3 days of the `is_salary_week` flag (1st of the month).
- **Tax Season:** Spike in investment products and tax-saving mutual funds during February-March.

## 3. Customer Lifecycle & Churn Behavior
- **Tenure-based Attrition:** Churn probability should be highest in the first 6 months (early attrition) and spike again around the 24-month mark (product maturity).
- **Engagement Tapering:** Instead of abrupt churn, simulate a gradual 3-month decline in transaction frequency before the churn event to allow predictive models (like the Random Forest) to capture the signal more realistically.
- **Multi-Product Stickiness:** Customers with `total_products_held >= 3` should have their baseline churn probability reduced by 60%.

## 4. Product & Channel Distribution
- **Channel Shift:** Simulate a gradual transition from 'Branch' and 'Web' to 'Mobile Banking' over the timeline (e.g., Mobile usage should grow 15% YoY).
- **Balanced Segments:** Ensure that high-net-worth individuals (HNWIs) constitute no more than 8-12% of the total customer base to maintain a realistic portfolio distribution, but contribute to >30% of the revenue.

## Execution Checklist
When rebuilding the data generation script (`warehouse_loader.py` or a dedicated generator):
- [ ] Implement `SeasonalityMultiplier` class.
- [ ] Implement `MacroEconomicTrend` class.
- [ ] Update `fact_transactions` generator to apply these multipliers to `amount` and frequency.
- [ ] Re-run full pipeline and validate `02_customer_kpis.sql` to ensure distributions match specifications.
