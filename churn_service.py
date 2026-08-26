from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_churn_summary(db: Session) -> Dict[str, Any]:
    """
    Return:
      - total_customers: int
      - churned: int
      - churn_rate: float (0..1)
      - churn_by_contract: list[{"contract_type": str, "churn_rate": float}]
      - churn_by_internet: list[{"internet_service": str, "churn_rate": float}]

    """
    # totals
    total_customers = 0
    churned = 0
    churn_rate = 0.0
    churn_by_contract: List[Dict[str, Any]] = []
    churn_by_internet: List[Dict[str, Any]] = []

    # 1) total customers (try customers, then stg_customer2, then stg_customer_raw)
    for q in (
        "SELECT COUNT(*) FROM stg_customer_raw",
    ):
        try:
            res = db.execute(text(q)).scalar()
            total_customers = int(res or 0)
            if total_customers:
                break
        except Exception:
            continue

    # 2) total churned (try fact_customer_account, then stg_customer2 numeric churn, then stg_customer_raw string 'Yes')
    churn_res = None
    try:
        churn_res = db.execute(text("SELECT SUM(churn_flag) FROM fact_customer_account")).scalar()
    except Exception:
        pass
    if churn_res is None:
        for q in (
            "SELECT COUNT(*) FROM stg_customer_raw WHERE LOWER(TRIM(Churn)) = 'yes'",
        ):
            try:
                churn_res = db.execute(text(q)).scalar()
                if churn_res is not None:
                    break
            except Exception:
                churn_res = None
                continue
    churned = int(churn_res or 0)

    churn_rate = (churned / total_customers) if total_customers else 0.0

    # 3) churn by contract - prefer fact/dim join, fallback to raw staging
    try:
        rows = db.execute(
            text(
                """
                SELECT dc.contract_type, AVG(f.churn_flag) AS churn_rate
                FROM fact_customer_account f
                JOIN dim_contract dc ON f.contract_id = dc.contract_id
                GROUP BY dc.contract_type
                ORDER BY churn_rate DESC
                """
            )
        ).mappings().all()
        churn_by_contract = [
            {"contract_type": r["contract_type"], "churn_rate": float(r["churn_rate"] or 0.0)} for r in rows
        ]
    except Exception:
        try:
            rows = db.execute(
                text(
                    """
                    SELECT TRIM(Contract) AS contract_type,
                           AVG(CASE WHEN LOWER(TRIM(Churn)) = 'yes' THEN 1 ELSE 0 END) AS churn_rate
                    FROM stg_customer_raw
                    GROUP BY TRIM(Contract)
                    ORDER BY churn_rate DESC
                    """
                )
            ).mappings().all()
            churn_by_contract = [
                {"contract_type": r["contract_type"], "churn_rate": float(r["churn_rate"] or 0.0)} for r in rows
            ]
        except Exception:
            churn_by_contract = []

    # 4) churn by internet service (use staging)
    try:
        rows = db.execute(
            text(
                """
                SELECT TRIM(InternetService) AS internet_service,
                       AVG(CASE WHEN LOWER(TRIM(Churn)) = 'yes' THEN 1 ELSE 0 END) AS churn_rate
                FROM stg_customer_raw
                GROUP BY TRIM(InternetService)
                ORDER BY churn_rate DESC
                """
            )
        ).mappings().all()
        churn_by_internet = [
            {"internet_service": r["internet_service"], "churn_rate": float(r["churn_rate"] or 0.0)} for r in rows
        ]
    except Exception:
        churn_by_internet = []

    return {
        "total_customers": total_customers,
        "churned": churned,
        "churn_rate": churn_rate,
        "churn_by_contract": churn_by_contract,
        "churn_by_internet": churn_by_internet,
    }


def get_high_risk_customers(
    db: Session, limit: int = 50, min_tenure: Optional[int] = None, max_tenure: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query the view v_high_risk_customers.
    Optional filters: min_tenure, max_tenure. Limit default 50.
    Returns list of dicts containing:
      customer_id, tenure, monthly_charges, contract_type, risk_reason
    """
    sql = "SELECT customer_id, tenure, monthly_charges, contract_type, risk_reason FROM v_high_risk_customers WHERE 1=1"
    params = {}
    if min_tenure is not None:
        sql += " AND tenure >= :min_tenure"
        params["min_tenure"] = int(min_tenure)
    if max_tenure is not None:
        sql += " AND tenure <= :max_tenure"
        params["max_tenure"] = int(max_tenure)
    sql += " LIMIT :limit"
    params["limit"] = int(limit)

    try:
        rows = db.execute(text(sql), params).mappings().all()
        return [
            {
                "customer_id": r["customer_id"],
                "tenure": r["tenure"],
                "monthly_charges": float(r["monthly_charges"]) if r["monthly_charges"] is not None else 0.0,
                "contract_type": r["contract_type"],
                "risk_reason": r["risk_reason"],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying v_high_risk_customers: {e}")
        return []