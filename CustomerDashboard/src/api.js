const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const API_KEY = import.meta.env.VITE_API_KEY || "qwertyuiop";

export { BASE_URL, API_KEY };

export const getChurnSummary = async () => {
  const response = await fetch(`${BASE_URL}/churn/summary`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    }
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return await response.json();
};

export const getCustomers = async () => {
  const response = await fetch(`${BASE_URL}/customers`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    }
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return await response.json();
};

export const sendAssistantMessage = async (message, history = [], useThinking = false) => {
  const response = await fetch(`${BASE_URL}/assistant/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    },
    body: JSON.stringify({ message, history, use_thinking: useThinking })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || `API error: ${response.statusText}`);
  }

  return data;
};

export const getCustomer = async (customerId) => {
  const response = await fetch(`${BASE_URL}/customers/${customerId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    }
  });

  if (response.status === 404) {
    throw new Error("Customer not found");
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return await response.json();
};