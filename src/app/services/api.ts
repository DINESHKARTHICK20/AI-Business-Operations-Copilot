/**
 * Centralized API service for frontend -> backend communication
 * Connects React UI to FastAPI backend running on http://localhost:8000
 */

export function getBaseApiUrl(): string {
  // In the browser, always return relative path "" so that all API requests
  // are routed through the Vite proxy (http://localhost:5173 -> http://127.0.0.1:8000),
  // keeping the application on ONLY http://localhost:5173/ and avoiding cross-origin issues.
  return "";
}

// ─── Interfaces & Types ────────────────────────────────────────────────────────

export interface Customer {
  id: number;
  name: string;
  email: string;
  company: string;
  status: "Active" | "Inactive" | "At Risk";
  ltv: string;
  total_spend?: number;
  orders: number;
  joined: string;
  churn: number;
  days_since_last_purchase?: number;
  support_tickets?: number;
  complaints?: number;
  average_order_value?: number;
}

export interface Employee {
  id: number;
  name: string;
  role: string;
  dept: string;
  salary: string;
  status: "Active" | "On Leave" | "Inactive";
  attendance: number;
  performance: number;
  joined: string;
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  category: string;
  stock: number;
  reorder: number;
  price: string;
  price_num?: number;
  status: "In Stock" | "Low Stock" | "Critical" | "Out of Stock";
  trend: string;
  avg_daily_demand?: number;
  trend_factor?: number;
  promotion_factor?: number;
}

export interface InvoiceItem {
  id?: number;
  invoice_id?: string;
  product_id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
  line_total?: number;
}

export interface Invoice {
  id: string;
  client: string;
  amount: string;
  amount_num?: number;
  due: string;
  issued: string;
  status: "Paid" | "Pending" | "Overdue" | "Draft";
  items?: string;
  subtotal?: number;
  tax?: number;
  discount?: number;
  total?: number;
  line_items?: InvoiceItem[];
}

export interface ChurnPredictionResult {
  customer_id?: number;
  name?: string;
  churn_probability: number;
  risk: "HIGH" | "MEDIUM" | "LOW";
  recommendation: string;
}

export interface InventoryForecastResult {
  product_id: number;
  name: string;
  current_stock: number;
  reorder_level: number;
  predicted_demand_7_days: number;
  predicted_demand_30_days: number;
  stockout_risk: "HIGH" | "MEDIUM" | "LOW";
  recommended_reorder: number;
  recommendation: string;
}

export interface SalesForecastResult {
  has_forecast: boolean;
  message?: string;
  monthly_forecasts?: Array<{
    month: string;
    predicted_revenue: number;
    predicted_revenue_formatted: string;
    delta: string;
    confidence: number;
  }>;
  q3_forecast?: string | null;
  q3_delta?: string | null;
  q3_confidence?: number | null;
  annual_target?: string | null;
  annual_delta?: string | null;
  annual_confidence?: number | null;
}

export interface SalesHeatmapDay {
  date: string;
  day_label: string;
  sales: number;
  orders: number;
  intensity: number;
}

export interface SalesOverview {
  kpis: {
    total_revenue: string;
    total_revenue_change: string;
    total_orders: string;
    total_orders_change: string;
    avg_order_value: string;
    avg_order_value_change: string;
    conversion_rate: string;
    conversion_rate_change: string;
  };
  monthly: Array<{ month: string; revenue: number; expenses: number; profit: number }>;
  daily: Array<{ day: string; sales: number; orders: number }>;
  heatmap: Array<SalesHeatmapDay>;
  customer_growth: Array<{ month: string; new: number; returning: number }>;
  product_categories: Array<{ name: string; value: number; color: string }>;
}

export interface DashboardStats {
  kpis: {
    today_revenue: string;
    today_revenue_change: string;
    monthly_revenue: string;
    monthly_revenue_change: string;
    active_customers: string;
    active_customers_change: string;
    pending_orders: string;
    pending_orders_change: string;
    inventory_health: string;
    inventory_health_change: string;
    business_health: string;
    business_health_change: string;
  };
  low_stock_alerts: Product[];
}

