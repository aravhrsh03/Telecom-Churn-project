import { useEffect, useState } from "react";
import "./HighRiskCustomer.css";

const BASE_URL=import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_KEY="qwertyuiop";

function HighRiskCustomer() {
  const [records, setRecords]=useState([]);
  const [limit, setLimit]=useState(50);
  const [sortAscending, setSortAscending]=useState(true);
  const [loading, setLoading]=useState(true);
  const [error, setError]=useState("");

  useEffect(()=> {
    const getRecords=async ()=> {
      setLoading(true);
      setError("");

      try {
        const response=await fetch(
          `${BASE_URL}/customers/high-risk?limit=${limit}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "X-API-Key": API_KEY
            }
          }
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.statusText}`);
        }

        const data=await response.json();
        setRecords(data.items || []);
        console.log("High Risk Customers:", data);
      } catch (error) {
        console.error(error);
        setError("Unable to load high-risk customers");
      } finally {
        setLoading(false);
      }
    };

    getRecords();
  }, [limit]);

  const updateLimit=()=> {
    setLimit((prev)=> prev + 50);
  };

  const toggleSort=()=> {
    setSortAscending((prev)=> !prev);
  };

  if (loading) {
    return <div className="loading-spinner"><p>Loading high-risk customers...</p></div>;
  }

  if (error) {
    return <div className="error-message">⚠️ {error}</div>;
  }

  const sortedRecords=[...records].sort((a, b)=>
    sortAscending
      ? a.tenure - b.tenure
      : b.tenure - a.tenure
  );

  return (
    <div className="high-risk-container">
      <div className="header-section">
        <h2>High-Risk Customers</h2>
        <p className="description">
          {sortedRecords.length} customer{sortedRecords.length !==1 ? 's' : ''} identified at risk of churn
        </p>
      </div>

      <div className="controls-section">
        <button className="btn btn-primary" onClick={toggleSort}>
          Sort Tenure {sortAscending ? "↑" : "↓"}
        </button>
        <button className="btn btn-secondary" onClick={updateLimit}>
          Load More (+50)
        </button>
      </div>

      {sortedRecords.length===0 ? (
        <div className="no-results">No high-risk customers found</div>
      ) : (
        <div className="table-wrapper">
          <table className="high-risk-table">
            <thead>
              <tr>
                <th>Customer ID</th>
                <th>Tenure (months)</th>
                <th>Monthly Charges</th>
                <th>Contract Type</th>
                <th>Risk Reason</th>
              </tr>
            </thead>
            <tbody>
              {sortedRecords.map((item)=> (
                <tr key={item.customer_id}>
                  <td className="customer-id">{item.customer_id}</td>
                  <td>{item.tenure}</td>
                  <td>${item.monthly_charges?.toFixed(2) || "0.00"}</td>
                  <td>{item.contract_type}</td>
                  <td className="risk-reason">{item.risk_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default HighRiskCustomer;