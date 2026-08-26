import {useState } from "react";
import axios from "axios";
import { BASE_URL } from "../api";
import "./ChurnPrediction.css";

function ChurnPrediction() {

const [tenure, setTenure]=useState("");
  const [monthlyCharges, setMonthlyCharges]=useState("");
  const [contractType, setContractType]=useState("");
  const [serviceCount, setServiceCount]=useState("");

  const [prediction, setprediction]=useState({
    risk_score: 0,
    prediction: ""
  });

  const [loading, setLoading]=useState(false);
  const [error, setError]=useState("");

  const getRecord=async ()=> {
    setLoading(true);
    setError("");

    try {
      const response=await axios.post(
        `${BASE_URL}/predict-churn`,
        {
          tenure: Number(tenure),
          monthly_charges: Number(monthlyCharges),
          contract_type: contractType,
          service_count: Number(serviceCount)
        }
      );

      const data={
        risk_score: response.data.risk_score,
        prediction: response.data.prediction
      };

      setprediction(data);
      console.log(response.data.risk_score);
    } catch (error) {
      console.error(error);
      setError("Unable to predict churn");
    } finally {
      setLoading(false);
    }
  };

  const getRiskClass=()=> {
    if (prediction.risk_score < 0.3) {
      return "low-risk";
    }

    if (prediction.risk_score <=0.6) {
      return "medium-risk";
    }

    return "high-risk";
  };

  if (error) {
    return <p>{error}</p>;
  }

  return (
    <>
      <form
        className="form"
        onSubmit={(e)=> {
          e.preventDefault();
          getRecord();
        }}
      >
        <div className="form-group">
          <label htmlFor="tenure">Tenure</label>
          <input
            type="number"
            id="tenure"
            name="tenure"
            value={tenure}
            onChange={(e)=> setTenure(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="monthly_charges">Monthly Charges</label>
          <input
            type="number"
            id="monthly_charges"
            name="monthly_charges"
            value={monthlyCharges}
            onChange={(e)=> setMonthlyCharges(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="contract_type">Contract Type</label>
          <select
            id="contract_type"
            name="contract_type"
            value={contractType}
            onChange={(e)=> setContractType(e.target.value)}
          >
            <option value="">Select contract type</option>
            <option value="Month-to-month">Month-to-month</option>
            <option value="One year">One year</option>
            <option value="Two year">Two year</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="service_count">Service Count</label>
          <input
            type="number"
            id="service_count"
            name="service_count"
            min="0"
            max="6"
            value={serviceCount}
            onChange={(e)=> setServiceCount(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="submit-button"
          disabled={loading}
        >
          {/* #171 Submit Loading */}
          {loading ? "Predicting..." : "Submit"}
        </button>
      </form>

      {/* #169 Prediction Result */}
      <div className={`prediction-box ${getRiskClass()}`}>
        <p>
          Risk Score:{" "}
          <strong>
            {(prediction.risk_score * 100).toFixed(2)}%
          </strong>
        </p>

        <p>
          Prediction: <strong>{prediction.prediction}</strong>
        </p>

        <p>
          Confidence Level:{" "}
          <strong>{prediction.risk_score}</strong>
        </p>

        {/* #170 Risk Visual */}
        <div className="risk-bar-container">
          <div
            className="risk-bar"
            style={{
              width: `${prediction.risk_score * 100}%`,
            }}
          ></div>
        </div>
      </div>
    </>
  );
}

export default ChurnPrediction;