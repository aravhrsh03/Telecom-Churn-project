import logging
from datetime import datetime
from pathlib import Path

import nbimporter
import pandas as pd

from customer_cleaner import CustomerCleaner


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATA_PATH = Path(r"D:\projectpart1\WA_Fn-UseC_-Telco-Customer-Churn.csv")
OUTPUT_DIR = Path(r"D:\projectpart1\telco2\outputs2")


def save_outputs(clean_df, feature_df, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_path = output_dir / f"cleaned_customer_data_{timestamp}.csv"
    feature_path = output_dir / f"customer_features_{timestamp}.csv"

    clean_df.to_csv(clean_path, index=False)
    feature_df.to_csv(feature_path, index=False)

    logging.info("Saved clean data to %s", clean_path)
    logging.info("Saved feature data to %s", feature_path)

    return clean_path, feature_path


def main():
    start_time = datetime.now()
    logging.info("Pipeline started at %s", start_time)

    try:
        df = load_data(DATA_PATH)

        logging.info("Initializing cleaner")
        cleaner = CustomerCleaner(df)
        clean_df = cleaner.clean()

        logging.info("Cleaned data shape: %s", clean_df.shape)

        feature_df = build_features(clean_df)

        if "monthly_charges" in feature_df.columns:
            assert feature_df["monthly_charges"].notna().all(), "monthly_charges contains null values"

        if "churn" in feature_df.columns:
            churn_numeric = pd.to_numeric(feature_df["churn"], errors="coerce")
            assert set(churn_numeric.dropna().astype(int).unique()).issubset({0, 1}), \
                "churn must contain only 0/1 values"

        save_outputs(clean_df, feature_df, OUTPUT_DIR)

    except Exception as e:
        logging.exception("Pipeline failed: %s", str(e))
        raise

    logging.info("Pipeline completed in %s", datetime.now() - start_time)


if __name__ == "__main__":
    main()