export interface DashboardInsight {
  text: string;
  type: "positive" | "warning" | "danger" | "info";
}

export interface BusinessHealthComponent {
  score: number;
  weight: number;
  metric: string;
  status: "positive" | "warning" | "danger";
}

export interface BusinessHealthReason {
  type: "positive" | "negative";
  component: string;
  text: string;
}

export interface BusinessHealthData {
  overall_score: number;
  score?: number;
  health_level: "Excellent" | "Good" | "Needs Attention" | "At Risk" | "Critical" | string;
  weights: Record<string, number>;
  components: {
    sales_growth: number;
    profit_margin: number;
    inventory_health: number;
    customer_churn: number;
    outstanding_invoices: number;
    employee_performance: number;
  };
  component_details: {
    sales_growth: BusinessHealthComponent;
    profit_margin: BusinessHealthComponent;
    inventory_health: BusinessHealthComponent;
    customer_churn: BusinessHealthComponent;
    outstanding_invoices: BusinessHealthComponent;
    employee_performance: BusinessHealthComponent;
  };
  reasons: BusinessHealthReason[];
  last_updated: string;
}

export type ActionPriority = "critical" | "high" | "medium" | "low" | string;
export type ActionCategory = "inventory" | "customers" | "invoices" | "sales" | "profit" | "employees" | string;

export interface ActionItem {
  id: string;
  priority: ActionPriority;
  category: ActionCategory;
  title: string;
  problem?: string;
  description?: string;
  data_metrics?: string;
  metric?: string;
  recommendation: string;
  why_explanation?: string;
  why_reason?: string;
  impact?: string;
  entity_id: string | number;
  entity_type: string;
  action_type: string;
  action_label?: string;
  target_page: string;
  primary_button_label?: string;
  secondary_button_label?: string;
}

export interface ActionCenterSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  by_category: Record<string, number>;
}

export interface ActionCenterData {
  status: string;
  summary: ActionCenterSummary;
  actions: ActionItem[];
  items?: ActionItem[];
  last_analyzed: string;
}

export interface DashboardActivity {
  icon: string;
  text: string;
  time: string;
  color: string;
}

export interface CopilotResponse {
  role: "ai";
  content: string;
  chart?: boolean;
}

export interface ReportData {
  headers: string[];
  rows: (string | number)[][];
  summary: Array<{ label: string; value: string }>;
}

export interface ProfitProduct {
  id: number;
  name: string;
  category: string;
  buy: number;
  sell: number;
  qty: number;
}

export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  desc: string;
  read: boolean | number;
  time?: string;
  created_at?: string;
}

export interface UserSession {
  id?: number;
  name: string;
  email: string;
  company?: string;
  biz_type?: string;
}

export interface AuthResponse {
  status: string;
  message?: string;
  token?: string;
  id?: number;
  name?: string;
  email?: string;
  company?: string;
  biz_type?: string;
  csrf_token?: string;
  user?: UserSession;
}

// ─── Generic HTTP Request Handler ─────────────────────────────────────────────

// Automatically purge legacy session tokens from browser localStorage on script evaluation
if (typeof localStorage !== "undefined") {
  try {
    localStorage.removeItem("bizops_session_token");
  } catch {}
}

let inMemoryCsrfToken: string | null = null;

export function setCsrfToken(token: string) {
  inMemoryCsrfToken = token;
}

