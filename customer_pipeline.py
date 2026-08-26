import logging
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

PROJECT_DIR=Path(__file__).resolve().parent
LOG_DIR=PROJECT_DIR
LOG_FILE=LOG_DIR / "customer_pipeline.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    ],
    force=True,
)

logger=logging.getLogger(__name__)

sys.path.insert(0, str(PROJECT_DIR))

try:
    from customer_cleaner import CustomerCleaner
except Exception as e:
    logger.exception("Failed to import CustomerCleaner: %s", e)
    raise

DATA_PATH=Path(r"D:\projectpart1\WA_Fn-UseC_-Telco-Customer-Churn.csv")
OUTPUT_DIR=PROJECT_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_data(filepath):
    logger.info("Loading data from %s", filepath)
    df=pd.read_csv(filepath)
    logger.info("Loaded %s rows", len(df))
    return df


def build_features(df):
    logger.info("Starting feature engineering")

    df=df.copy()

    bins=[0, 12, 24, 48, 72]
    labels=["0-12", "13-24", "25-48", "49-72"]
    df["tenure_bucket"]=pd.cut(
        df["tenure"],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    median_monthly_charges=df["monthly_charges"].median()
    df["high_charge_flag"]=(df["monthly_charges"] > median_monthly_charges).astype(int)

    service_columns=[
        "online_security",
        "online_backup",
        "device_protection",
        "tech_support",
        "streaming_tv",
        "streaming_movies"
    ]

    mapping={"Yes": 1, "No": 0, "No internet service": 0}

    for col in service_columns:
        df[col]=df[col].replace(mapping).fillna(0).astype(int)

    df["service_count"]=df[service_columns].sum(axis=1)
    df["is_long_term_customer"]=(df["tenure"] >=24).astype(int)
    df["has_streaming_bundle"]=(
        ((df["streaming_tv"]==1) & (df["streaming_movies"]==1)).astype(int)
    )
    df["auto_pay_flag"]=(
        df["payment_method"]
        .astype(str)
        .str.contains("automatic", case=False, na=False)
        .astype(int)
    )

    logger.info("Feature engineering completed. Shape: %s", df.shape)
    return df


def save_outputs(clean_df, feature_df, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_path=output_dir / f"cleaned_customer_data_{timestamp}.csv"
    feature_path=output_dir / f"customer_features_{timestamp}.csv"

    clean_df.to_csv(clean_path, index=False)
    feature_df.to_csv(feature_path, index=False)

    logger.info("Saved clean data to %s", clean_path)
    logger.info("Saved feature data to %s", feature_path)

    return clean_path, feature_path


def main():
    start_time=datetime.now()
    logger.info("Pipeline started at %s", start_time)

    try:
        df=load_data(DATA_PATH)

        logger.info("Initializing cleaner")
        cleaner=CustomerCleaner(df)
        clean_result=cleaner.clean()

        if clean_result is None:
            clean_df=cleaner.df
        else:
            clean_df=clean_result

        logger.info("Cleaned data shape: %s", clean_df.shape)

        feature_df=build_features(clean_df)

        if "monthly_charges" in feature_df.columns:
            assert feature_df["monthly_charges"].notna().all(), "monthly_charges contains null values"

        if "churn" in feature_df.columns:
            churn_numeric=pd.to_numeric(feature_df["churn"], errors="coerce")
            assert set(churn_numeric.dropna().astype(int).unique()).issubset({0, 1}), \
                "churn must contain only 0/1 values"

        save_outputs(clean_df, feature_df, OUTPUT_DIR)

    except Exception as e:
        logger.exception("Pipeline failed: %s", str(e))
        raise

    logger.info("Pipeline completed in %s", datetime.now() - start_time)


if __name__=="__main__":
    main()