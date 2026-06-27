"""
Customer Finance 360° Intelligence Platform
Data Ingestion Module

Reads raw CSV datasets, applies Indian localization,
and loads into PostgreSQL staging tables.

Source Datasets:
    1. BankChurners.csv → dim_customer (after localization)
    2. fraudTrain.csv + fraudTest.csv → distribution template for fact_transactions

Usage:
    python -m src.etl.data_ingestion
"""

import hashlib
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.etl.config import (
    CHURN_LABEL_MAP,
    INCOME_BRACKET_MAP,
    INR_CONVERSION_FACTOR,
    INDIAN_CITIES,
    INDIAN_STATES,
    MERCHANT_CATEGORY_MAP,
    PATHS,
    SCHEMA,
    get_engine,
)

logger = logging.getLogger("customer360.ingestion")


# ============================================================
# 1. BankChurners Ingestion → dim_customer
# ============================================================
def load_bankchurners(filepath=None) -> pd.DataFrame:
    """
    Load and validate BankChurners.csv.
    
    Returns:
        Raw DataFrame with original column names.
    
    Raises:
        FileNotFoundError: If CSV file is missing.
        ValueError: If critical columns are absent.
    """
    filepath = filepath or PATHS.BANKCHURNERS_CSV
    
    if not filepath.exists():
        raise FileNotFoundError(
            f"BankChurners.csv not found at {filepath}. "
            "Download from: https://www.kaggle.com/datasets/sakshigoyal7/credit-card-customers"
        )
    
    logger.info(f"Loading BankChurners from {filepath}")
    df = pd.read_csv(filepath)
    
    # Drop the two Naive Bayes columns (model artifacts, not raw data)
    naive_cols = [c for c in df.columns if "Naive" in c or "Bayes" in c]
    if naive_cols:
        df.drop(columns=naive_cols, inplace=True)
        logger.info(f"Dropped {len(naive_cols)} Naive Bayes columns")
    
    # Validate required columns
    required = [
        "CLIENTNUM", "Attrition_Flag", "Customer_Age", "Gender",
        "Dependent_count", "Education_Level", "Marital_Status",
        "Income_Category", "Card_Category", "Months_on_book",
        "Total_Relationship_Count", "Months_Inactive_12_mon",
        "Contacts_Count_12_mon", "Credit_Limit", "Total_Revolving_Bal",
        "Avg_Open_To_Buy", "Total_Amt_Chng_Q4_Q1", "Total_Trans_Amt",
        "Total_Trans_Ct", "Total_Ct_Chng_Q4_Q1", "Avg_Utilization_Ratio",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    logger.info(f"Loaded {len(df):,} customers, {len(df.columns)} columns")
    logger.info(f"Churn distribution: {df['Attrition_Flag'].value_counts().to_dict()}")
    return df


def localize_customer_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform BankChurners data into Indian banking context.
    
    Localization rules:
    - Convert income brackets to INR
    - Scale monetary values by INR_CONVERSION_FACTOR
    - Assign Indian states and cities
    - Generate Indian names
    - Derive customer_since from Months_on_book
    - Assign risk categories and preferred channels
    
    Statistical Integrity:
    - Income bracket ordering preserved
    - Credit limit distribution preserved (scaled)
    - Behavioral ratios unchanged
    - Geographic distribution weighted by real urban population
    """
    logger.info("Applying Indian localization to customer data")
    rng = np.random.default_rng(42)  # Reproducible randomness
    n = len(df)
    
    result = pd.DataFrame()
    
    # --- Core Identity ---
    result["customer_id"] = df["CLIENTNUM"].values
    
    # Generate Indian names (deterministic from customer_id)
    result["first_name"] = _generate_indian_names(df["CLIENTNUM"], df["Gender"], "first", rng)
    result["last_name"] = _generate_indian_names(df["CLIENTNUM"], df["Gender"], "last", rng)
    
    # --- Demographics ---
    result["age"] = df["Customer_Age"].values
    result["gender"] = df["Gender"].map({"M": "Male", "F": "Female"}).values
    result["dependents"] = df["Dependent_count"].values
    result["education_level"] = df["Education_Level"].replace("Unknown", None).values
    result["marital_status"] = df["Marital_Status"].replace("Unknown", None).values
    result["income_bracket"] = df["Income_Category"].map(INCOME_BRACKET_MAP).values
    
    # --- Geography (weighted by Indian urban population) ---
    states = list(INDIAN_STATES.keys())
    state_weights = list(INDIAN_STATES.values())
    assigned_states = rng.choice(states, size=n, p=state_weights)
    result["state"] = assigned_states
    result["city"] = [
        rng.choice(INDIAN_CITIES[s]) for s in assigned_states
    ]
    
    # --- Tenure & Status ---
    result["customer_tenure_months"] = df["Months_on_book"].values
    # Derive customer_since: data cutoff assumed Dec 2024
    cutoff = pd.Timestamp("2024-12-31")
    result["customer_since"] = [
        (cutoff - pd.DateOffset(months=int(m))).strftime("%Y-%m-%d")
        for m in df["Months_on_book"]
    ]
    result["customer_status"] = df["Attrition_Flag"].map(CHURN_LABEL_MAP).values
    
    # --- Financial (scaled to INR) ---
    result["credit_limit"] = (df["Credit_Limit"] * INR_CONVERSION_FACTOR).round(-2)  # Round to nearest ₹100
    result["total_revolving_bal"] = (df["Total_Revolving_Bal"] * INR_CONVERSION_FACTOR).round(2)
    result["avg_open_to_buy"] = (df["Avg_Open_To_Buy"] * INR_CONVERSION_FACTOR).round(2)
    result["credit_utilization_ratio"] = df["Avg_Utilization_Ratio"].round(4)
    
    # --- Product & Behavior ---
    # Procedural Assignment for Business Realism
    # Premium Card relies on income, spend, and tenure.
    income_score = result["income_bracket"].map({"Above ₹15L": 4, "₹8L - ₹15L": 3, "₹4L - ₹8L": 2, "Below ₹4L": 1}).fillna(1)
    spend_pct = df["Total_Trans_Amt"].rank(pct=True)
    tenure_pct = result["customer_tenure_months"].rank(pct=True)
    
    premium_score = (income_score * 1.4) + (spend_pct * 2.5) + (tenure_pct * 2.0) + rng.normal(0, 1.5, size=n)
    premium_ranks = premium_score.rank(pct=True)
    
    conditions = [
        premium_ranks >= 0.95,
        premium_ranks >= 0.85,
        premium_ranks >= 0.40
    ]
    choices = ["Platinum", "Gold", "Silver"]
    result["card_category"] = np.select(conditions, choices, default="Blue")
    
    # Products held relies on income, spend, tenure and card category
    base_products = np.ones(n)
    base_products += (income_score >= 3).astype(int)
    base_products += (spend_pct > 0.6).astype(int)
    base_products += (spend_pct > 0.9).astype(int)
    base_products += (tenure_pct > 0.6).astype(int)
    base_products += (result["card_category"].isin(["Platinum", "Gold"])).astype(int)
    
    noise = rng.integers(-1, 2, size=n)
    result["total_products_held"] = np.clip(base_products + noise, 1, 6)
    result["months_inactive_12m"] = df["Months_Inactive_12_mon"].values
    result["contacts_count_12m"] = df["Contacts_Count_12_mon"].values
    result["total_trans_amt_12m"] = (df["Total_Trans_Amt"] * INR_CONVERSION_FACTOR).round(2)
    result["total_trans_ct_12m"] = df["Total_Trans_Ct"].values
    result["amt_change_q4_q1"] = df["Total_Amt_Chng_Q4_Q1"].round(4)
    result["ct_change_q4_q1"] = df["Total_Ct_Chng_Q4_Q1"].round(4)
    
    # --- Derived Fields ---
    # Risk category based on utilization + inactivity + churn status
    result["risk_category"] = _assign_risk_category(df)
    
    # Preferred channel weighted by age and income
    result["preferred_channel"] = _assign_preferred_channel(df, rng)
    
    logger.info(f"Localization complete: {len(result):,} customers")
    logger.info(f"States: {result['state'].nunique()} | Cities: {result['city'].nunique()}")
    return result


def _generate_indian_names(client_nums, genders, name_type, rng):
    """Generate deterministic Indian names based on customer_id hash."""
    
    MALE_FIRST = [
        "Aarav", "Vihaan", "Aditya", "Sai", "Arjun", "Reyansh", "Ayaan",
        "Krishna", "Ishaan", "Shaurya", "Atharv", "Vivaan", "Ansh", "Dhruv",
        "Kabir", "Ritesh", "Manish", "Suresh", "Rajesh", "Vikram", "Amit",
        "Rahul", "Deepak", "Sandeep", "Rohit", "Mohit", "Nikhil", "Gaurav",
        "Sachin", "Pradeep", "Manoj", "Sanjay", "Ajay", "Vijay", "Ashish",
        "Karan", "Rohan", "Kunal", "Akash", "Harsh", "Pranav", "Chirag",
        "Dev", "Yash", "Tanmay", "Rishab", "Omkar", "Neeraj", "Piyush",
    ]
    FEMALE_FIRST = [
        "Aadhya", "Diya", "Saanvi", "Ananya", "Aaradhya", "Myra", "Anika",
        "Navya", "Isha", "Sara", "Aanya", "Kiara", "Riya", "Priya",
        "Neha", "Pooja", "Meera", "Nisha", "Kavita", "Sunita", "Anjali",
        "Shreya", "Kriti", "Tanvi", "Aditi", "Sneha", "Divya", "Swati",
        "Pallavi", "Rashmi", "Mansi", "Nandini", "Garima", "Sonal", "Vaishali",
        "Bhavna", "Jyoti", "Rekha", "Seema", "Tanya", "Simran", "Komal",
        "Megha", "Nikita", "Payal", "Preeti", "Sakshi", "Shweta", "Trisha",
    ]
    LAST_NAMES = [
        "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Shah",
        "Reddy", "Nair", "Pillai", "Iyer", "Menon", "Joshi", "Desai",
        "Mehta", "Chauhan", "Yadav", "Tiwari", "Pandey", "Mishra",
        "Agarwal", "Bansal", "Malhotra", "Kapoor", "Arora", "Bhatia",
        "Khanna", "Srivastava", "Saxena", "Jain", "Goyal", "Mittal",
        "Chopra", "Sethi", "Dutta", "Das", "Roy", "Chatterjee", "Mukherjee",
        "Banerjee", "Ghosh", "Bose", "Rao", "Naidu", "Kulkarni", "Patil",
        "Choudhury", "Thakur", "Dubey", "Dwivedi",
    ]
    
    names = []
    for cnum, gender in zip(client_nums, genders):
        # Deterministic: hash of customer ID selects name index
        seed = int(hashlib.md5(str(cnum).encode()).hexdigest()[:8], 16)
        if name_type == "first":
            pool = MALE_FIRST if gender == "M" else FEMALE_FIRST
        else:
            pool = LAST_NAMES
        names.append(pool[seed % len(pool)])
    
    return names


def _assign_risk_category(df: pd.DataFrame) -> list:
    """
    Assign risk category based on behavioral signals.
    
    Business Logic:
    - High: Churned, OR (utilization > 0.8 AND inactive > 3 months)
    - Medium: Utilization > 0.5 OR inactive > 2 months
    - Low: Everything else
    """
    risk = []
    for _, row in df.iterrows():
        if row["Attrition_Flag"] == "Attrited Customer":
            risk.append("High")
        elif (row["Avg_Utilization_Ratio"] > 0.8 and row["Months_Inactive_12_mon"] > 3):
            risk.append("High")
        elif (row["Avg_Utilization_Ratio"] > 0.5 or row["Months_Inactive_12_mon"] > 2):
            risk.append("Medium")
        else:
            risk.append("Low")
    return risk


def _assign_preferred_channel(df: pd.DataFrame, rng) -> list:
    """
    Assign preferred channel based on age and income.
    
    Business Logic:
    - Younger customers (< 35): Higher probability of UPI/Mobile Banking
    - Middle age (35-55): Mix of Net Banking, Mobile Banking, Debit Card
    - Older (55+): Higher probability of Branch, ATM
    - Higher income: Higher probability of Credit Card, Net Banking
    """
    channels = []
    for _, row in df.iterrows():
        age = row["Customer_Age"]
        income = row["Income_Category"]
        
        if age < 35:
            weights = {"UPI": 0.30, "Mobile Banking": 0.30, "Net Banking": 0.15,
                       "Debit Card": 0.10, "Credit Card": 0.10, "ATM": 0.05}
        elif age < 55:
            weights = {"Net Banking": 0.25, "Mobile Banking": 0.20, "UPI": 0.15,
                       "Credit Card": 0.15, "Debit Card": 0.15, "ATM": 0.05, "Branch": 0.05}
        else:
            weights = {"Branch": 0.20, "ATM": 0.15, "Net Banking": 0.20,
                       "Debit Card": 0.15, "Mobile Banking": 0.15, "Credit Card": 0.10, "UPI": 0.05}
        
        # Boost Credit Card for high income
        if income in ("$80K - $120K", "$120K +"):
            weights["Credit Card"] = weights.get("Credit Card", 0.1) + 0.10
            # Renormalize
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}
        
        ch_names = list(weights.keys())
        ch_probs = list(weights.values())
        channels.append(rng.choice(ch_names, p=ch_probs))
    
    return channels


# ============================================================
# 2. Sparkov Transactions → Distribution Template
# ============================================================
def load_sparkov_template(train_path=None, test_path=None) -> pd.DataFrame:
    """
    Load Sparkov credit card transaction data as a distribution template.
    
    We don't use these rows directly as our transactions.
    Instead, we extract statistical patterns:
    - Amount distribution per category
    - Category frequency proportions
    - Temporal patterns (hour of day, day of week, monthly seasonality)
    - Merchant name pools per category
    
    Returns:
        DataFrame with cleaned Sparkov transactions for pattern extraction.
    """
    train_path = train_path or PATHS.FRAUD_TRAIN_CSV
    test_path = test_path or PATHS.FRAUD_TEST_CSV
    
    frames = []
    for path, label in [(train_path, "train"), (test_path, "test")]:
        if path.exists():
            logger.info(f"Loading Sparkov {label} from {path}")
            df = pd.read_csv(path, parse_dates=["trans_date_trans_time"])
            frames.append(df)
        else:
            logger.warning(f"Sparkov {label} not found at {path}")
    
    if not frames:
        raise FileNotFoundError(
            "No Sparkov transaction files found. "
            "Download from: https://www.kaggle.com/datasets/kartik2112/fraud-detection"
        )
    
    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Loaded {len(combined):,} Sparkov transactions")
    
    # Map categories to Indian equivalents
    combined["category_mapped"] = combined["category"].map(MERCHANT_CATEGORY_MAP)
    unmapped = combined["category_mapped"].isna().sum()
    if unmapped > 0:
        logger.warning(f"{unmapped:,} transactions have unmapped categories, using 'Miscellaneous'")
        combined["category_mapped"].fillna("Miscellaneous", inplace=True)
    
    return combined


def extract_distribution_patterns(sparkov_df: pd.DataFrame) -> dict:
    """
    Extract statistical patterns from Sparkov data for transaction generation.
    
    Returns:
        Dictionary containing:
        - category_proportions: {category: proportion}
        - amount_stats: {category: {mean, std, min, max, p25, p50, p75}}
        - hourly_weights: {hour: weight}
        - dow_weights: {day_of_week: weight}
        - monthly_weights: {month: weight}
    """
    logger.info("Extracting distribution patterns from Sparkov template")
    
    patterns = {}
    
    # Category proportions (how spend is distributed across categories)
    cat_counts = sparkov_df["category_mapped"].value_counts(normalize=True)
    patterns["category_proportions"] = cat_counts.to_dict()
    
    # Amount statistics per category
    amt_stats = {}
    for cat in sparkov_df["category_mapped"].unique():
        cat_data = sparkov_df[sparkov_df["category_mapped"] == cat]["amt"]
        amt_stats[cat] = {
            "mean": float(cat_data.mean()),
            "std": float(cat_data.std()),
            "min": float(cat_data.min()),
            "p25": float(cat_data.quantile(0.25)),
            "median": float(cat_data.median()),
            "p75": float(cat_data.quantile(0.75)),
            "max": float(cat_data.max()),
        }
    patterns["amount_stats"] = amt_stats
    
    # Temporal patterns
    patterns["hourly_weights"] = (
        sparkov_df["trans_date_trans_time"].dt.hour
        .value_counts(normalize=True).sort_index().to_dict()
    )
    patterns["dow_weights"] = (
        sparkov_df["trans_date_trans_time"].dt.dayofweek
        .value_counts(normalize=True).sort_index().to_dict()
    )
    patterns["monthly_weights"] = (
        sparkov_df["trans_date_trans_time"].dt.month
        .value_counts(normalize=True).sort_index().to_dict()
    )
    
    # Merchant names per category (for Indian localization)
    # We'll use our own Indian merchant names, but log originals for reference
    patterns["original_merchants_per_cat"] = (
        sparkov_df.groupby("category_mapped")["merchant"]
        .apply(lambda x: x.unique()[:10].tolist()).to_dict()
    )
    
    logger.info(f"Extracted patterns for {len(patterns['category_proportions'])} categories")
    return patterns


# ============================================================
# 3. Database Loading
# ============================================================
def load_customers_to_db(customer_df: pd.DataFrame, engine=None):
    """
    Load localized customer data into dim_customer table.
    
    Uses pandas to_sql with 'replace' for idempotent loads.
    """
    engine = engine or get_engine()
    
    logger.info(f"Loading {len(customer_df):,} customers into {SCHEMA}.dim_customer")
    
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.dim_customer CASCADE;"))
        conn.commit()
    
    customer_df.to_sql(
        name="dim_customer",
        con=engine,
        schema=SCHEMA,
        if_exists="append",  # Schema already created via DDL
        index=False,
        method="multi",
        chunksize=1000,
    )
    
    # Verify
    with engine.connect() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.dim_customer")
        ).scalar()
        logger.info(f"✅ dim_customer loaded: {count:,} rows")
    
    return count


# ============================================================
# 4. Pipeline Orchestration
# ============================================================
def run_ingestion_pipeline():
    """
    Execute the complete data ingestion pipeline:
    1. Load BankChurners.csv
    2. Localize to Indian context
    3. Extract Sparkov distribution patterns
    4. Save processed data
    5. Load dim_customer to PostgreSQL
    """
    logger.info("=" * 60)
    logger.info("Starting Data Ingestion Pipeline")
    logger.info("=" * 60)
    
    # Step 1: Load BankChurners
    raw_customers = load_bankchurners()
    
    # Step 2: Localize
    customers = localize_customer_data(raw_customers)
    
    # Step 3: Save processed customer data
    processed_path = PATHS.PROCESSED_DATA / "dim_customer.csv"
    PATHS.PROCESSED_DATA.mkdir(parents=True, exist_ok=True)
    customers.to_csv(processed_path, index=False)
    logger.info(f"Saved processed customers to {processed_path}")
    
    # Step 4: Load Sparkov template and extract patterns
    try:
        sparkov = load_sparkov_template()
        patterns = extract_distribution_patterns(sparkov)
        
        # Save patterns for later use in transaction generation
        import json
        patterns_path = PATHS.PROCESSED_DATA / "sparkov_patterns.json"
        
        # Convert numpy types for JSON serialization
        serializable_patterns = {
            "category_proportions": patterns["category_proportions"],
            "amount_stats": patterns["amount_stats"],
            "hourly_weights": {str(k): v for k, v in patterns["hourly_weights"].items()},
            "dow_weights": {str(k): v for k, v in patterns["dow_weights"].items()},
            "monthly_weights": {str(k): v for k, v in patterns["monthly_weights"].items()},
        }
        with open(patterns_path, "w") as f:
            json.dump(serializable_patterns, f, indent=2)
        logger.info(f"Saved distribution patterns to {patterns_path}")
        
    except FileNotFoundError as e:
        logger.warning(f"Sparkov data not available: {e}")
        logger.warning("Transaction generation will be limited without distribution patterns.")
    
    # Step 5: Load to PostgreSQL
    try:
        count = load_customers_to_db(customers)
        logger.info(f"✅ Ingestion pipeline complete: {count:,} customers loaded")
    except Exception as e:
        logger.error(f"❌ Database loading failed: {e}")
        logger.info("Processed data saved to CSV. Load manually after fixing DB connection.")
    
    logger.info("=" * 60)
    return customers


if __name__ == "__main__":
    run_ingestion_pipeline()