export function getStoredCsrfToken(): string | null {
  return inMemoryCsrfToken || getCookie("csrf_token");
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)(${name})=([^;]*)`));
  return match ? decodeURIComponent(match[3]) : null;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getBaseApiUrl();
  const primaryUrl = `${baseUrl}${endpoint}`;
  const method = (options.method || "GET").toUpperCase();
  const csrfToken = inMemoryCsrfToken || getCookie("csrf_token");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method) ? { "X-CSRF-Token": csrfToken } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  const controller = new AbortController();
  const timeoutMs = (options as any)?.timeout || 15000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const executeFetch = async (targetUrl: string) => {
    return await fetch(targetUrl, {
      ...options,
      signal: controller.signal,
      headers,
      credentials: "include",
    });
  };

  let res: Response;
  try {
    res = await executeFetch(primaryUrl);
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err?.name === "AbortError") {
      throw new Error("Request timed out. The server took too long to respond. Please try again.");
    }
    console.error(`Network Error on [${method} ${endpoint}]:`, err);
    throw new Error("Unable to connect to the backend server. Please verify the FastAPI backend is running and healthy.");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    if (res.status === 401) {
      if (typeof localStorage !== "undefined") {
        localStorage.removeItem("bizops_session_token");
        localStorage.removeItem("bizops_user");
      }
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("bizops_unauthorized"));
      }
    }

    const errorText = await res.text();
    let errorJson: any = null;
    try {
      errorJson = JSON.parse(errorText);
    } catch {
      errorJson = null;
    }

    if (!errorJson && (res.status === 502 || res.status === 503 || res.status === 504)) {
      throw new Error("Unable to connect to the backend server. Please verify the FastAPI backend is running and healthy.");
    }

    const errMsg =
      errorJson?.detail ||
      errorJson?.message ||
      (res.status === 500
        ? "An unexpected server error occurred while processing your request. Please try again."
        : res.status === 403
        ? "Access denied. You do not have permission to view or modify this resource."
        : res.status === 404
        ? "The requested resource was not found."
        : `HTTP Error ${res.status}: ${res.statusText}`);
    throw new Error(errMsg);
  }
  const data = await res.json();
  if (data && typeof data === "object" && data.csrf_token) {
    inMemoryCsrfToken = data.csrf_token;
  }
  return data;
}

async function requestBlob(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const baseUrl = getBaseApiUrl();
  const primaryUrl = `${baseUrl}${endpoint}`;
  const method = (options.method || "GET").toUpperCase();
  const csrfToken = inMemoryCsrfToken || getCookie("csrf_token");

  const headers: Record<string, string> = {
    ...(csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method) ? { "X-CSRF-Token": csrfToken } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(primaryUrl, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    let errDetail = `Server responded with HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) errDetail = errJson.detail;
    } catch {}
    throw new Error(errDetail);
  }

  return await res.blob();
}

// ─── API Client Methods ───────────────────────────────────────────────────────

