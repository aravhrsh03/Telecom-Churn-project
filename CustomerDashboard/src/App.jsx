import { useState } from 'react';
import './App.css';
import ChurnSummary from './pages/ChurnSummary';
import CustomerSearch from './pages/CustomerSearch/CustomerSearch';
import HighRiskCustomer from './pages/HighRiskCustomers';
import ChurnPrediction from './pages/ChurnPrediction';
import AssistantChat from './pages/AssistantChat';


function App() {
  const [activeTab, setActiveTab]=useState('summary');

  return (
    <div className="App">
      <header className="app-header">
        <h1>Telco Customer Dashboard</h1>
      </header>

      <nav className="tab-navigation">
        <button
          className={`tab-button ${activeTab==='summary' ? 'active' : ''}`}
          onClick={()=> setActiveTab('summary')}
        >
          Churn Summary
        </button>
        <button
          className={`tab-button ${activeTab==='search' ? 'active' : ''}`}
          onClick={()=> setActiveTab('search')}
        >
          Customer Search
        </button>
        <button
          className={`tab-button ${activeTab==='highrisk' ? 'active' : ''}`}
          onClick={()=> setActiveTab('highrisk')}
        >
          High Risk Customers
        </button>
        <button
          className={`tab-button ${activeTab==='prediction' ? 'active' : ''}`}
          onClick={()=> setActiveTab('prediction')}
        >
          Churn Prediction
        </button>
        <button
          className={`tab-button ${activeTab==='assistant' ? 'active' : ''}`}
          onClick={()=> setActiveTab('assistant')}
        >
          Retention Assistant
        </button>
      </nav>

      <main className="tab-content">
        {activeTab==='summary' && <ChurnSummary />}
        {activeTab==='search' && <CustomerSearch />}
        {activeTab==='highrisk' && <HighRiskCustomer />}
        {activeTab==='prediction' && <ChurnPrediction />}
        {activeTab==='assistant' && <AssistantChat />}
      </main>
    </div>
  );
}

export default App;