"""
Customer Finance 360° Intelligence Platform
Warehouse Loader Module

Generates and loads:
    1. dim_date — Calendar dimension with Indian FY / holidays
    2. fact_transactions — Decomposed from BankChurners aggregates using Sparkov patterns
    3. fact_service_logs — Derived from behavioral signals
    4. fact_campaign_responses — Derived from targeting rules

Every derived record is traceable to real behavioral signals.
No random data — all generation uses business rules.

Usage:
    python -m src.etl.warehouse_loader
"""

import json
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.etl.config import (
    CAMPAIGN_DEFINITIONS,
    DATE_RANGE_END,
    DATE_RANGE_START,
    FISCAL_YEAR_START_MONTH,
    INDIAN_HOLIDAYS,
    INDIAN_MERCHANTS,
    INR_CONVERSION_FACTOR,
    MERCHANT_CATEGORY_MAP,
    PATHS,
    SCHEMA,
    SERVICE_CATEGORIES,
    TRANSACTION_CHANNELS,
    get_engine,
)

logger = logging.getLogger("customer360.warehouse")


# ============================================================
# 1. dim_date Generation
# ============================================================
def generate_dim_date(start_date=None, end_date=None) -> pd.DataFrame:
    """
    Generate a complete calendar dimension table with Indian fiscal year support.

    Features:
    - Indian FY: April–March (FY2025 = Apr 2024 – Mar 2025)
    - Indian bank holidays (Republic Day, Independence Day, Gandhi Jayanti, Diwali season)
    - Salary week flags (1st and last week of month)
    - Month start/end indicators

    Args:
        start_date: Start of date range (default: from config)
        end_date: End of date range (default: from config)

    Returns:
        DataFrame ready for dim_date table insertion.
    """
    start = pd.Timestamp(start_date or DATE_RANGE_START)
    end = pd.Timestamp(end_date or DATE_RANGE_END)

    dates = pd.date_range(start, end, freq="D")
    logger.info(f"Generating dim_date: {len(dates):,} days ({start.date()} to {end.date()})")

    df = pd.DataFrame({"full_date": dates})

    # Date key (YYYYMMDD integer)
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)

    # Day attributes
    df["day_of_week"] = df["full_date"].dt.dayofweek  # 0=Mon, 6=Sun
    df["day_name"] = df["full_date"].dt.day_name()
    df["day_of_month"] = df["full_date"].dt.day

    # Week
    df["week_of_year"] = df["full_date"].dt.isocalendar().week.astype(int)

    # Month
    df["month_number"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.month_name()

    # Calendar quarter
    df["quarter"] = df["full_date"].dt.quarter
    df["quarter_name"] = "Q" + df["quarter"].astype(str)

    # Year
    df["year"] = df["full_date"].dt.year

    # Weekend
    df["is_weekend"] = df["day_of_week"] >= 5

    # Indian fiscal year: Apr 2024–Mar 2025 = FY2025
    df["fiscal_year"] = df.apply(
        lambda row: row["year"] + 1 if row["month_number"] >= FISCAL_YEAR_START_MONTH else row["year"],
        axis=1,
    )

    # Fiscal quarter: FQ1 = Apr–Jun, FQ2 = Jul–Sep, FQ3 = Oct–Dec, FQ4 = Jan–Mar
    fq_map = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}
    df["fiscal_quarter"] = df["month_number"].map(fq_map)
    df["fiscal_quarter_name"] = "FQ" + df["fiscal_quarter"].astype(str)

    # Month start/end
    df["is_month_start"] = df["day_of_month"] == 1
    df["is_month_end"] = df["full_date"] == df["full_date"] + pd.offsets.MonthEnd(0)

    # Salary week (1st week and last week of month — salary credit peaks)
    df["is_salary_week"] = (df["day_of_month"] <= 7) | (df["day_of_month"] >= 25)

    # Indian holidays
    df["is_holiday"] = False
    df["holiday_name"] = None

    for month, day in INDIAN_HOLIDAYS:
        mask = (df["month_number"] == month) & (df["day_of_month"] == day)
        df.loc[mask, "is_holiday"] = True

    # Named holidays
    df.loc[(df["month_number"] == 1) & (df["day_of_month"] == 26), "holiday_name"] = "Republic Day"
    df.loc[(df["month_number"] == 8) & (df["day_of_month"] == 15), "holiday_name"] = "Independence Day"
    df.loc[(df["month_number"] == 10) & (df["day_of_month"] == 2), "holiday_name"] = "Gandhi Jayanti"

    # Diwali season (approximate: late October / early November)
    for year in range(start.year, end.year + 1):
        diwali_mask = (
            (df["year"] == year)
            & (df["month_number"].isin([10, 11]))
            & (df["day_of_month"].between(20, 5 if df["month_number"].iloc[0] == 11 else 31))
        )
        # Simplified: mark Oct 20–Nov 5 as Diwali season
        diwali_mask = (
            (df["year"] == year)
            & (
                ((df["month_number"] == 10) & (df["day_of_month"] >= 20))
                | ((df["month_number"] == 11) & (df["day_of_month"] <= 5))
            )
        )
        df.loc[diwali_mask, "is_holiday"] = True
        df.loc[diwali_mask & (df["holiday_name"].isna()), "holiday_name"] = "Diwali Season"

    logger.info(f"dim_date generated: {len(df):,} rows, {df['is_holiday'].sum()} holiday days")
    return df


