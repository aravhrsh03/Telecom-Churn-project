import logging
import re
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class CustomerCleaner:
    def __init__(self, df: pd.DataFrame):
        self.df=df.copy()
        logging.info("CustomerCleaner initialized with DataFrame shape %s", self.df.shape)

    def standard(self):
        logging.info("Standardizing column names")

        def to_snake_case(column_name):
            name=re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', column_name)
            name=re.sub(r'[\s\-]+', '_', name)
            return name.lower()

        self.df.columns=[to_snake_case(col) for col in self.df.columns]

        logging.info("Column standardization completed")

    def total_cha(self):
        logging.info("Fixing total_charges column")

        try:
            if "total_charges" not in self.df.columns:
                logging.warning("total_charges column not found")
                return

            blank_count=(
                self.df["total_charges"]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )

            self.df["total_charges"]=(
                self.df["total_charges"]
                .replace(r'^\s*$', np.nan, regex=True)
            )

            self.df["total_charges"]=pd.to_numeric(
                self.df["total_charges"],
                errors="coerce"
            )

            logging.info(
                "Converted total_charges to numeric. Blank rows affected: %s",
                blank_count
            )

        except Exception as e:
            logging.exception(
                "Unexpected error while processing total_charges: %s",
                str(e)
            )

    def normal(self):
        logging.info("Normalizing binary columns")

        binary_columns=[
            "partner",
            "dependents",
            "phone_service",
            "paperless_billing",
            "churn"
        ]

        mapping={
            "Yes": 1,
            "No": 0
        }

        for col in binary_columns:
            if col in self.df.columns:
                self.df[col]=self.df[col].map(mapping)
                logging.info("Normalized column: %s", col)

        logging.info("Binary column normalization completed")

    def null_handler(self):
        logging.info("Handling null values")

        if "total_charges" in self.df.columns and "monthly_charges" in self.df.columns:
            null_count=self.df["total_charges"].isna().sum()

            self.df["total_charges"]=self.df["total_charges"].fillna(
                self.df["monthly_charges"]
            )

            logging.info(
                "Filled %s null values in total_charges using monthly_charges",
                null_count
            )

    def clean(self):
        """
        Run complete cleaning pipeline.
        """

        logging.info("Starting data cleaning pipeline")

        self.standard()
        self.total_cha()
        self.normal()
        self.null_handler()

        logging.info(
            "Data cleaning completed. Final DataFrame shape: %s",
            self.df.shape
        )

        return self.df



