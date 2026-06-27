"""
Customer Finance 360° Intelligence Platform
Configuration Module

Centralizes all configuration: database connections, file paths,
logging setup, and project constants. No hardcoded values elsewhere.

Usage:
    from src.etl.config import get_engine, PATHS, SCHEMA
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ============================================================
# Environment Loading
# ============================================================
# Load .env from project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# Database Configuration
# ============================================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "name": os.getenv("DB_NAME", "customer360"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

SCHEMA = os.getenv("DB_SCHEMA", "customer360")


import urllib.parse

def get_connection_url() -> str:
    """Build PostgreSQL connection URL from environment variables."""
    encoded_password = urllib.parse.quote_plus(DB_CONFIG['password'])
    return (
        f"postgresql://{DB_CONFIG['user']}:{encoded_password}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['name']}"
    )


def get_engine(echo: bool = False):
    """
    Create and return a SQLAlchemy engine connected to PostgreSQL.
    
    Args:
        echo: If True, log all SQL statements (useful for debugging).
    
    Returns:
        SQLAlchemy Engine instance.
    """
    return create_engine(get_connection_url(), echo=echo)


def test_connection() -> bool:
    """
    Test the database connection and return True if successful.
    
    Prints connection status and PostgreSQL version.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✅ Connected to PostgreSQL: {version[:60]}...")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