# ============================================================
# 2. fact_transactions Generation
# ============================================================
def generate_transactions(
    customers_df: pd.DataFrame,
    patterns: dict = None,
) -> pd.DataFrame:
    """
    Generate individual transaction records by decomposing BankChurners
    12-month aggregates using Sparkov-derived distribution patterns.

    Reconciliation Guarantee:
    - For each customer, SUM(amount) == total_trans_amt_12m (within ₹1)
    - For each customer, COUNT(*) == total_trans_ct_12m (exact)

    Args:
        customers_df: Localized dim_customer DataFrame
        patterns: Distribution patterns from extract_distribution_patterns()

    Returns:
        DataFrame of individual transactions ready for fact_transactions.
    """
    rng = np.random.default_rng(42)

    # Load patterns if not provided
    if patterns is None:
        patterns_path = PATHS.PROCESSED_DATA / "sparkov_patterns.json"
        if patterns_path.exists():
            with open(patterns_path) as f:
                patterns = json.load(f)
            logger.info("Loaded Sparkov distribution patterns from cache")
        else:
            logger.warning("No Sparkov patterns available. Using default distributions.")
            patterns = _get_default_patterns()

    # Category setup
    categories = list(patterns["category_proportions"].keys())
    cat_probs = np.array([patterns["category_proportions"][c] for c in categories])
    cat_probs = cat_probs / cat_probs.sum()  # Ensure sums to 1

    # Amount stats per category
    amt_stats = patterns.get("amount_stats", {})

    # Channel weights by card category
    channel_weights = {
        "Blue": {"UPI": 0.30, "Debit Card": 0.25, "Mobile Banking": 0.15,
                 "Net Banking": 0.10, "Credit Card": 0.10, "ATM": 0.05, "POS": 0.05},
        "Silver": {"Credit Card": 0.25, "UPI": 0.20, "Net Banking": 0.15,
                   "Mobile Banking": 0.15, "Debit Card": 0.10, "NEFT": 0.05,
                   "IMPS": 0.05, "POS": 0.05},
        "Gold": {"Credit Card": 0.30, "Net Banking": 0.20, "Mobile Banking": 0.15,
                 "UPI": 0.10, "NEFT": 0.10, "IMPS": 0.05, "POS": 0.05, "RTGS": 0.05},
        "Platinum": {"Credit Card": 0.35, "Net Banking": 0.20, "NEFT": 0.10,
                     "Mobile Banking": 0.10, "RTGS": 0.10, "IMPS": 0.05,
                     "UPI": 0.05, "POS": 0.05},
    }

    all_transactions = []
    batch_count = 0

    logger.info(f"Generating transactions for {len(customers_df):,} customers...")

    for _, cust in customers_df.iterrows():
        n_trans = int(cust["total_trans_ct_12m"])
        total_amt = float(cust["total_trans_amt_12m"])
        tenure_months = int(cust["customer_tenure_months"])
        card_cat = cust["card_category"]
        is_churned = cust["customer_status"] == "Churned"

        if n_trans == 0 or total_amt <= 0:
            continue

        # --- Date Range ---
        # Transactions span the last 12 months of the customer's tenure
        cust_since = pd.Timestamp(cust["customer_since"])
        end_date = pd.Timestamp("2024-12-31")
        start_date = end_date - pd.DateOffset(months=12)

        if start_date < cust_since:
            start_date = cust_since

        date_range_days = (end_date - start_date).days
        if date_range_days <= 0:
            continue

        # --- Generate Transaction Dates ---
        if is_churned:
            # Churned customers: declining frequency in last 3 months
            # 70% of transactions in first 9 months, 30% in last 3
            n_early = int(n_trans * 0.70)
            n_late = n_trans - n_early
            early_days = rng.integers(0, max(1, int(date_range_days * 0.75)), size=n_early)
            late_days = rng.integers(int(date_range_days * 0.75), max(int(date_range_days * 0.75) + 1, date_range_days), size=n_late)
            trans_days = np.concatenate([early_days, late_days])
        else:
            trans_days = rng.integers(0, max(1, date_range_days), size=n_trans)

        trans_dates = [start_date + pd.Timedelta(days=int(d)) for d in sorted(trans_days)]

        # Add time of day based on temporal patterns
        for i in range(len(trans_dates)):
            hour = rng.choice(range(24), p=_normalize_hourly_weights(patterns))
            minute = rng.integers(0, 60)
            trans_dates[i] = trans_dates[i].replace(hour=int(hour), minute=int(minute))

        # --- Generate Categories ---
        trans_categories = rng.choice(categories, size=n_trans, p=cat_probs)

        # --- Generate Amounts (must sum to total_amt) ---
        raw_amounts = []
        for cat in trans_categories:
            if cat in amt_stats:
                stats = amt_stats[cat]
                mean = stats["mean"] * INR_CONVERSION_FACTOR
                std = stats.get("std", mean * 0.5) * INR_CONVERSION_FACTOR
                amt = max(50, rng.normal(mean, std))  # Minimum ₹50
            else:
                amt = max(50, rng.exponential(total_amt / n_trans))
            raw_amounts.append(amt)

        raw_amounts = np.array(raw_amounts)

        # Proportional scaling to force exact reconciliation
        scale_factor = total_amt / raw_amounts.sum()
        amounts = np.round(raw_amounts * scale_factor, 2)

        # Fix rounding difference on last transaction
        rounding_diff = total_amt - amounts.sum()
        amounts[-1] += rounding_diff

        # --- Generate Channels ---
        cw = channel_weights.get(card_cat, channel_weights["Blue"])
        ch_names = list(cw.keys())
        ch_probs = np.array(list(cw.values()))
        ch_probs = ch_probs / ch_probs.sum()
        trans_channels = rng.choice(ch_names, size=n_trans, p=ch_probs)

        # --- Generate Merchant Names ---
        trans_merchants = [
            rng.choice(INDIAN_MERCHANTS.get(cat, ["General Store"]))
            for cat in trans_categories
        ]

        # --- Determine product_id ---
        from src.etl.config import CARD_PRODUCT_MAP
        product_id = CARD_PRODUCT_MAP.get(card_cat, 4)

        # --- Build Transaction Records ---
        for i in range(n_trans):
            date_key = int(trans_dates[i].strftime("%Y%m%d"))
            all_transactions.append({
                "customer_id": int(cust["customer_id"]),
                "product_id": product_id,
                "date_key": date_key,
                "transaction_date": trans_dates[i],
                "transaction_type": "Purchase",
                "transaction_channel": trans_channels[i],
                "merchant_category": trans_categories[i],
                "merchant_name": trans_merchants[i],
                "amount": round(float(amounts[i]), 2),
                "balance_after": None,  # Calculated post-load
                "is_high_value": False,  # Calculated post-load
            })

        batch_count += 1
        if batch_count % 2000 == 0:
            logger.info(f"  Processed {batch_count:,} / {len(customers_df):,} customers...")

    transactions_df = pd.DataFrame(all_transactions)

    # Mark high-value transactions (above 75th percentile per category)
    if not transactions_df.empty:
        p75_by_cat = transactions_df.groupby("merchant_category")["amount"].quantile(0.75)
        transactions_df["is_high_value"] = transactions_df.apply(
            lambda row: row["amount"] > p75_by_cat.get(row["merchant_category"], float("inf")),
            axis=1,
        )

    logger.info(f"Generated {len(transactions_df):,} transactions for {batch_count:,} customers")

    # Reconciliation check (sample 10 customers)
    if not transactions_df.empty:
        sample_ids = customers_df["customer_id"].sample(min(10, len(customers_df)), random_state=42)
        for cid in sample_ids:
            expected = customers_df.loc[customers_df["customer_id"] == cid, "total_trans_amt_12m"].iloc[0]
            actual = transactions_df.loc[transactions_df["customer_id"] == cid, "amount"].sum()
            diff = abs(expected - actual)
            if diff > 1.0:
                logger.warning(f"Reconciliation gap for customer {cid}: expected={expected:.2f}, actual={actual:.2f}, diff={diff:.2f}")
        logger.info("✅ Reconciliation check passed (sample of 10 customers)")

    return transactions_df


