import { useState } from 'react';
import { getCustomer } from '../../api';
import './CustomerSearch.css';

function CustomerSearch() {
  const [customerId, setCustomerId] = useState('');
  const [customer, setCustomer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();

    if (!customerId.trim()) {
      setError('Please enter a customer ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSearched(true);
      const data = await getCustomer(customerId.trim());
      setCustomer(data);
      console.log("Customer Profile:", data);
    } catch (err) {
      console.error("Search Error:", err);
      setCustomer(null);
      setError(err.message || "Failed to fetch customer");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="customer-search-container">
      <h2>Customer Search</h2>

      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          placeholder="Enter Customer ID (e.g., 0002-ORFBO)"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          className="search-input"
        />
        <button type="submit" className="search-button">
          Search
        </button>
      </form>

      {loading && (
        <div className="loading-spinner">
          <p>Loading...</p>
        </div>
      )}

      {error && (
        <div className="error-message">
          ⚠️ {error}
        </div>
      )}

      {searched && !loading && !error && !customer && (
        <div className="no-result">
          Customer not found
        </div>
      )}

      {customer && (
        <div className="customer-card">
          <div className="card-header">
            <h3>{customer.customer_id}</h3>
            <div className={`churn-badge ${customer.churn === 'Yes' || customer.churn === 1 ? 'churned' : 'active'}`}>
              {customer.churn === 'Yes' || customer.churn === 1 ? 'CHURNED' : 'ACTIVE'}
            </div>
          </div>

          <div className="card-body">
            <div className="info-row">
              <span className="label">Gender:</span>
              <span className="value">{customer.gender || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Tenure (months):</span>
              <span className="value">{customer.tenure || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Contract:</span>
              <span className="value">{customer.contract || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Internet Service:</span>
              <span className="value">{customer.internet_service || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Monthly Charges:</span>
              <span className="value">${customer.monthly_charges?.toFixed(2) || '0.00'}</span>
            </div>

            <div className="info-row">
              <span className="label">Total Charges:</span>
              <span className="value">${customer.total_charges?.toFixed(2) || '0.00'}</span>
            </div>

            <div className="info-row">
              <span className="label">Senior Citizen:</span>
              <span className="value">{customer.senior_citizen === 1 || customer.senior_citizen === '1' ? 'Yes' : 'No'}</span>
            </div>

            <div className="info-row">
              <span className="label">Partner:</span>
              <span className="value">{customer.partner || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Dependents:</span>
              <span className="value">{customer.dependents || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Phone Service:</span>
              <span className="value">{customer.phone_service || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Online Security:</span>
              <span className="value">{customer.online_security || 'N/A'}</span>
            </div>

            <div className="info-row">
              <span className="label">Payment Method:</span>
              <span className="value">{customer.payment_method || 'N/A'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CustomerSearch;