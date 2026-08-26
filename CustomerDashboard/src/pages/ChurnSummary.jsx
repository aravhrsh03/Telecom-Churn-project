import { useEffect, useState } from 'react';
import { getChurnSummary } from '../api';
import './ChurnSummary.css';

function ChurnSummary() {
  const [churnData, setChurnData]=useState(null);
  const [loading, setLoading]=useState(true);
  const [error, setError]=useState(null);

  useEffect(()=> {
    const fetchChurnSummary=async ()=> {
      try {
        setLoading(true);
        setError(null);
        const data=await getChurnSummary();
        setChurnData(data);
        console.log("Churn Summary Response:", data);
      } catch (err) {
        console.error("API Error:", err);
        setError(err.message || "Failed to fetch churn summary");
      } finally {
        setLoading(false);
      }
    };

    fetchChurnSummary();
  }, []);

  return (
    <div className="churn-summary-container">
      <div className="summary-header">
        <h2>Churn Analysis Dashboard</h2>
        <p className="summary-description">
          Monitor customer churn metrics by contract type and identify at-risk segments
        </p>
      </div>

      {loading && (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading churn data...</p>
        </div>
      )}

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}

      {churnData && !loading && (
        <>
          
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Total Customers</div>
              <div className="metric-value">{churnData.total_customers.toLocaleString()}</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Churned</div>
              <div className="metric-value churned">{churnData.churned.toLocaleString()}</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Churn Rate</div>
              <div className="metric-value rate">
                {(churnData.churn_rate * 100).toFixed(1)}%
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Retained</div>
              <div className="metric-value retained">
                {(churnData.total_customers - churnData.churned).toLocaleString()}
              </div>
            </div>
          </div>

          {churnData.churn_by_contract && churnData.churn_by_contract.length > 0 && (
            <div className="table-section">
              <h3>Churn Rate by Contract Type</h3>
              <div className="table-wrapper">
                <table className="churn-table">
                  <thead>
                    <tr>
                      <th>Contract Type</th>
                      <th>Churn Rate</th>
                      <th>Visual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {churnData.churn_by_contract.map((item, idx)=> {
                      const percentage=(item.churn_rate * 100).toFixed(1);
                      return (
                        <tr key={idx}>
                          <td className="contract-name">{item.contract_type}</td>
                          <td className="churn-rate-value">{percentage}%</td>
                          <td className="visual-bar-cell">
                            <div className="bar-container">
                              <div
                                className="bar-fill"
                                style={{
                                  width: `${percentage}%`,
                                  backgroundColor: getBarColor(percentage)
                                }}
                              >
                                <span className="bar-label">{percentage}%</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {churnData.churn_by_internet && churnData.churn_by_internet.length > 0 && (
            <div className="table-section">
              <h3>Churn Rate by Internet Service</h3>
              <div className="table-wrapper">
                <table className="churn-table">
                  <thead>
                    <tr>
                      <th>Internet Service</th>
                      <th>Churn Rate</th>
                      <th>Visual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {churnData.churn_by_internet.map((item, idx)=> {
                      const percentage=(item.churn_rate * 100).toFixed(1);
                      return (
                        <tr key={idx}>
                          <td className="contract-name">{item.internet_service}</td>
                          <td className="churn-rate-value">{percentage}%</td>
                          <td className="visual-bar-cell">
                            <div className="bar-container">
                              <div
                                className="bar-fill"
                                style={{
                                  width: `${percentage}%`,
                                  backgroundColor: getBarColor(percentage)
                                }}
                              >
                                <span className="bar-label">{percentage}%</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function getBarColor(percentage) {
  const percent=parseFloat(percentage);
  if (percent >=40) return '#dc3545'; // Red - High risk
  if (percent >=25) return '#fd7e14'; // Orange - Medium risk
  if (percent >=10) return '#ffc107'; // Yellow - Low-medium risk
  return '#28a745'; // Green - Low risk
}

export default ChurnSummary;