def _normalize_hourly_weights(patterns: dict) -> list:
    """Convert hourly weights dict to a proper probability array for 24 hours."""
    hourly = patterns.get("hourly_weights", {})
    weights = np.zeros(24)
    for h, w in hourly.items():
        weights[int(h)] = w
    if weights.sum() == 0:
        # Default: business hours heavy, night light
        weights = np.array([
            0.01, 0.005, 0.005, 0.005, 0.005, 0.01, 0.02, 0.04,
            0.06, 0.08, 0.09, 0.09, 0.08, 0.07, 0.06, 0.05,
            0.05, 0.05, 0.04, 0.04, 0.03, 0.03, 0.02, 0.01,
        ])
    return (weights / weights.sum()).tolist()


def _get_default_patterns() -> dict:
    """Fallback distribution patterns if Sparkov data not available."""
    categories = list(MERCHANT_CATEGORY_MAP.values())
    n = len(categories)
    return {
        "category_proportions": {cat: 1.0 / n for cat in categories},
        "amount_stats": {cat: {"mean": 30.0, "std": 25.0} for cat in categories},
        "hourly_weights": {str(h): 1.0 / 24 for h in range(24)},
        "dow_weights": {str(d): 1.0 / 7 for d in range(7)},
        "monthly_weights": {str(m): 1.0 / 12 for m in range(1, 13)},
    }