export const api = {
  // System Health
  async checkHealth(): Promise<{ status: string; database: string; models: Record<string, boolean> }> {
    return request("/health");
  },

  // Customers
  async getCustomers(): Promise<Customer[]> {
    return request<Customer[]>("/api/customers");
  },

  async createCustomer(customer: Partial<Customer>): Promise<Customer> {
    return request<Customer>("/api/customers", {
      method: "POST",
      body: JSON.stringify(customer),
    });
  },

  async updateCustomer(id: number, customer: Partial<Customer>): Promise<Customer> {
    return request<Customer>(`/api/customers/${id}`, {
      method: "PUT",
      body: JSON.stringify(customer),
    });
  },

  async deleteCustomer(id: number): Promise<{ status: string; deleted_id: number }> {
    return request(`/api/customers/${id}`, {
      method: "DELETE",
    });
  },

  async predictCustomerChurn(customerId: number): Promise<ChurnPredictionResult> {
    return request<ChurnPredictionResult>(`/api/customers/${customerId}/churn`, {
      method: "POST",
    });
  },

  async predictChurnStandalone(params: {
    total_orders: number;
    total_spend: number;
    days_since_last_purchase: number;
    support_tickets: number;
    complaints: number;
    average_order_value: number;
  }): Promise<ChurnPredictionResult> {
    return request<ChurnPredictionResult>("/api/predict/churn", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  // Employees
  async getEmployees(): Promise<Employee[]> {
    return request<Employee[]>("/api/employees");
  },

  async createEmployee(employee: Partial<Employee>): Promise<Employee> {
    return request<Employee>("/api/employees", {
      method: "POST",
      body: JSON.stringify(employee),
    });
  },

  async updateEmployee(id: number, employee: Partial<Employee>): Promise<Employee> {
    return request<Employee>(`/api/employees/${id}`, {
      method: "PUT",
      body: JSON.stringify(employee),
    });
  },

  async deleteEmployee(id: number): Promise<{ status: string; deleted_id: number }> {
    return request(`/api/employees/${id}`, {
      method: "DELETE",
    });
  },

  // Inventory / Products
  async getInventory(): Promise<Product[]> {
    return request<Product[]>("/api/inventory");
  },

  async createProduct(product: Partial<Product>): Promise<Product> {
    return request<Product>("/api/inventory", {
      method: "POST",
      body: JSON.stringify(product),
    });
  },

  async updateProduct(id: number, product: Partial<Product>): Promise<Product> {
    return request<Product>(`/api/inventory/${id}`, {
      method: "PUT",
      body: JSON.stringify(product),
    });
  },

  async deleteProduct(id: number): Promise<{ status: string; deleted_id: number }> {
    return request(`/api/inventory/${id}`, {
      method: "DELETE",
    });
  },

  async restockProduct(id: number, quantity: number = 50): Promise<Product> {
    return request<Product>(`/api/inventory/${id}/restock?quantity=${quantity}`, {
      method: "POST",
    });
  },

  async predictProductDemand(productId: number): Promise<InventoryForecastResult> {
    return request<InventoryForecastResult>(`/api/inventory/${productId}/forecast`, {
      method: "POST",
    });
  },

  async predictInventoryStandalone(params: {
    avg_daily_demand: number;
    trend: number;
    promotion_factor: number;
    current_stock: number;
    reorder_level: number;
  }): Promise<{
    predicted_demand_7_days: number;
    predicted_demand_30_days: number;
    stockout_risk: "HIGH" | "MEDIUM" | "LOW";
    recommended_reorder: number;
    recommendation: string;
  }> {
    return request("/api/predict/inventory", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  // Invoices
  async getInvoices(): Promise<Invoice[]> {
    return request<Invoice[]>("/api/invoices");
  },

  async getInvoice(id: string): Promise<Invoice> {
    return request<Invoice>(`/api/invoices/${encodeURIComponent(id)}`);
  },

  async createInvoice(invoice: Partial<Invoice> & { line_items?: Array<{ product_id: number; quantity: number; unit_price?: number; product_name?: string }> }): Promise<Invoice> {
    return request<Invoice>("/api/invoices", {
      method: "POST",
      body: JSON.stringify(invoice),
    });
  },

  async updateInvoiceStatus(id: string, status: string): Promise<Invoice> {
    return request<Invoice>(`/api/invoices/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  async deleteInvoice(id: string): Promise<{ status: string; deleted_id: string }> {
    return request(`/api/invoices/${id}`, {
      method: "DELETE",
    });
  },

  async downloadInvoicePDF(id: string): Promise<Blob> {
    return requestBlob(`/api/invoices/${encodeURIComponent(id)}/pdf`);
  },

  // Global Multi-Entity Search
  async globalSearch(q: string): Promise<{
    query: string;
    total: number;
    results: {
      customers: any[];
      products: any[];
      invoices: any[];
      employees: any[];
    };
  }> {
    return request(`/api/search?q=${encodeURIComponent(q)}`);
  },

  // AI & ML Model Holdout Metrics
  async getModelMetrics(): Promise<any> {
    return request("/api/ai/models/metrics");
  },

  // Sales Analytics
  async getSalesOverview(): Promise<SalesOverview> {
    return request<SalesOverview>("/api/sales/overview");
  },

  async getSalesForecast(): Promise<SalesForecastResult> {
    return request<SalesForecastResult>("/api/sales/forecast");
  },

  async predictSalesStandalone(params: {
    month_index: number;
    orders: number;
    marketing_spend: number;
  }): Promise<{ predicted_revenue: number; currency: string }> {
    return request("/api/predict/sales", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    return request<DashboardStats>("/api/dashboard/stats");
  },

  async getBusinessHealth(): Promise<BusinessHealthData> {
    return request<BusinessHealthData>("/api/business-health");
  },

  async getActionCenter(): Promise<ActionCenterData> {
    return request<ActionCenterData>("/api/action-center");
  },

  async getDashboardInsights(): Promise<DashboardInsight[]> {
    return request<DashboardInsight[]>("/api/dashboard/insights");
  },

  async getDashboardActivity(): Promise<DashboardActivity[]> {
    return request<DashboardActivity[]>("/api/dashboard/activity");
  },

  // AI Copilot
  async sendCopilotMessage(message: string): Promise<CopilotResponse> {
    return request<CopilotResponse>("/api/copilot/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },

  // Reports
  async getReport(reportType: string): Promise<ReportData> {
    return request<ReportData>(`/api/reports/${encodeURIComponent(reportType)}`);
  },

  // Profit Analyzer
  async getProfitProducts(): Promise<ProfitProduct[]> {
    return request<ProfitProduct[]>("/api/profit/products");
  },

  // Notifications
  async getNotifications(): Promise<NotificationItem[]> {
    return request<NotificationItem[]>("/api/notifications");
  },

  async markAllNotificationsRead(): Promise<{ status: string }> {
    return request<{ status: string }>("/api/notifications/read-all", { method: "POST" });
  },

  async markNotificationRead(id: number): Promise<{ status: string }> {
    return request<{ status: string }>(`/api/notifications/${id}/read`, { method: "POST" });
  },

  async deleteNotification(id: number): Promise<{ status: string }> {
    return request<{ status: string }>(`/api/notifications/${id}`, { method: "DELETE" });
  },

  async clearAllNotifications(): Promise<{ status: string }> {
    return request<{ status: string }>("/api/notifications", { method: "DELETE" });
  },

  // Authentication & Users
  async registerUser(data: { name: string; email: string; password?: string; company?: string; biz_type?: string }): Promise<AuthResponse> {
    return request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async register(data: { name: string; email: string; password?: string; company?: string; biz_type?: string }): Promise<AuthResponse> {
    return this.registerUser(data);
  },

  async loginUser(data: { email: string; password?: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
    // Session is maintained strictly via HttpOnly cookie; ensure no session tokens exist in localStorage
    if (typeof localStorage !== "undefined") {
      try {
        localStorage.removeItem("bizops_session_token");
      } catch {}
    }
    return res;
  },

  async login(data: { email: string; password?: string }): Promise<AuthResponse> {
    return this.loginUser(data);
  },

  async getCurrentUser(): Promise<AuthResponse> {
    try {
      return await request<AuthResponse>("/api/auth/me");
    } catch (err: any) {
      if (typeof localStorage !== "undefined" && err?.message?.includes("401")) {
        try {
          localStorage.removeItem("bizops_session_token");
        } catch {}
      }
      throw err;
    }
  },

  async getMe(email?: string): Promise<AuthResponse> {
    if (email) {
      return request<AuthResponse>(`/api/auth/me?email=${encodeURIComponent(email)}`);
    }
    return this.getCurrentUser();
  },

  async getCsrfToken(): Promise<{ csrf_token: string }> {
    return request<{ csrf_token: string }>("/api/auth/csrf");
  },

  async logoutUser(): Promise<{ status: string; message?: string }> {
    try {
      return await request<{ status: string; message?: string }>("/api/auth/logout", {
        method: "POST",
      });
    } finally {
      if (typeof localStorage !== "undefined") {
        localStorage.removeItem("bizops_session_token");
        localStorage.removeItem("bizops_user");
      }
      inMemoryCsrfToken = null;
    }
  },

  async logout(): Promise<{ status: string; message?: string }> {
    return this.logoutUser();
  },
};