# ============================================================
# File Paths
# ============================================================
class PATHS:
    """Centralized project path constants."""
    ROOT = PROJECT_ROOT
    
    # Data directories
    RAW_DATA = PROJECT_ROOT / os.getenv("RAW_DATA_DIR", "data/raw")
    PROCESSED_DATA = PROJECT_ROOT / os.getenv("PROCESSED_DATA_DIR", "data/processed")
    OUTPUT_DATA = PROJECT_ROOT / os.getenv("OUTPUT_DATA_DIR", "data/output")
    
    # Source directories
    SQL_DIR = PROJECT_ROOT / "src" / "sql"
    ETL_DIR = PROJECT_ROOT / "src" / "etl"
    ML_DIR = PROJECT_ROOT / "src" / "ml"
    
    # Output directories
    MODELS_DIR = PROJECT_ROOT / os.getenv("MODELS_DIR", "models")
    NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
    DOCS_DIR = PROJECT_ROOT / "docs"
    DASHBOARDS_DIR = PROJECT_ROOT / "dashboards"
    
    # Specific raw files
    BANKCHURNERS_CSV = RAW_DATA / "BankChurners.csv"
    FRAUD_TRAIN_CSV = RAW_DATA / "fraudTrain.csv"
    FRAUD_TEST_CSV = RAW_DATA / "fraudTest.csv"

    @classmethod
    def ensure_dirs(cls):
        """Create all required directories if they don't exist."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Path) and attr_name.endswith("_DATA") or attr_name.endswith("_DIR"):
                attr.mkdir(parents=True, exist_ok=True)


# ============================================================
# Logging Configuration
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s │ %(name)-20s │ %(levelname)-8s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("customer360")


# ============================================================
# Project Constants
# ============================================================

# Indian banking localization
INR_CONVERSION_FACTOR = 83.0  # USD → INR approximate scaling factor

# Date range for dim_date generation
DATE_RANGE_START = "2020-01-01"
DATE_RANGE_END = "2025-12-31"

# Indian fiscal year starts April 1
FISCAL_YEAR_START_MONTH = 4

# Churn label mapping from BankChurners
CHURN_LABEL_MAP = {
    "Existing Customer": "Active",
    "Attrited Customer": "Churned",
}

# Card category to product mapping
CARD_PRODUCT_MAP = {
    "Blue": 4,      # product_id for Credit Card - Blue
    "Silver": 5,    # Credit Card - Silver
    "Gold": 6,      # Credit Card - Gold
    "Platinum": 7,  # Credit Card - Platinum
}

# Income category mapping (USD → INR brackets)
INCOME_BRACKET_MAP = {
    "Less than $40K": "Below ₹3L",
    "$40K - $60K": "₹3L - ₹5L",
    "$60K - $80K": "₹5L - ₹8L",
    "$80K - $120K": "₹8L - ₹15L",
    "$120K +": "Above ₹15L",
    "Unknown": "Unknown",
}

# Indian merchant categories (mapped from Sparkov categories)
MERCHANT_CATEGORY_MAP = {
    "grocery_pos": "Groceries",
    "grocery_net": "Online Groceries",
    "shopping_pos": "Retail Shopping",
    "shopping_net": "Online Shopping",
    "food_dining": "Food & Dining",
    "entertainment": "Entertainment",
    "gas_transport": "Fuel & Transport",
    "health_fitness": "Health & Fitness",
    "home": "Home & Living",
    "kids_pets": "Kids & Pets",
    "misc_net": "Online Services",
    "misc_pos": "Miscellaneous",
    "personal_care": "Personal Care",
    "travel": "Travel",
}

# Indian merchant name examples (for localization)
INDIAN_MERCHANTS = {
    "Groceries": ["BigBazaar", "DMart", "Reliance Fresh", "Spencer's", "More Megastore",
                  "Nature's Basket", "Star Bazaar", "Ratnadeep", "Heritage Fresh"],
    "Online Shopping": ["Flipkart", "Amazon India", "Myntra", "Ajio", "Tata CLiQ",
                        "Meesho", "JioMart", "Nykaa", "Snapdeal"],
    "Food & Dining": ["Swiggy", "Zomato", "Domino's", "McDonald's India", "KFC India",
                      "Haldiram's", "Barbeque Nation", "Chai Point", "Cafe Coffee Day"],
    "Fuel & Transport": ["Indian Oil", "Bharat Petroleum", "Hindustan Petroleum",
                         "Ola", "Uber India", "Rapido", "RedBus", "IRCTC"],
    "Online Services": ["Paytm", "PhonePe", "Google Pay", "Jio Recharge",
                        "Airtel Thanks", "Netflix India", "Hotstar", "SonyLIV"],
    "Travel": ["MakeMyTrip", "Goibibo", "IRCTC", "Yatra", "Cleartrip",
               "OYO Rooms", "Taj Hotels", "IndiGo Airlines"],
    "Entertainment": ["BookMyShow", "PVR Cinemas", "INOX", "Netflix India",
                      "Amazon Prime", "Hotstar", "Spotify India"],
    "Health & Fitness": ["Apollo Pharmacy", "Medplus", "1mg", "PharmEasy",
                         "Cult.fit", "Practo", "Dr. Lal PathLabs"],
    "Retail Shopping": ["Shoppers Stop", "Lifestyle", "Westside", "Central",
                        "Reliance Digital", "Croma", "Vijay Sales"],
    "Home & Living": ["Urban Ladder", "Pepperfry", "IKEA India", "Home Centre",
                      "Asian Paints", "Nilkamal", "Godrej Interio"],
    "Personal Care": ["Lakme Salon", "VLCC", "Nykaa", "Bath & Body Works India",
                      "Forest Essentials", "The Body Shop India"],
    "Kids & Pets": ["FirstCry", "Hopscotch", "Mothercare India", "Hamleys India",
                    "Supertails", "Heads Up For Tails"],
    "Miscellaneous": ["India Post", "Courier Services", "Subscription Box",
                      "Gift Cards", "Donations", "Government Fees"],
    "Online Groceries": ["BigBasket", "JioMart", "Blinkit", "Zepto",
                         "Amazon Fresh", "Swiggy Instamart"],
}

# Transaction channels for Indian banking
TRANSACTION_CHANNELS = [
    "UPI", "NEFT", "RTGS", "IMPS",
    "Debit Card", "Credit Card",
    "Mobile Banking", "Net Banking",
    "Branch", "ATM", "POS",
]

# Indian states with population weights (for geographic distribution)
INDIAN_STATES = {
    "Maharashtra": 0.15,
    "Karnataka": 0.12,
    "Tamil Nadu": 0.10,
    "Delhi": 0.10,
    "Telangana": 0.08,
    "Gujarat": 0.07,
    "Uttar Pradesh": 0.07,
    "West Bengal": 0.06,
    "Rajasthan": 0.05,
    "Kerala": 0.05,
    "Madhya Pradesh": 0.04,
    "Punjab": 0.03,
    "Haryana": 0.03,
    "Bihar": 0.02,
    "Odisha": 0.02,
    "Andhra Pradesh": 0.01,
}

# City mapping by state (major cities for each state)
INDIAN_CITIES = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "Delhi": ["New Delhi", "Dwarka", "Rohini", "Saket"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur", "Agra"],
    "West Bengal": ["Kolkata", "Howrah", "Siliguri", "Durgapur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "Punjab": ["Chandigarh", "Ludhiana", "Amritsar", "Jalandhar"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Karnal"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Tirupati"],
}

# Campaign definitions (for derived fact_campaign_responses)
CAMPAIGN_DEFINITIONS = [
    {
        "campaign_id": 1,
        "campaign_name": "Credit Limit Upgrade",
        "campaign_type": "Email",
        "target_segment": "High Utilization",
        "objective": "Cross-sell",
        "budget": 500000,  # ₹5 Lakh
    },
    {
        "campaign_id": 2,
        "campaign_name": "Premium Card Upgrade",
        "campaign_type": "Outbound Call",
        "target_segment": "Affluent",
        "objective": "Upsell",
        "budget": 800000,  # ₹8 Lakh
    },
    {
        "campaign_id": 3,
        "campaign_name": "Re-engagement Offer",
        "campaign_type": "SMS",
        "target_segment": "At Risk",
        "objective": "Retention",
        "budget": 300000,  # ₹3 Lakh
    },
    {
        "campaign_id": 4,
        "campaign_name": "Cross-sell Insurance",
        "campaign_type": "Push Notification",
        "target_segment": "Mass",
        "objective": "Cross-sell",
        "budget": 450000,  # ₹4.5 Lakh
    },
    {
        "campaign_id": 5,
        "campaign_name": "Loyalty Rewards Program",
        "campaign_type": "Email",
        "target_segment": "Loyal",
        "objective": "Engagement",
        "budget": 600000,  # ₹6 Lakh
    },
]

# Service complaint categories (for derived fact_service_logs)
SERVICE_CATEGORIES = {
    "Blue": ["Fee Dispute", "Transaction Error", "Card Decline",
             "ATM Issue", "Statement Query", "PIN Reset"],
    "Silver": ["Reward Points", "Limit Increase", "Digital Banking",
               "Card Replacement", "EMI Conversion", "Fee Waiver"],
    "Gold": ["Reward Points", "Concierge Service", "Limit Increase",
             "Travel Insurance", "Priority Service", "Lounge Access"],
    "Platinum": ["Concierge Service", "Travel Insurance", "Priority Resolution",
                 "Wealth Management", "Lounge Access", "Golf Booking"],
}

# Indian bank holidays (major ones for dim_date)
INDIAN_HOLIDAYS = [
    # Fixed holidays (month, day)
    (1, 26),   # Republic Day
    (8, 15),   # Independence Day
    (10, 2),   # Gandhi Jayanti
    # Variable holidays marked separately during dim_date generation
]


# ============================================================
# Initialization
# ============================================================
def initialize_project():
    """
    Run project initialization:
    - Create required directories
    - Test database connection
    - Log configuration summary
    """
    PATHS.ensure_dirs()
    logger.info("=" * 60)
    logger.info("Customer Finance 360° Intelligence Platform")
    logger.info("=" * 60)
    logger.info(f"Project Root : {PATHS.ROOT}")
    logger.info(f"Database     : {DB_CONFIG['name']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    logger.info(f"Schema       : {SCHEMA}")
    logger.info(f"Log Level    : {LOG_LEVEL}")
    logger.info("=" * 60)
    return test_connection()


if __name__ == "__main__":
    initialize_project()