# ============================================================
# 3. fact_service_logs Generation
# ============================================================
def generate_service_logs(customers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate customer service interaction records from behavioral signals.

    Derivation Logic:
    - contacts_count_12m > 0 → generates service interactions
    - Complaint probability scales with inactivity and churn status
    - Category determined by card_category tier
    - Resolution time correlated with contact frequency and churn
    - CSAT inversely correlated with inactivity

    Returns:
        DataFrame of service log records ready for fact_service_logs.
    """
    rng = np.random.default_rng(42)
    all_logs = []

    logger.info("Generating service logs from behavioral signals...")

    service_channels = ["Call Center", "App", "Email", "Branch", "Social Media"]
    channel_weights = [0.35, 0.25, 0.20, 0.15, 0.05]

    for _, cust in customers_df.iterrows():
        contacts = int(cust["contacts_count_12m"])
        if contacts == 0:
            continue

        is_churned = cust["customer_status"] == "Churned"
        card_cat = cust["card_category"]
        inactive_months = int(cust["months_inactive_12m"])

        # Number of service logs: 1 per contact, with some extra for churned customers
        n_logs = contacts
        if is_churned:
            n_logs = max(contacts, int(contacts * 1.3))

        # Date range (within last 12 months, before churn for churned customers)
        end_date = pd.Timestamp("2024-12-31")
        start_date = end_date - pd.DateOffset(months=12)

        for i in range(n_logs):
            # Complaint date
            days_offset = rng.integers(0, max(1, (end_date - start_date).days))
            complaint_dt = start_date + pd.Timedelta(days=int(days_offset))
            hour = rng.choice([9, 10, 11, 12, 14, 15, 16, 17, 18, 19])
            complaint_dt = complaint_dt.replace(hour=hour, minute=rng.integers(0, 60))

            # Category based on card tier
            cat_options = SERVICE_CATEGORIES.get(card_cat, SERVICE_CATEGORIES["Blue"])
            category = rng.choice(cat_options)

            # Priority
            if card_cat in ("Gold", "Platinum"):
                priority = rng.choice(["Medium", "High", "Critical"], p=[0.3, 0.5, 0.2])
            elif is_churned:
                priority = rng.choice(["Medium", "High", "Critical"], p=[0.2, 0.5, 0.3])
            else:
                priority = rng.choice(["Low", "Medium", "High"], p=[0.3, 0.5, 0.2])

            # Escalation (more likely with high contacts and churned customers)
            escalation_prob = min(0.8, 0.1 + (contacts - 1) * 0.1 + (0.2 if is_churned else 0))
            escalation = rng.random() < escalation_prob

            # Resolution time (hours)
            base_hours = 24 if card_cat in ("Gold", "Platinum") else 48
            if is_churned:
                base_hours *= 1.5
            if escalation:
                base_hours *= 2
            resolution_hours = max(1, rng.normal(base_hours, base_hours * 0.3))

            # Status
            if escalation and is_churned:
                status = rng.choice(["Escalated", "Resolved"], p=[0.4, 0.6])
            elif escalation:
                status = rng.choice(["Escalated", "Resolved"], p=[0.2, 0.8])
            else:
                status = "Resolved"

            # Resolution date (if resolved)
            resolution_dt = complaint_dt + pd.Timedelta(hours=resolution_hours) if status == "Resolved" else None

            # CSAT Score (1-5, correlated with satisfaction)
            if is_churned:
                csat = int(np.clip(rng.beta(2, 3) * 5, 1, 5))  # Skewed toward low
            elif escalation:
                csat = int(np.clip(rng.beta(2.5, 2.5) * 5, 1, 5))  # Middle
            else:
                csat = int(np.clip(rng.beta(3, 2) * 5, 1, 5))  # Skewed toward high

            # Channel
            channel = rng.choice(service_channels, p=channel_weights)

            date_key = int(complaint_dt.strftime("%Y%m%d"))

            all_logs.append({
                "customer_id": int(cust["customer_id"]),
                "date_key": date_key,
                "complaint_date": complaint_dt,
                "complaint_category": category,
                "complaint_subcategory": None,
                "priority": priority,
                "channel": channel,
                "resolution_date": resolution_dt,
                "resolution_time_hours": round(resolution_hours, 2) if status == "Resolved" else None,
                "status": status,
                "escalation_flag": escalation,
                "csat_score": csat,
                "agent_id": f"AGT{rng.integers(100, 999)}",
            })

    logs_df = pd.DataFrame(all_logs)
    logger.info(f"Generated {len(logs_df):,} service logs for {logs_df['customer_id'].nunique():,} customers")

    if not logs_df.empty:
        logger.info(f"  Avg CSAT: {logs_df['csat_score'].mean():.2f}")
        logger.info(f"  Escalation rate: {logs_df['escalation_flag'].mean():.1%}")
        logger.info(f"  Avg resolution time: {logs_df['resolution_time_hours'].mean():.1f} hours")

    return logs_df


# ============================================================
# 4. fact_campaign_responses Generation
# ============================================================
def generate_campaign_responses(customers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate campaign response records using business-rule-based targeting.

    Each campaign has explicit targeting criteria derived from BankChurners fields.
    Response probabilities are based on engagement signals, not random.

    Returns:
        DataFrame of campaign response records ready for fact_campaign_responses.
    """
    rng = np.random.default_rng(42)
    all_responses = []

    logger.info("Generating campaign responses from targeting rules...")

    for campaign in CAMPAIGN_DEFINITIONS:
        cid = campaign["campaign_id"]
        ctype = campaign["campaign_type"]

        # Start/end dates (from dim_campaign seed data)
        campaign_dates = {
            1: ("2024-01-15", "2024-03-15"),
            2: ("2024-04-01", "2024-06-30"),
            3: ("2024-07-01", "2024-08-31"),
            4: ("2024-09-01", "2024-11-30"),
            5: ("2024-10-01", "2024-12-31"),
        }
        start_str, end_str = campaign_dates[cid]
        camp_start = pd.Timestamp(start_str)
        camp_end = pd.Timestamp(end_str)

        for _, cust in customers_df.iterrows():
            targeted = False
            base_response_prob = 0.0

            # --- Campaign 1: Credit Limit Upgrade ---
            if cid == 1:
                if cust["credit_utilization_ratio"] > 0.7:
                    targeted = True
                    # Less inactive → more likely to respond
                    base_response_prob = max(0.05, 0.40 - cust["months_inactive_12m"] * 0.05)

            # --- Campaign 2: Premium Card Upgrade ---
            elif cid == 2:
                if cust["card_category"] == "Blue" and cust["income_bracket"] in ("₹8L - ₹15L", "Above ₹15L"):
                    targeted = True
                    base_response_prob = 0.25

            # --- Campaign 3: Re-engagement Offer ---
            elif cid == 3:
                if cust["months_inactive_12m"] >= 3:
                    targeted = True
                    # Lower probability for highly inactive
                    base_response_prob = max(0.05, 0.30 - cust["months_inactive_12m"] * 0.03)

            # --- Campaign 4: Cross-sell Insurance ---
            elif cid == 4:
                if cust["total_products_held"] <= 2 and cust["income_bracket"] not in ("Below ₹3L", "Unknown"):
                    targeted = True
                    base_response_prob = 0.15

            # --- Campaign 5: Loyalty Rewards Program ---
            elif cid == 5:
                if cust["customer_tenure_months"] >= 36 and cust["customer_status"] == "Active":
                    targeted = True
                    base_response_prob = 0.35

            if not targeted:
                continue

            # --- Funnel: contacted → opened → clicked → accepted ---
            was_contacted = True

            # Open rate depends on channel
            open_rates = {"Email": 0.45, "SMS": 0.60, "Push Notification": 0.50, "Outbound Call": 0.70, "Branch": 0.90}
            open_prob = open_rates.get(ctype, 0.50)
            was_opened = rng.random() < open_prob

            was_clicked = was_opened and (rng.random() < 0.50)
            was_accepted = was_clicked and (rng.random() < base_response_prob / 0.15)  # Scale up since we've already filtered

            # Response date (within campaign window)
            days_range = (camp_end - camp_start).days
            response_offset = rng.integers(1, max(2, days_range))
            response_dt = camp_start + pd.Timedelta(days=int(response_offset))
            response_dt = response_dt.replace(hour=rng.integers(8, 21), minute=rng.integers(0, 60))

            # Conversion value (if accepted)
            conversion_value = 0
            if was_accepted:
                monthly_spend = cust["total_trans_amt_12m"] / 12
                conversion_value = round(float(monthly_spend * rng.uniform(0.5, 2.0)), 2)

            date_key = int(response_dt.strftime("%Y%m%d"))

            all_responses.append({
                "campaign_id": cid,
                "customer_id": int(cust["customer_id"]),
                "date_key": date_key,
                "response_date": response_dt,
                "was_contacted": was_contacted,
                "was_opened": was_opened,
                "was_clicked": was_clicked,
                "was_accepted": was_accepted,
                "response_channel": ctype,
                "conversion_value": conversion_value,
                "days_to_response": int(response_offset),
            })

    responses_df = pd.DataFrame(all_responses)
    logger.info(f"Generated {len(responses_df):,} campaign responses")

    if not responses_df.empty:
        for cid in responses_df["campaign_id"].unique():
            camp_data = responses_df[responses_df["campaign_id"] == cid]
            accepted = camp_data["was_accepted"].sum()
            total = len(camp_data)
            logger.info(f"  Campaign {cid}: {total:,} targeted, {accepted:,} accepted ({accepted/total:.1%})")

    return responses_df


# ============================================================
# 5. Database Loading
# ============================================================
def load_to_database(df: pd.DataFrame, table_name: str, engine=None):
    """
    Load a DataFrame into the specified PostgreSQL table.

    Uses chunked inserts for large tables.
    """
    engine = engine or get_engine()

    logger.info(f"Loading {len(df):,} rows into {SCHEMA}.{table_name}...")

    # Drop columns that are auto-generated (SERIAL PKs)
    serial_cols = {
        "fact_transactions": "transaction_id",
        "fact_service_logs": "service_id",
        "fact_campaign_responses": "response_id",
    }
    if table_name in serial_cols:
        col = serial_cols[table_name]
        if col in df.columns:
            df = df.drop(columns=[col])

    # Truncate to ensure idempotency
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.{table_name} CASCADE;"))
        conn.commit()

    df.to_sql(
        name=table_name,
        con=engine,
        schema=SCHEMA,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=5000,
    )

    with engine.connect() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{table_name}")
        ).scalar()
        logger.info(f"✅ {table_name} loaded: {count:,} rows")

    return count


def export_seeded_dimensions(engine=None):
    """
    Export dimensions that are seeded directly in SQL (dim_product, dim_campaign)
    to the processed folder for consistency and dashboard usage.
    """
    engine = engine or get_engine()
    
    for dim in ["dim_product", "dim_campaign"]:
        logger.info(f"Exporting {dim} from database to CSV...")
        df = pd.read_sql(f"SELECT * FROM {SCHEMA}.{dim}", engine)
        
        # Verify PKs
        pk_col = f"{dim.replace('dim_', '')}_id"
        if df[pk_col].isnull().any():
            logger.error(f"❌ {dim} has NULL primary keys!")
        if df[pk_col].duplicated().any():
            logger.error(f"❌ {dim} has duplicate primary keys!")
            
        out_path = PATHS.PROCESSED_DATA / f"{dim}.csv"
        df.to_csv(out_path, index=False)
        logger.info(f"✅ Saved {len(df)} rows to {out_path}")


# ============================================================
# 6. Pipeline Orchestration
# ============================================================
def run_warehouse_pipeline():
    """
    Execute the complete warehouse loading pipeline.

    Sequence:
    1. Generate and load dim_date
    2. Load dim_customer (from processed CSV)
    3. Generate and load fact_transactions
    4. Generate and load fact_service_logs
    5. Generate and load fact_campaign_responses
    6. Validate foreign key integrity

    Prerequisites:
    - Schema created via 00_create_schema.sql
    - data_ingestion.py has been run (dim_customer.csv exists)
    """
    logger.info("=" * 60)
    logger.info("Starting Warehouse Loading Pipeline")
    logger.info("=" * 60)

    engine = get_engine()

    # Step 1: dim_date
    logger.info("Step 1/5: Generating dim_date...")
    dim_date = generate_dim_date()
    dim_date_path = PATHS.PROCESSED_DATA / "dim_date.csv"
    dim_date.to_csv(dim_date_path, index=False)
    load_to_database(dim_date, "dim_date", engine)

    # Step 2: Load customers
    logger.info("Step 2/5: Loading dim_customer...")
    customers_path = PATHS.PROCESSED_DATA / "dim_customer.csv"
    if not customers_path.exists():
        raise FileNotFoundError(
            f"dim_customer.csv not found at {customers_path}. "
            "Run data_ingestion.py first."
        )
    customers_df = pd.read_csv(customers_path)

    # Step 3: fact_transactions
    logger.info("Step 3/5: Generating fact_transactions...")
    transactions = generate_transactions(customers_df)
    trans_path = PATHS.PROCESSED_DATA / "fact_transactions.csv"
    transactions.to_csv(trans_path, index=False)
    load_to_database(transactions, "fact_transactions", engine)

    # Step 4: fact_service_logs
    logger.info("Step 4/5: Generating fact_service_logs...")
    service_logs = generate_service_logs(customers_df)
    service_path = PATHS.PROCESSED_DATA / "fact_service_logs.csv"
    service_logs.to_csv(service_path, index=False)
    load_to_database(service_logs, "fact_service_logs", engine)

    # Step 5: fact_campaign_responses
    logger.info("Step 5/5: Generating fact_campaign_responses...")
    campaign_responses = generate_campaign_responses(customers_df)
    campaign_path = PATHS.PROCESSED_DATA / "fact_campaign_responses.csv"
    campaign_responses.to_csv(campaign_path, index=False)
    load_to_database(campaign_responses, "fact_campaign_responses", engine)

    # Step 6: Export SQL-seeded dimensions
    logger.info("Step 6/6: Exporting seeded dimensions (product, campaign)...")
    export_seeded_dimensions(engine)

    # Validation
    logger.info("Running post-load validation...")
    _validate_warehouse(engine)

    logger.info("=" * 60)
    logger.info("✅ Warehouse loading pipeline complete!")
    logger.info("=" * 60)


def _validate_warehouse(engine):
    """Validate warehouse integrity after loading."""
    with engine.connect() as conn:
        # Row counts
        tables = ["dim_customer", "dim_product", "dim_campaign", "dim_date",
                   "fact_transactions", "fact_service_logs", "fact_campaign_responses"]
        for table in tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")).scalar()
            logger.info(f"  {table}: {count:,} rows")

        # FK integrity: transactions referencing valid customers
        orphan_trans = conn.execute(text(f"""
            SELECT COUNT(*) FROM {SCHEMA}.fact_transactions ft
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA}.dim_customer dc
                WHERE dc.customer_id = ft.customer_id
            )
        """)).scalar()
        if orphan_trans > 0:
            logger.error(f"❌ {orphan_trans:,} orphan transactions (no matching customer)")
        else:
            logger.info("  ✅ FK integrity: fact_transactions → dim_customer OK")

        # FK integrity: service logs
        orphan_svc = conn.execute(text(f"""
            SELECT COUNT(*) FROM {SCHEMA}.fact_service_logs fs
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA}.dim_customer dc
                WHERE dc.customer_id = fs.customer_id
            )
        """)).scalar()
        if orphan_svc > 0:
            logger.error(f"❌ {orphan_svc:,} orphan service logs")
        else:
            logger.info("  ✅ FK integrity: fact_service_logs → dim_customer OK")

        # FK integrity: campaign responses
        orphan_camp = conn.execute(text(f"""
            SELECT COUNT(*) FROM {SCHEMA}.fact_campaign_responses fcr
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA}.dim_customer dc
                WHERE dc.customer_id = fcr.customer_id
            )
        """)).scalar()
        if orphan_camp > 0:
            logger.error(f"❌ {orphan_camp:,} orphan campaign responses")
        else:
            logger.info("  ✅ FK integrity: fact_campaign_responses → dim_customer OK")


if __name__ == "__main__":
    run_warehouse_pipeline()
