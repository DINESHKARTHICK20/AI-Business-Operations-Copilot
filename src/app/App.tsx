import { useState, useRef, useEffect, useMemo } from "react";
import {
  LayoutDashboard, Bot, Users, TrendingUp, Package, FileText,
  UserCheck, BarChart3, Settings, LogOut, Bell, Search, ChevronDown,
  ArrowUpRight, ArrowDownRight, Plus, Send, Mic, Paperclip, Star,
  Download, Eye, EyeOff, Edit2, Trash2, Filter, Calendar, RefreshCw,
  ShoppingCart, DollarSign, Activity, AlertTriangle, CheckCircle,
  Clock, Mail, Phone, MapPin, Shield, Key, CreditCard, Zap,
  BarChart2, PieChart, Map, Upload, X, ChevronRight, ChevronLeft,
  Menu, Briefcase, Award, Target, Globe, Cpu, Database, Lock,
  Layers, Sliders, Moon, Sun, BookOpen, HelpCircle, ExternalLink,
  Building2, Tag, Truck, RotateCcw, MessageSquare, Sparkles,
  TrendingDown, Home, Info, Grid, List, MoreHorizontal, Check,
  Volume2, Code, Palette, Type, Square, Circle, Loader2
} from "lucide-react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart as RePieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";

import {
  api,
  Customer,
  Employee,
  Product,
  Invoice,
  DashboardStats,
  DashboardInsight,
  DashboardActivity,
  BusinessHealthData,
  ActionItem,
  ActionCenterData,
  ActionPriority,
  ActionCategory,
  SalesOverview,
  SalesForecastResult,
  ReportData,
  ProfitProduct,
  ChurnPredictionResult,
  InventoryForecastResult,
  UserSession,
} from "./services/api";

function getInitials(name?: string): string {
  if (!name || !name.trim()) return "U";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) {
    return parts[0].length > 1 ? parts[0].slice(0, 2).toUpperCase() : parts[0].toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ─── Shared SVG Gradient Defs ──────────────────────────────────────────────────

function GradientDefs() {
  return (
    <svg width={0} height={0} style={{ position: "absolute" }}>
      <defs>
        <linearGradient id="hero-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.2} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="dash-rev" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="dash-exp" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.1} />
          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="sales-gr1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.2} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="reports-rg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="design-ds1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.2} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="profit-rev" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.25} />
          <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="profit-pft" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="profit-cost" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
        </linearGradient>
      </defs>
    </svg>
  );
}

// ─── Types ──────────────────────────────────────────────────────────────────

type Page =
  | "landing" | "login" | "signup"
  | "dashboard" | "business-health" | "action-center" | "copilot" | "customers" | "sales"
  | "inventory" | "invoices" | "employees" | "reports"
  | "notifications" | "settings" | "profile" | "pricing"
  | "design-system" | "profit";

// ─── Fallback Initial Data ───────────────────────────────────────────────────

const initialRevenueData = [
  { month: "Jan", revenue: 42000, expenses: 28000, profit: 14000 },
  { month: "Feb", revenue: 47500, expenses: 30000, profit: 17500 },
  { month: "Mar", revenue: 51200, expenses: 31500, profit: 19700 },
  { month: "Apr", revenue: 49800, expenses: 29000, profit: 20800 },
  { month: "May", revenue: 58600, expenses: 33000, profit: 25600 },
  { month: "Jun", revenue: 63400, expenses: 35000, profit: 28400 },
  { month: "Jul", revenue: 61200, expenses: 34000, profit: 27200 },
  { month: "Aug", revenue: 67800, expenses: 36500, profit: 31300 },
  { month: "Sep", revenue: 72400, expenses: 38000, profit: 34400 },
  { month: "Oct", revenue: 69100, expenses: 37200, profit: 31900 },
  { month: "Nov", revenue: 78500, expenses: 41000, profit: 37500 },
  { month: "Dec", revenue: 85200, expenses: 44500, profit: 40700 },
];

const initialDailyData = [
  { day: "Mon", sales: 3200, orders: 28 },
  { day: "Tue", sales: 4100, orders: 35 },
  { day: "Wed", sales: 3800, orders: 31 },
  { day: "Thu", sales: 5200, orders: 44 },
  { day: "Fri", sales: 6100, orders: 52 },
  { day: "Sat", sales: 4700, orders: 40 },
  { day: "Sun", sales: 3100, orders: 26 },
];

const initialCustomerGrowth = [
  { month: "Jan", new: 120, returning: 280 },
  { month: "Feb", new: 145, returning: 310 },
  { month: "Mar", new: 162, returning: 340 },
  { month: "Apr", new: 138, returning: 365 },
  { month: "May", new: 190, returning: 390 },
  { month: "Jun", new: 215, returning: 420 },
  { month: "Jul", new: 203, returning: 445 },
];

const initialProductPieData = [
  { name: "Software", value: 38, color: "#4f46e5" },
  { name: "Hardware", value: 25, color: "#8b5cf6" },
  { name: "Services", value: 22, color: "#06b6d4" },
  { name: "Training", value: 15, color: "#10b981" },
];

const fallbackCustomers: Customer[] = [
  { id: 1, name: "Selvaraj Annamalai", email: "selvaraj@techcorp.in", company: "TechCorp India Pvt. Ltd", status: "Active", ltv: "₹10,40,000", orders: 24, joined: "Mar 2023", churn: 8 },
  { id: 2, name: "Kavitha Sundaram", email: "kavitha@buildfast.in", company: "BuildFast Solutions", status: "Active", ltv: "₹7,20,000", orders: 17, joined: "Jun 2023", churn: 15 },
  { id: 3, name: "Rajendhiran Palaniswamy", email: "rajendhiran@dataflow.in", company: "DataFlow Systems", status: "At Risk", ltv: "₹18,00,000", orders: 41, joined: "Jan 2023", churn: 67 },
  { id: 4, name: "Gowrishankar Venkatesh", email: "gowri@cloudshift.in", company: "CloudShift India", status: "Inactive", ltv: "₹2,60,000", orders: 6, joined: "Sep 2023", churn: 88 },
  { id: 5, name: "Tamilselvi Natarajan", email: "tamilselvi@nexalabs.in", company: "Nexa Labs Chennai", status: "Active", ltv: "₹26,50,000", orders: 63, joined: "Nov 2022", churn: 5 },
  { id: 6, name: "Senthilkumar Murugan", email: "senthil@brightbridge.in", company: "BrightBridge Tech", status: "Active", ltv: "₹5,80,000", orders: 14, joined: "Apr 2023", churn: 22 },
];

const fallbackProducts: Product[] = [
  { id: 1, name: "Enterprise Suite Pro", sku: "ESP-001", category: "Software", stock: 245, reorder: 50, price: "₹3,49,000", status: "In Stock", trend: "+12%" },
  { id: 2, name: "Cloud Storage 1TB", sku: "CS1T-002", category: "Storage", stock: 12, reorder: 25, price: "₹24,900", status: "Low Stock", trend: "+8%" },
  { id: 3, name: "API Access Tokens", sku: "AAT-003", category: "Services", stock: 891, reorder: 100, price: "₹4,099/mo", status: "In Stock", trend: "+31%" },
  { id: 4, name: "Analytics Dashboard", sku: "AD-004", category: "Software", stock: 3, reorder: 20, price: "₹1,49,900", status: "Critical", trend: "-4%" },
  { id: 5, name: "Hardware Sensor Kit", sku: "HSK-005", category: "Hardware", stock: 67, reorder: 30, price: "₹74,000", status: "In Stock", trend: "+5%" },
  { id: 6, name: "Training Credits", sku: "TC-006", category: "Training", stock: 0, reorder: 50, price: "₹9,999", status: "Out of Stock", trend: "N/A" },
];

const fallbackInvoices: Invoice[] = [
  { id: "INV-2026-001", client: "TechCorp India Pvt. Ltd", amount: "₹1,03,500", due: "Aug 15, 2026", issued: "Jul 15, 2026", status: "Paid", items: "Enterprise Suite Pro — 1 seat" },
  { id: "INV-2026-002", client: "DataFlow Systems", amount: "₹72,800", due: "Aug 22, 2026", issued: "Jul 22, 2026", status: "Pending", items: "Hardware Sensor Kit & Support" },
  { id: "INV-2026-003", client: "CloudShift India", amount: "₹26,600", due: "Jul 30, 2026", issued: "Jun 30, 2026", status: "Overdue", items: "Cloud Storage 1TB (Annual)" },
  { id: "INV-2026-004", client: "Nexa Labs Chennai", amount: "₹1,80,000", due: "Sep 1, 2026", issued: "Aug 1, 2026", status: "Draft", items: "Enterprise Analytics Suite" },
  { id: "INV-2026-005", client: "BuildFast Solutions", amount: "₹56,700", due: "Aug 10, 2026", issued: "Jul 10, 2026", status: "Paid", items: "API Access Tokens & Cloud Storage" },
];

const fallbackEmployees: Employee[] = [
  { id: 1, name: "Anbarasi Krishnamoorthy", role: "Head of Sales", dept: "Sales", salary: "₹82,000/mo", status: "Active", attendance: 96, performance: 94, joined: "Jan 2021" },
  { id: 2, name: "Thirunavukkarasu Rajan", role: "Senior Engineer", dept: "Engineering", salary: "₹1,04,000/mo", status: "Active", attendance: 98, performance: 91, joined: "Mar 2020" },
  { id: 3, name: "Meenakshi Sundareswaran", role: "Product Manager", dept: "Product", salary: "₹94,000/mo", status: "Active", attendance: 94, performance: 88, joined: "Jun 2021" },
  { id: 4, name: "Pazhanivel Arumugam", role: "Customer Success", dept: "Support", salary: "₹63,000/mo", status: "On Leave", attendance: 82, performance: 87, joined: "Sep 2022" },
  { id: 5, name: "Valarmathi Subramanian", role: "Data Analyst", dept: "Analytics", salary: "₹74,000/mo", status: "Active", attendance: 97, performance: 92, joined: "Feb 2022" },
];

const notifications = [
  { id: 1, type: "ai", title: "AI Insight: Revenue spike detected", desc: "Today's revenue is 34% above your weekly average. AI suggests extending flash sale.", time: "2 min ago", read: false },
  { id: 2, type: "inventory", title: "Low stock alert: Analytics Dashboard", desc: "Only 3 units remaining. Reorder level is 20. AI recommends restocking immediately.", time: "18 min ago", read: false },
  { id: 3, type: "payment", title: "Payment overdue: CloudShift invoice", desc: "INV-2026-003 for ₹26,600 is 5 days past due. Follow-up email sent.", time: "1 hr ago", read: false },
  { id: 4, type: "customer", title: "Churn risk: Priya Nair (DataFlow AI)", desc: "67% churn probability detected. Last purchase 45 days ago. Recommend outreach.", time: "3 hrs ago", read: true },
  { id: 5, type: "revenue", title: "Monthly target achieved", desc: "You've hit 87% of July's revenue target with 3 days remaining.", time: "Yesterday", read: true },
  { id: 6, type: "employee", title: "Leave request: Carlos Mendez", desc: "Requested 5 days leave from Aug 12-16. Pending your approval.", time: "2 days ago", read: true },
];

const chatHistory = [
  { id: 1, title: "Revenue analysis July", time: "Today" },
  { id: 2, title: "Inventory restock plan", time: "Yesterday" },
  { id: 3, title: "Customer churn report", time: "Jul 24" },
  { id: 4, title: "Invoice generation Q2", time: "Jul 22" },
  { id: 5, title: "Sales forecast Q3", time: "Jul 18" },
];

const suggestedPrompts = [
  "Show today's revenue breakdown",
  "Predict next month's sales",
  "Generate invoice for TechCorp",
  "Summarize customer feedback",
  "Which products need restocking?",
  "Show top 5 performing employees",
];

// ─── Shared Components ───────────────────────────────────────────────────────

function Badge({ label, variant = "default" }: { label: string; variant?: "default" | "success" | "warning" | "danger" | "info" | "purple" }) {
  const variants = {
    default: "bg-slate-100 text-slate-600",
    success: "bg-emerald-50 text-emerald-700",
    warning: "bg-amber-50 text-amber-700",
    danger: "bg-red-50 text-red-600",
    info: "bg-blue-50 text-blue-700",
    purple: "bg-violet-50 text-violet-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${variants[variant] || variants.default}`}>
      {label}
    </span>
  );
}

function KPICard({ title, value, change, icon: Icon, color, prefix = "" }: {
  title: string; value: string; change: string; icon: any; color: string; prefix?: string;
}) {
  const isPositive = change.startsWith("+");
  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
        <span className={`flex items-center gap-1 text-xs font-semibold ${isPositive ? "text-emerald-600" : "text-red-500"}`}>
          {isPositive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          {change}
        </span>
      </div>
      <p className="text-2xl font-bold text-slate-800 mb-1">{prefix}{value}</p>
      <p className="text-xs text-slate-500">{title}</p>
    </div>
  );
}

function GradientButton({ children, onClick, size = "md", variant = "primary", className = "", disabled = false }: {
  children: React.ReactNode; onClick?: () => void; size?: "sm" | "md" | "lg"; variant?: "primary" | "secondary" | "outline" | "ghost"; className?: string; disabled?: boolean;
}) {
  const sizes = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm", lg: "px-6 py-3 text-base" };
  const variants = {
    primary: "bg-gradient-to-r from-indigo-500 to-violet-600 text-white hover:from-indigo-600 hover:to-violet-700 shadow-sm shadow-indigo-200",
    secondary: "bg-slate-100 text-slate-700 hover:bg-slate-200",
    outline: "border border-slate-200 text-slate-700 hover:bg-slate-50",
    ghost: "text-slate-600 hover:bg-slate-100",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 font-medium rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed ${sizes[size]} ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

function SearchBar({ value, onChange, placeholder = "Search..." }: { value?: string; onChange?: (val: string) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        value={value || ""}
        onChange={e => onChange && onChange(e.target.value)}
        className="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 w-64"
        placeholder={placeholder}
      />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    Active: "bg-emerald-50 text-emerald-700",
    Inactive: "bg-slate-100 text-slate-500",
    "At Risk": "bg-amber-50 text-amber-700",
    "In Stock": "bg-emerald-50 text-emerald-700",
    "Low Stock": "bg-amber-50 text-amber-700",
    Critical: "bg-red-50 text-red-600",
    "Out of Stock": "bg-red-50 text-red-600",
    Paid: "bg-emerald-50 text-emerald-700",
    Pending: "bg-amber-50 text-amber-700",
    Overdue: "bg-red-50 text-red-600",
    Draft: "bg-slate-100 text-slate-500",
    "On Leave": "bg-blue-50 text-blue-600",
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-slate-100 text-slate-600"}`}>
      {status}
    </span>
  );
}

// ─── Layout Components ────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "business-health", label: "AI Business Health", icon: Activity },
  { id: "action-center", label: "AI Action Center", icon: Zap },
  { id: "copilot", label: "AI Copilot", icon: Bot },
  { id: "sales", label: "Sales Analytics", icon: TrendingUp },
  { id: "inventory", label: "Inventory", icon: Package },
  { id: "customers", label: "Customers", icon: Users },
  { id: "invoices", label: "Invoices", icon: FileText },
  { id: "employees", label: "Employees", icon: UserCheck },
  { id: "profit", label: "Profit Analyzer", icon: PieChart },
  { id: "reports", label: "Reports", icon: BarChart3 },
];

function Sidebar({ page, setPage, collapsed, setCollapsed, user, onLogout }: {
  page: Page; setPage: (p: Page) => void; collapsed: boolean; setCollapsed: (c: boolean) => void; user: UserSession | null; onLogout: () => void;
}) {
  return (
    <aside className={`flex flex-col h-screen bg-slate-900 transition-all duration-300 ${collapsed ? "w-16" : "w-60"} shrink-0`}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center shrink-0">
          <Cpu size={16} className="text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-white font-semibold text-sm leading-tight truncate">AI BizOps</p>
            <p className="text-slate-400 text-xs truncate">Copilot</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-slate-400 hover:text-white transition-colors shrink-0"
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Business selector */}
      {!collapsed && (
        <div className="px-3 py-3 border-b border-white/10">
          <button className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
            <Building2 size={14} className="text-slate-400 shrink-0" />
            <span className="text-slate-300 text-xs font-medium truncate flex-1 text-left">{user?.company || "Nexus Commerce Ltd"}</span>
            <ChevronDown size={12} className="text-slate-400 shrink-0" />
          </button>
        </div>
      )}

      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = page === id;
          return (
            <button
              key={id}
              onClick={() => setPage(id as Page)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${active
                ? "bg-gradient-to-r from-indigo-500/20 to-violet-500/10 text-indigo-300 border border-indigo-500/20"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
            >
              <Icon size={16} className={`shrink-0 ${active ? "text-indigo-400" : ""}`} />
              {!collapsed && <span className="truncate">{label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Bottom nav */}
      <div className="px-2 py-3 border-t border-white/10 space-y-0.5">
        {[
          { id: "notifications", label: "Notifications", icon: Bell },
          { id: "settings", label: "Settings", icon: Settings },
          { id: "profile", label: "Profile", icon: Users },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setPage(id as Page)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${page === id ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
          >
            <Icon size={16} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </button>
        ))}
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-all"
        >
          <LogOut size={16} className="shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  );
}

function TopBar({ page, setPage, user }: { page: Page; setPage: (p: Page) => void; user: UserSession | null }) {
  const labels: Record<string, string> = {
    dashboard: "Dashboard", "business-health": "AI Business Health", "action-center": "AI Action Center", copilot: "AI Copilot", customers: "Customers",
    sales: "Sales Analytics", inventory: "Inventory", invoices: "Invoices",
    employees: "Employees", reports: "Reports", notifications: "Notifications",
    settings: "Settings", profile: "Profile", pricing: "Pricing & Billing",
    "design-system": "Design System", profit: "Profit Analyzer",
  };
  return (
    <header className="h-14 bg-white border-b border-slate-100 flex items-center px-6 gap-4 shrink-0">
      <h1 className="font-semibold text-slate-800 text-sm">{labels[page] || page}</h1>

      <div className="flex-1" />
      <SearchBar placeholder="Search anything..." />
      <button
        className="relative w-8 h-8 rounded-xl border border-slate-200 flex items-center justify-center text-slate-500 hover:bg-slate-50"
        onClick={() => setPage("notifications")}
      >
        <Bell size={15} />
        <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
      </button>
      <button
        onClick={() => setPage("profile")}
        className="flex items-center gap-2 px-2 py-1 rounded-xl hover:bg-slate-50 transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xs font-semibold">
          {getInitials(user?.name)}
        </div>
        <span className="text-sm font-medium text-slate-700">{user?.name || "User"}</span>
        <ChevronDown size={13} className="text-slate-400" />
      </button>
    </header>
  );
}

function AppLayout({ page, setPage, user, onLogout, children }: { page: Page; setPage: (p: Page) => void; user: UserSession | null; onLogout: () => void; children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden" style={{ fontFamily: "'Inter', sans-serif" }}>
      <Sidebar page={page} setPage={setPage} collapsed={collapsed} setCollapsed={setCollapsed} user={user} onLogout={onLogout} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar page={page} setPage={setPage} user={user} />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}


// ─── Landing Page ─────────────────────────────────────────────────────────────

function LandingPage({ setPage }: { setPage: (p: Page) => void }) {
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const features = [
    { icon: Bot, title: "AI-Powered Insights", desc: "Get real-time business intelligence with natural language queries. Ask anything about your operations.", color: "from-indigo-500 to-indigo-600" },
    { icon: TrendingUp, title: "Sales Forecasting", desc: "Predict next month's revenue with 94% accuracy using our advanced ML models trained on your data.", color: "from-violet-500 to-violet-600" },
    { icon: Package, title: "Smart Inventory", desc: "Automatic reorder alerts and demand prediction. Never run out of stock or overstock again.", color: "from-cyan-500 to-cyan-600" },
    { icon: Users, title: "Customer Intelligence", desc: "Identify at-risk customers before they churn. AI-driven outreach recommendations and LTV analysis.", color: "from-emerald-500 to-emerald-600" },
    { icon: FileText, title: "Invoice Automation", desc: "Generate, send, and track invoices in seconds. AI extracts data and fills forms automatically.", color: "from-amber-500 to-amber-600" },
    { icon: UserCheck, title: "HR & Payroll", desc: "Manage employees, track attendance, and automate payroll. AI flags anomalies and suggests optimizations.", color: "from-rose-500 to-rose-600" },
  ];

  const testimonials = [
    { name: "Sarah Mitchell", role: "CEO, TechCorp Inc.", text: "AI BizOps replaced 3 separate tools. Our operations team saves 20+ hours a week. The AI insights are genuinely useful, not just dashboard fluff.", avatar: "SM" },
    { name: "James Rodriguez", role: "Founder, BuildFast Co.", text: "The inventory AI caught a stockout risk we completely missed. Saved us from losing our biggest client. Worth every penny of the Pro plan.", avatar: "JR" },
    { name: "Emily Chen", role: "COO, Nexa Labs", text: "Best operations platform we've used. The chat interface is like having a business analyst on call 24/7. Onboarding took less than a day.", avatar: "EC" },
  ];

  const faqs = [
    { q: "How does the AI Copilot work?", a: "The AI Copilot connects to all your business data and lets you ask questions in plain English. It uses large language models fine-tuned on business operations data to provide accurate, actionable answers." },
    { q: "How long does onboarding take?", a: "Most businesses are fully set up within 24 hours. We offer guided setup, CSV imports, and 40+ integrations. Our team is available to help at every step." },
    { q: "Is my data secure?", a: "Yes. We're SOC 2 Type II certified, GDPR compliant, and use AES-256 encryption at rest and TLS 1.3 in transit. Your data is never used to train our models." },
    { q: "Can I cancel anytime?", a: "Absolutely. No lock-in contracts. Cancel anytime from your dashboard and your data is exported automatically. We also offer a 30-day money-back guarantee." },
    { q: "Do you support multiple businesses?", a: "Yes. The Business and Enterprise plans support multiple business entities under one account, each with separate data, users, and settings." },
  ];

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }} className="min-h-screen bg-white">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Cpu size={16} className="text-white" />
            </div>
            <span className="font-bold text-slate-800">AI BizOps</span>
          </div>
          <div className="hidden md:flex items-center gap-6 flex-1">
            {["Features", "Pricing", "Customers", "Docs"].map(l => (
              <a key={l} href="#" className="text-sm text-slate-500 hover:text-slate-800 transition-colors">{l}</a>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => setPage("login")} className="text-sm font-medium text-slate-600 hover:text-slate-800 px-4 py-2">Sign in</button>
            <button onClick={() => setPage("signup")} className="text-sm font-semibold bg-gradient-to-r from-indigo-500 to-violet-600 text-white px-5 py-2 rounded-xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-sm shadow-indigo-200">
              Get Started Free
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden pt-20 pb-24">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-50 via-white to-violet-50" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-r from-indigo-400/20 to-violet-400/20 blur-3xl rounded-full" />
        <div className="relative max-w-6xl mx-auto px-6 text-center">
          <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 leading-tight mb-6 tracking-tight">
            Your AI Employee for<br />
            <span className="bg-gradient-to-r from-indigo-500 to-violet-600 bg-clip-text text-transparent">Business Operations</span>
          </h1>
          <p className="text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Automate invoicing, manage inventory, predict sales, and get AI-powered insights — all in one platform built for growing businesses.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <button onClick={() => setPage("signup")} className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold rounded-2xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-lg shadow-indigo-200 text-base">
              Get Started Free
              <ArrowUpRight size={18} />
            </button>
            <button onClick={() => setPage("login")} className="flex items-center gap-2 px-8 py-4 bg-white border border-slate-200 text-slate-700 font-semibold rounded-2xl hover:bg-slate-50 transition-all text-base">
              Sign In
            </button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 bg-white">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <Badge label="Features" variant="info" />
            <h2 className="text-4xl font-extrabold text-slate-900 mt-4 mb-4">Everything you need to run smarter</h2>
            <p className="text-lg text-slate-500 max-w-xl mx-auto">One platform that replaces five tools and adds AI intelligence on top.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {features.map(({ icon: Icon, title, desc, color }) => (
              <div key={title} className="group p-6 rounded-2xl border border-slate-100 hover:border-indigo-100 hover:shadow-lg hover:shadow-indigo-50 transition-all bg-white">
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center mb-5`}>
                  <Icon size={22} className="text-white" />
                </div>
                <h3 className="text-base font-semibold text-slate-800 mb-2">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 bg-slate-50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <Badge label="Testimonials" variant="purple" />
            <h2 className="text-4xl font-extrabold text-slate-900 mt-4 mb-4">Trusted by 2,400+ businesses</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {testimonials.map(({ name, role, text, avatar }) => (
              <div key={name} className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
                <div className="flex gap-1 mb-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star key={i} size={14} className="text-amber-400 fill-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-slate-600 leading-relaxed mb-6">&ldquo;{text}&rdquo;</p>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold">
                    {avatar}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{name}</p>
                    <p className="text-xs text-slate-500">{role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-24 bg-slate-50">
        <div className="max-w-2xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold text-slate-900">Frequently Asked Questions</h2>
          </div>
          <div className="space-y-3">
            {faqs.map(({ q, a }, i) => (
              <div key={i} className="bg-white rounded-2xl border border-slate-100 overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="text-sm font-semibold text-slate-800">{q}</span>
                  <ChevronDown size={15} className={`text-slate-400 transition-transform ${openFaq === i ? "rotate-180" : ""}`} />
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4">
                    <p className="text-sm text-slate-500 leading-relaxed">{a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            <div className="col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center">
                  <Cpu size={14} className="text-white" />
                </div>
                <span className="text-white font-bold">AI BizOps</span>
              </div>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xs">
                The AI-powered operations platform for ambitious small and medium businesses.
              </p>
            </div>
            {[
              { title: "Product", links: ["Features", "Pricing", "Changelog", "Roadmap"] },
              { title: "Company", links: ["About", "Blog", "Careers", "Press"] },
              { title: "Legal", links: ["Privacy", "Terms", "Security", "GDPR"] },
            ].map(({ title, links }) => (
              <div key={title}>
                <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-4">{title}</h4>
                <ul className="space-y-2">
                  {links.map(l => <li key={l}><a href="#" className="text-sm hover:text-white transition-colors">{l}</a></li>)}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-white/10 pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-xs">© 2026 AI BizOps Copilot. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ─── Login Page ───────────────────────────────────────────────────────────────

function LoginPage({
  setPage,
  onLoginSuccess,
  initialNotice,
  initialEmail = "",
}: {
  setPage: (p: Page) => void;
  onLoginSuccess: (u: UserSession) => void;
  initialNotice?: string | null;
  initialEmail?: string;
}) {
  const [email, setEmail] = useState(() => {
    try {
      return initialEmail || localStorage.getItem("bizops_remembered_email") || "";
    } catch {
      return initialEmail || "";
    }
  });
  const [pass, setPass] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(() => {
    try {
      return !!localStorage.getItem("bizops_remembered_email");
    } catch {
      return false;
    }
  });
  const [loading, setLoading] = useState(false);
  const [checkingServer, setCheckingServer] = useState(false);
  const [serverStatus, setServerStatus] = useState<"checking" | "online" | "offline">("checking");
  const [isConnectionError, setIsConnectionError] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(initialNotice || null);

  useEffect(() => {
    if (initialNotice) {
      setSuccessMsg(initialNotice);
    }
    if (initialEmail) {
      setEmail(initialEmail);
    }
  }, [initialNotice, initialEmail]);

  const checkServerStatus = async () => {
    setCheckingServer(true);
    try {
      const res = await api.checkHealth();
      if (res && res.status === "healthy") {
        setServerStatus("online");
        if (isConnectionError) {
          setErrorMsg(null);
          setIsConnectionError(false);
        }
      } else {
        setServerStatus("offline");
      }
    } catch {
      setServerStatus("offline");
    } finally {
      setCheckingServer(false);
    }
  };

  useEffect(() => {
    checkServerStatus();
  }, []);

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    const loginPassword = pass;

    // Real email format validation
    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!cleanEmail) {
      setErrorMsg("Please enter your email address.");
      return;
    }
    if (!emailRegex.test(cleanEmail)) {
      setErrorMsg("Please enter a valid email address (e.g. name@company.com).");
      return;
    }
    if (!loginPassword) {
      setErrorMsg("Please enter your password.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setIsConnectionError(false);
    try {
      const res = await api.loginUser({ email: cleanEmail, password: loginPassword });
      const user = res?.user || (res?.email ? { id: res.id, name: res.name, email: res.email, company: res.company, biz_type: res.biz_type } : null);
      if (user) {
        setServerStatus("online");
        if (remember) {
          try {
            localStorage.setItem("bizops_remembered_email", cleanEmail);
          } catch {}
        } else {
          try {
            localStorage.removeItem("bizops_remembered_email");
          } catch {}
        }
        onLoginSuccess(user);
        return;
      } else {
        setErrorMsg("Invalid email or password.");
      }
    } catch (err: any) {
      const msg = err?.message || "";
      if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError") ||
        err.name === "TypeError" ||
        msg.includes("Unable to connect") ||
        msg.includes("unreachable") ||
        msg.includes("502") ||
        msg.includes("504")
      ) {
        setServerStatus("offline");
        setIsConnectionError(true);
        setErrorMsg("Unable to connect to the backend server. Please verify the FastAPI backend is running on http://localhost:8000 and try again.");
      } else {
        setIsConnectionError(false);
        setErrorMsg(msg || "Failed to sign in. Please verify your credentials.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-6" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
      </div>
      <div className="relative w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2.5 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Cpu size={20} className="text-white" />
            </div>
            <span className="text-white font-bold text-xl tracking-tight">AI BizOps</span>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Welcome back</h1>
          <p className="text-slate-400 text-sm">Sign in with your email and password</p>
        </div>

        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          {successMsg && (
            <div className="mb-5 px-4 py-3 bg-emerald-500/15 border border-emerald-500/30 rounded-xl flex items-center gap-2.5 text-emerald-300 text-xs">
              <CheckCircle size={15} className="text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {errorMsg && (
            <div className="mb-5 p-4 bg-red-500/15 border border-red-500/30 rounded-xl text-red-300 text-xs space-y-3">
              <div className="flex items-start gap-2.5">
                <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold text-red-200">
                    {isConnectionError ? "Unable to connect to server" : "Sign In Notice"}
                  </p>
                  <p className="text-red-300/90 leading-relaxed">{errorMsg}</p>
                </div>
              </div>

              {isConnectionError && (
                <div className="pt-2 border-t border-red-500/20 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={async () => {
                      await checkServerStatus();
                      if (email && pass) handleLogin();
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-xs font-medium transition-colors"
                  >
                    <RefreshCw size={12} className={checkingServer || loading ? "animate-spin" : ""} />
                    Retry Connection
                  </button>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address <span className="text-red-400">*</span></label>
              <input
                value={email}
                onChange={e => { setEmail(e.target.value); setErrorMsg(null); setSuccessMsg(null); setIsConnectionError(false); }}
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-300">Password <span className="text-red-400">*</span></label>
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); setErrorMsg("Please contact your administrator to reset your account password."); }}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                >
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <input
                  value={pass}
                  onChange={e => { setPass(e.target.value); setErrorMsg(null); setIsConnectionError(false); }}
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-4 pr-10 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="remember"
                checked={remember}
                onChange={e => setRemember(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 accent-indigo-500"
              />
              <label htmlFor="remember" className="text-sm text-slate-400">Remember my email</label>
            </div>

            <button
              type="submit"
              disabled={!email.trim() || !pass || loading}
              className="w-full mt-6 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold rounded-xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-lg shadow-indigo-900/50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : "Sign In"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-5">
            Don&apos;t have an account?{" "}
            <button onClick={() => setPage("signup")} className="text-indigo-400 hover:text-indigo-300 font-medium">
              Create Account
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}



// ─── Signup Page ──────────────────────────────────────────────────────────────

function SignUpPage({
  setPage,
  onRegistered,
}: {
  setPage: (p: Page) => void;
  onRegistered?: (email: string) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [bizType, setBizType] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const businessTypes = ["Select business type", "E-commerce", "Retail", "SaaS", "Consulting", "Manufacturing", "Healthcare", "Food & Beverage", "Logistics", "Real Estate", "Other"];

  const handleRegister = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    const cleanName = fullName.trim();
    const cleanCompany = company.trim();
    const cleanBiz = bizType.trim();
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanName || !cleanCompany || !cleanBiz || !cleanEmail || !password) {
      setErrorMsg("Please fill in all required fields.");
      return;
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailRegex.test(cleanEmail)) {
      setErrorMsg("Please enter a valid email address (e.g. you@company.com).");
      return;
    }

    if (password.length < 6) {
      setErrorMsg("Password must be at least 6 characters.");
      return;
    }

    if (password !== confirm) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    if (!agreed) {
      setErrorMsg("You must agree to the Terms of Service.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.registerUser({
        name: cleanName,
        email: cleanEmail,
        password,
        company: cleanCompany,
        biz_type: cleanBiz,
      });
      if (res?.status === "success" || res?.user) {
        setSuccessMsg("Account created successfully! Redirecting to sign in...");
        setTimeout(() => {
          if (onRegistered) {
            onRegistered(cleanEmail);
          } else {
            setPage("login");
          }
        }, 1200);
      } else {
        setErrorMsg("Failed to create account. Please try again.");
      }
    } catch (err: any) {
      const msg = err?.message || "";
      if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || err.name === "TypeError" || msg.includes("Unable to connect") || msg.includes("unreachable")) {
        setErrorMsg("Unable to connect to the backend server. Please verify the FastAPI backend is running on http://localhost:8000.");
      } else if (msg.includes("already exists")) {
        setErrorMsg("An account with this email already exists. Please sign in.");
      } else {
        setErrorMsg(msg || "Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-6" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl" />
      </div>
      <div className="relative w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2.5 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center">
              <Cpu size={20} className="text-white" />
            </div>
            <span className="text-white font-bold text-xl">AI BizOps</span>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Create your account</h1>
          <p className="text-slate-400 text-sm">Start automating your operations in minutes</p>
        </div>
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          {successMsg && (
            <div className="mb-5 px-4 py-3 bg-emerald-500/15 border border-emerald-500/30 rounded-xl flex items-center gap-2.5 text-emerald-300 text-xs">
              <CheckCircle size={15} className="text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {errorMsg && (
            <div className="mb-5 px-4 py-3 bg-red-500/15 border border-red-500/30 rounded-xl flex items-center gap-2.5 text-red-300 text-xs">
              <AlertTriangle size={15} className="text-red-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name <span className="text-red-400">*</span></label>
                <input
                  value={fullName}
                  onChange={e => { setFullName(e.target.value); setErrorMsg(null); }}
                  type="text"
                  placeholder="Enter your full name"
                  autoComplete="name"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Company Name <span className="text-red-400">*</span></label>
                <input
                  value={company}
                  onChange={e => { setCompany(e.target.value); setErrorMsg(null); }}
                  type="text"
                  placeholder="Your company name"
                  autoComplete="organization"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Business Type <span className="text-red-400">*</span></label>
              <select
                value={bizType}
                onChange={e => { setBizType(e.target.value); setErrorMsg(null); }}
                className="w-full bg-slate-850 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30 appearance-none bg-slate-800"
                style={{ color: bizType ? "#fff" : "#64748b" }}
              >
                {businessTypes.map(t => (
                  <option key={t} value={t === "Select business type" ? "" : t} className="text-slate-900 bg-white">
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Work Email <span className="text-red-400">*</span></label>
              <input
                value={email}
                onChange={e => { setEmail(e.target.value); setErrorMsg(null); }}
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Password <span className="text-red-400">*</span></label>
                <div className="relative">
                  <input
                    value={password}
                    onChange={e => { setPassword(e.target.value); setErrorMsg(null); }}
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Min. 6 characters"
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-4 pr-10 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/30"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Confirm Password <span className="text-red-400">*</span></label>
                <div className="relative">
                  <input
                    value={confirm}
                    onChange={e => { setConfirm(e.target.value); setErrorMsg(null); }}
                    type={showConfirm ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Repeat password"
                    className={`w-full bg-white/5 border rounded-xl pl-4 pr-10 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 ${confirm && confirm !== password ? "border-red-500/50" : "border-white/10 focus:border-indigo-500/30"}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                    tabIndex={-1}
                    aria-label={showConfirm ? "Hide password" : "Show password"}
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {confirm && confirm !== password && (
                  <p className="text-xs text-red-400 mt-1">Passwords do not match</p>
                )}
              </div>
            </div>
            <div className="flex items-start gap-2.5 pt-1">
              <input
                type="checkbox"
                id="agree"
                checked={agreed}
                onChange={e => { setAgreed(e.target.checked); setErrorMsg(null); }}
                className="w-4 h-4 mt-0.5 rounded border-white/20 accent-indigo-500 shrink-0"
              />
              <label htmlFor="agree" className="text-xs text-slate-400 leading-relaxed">
                I agree to the{" "}
                <a href="#" className="text-indigo-400 hover:text-indigo-300">Terms of Service</a>{" "}
                and{" "}
                <a href="#" className="text-indigo-400 hover:text-indigo-300">Privacy Policy</a>
              </label>
            </div>

            <button
              type="submit"
              disabled={!fullName.trim() || !company.trim() || !bizType.trim() || !email.trim() || !password || password !== confirm || !agreed || loading || !!successMsg}
              className="w-full mt-5 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold rounded-xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-lg shadow-indigo-900/50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : "Create Account"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-5">
            Already have an account?{" "}
            <button onClick={() => setPage("login")} className="text-indigo-400 hover:text-indigo-300 font-medium">Sign in</button>
          </p>
        </div>
      </div>
    </div>
  );
}


// ─── Dashboard Page ───────────────────────────────────────────────────────────

function DashboardPage({ setPage, user }: { setPage: (p: Page) => void; user: UserSession | null }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [insights, setInsights] = useState<DashboardInsight[]>([]);
  const [activity, setActivity] = useState<DashboardActivity[]>([]);
  const [salesOverview, setSalesOverview] = useState<SalesOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getDashboardStats().catch(() => null),
      api.getDashboardInsights().catch(() => []),
      api.getDashboardActivity().catch(() => []),
      api.getSalesOverview().catch(() => null),
    ]).then(([statsData, insightsData, activityData, salesData]) => {
      if (statsData) setStats(statsData);
      if (insightsData.length > 0) setInsights(insightsData);
      if (activityData.length > 0) setActivity(activityData);
      if (salesData) setSalesOverview(salesData);
      setLoading(false);
    });
  }, []);

  const kpis = stats?.kpis || {
    today_revenue: "₹7,02,500", today_revenue_change: "+23%",
    monthly_revenue: "₹52.8L", monthly_revenue_change: "+12%",
    active_customers: "1,284", active_customers_change: "+8%",
    pending_orders: "47", pending_orders_change: "-3%",
    inventory_health: "78%", inventory_health_change: "-5%",
    business_health: "82/100",
    business_health_change: "Good"
  };

  const currentRevenueData = salesOverview?.monthly || initialRevenueData;
  const currentCategoryData = salesOverview?.product_categories || initialProductPieData;
  const currentGrowthData = salesOverview?.customer_growth || initialCustomerGrowth;

  const lowStockItems = stats?.low_stock_alerts && stats.low_stock_alerts.length > 0
    ? stats.low_stock_alerts.slice(0, 3)
    : fallbackProducts.filter(p => p.status !== "In Stock").slice(0, 3);

  const fallbackActivity = [
    { icon: DollarSign, text: "Invoice #INV-2026-001 paid by TechCorp India — ₹1,03,500", time: "2 min ago", color: "text-emerald-500" },
    { icon: Users, text: "New customer: Gowrishankar Venkatesh (CloudShift India)", time: "34 min ago", color: "text-indigo-500" },
    { icon: AlertTriangle, text: "Low stock alert: Analytics Dashboard (3 left)", time: "1 hr ago", color: "text-amber-500" },
    { icon: ShoppingCart, text: "47 pending orders require processing", time: "2 hrs ago", color: "text-violet-500" },
    { icon: UserCheck, text: "Pazhanivel Arumugam submitted leave request", time: "3 hrs ago", color: "text-blue-500" },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Welcome back, {user?.name || "User"} 👋</h1>
          <p className="text-xs text-slate-500 mt-0.5">Here is your business operations overview for today.</p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {[
          { title: "Today's Revenue", value: kpis.today_revenue, change: kpis.today_revenue_change, icon: DollarSign, color: "bg-indigo-500" },
          { title: "Monthly Revenue", value: kpis.monthly_revenue, change: kpis.monthly_revenue_change, icon: TrendingUp, color: "bg-violet-500" },
          { title: "Active Customers", value: kpis.active_customers, change: kpis.active_customers_change, icon: Users, color: "bg-cyan-500" },
          { title: "Pending Orders", value: kpis.pending_orders, change: kpis.pending_orders_change, icon: ShoppingCart, color: "bg-amber-500" },
          { title: "Inventory Health", value: kpis.inventory_health, change: kpis.inventory_health_change, icon: Package, color: "bg-rose-500" },
          { title: "Business Health", value: kpis.business_health, change: kpis.business_health_change, icon: Activity, color: "bg-emerald-500" },
        ].map(card => <KPICard key={card.title} {...card} />)}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Revenue Overview</h2>
              <p className="text-xs text-slate-400 mt-0.5">Revenue vs Expenses — Last 7 months (Live Backend)</p>
            </div>
            <select className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600">
              <option>Full Year 2026</option>
              <option>Jan</option>
              <option>Feb</option>
              <option>Mar</option>
              <option>Apr</option>
              <option>May</option>
              <option>Jun</option>
              <option>Jul</option>
              <option>Aug</option>
              <option>Sep</option>
              <option>Oct</option>
              <option>Nov</option>
              <option>Dec</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={currentRevenueData}>
              <CartesianGrid key="cg" strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis key="x" dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis key="y" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={v => `₹${v / 1000}k`} />
              <Tooltip key="tt" formatter={(v: any) => [`₹${v.toLocaleString()}`, ""]} contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #e2e8f0" }} />
              <Legend key="lg" wrapperStyle={{ fontSize: 11 }} />
              <Area key="revenue" type="monotone" dataKey="revenue" name="Revenue" stroke="#4f46e5" strokeWidth={2.5} fill="url(#dash-rev)" dot={false} />
              <Area key="expenses" type="monotone" dataKey="expenses" name="Expenses" stroke="#8b5cf6" strokeWidth={2} fill="url(#dash-exp)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-1">Sales by Category</h2>
          <p className="text-xs text-slate-400 mb-4">This month</p>
          <ResponsiveContainer width="100%" height={160}>
            <RePieChart>
              <Pie key="pie" data={currentCategoryData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {currentCategoryData.map((e, i) => <Cell key={`dash-pie-${i}`} fill={e.color} />)}
              </Pie>
              <Tooltip key="tt" formatter={(v: any) => [`${v}%`, ""]} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
            </RePieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {currentCategoryData.map(({ name, value, color }) => (
              <div key={name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="text-slate-600">{name}</span>
                </div>
                <span className="font-semibold text-slate-700">{value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-3 gap-5">
        {/* AI Insights */}
        <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-5 border border-indigo-100">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Sparkles size={14} className="text-white" />
            </div>
            <h2 className="text-sm font-semibold text-slate-800">AI Insights</h2>
          </div>
          <div className="space-y-3">
            {(insights.length > 0 ? insights : [
              { text: "Revenue up 23% today. Flash sale is performing above prediction.", type: "positive" as const },
              { text: "3 customers show churn risk. Recommend outreach campaign.", type: "warning" as const },
              { text: "Analytics Dashboard SKU critically low. Reorder recommended.", type: "danger" as const },
              { text: "August ML forecast: ₹56.8L (+7.6% vs last month).", type: "info" as const },
            ]).map(({ text, type }, i) => {
              const colors = { positive: "text-emerald-700 bg-emerald-50 border-emerald-200", warning: "text-amber-700 bg-amber-50 border-amber-200", danger: "text-red-600 bg-red-50 border-red-200", info: "text-indigo-700 bg-indigo-50 border-indigo-200" };
              return (
                <div key={i} className={`text-xs p-3 rounded-xl border ${colors[type] || colors.info} leading-relaxed`}>
                  {text}
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Recent Activity</h2>
          <div className="space-y-4">
            {(activity.length > 0 ? activity : fallbackActivity).map(({ text, time, color }, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-slate-50 flex items-center justify-center shrink-0">
                  <Activity size={13} className={color} />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-slate-700 leading-relaxed">{text}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions + Low Stock */}
        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800 mb-3">Quick Actions</h2>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "Invoice", icon: FileText, onClick: () => setPage("invoices") },
                { label: "AI Report", icon: Bot, onClick: () => setPage("copilot") },
                { label: "Add Customer", icon: Users, onClick: () => setPage("customers") },
              ].map(({ label, icon: Icon, onClick }) => (
                <button key={label} onClick={onClick} className="flex flex-col items-center gap-2 p-3 rounded-xl bg-slate-50 hover:bg-indigo-50 hover:text-indigo-600 transition-colors group">
                  <Icon size={18} className="text-slate-400 group-hover:text-indigo-500" />
                  <span className="text-xs font-medium text-slate-600 group-hover:text-indigo-600">{label}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-800">Low Stock Alerts</h2>
              <AlertTriangle size={14} className="text-amber-500" />
            </div>
            <div className="space-y-2.5">
              {lowStockItems.map((p) => {
                const max = p.reorder || 25;
                const stock = p.stock;
                return (
                  <div key={p.name}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-600 truncate">{p.name}</span>
                      <span className={`font-semibold ${stock === 0 ? "text-red-500" : "text-amber-600"}`}>{stock}/{max}</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${stock === 0 ? "bg-red-500" : stock / max < 0.3 ? "bg-amber-500" : "bg-emerald-500"}`}
                        style={{ width: `${Math.min(100, (stock / Math.max(1, max)) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Customer growth chart */}
      <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Customer Growth</h2>
            <p className="text-xs text-slate-400 mt-0.5">New vs Returning</p>
          </div>
          <button onClick={() => setPage("customers")} className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
            View All <ArrowUpRight size={12} />
          </button>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={currentGrowthData} barSize={18}>
            <CartesianGrid key="cg" strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis key="x" dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis key="y" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <Tooltip key="tt" contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #e2e8f0" }} />
            <Legend key="lg" wrapperStyle={{ fontSize: 11 }} />
            <Bar key="new" dataKey="new" name="New Customers" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            <Bar key="returning" dataKey="returning" name="Returning" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── AI Business Health Page ──────────────────────────────────────────────────

function BusinessHealthPage({ setPage }: { setPage: (p: Page) => void }) {
  const [healthData, setHealthData] = useState<BusinessHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = () => {
    setLoading(true);
    setError(null);
    api.getBusinessHealth()
      .then((data) => {
        setHealthData(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load business health metrics");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const overallScore = healthData?.overall_score ?? healthData?.score ?? 72;
  const healthLevel = healthData?.health_level ?? "Good";

  const getLevelStyles = (level: string) => {
    switch (level) {
      case "Excellent":
        return {
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          ring: "text-emerald-400",
          bar: "from-emerald-500 to-teal-400",
          chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        };
      case "Good":
        return {
          badge: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40",
          ring: "text-indigo-400",
          bar: "from-indigo-500 to-violet-500",
          chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
        };
      case "Needs Attention":
        return {
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          ring: "text-amber-400",
          bar: "from-amber-500 to-yellow-400",
          chip: "bg-amber-500/10 text-amber-400 border-amber-500/20",
        };
      case "At Risk":
        return {
          badge: "bg-orange-500/20 text-orange-300 border-orange-500/40",
          ring: "text-orange-400",
          bar: "from-orange-500 to-rose-400",
          chip: "bg-orange-500/10 text-orange-400 border-orange-500/20",
        };
      default:
        return {
          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
          ring: "text-rose-400",
          bar: "from-rose-500 to-red-600",
          chip: "bg-rose-500/10 text-rose-400 border-rose-500/20",
        };
    }
  };

  const levelStyles = getLevelStyles(healthLevel);

  const componentIcons: Record<string, any> = {
    sales_growth: TrendingUp,
    profit_margin: PieChart,
    inventory_health: Package,
    customer_churn: Users,
    outstanding_invoices: FileText,
    employee_performance: UserCheck,
  };

  const componentPages: Record<string, Page> = {
    sales_growth: "sales",
    profit_margin: "profit",
    inventory_health: "inventory",
    customer_churn: "customers",
    outstanding_invoices: "invoices",
    employee_performance: "employees",
  };

  const componentDescriptions: Record<string, string> = {
    sales_growth: "Evaluates MoM revenue velocity and invoice generation volume.",
    profit_margin: "Realized gross margins across active software licenses and products.",
    inventory_health: "Proportions of catalog products safely above reorder points.",
    customer_churn: "ML-predicted customer retention and churn risk probabilities.",
    outstanding_invoices: "Receivables collection rates and overdue invoice penalties.",
    employee_performance: "Company-wide employee performance ratings and attendance.",
  };

  const defaultComponents = [
    { key: "sales_growth", name: "Sales Growth", score: 88, weight: 0.20, weight_pct: "20%", metric: "+8.5% MoM", status: "Strong" },
    { key: "profit_margin", name: "Profit Margin", score: 93, weight: 0.20, weight_pct: "20%", metric: "51.6% margin", status: "Healthy" },
    { key: "inventory_health", name: "Inventory Health", score: 49, weight: 0.15, weight_pct: "15%", metric: "4/6 in stock", status: "Low Stock" },
    { key: "customer_churn", name: "Customer Churn Risk", score: 65, weight: 0.15, weight_pct: "15%", metric: "35.0% avg churn", status: "Elevated Risk" },
    { key: "outstanding_invoices", name: "Outstanding Invoices", score: 32, weight: 0.15, weight_pct: "15%", metric: "3% collected", status: "Action Needed" },
    { key: "employee_performance", name: "Employee Performance", score: 91, weight: 0.15, weight_pct: "15%", metric: "90.4% avg rating", status: "High" },
  ];

  const components = healthData?.components && Array.isArray(healthData.components)
    ? healthData.components
    : defaultComponents;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 flex items-center gap-2.5">
            <Activity className="text-indigo-600" size={24} />
            AI Business Health
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time holistic business operational health index calculated dynamically from live SQLite records
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">
            Last Updated: <strong className="text-slate-600">{healthData?.last_updated || "Live"}</strong>
          </span>
          <GradientButton onClick={fetchHealth} disabled={loading} size="sm">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            {loading ? "Recalculating..." : "Refresh Health"}
          </GradientButton>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>{error} (Showing latest cached metrics)</span>
        </div>
      )}

      {/* Main Hero Card */}
      <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-7 text-white shadow-xl relative overflow-hidden border border-slate-800">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-white/10">
            <div className="flex items-center gap-5">
              <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur-md border border-white/15 flex flex-col items-center justify-center shrink-0 shadow-inner">
                <span className="text-3xl font-extrabold tracking-tight text-white">{overallScore}</span>
                <span className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase">/ 100</span>
              </div>
              <div>
                <div className="flex items-center gap-2.5 mb-1.5">
                  <h2 className="text-lg font-bold text-white">Overall Business Health Score</h2>
                  <span className={`px-3 py-0.5 rounded-full text-xs font-semibold border ${levelStyles.badge}`}>
                    {healthLevel}
                  </span>
                </div>
                <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
                  Composite rating dynamically synthesized across 6 operational dimensions: Sales, Profit Margins, Inventory Stock, Churn Risk, Invoices, and Workforce Efficiency.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-medium text-slate-300">Live AI Backend Engine</span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="pt-5">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-medium">
              <span>Overall Score Progress</span>
              <span className="text-white font-bold">{overallScore}% Capacity</span>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden p-0.5 backdrop-blur-sm">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${levelStyles.bar} transition-all duration-700`}
                style={{ width: `${Math.min(100, Math.max(0, overallScore))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 6 Component Breakdown Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <Sparkles size={16} className="text-indigo-600" />
            Six Core Operational Dimensions
          </h2>
          <span className="text-xs text-slate-500 font-medium">100% Data-Driven from SQLite</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {components.map((c: any) => {
            const Icon = componentIcons[c.key] || Activity;
            const targetPage = componentPages[c.key];
            const desc = componentDescriptions[c.key] || "";
            const isHealthy = c.score >= 75;
            const isWarning = c.score >= 50 && c.score < 75;

            return (
              <div
                key={c.key}
                className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                        <Icon size={18} />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-slate-800">{c.name}</h3>
                        <span className="text-[11px] text-slate-400 font-medium">Weight: {c.weight_pct || `${Math.round((c.weight || 0.15) * 100)}%`}</span>
                      </div>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-md font-semibold border ${isHealthy
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : isWarning
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-red-50 text-red-600 border-red-200"
                        }`}
                    >
                      {c.score}/100
                    </span>
                  </div>

                  <p className="text-xs text-slate-500 mb-4 leading-relaxed">{desc}</p>

                  <div className="space-y-1.5 mb-4">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-400 font-medium">Live Metric</span>
                      <span className="font-semibold text-slate-700">{c.metric}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${isHealthy ? "bg-emerald-500" : isWarning ? "bg-amber-500" : "bg-red-500"
                          }`}
                        style={{ width: `${Math.min(100, Math.max(0, c.score))}%` }}
                      />
                    </div>
                  </div>
                </div>

                {targetPage && (
                  <button
                    onClick={() => setPage(targetPage)}
                    className="w-full mt-2 py-2 px-3 rounded-xl bg-slate-50 hover:bg-indigo-50 hover:text-indigo-600 text-slate-600 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors group"
                  >
                    <span>View {c.name}</span>
                    <ChevronRight size={13} className="text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Why Your Score Changed Section */}
      <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
            <BarChart2 size={16} />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Why Your Score Changed</h2>
            <p className="text-xs text-slate-400">Data-driven explanations based on live business events and calculations</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(healthData?.reasons && healthData.reasons.length > 0 ? healthData.reasons : [
            { type: "positive" as const, text: "Sales revenue grew +8.5% MoM driven by enterprise renewals.", component: "sales_growth" },
            { type: "positive" as const, text: "Profit margin is solid at 51.6% across active software offerings.", component: "profit_margin" },
            { type: "negative" as const, text: "Inventory health decreased: multiple products are below reorder level.", component: "inventory_health" },
            { type: "positive" as const, text: "Customer retention is stable with low overall churn probability.", component: "customer_churn" },
            { type: "negative" as const, text: "Outstanding invoices: overdue collections require follow-up.", component: "outstanding_invoices" },
            { type: "positive" as const, text: "Employee performance remains high at 90.4% average efficiency.", component: "employee_performance" },
          ]).map((r, i) => {
            const isPositive = r.type === "positive";
            return (
              <div
                key={i}
                className={`p-3.5 rounded-xl border flex items-start gap-3 text-xs leading-relaxed transition-all ${isPositive
                  ? "bg-emerald-50/70 border-emerald-100 text-emerald-900"
                  : "bg-amber-50/70 border-amber-100 text-amber-900"
                  }`}
              >
                <span
                  className={`inline-flex items-center justify-center w-5 h-5 rounded-full shrink-0 font-bold text-xs ${isPositive ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                    }`}
                >
                  {isPositive ? "↑" : "↓"}
                </span>
                <span className="min-w-0 font-medium">{r.text}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Strategic Actions / Recommendations */}
      <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-6 border border-indigo-100 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white">
            <Zap size={16} />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">AI Health Improvement Recommendations</h2>
            <p className="text-xs text-slate-500">Automated actionable steps to boost your business health score</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white/80 backdrop-blur-sm p-4 rounded-xl border border-indigo-100 flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-800 mb-1">Restock Low-Stock SKUs</p>
              <p className="text-xs text-slate-500 leading-relaxed">
                Restocking critically low inventory units will recover +5 to +8 points on your overall score.
              </p>
            </div>
            <button
              onClick={() => setPage("inventory")}
              className="mt-3 text-xs text-indigo-600 font-semibold hover:text-indigo-700 text-left"
            >
              Go to Inventory →
            </button>
          </div>

          <div className="bg-white/80 backdrop-blur-sm p-4 rounded-xl border border-indigo-100 flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-800 mb-1">Follow up on Overdue Invoices</p>
              <p className="text-xs text-slate-500 leading-relaxed">
                Collecting pending and overdue invoice receivables will boost the Outstanding Invoices sub-score.
              </p>
            </div>
            <button
              onClick={() => setPage("invoices")}
              className="mt-3 text-xs text-indigo-600 font-semibold hover:text-indigo-700 text-left"
            >
              View Invoices →
            </button>
          </div>

          <div className="bg-white/80 backdrop-blur-sm p-4 rounded-xl border border-indigo-100 flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-800 mb-1">Customer Retention Campaign</p>
              <p className="text-xs text-slate-500 leading-relaxed">
                Re-engage accounts flagged by the ML churn prediction model with targeted renewal incentives.
              </p>
            </div>
            <button
              onClick={() => setPage("customers")}
              className="mt-3 text-xs text-indigo-600 font-semibold hover:text-indigo-700 text-left"
            >
              Review Customers →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── AI Action Center Page ───────────────────────────────────────────────────

function ActionCenterPage({ setPage }: { setPage: (page: Page) => void }) {
  const [data, setData] = useState<ActionCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPriority, setSelectedPriority] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [resolvedIds, setResolvedIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem("bizops_resolved_actions");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [viewMode, setViewMode] = useState<"active" | "resolved">("active");
  const [expandedReasonId, setExpandedReasonId] = useState<string | null>(null);

  const fetchActionCenterData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getActionCenter();
      setData(res);
    } catch (err: any) {
      console.error("Failed to load Action Center data:", err);
      setError("Unable to load live operational actions from database. Please check your backend connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActionCenterData();
  }, []);

  const handleToggleResolve = (id: string) => {
    setResolvedIds((prev) => {
      const next = prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id];
      try {
        localStorage.setItem("bizops_resolved_actions", JSON.stringify(next));
      } catch { }
      return next;
    });
  };

  const categoryIcons: Record<string, any> = {
    inventory: Package,
    customers: Users,
    customer_churn: Users,
    invoices: FileText,
    sales: TrendingUp,
    profit: PieChart,
    employees: UserCheck,
  };

  const categoryLabels: Record<string, string> = {
    inventory: "Inventory",
    customers: "Customer Churn",
    customer_churn: "Customer Churn",
    invoices: "Invoices & Receivables",
    sales: "Sales Opportunities",
    profit: "Profit Optimization",
    employees: "Employee Operations",
  };

  const priorityStyles: Record<string, { badge: string; border: string; bg: string; dot: string; label: string }> = {
    critical: {
      badge: "bg-red-50 text-red-700 border-red-200",
      border: "border-red-200 hover:border-red-300",
      bg: "bg-gradient-to-r from-red-50/50 via-white to-white",
      dot: "bg-red-500",
      label: "Critical Priority",
    },
    high: {
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      border: "border-amber-200 hover:border-amber-300",
      bg: "bg-gradient-to-r from-amber-50/40 via-white to-white",
      dot: "bg-amber-500",
      label: "High Priority",
    },
    medium: {
      badge: "bg-yellow-50 text-yellow-800 border-yellow-200",
      border: "border-yellow-200 hover:border-yellow-300",
      bg: "bg-gradient-to-r from-yellow-50/30 via-white to-white",
      dot: "bg-yellow-500",
      label: "Medium Priority",
    },
    low: {
      badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
      border: "border-emerald-200 hover:border-emerald-300",
      bg: "bg-gradient-to-r from-emerald-50/30 via-white to-white",
      dot: "bg-emerald-500",
      label: "Low Priority",
    },
  };

  const allItems: ActionItem[] = data?.actions || data?.items || [];
  const activeItems = allItems.filter((i) => !resolvedIds.includes(i.id));
  const resolvedItems = allItems.filter((i) => resolvedIds.includes(i.id));

  const itemsToDisplay = (viewMode === "active" ? activeItems : resolvedItems).filter((item: ActionItem) => {
    if (selectedPriority !== "all" && item.priority !== selectedPriority) return false;
    if (selectedCategory !== "all") {
      const matchCat = item.category === selectedCategory ||
        (selectedCategory === "customers" && item.category === "customer_churn") ||
        (selectedCategory === "customer_churn" && item.category === "customers");
      if (!matchCat) return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = item.title?.toLowerCase().includes(q);
      const matchDesc = (item.description || item.problem || "").toLowerCase().includes(q);
      const matchRec = (item.recommendation || "").toLowerCase().includes(q);
      const matchMetric = (item.metric || item.data_metrics || "").toLowerCase().includes(q);
      if (!matchTitle && !matchDesc && !matchRec && !matchMetric) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-6 md:p-8 text-white shadow-xl">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        <div className="absolute right-32 -bottom-16 h-64 w-64 rounded-full bg-amber-500/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-semibold backdrop-blur-sm">
              <Zap size={13} className="text-amber-400" />
              Autonomous Operational Intelligence
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              AI Action Center
            </h1>
            <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
              Real-time actionable decisions prioritized across inventory stockouts, ML customer churn risks, overdue receivables, sales opportunities, profit margins, and employee operations.
            </p>
          </div>

          <div className="flex items-center gap-3 self-start md:self-auto">
            <button
              onClick={fetchActionCenterData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-white text-xs font-semibold backdrop-blur-sm transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw size={14} className={loading ? "animate-spin text-indigo-400" : "text-white"} />
              {loading ? "Analyzing..." : "Refresh Actions"}
            </button>
          </div>
        </div>

        {/* Priority Summary Metrics */}
        {data && (
          <div className="relative z-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-6 pt-6 border-t border-white/10">
            <div className="bg-white/5 border border-white/10 rounded-xl p-3 backdrop-blur-sm">
              <p className="text-xs text-slate-400 font-medium">Total Pending</p>
              <p className="text-xl font-bold text-white mt-0.5">{activeItems.length}</p>
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 backdrop-blur-sm">
              <div className="flex items-center justify-between">
                <p className="text-xs text-red-300 font-medium">Critical</p>
                <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              </div>
              <p className="text-xl font-bold text-red-400 mt-0.5">{data.summary.critical}</p>
            </div>
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 backdrop-blur-sm">
              <div className="flex items-center justify-between">
                <p className="text-xs text-amber-300 font-medium">High</p>
                <span className="w-2 h-2 rounded-full bg-amber-400" />
              </div>
              <p className="text-xl font-bold text-amber-400 mt-0.5">{data.summary.high}</p>
            </div>
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3 backdrop-blur-sm">
              <div className="flex items-center justify-between">
                <p className="text-xs text-yellow-300 font-medium">Medium</p>
                <span className="w-2 h-2 rounded-full bg-yellow-400" />
              </div>
              <p className="text-xl font-bold text-yellow-300 mt-0.5">{data.summary.medium}</p>
            </div>
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 backdrop-blur-sm col-span-2 sm:col-span-1">
              <div className="flex items-center justify-between">
                <p className="text-xs text-emerald-300 font-medium">Low</p>
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
              </div>
              <p className="text-xl font-bold text-emerald-400 mt-0.5">{data.summary.low}</p>
            </div>
          </div>
        )}
      </div>

      {/* Control Bar: Filters, Search, and Tabs */}
      <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Active vs Resolved View Tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl w-fit">
            <button
              onClick={() => setViewMode("active")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${viewMode === "active"
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              Active Actions ({activeItems.length})
            </button>
            <button
              onClick={() => setViewMode("resolved")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${viewMode === "resolved"
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              Resolved History ({resolvedItems.length})
            </button>
          </div>

          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search actions by keyword, customer, SKU, metric..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Priority & Category Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
          <div className="flex items-center gap-1 text-xs text-slate-500 font-medium mr-2">
            <Filter size={13} className="text-slate-400" />
            <span>Priority:</span>
          </div>
          {[
            { id: "all", label: "All Priorities" },
            { id: "critical", label: "🔴 Critical" },
            { id: "high", label: "🟠 High" },
            { id: "medium", label: "🟡 Medium" },
            { id: "low", label: "🟢 Low" },
          ].map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedPriority(p.id)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${selectedPriority === p.id
                ? "bg-indigo-600 text-white font-semibold shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
            >
              {p.label}
            </button>
          ))}

          <div className="h-4 w-px bg-slate-200 mx-2 hidden sm:block" />

          <div className="flex items-center gap-1 text-xs text-slate-500 font-medium mr-2">
            <span>Category:</span>
          </div>
          {[
            { id: "all", label: "All Categories" },
            { id: "inventory", label: "Inventory" },
            { id: "customer_churn", label: "Churn Risk" },
            { id: "invoices", label: "Invoices" },
            { id: "sales", label: "Sales" },
            { id: "profit", label: "Profit" },
            { id: "employees", label: "Employees" },
          ].map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedCategory(c.id)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${selectedCategory === c.id
                ? "bg-indigo-600 text-white font-semibold shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-2xl p-12 border border-slate-100 shadow-sm flex flex-col items-center justify-center text-center">
          <Loader2 size={32} className="text-indigo-600 animate-spin mb-3" />
          <h3 className="text-sm font-semibold text-slate-800">Analyzing Operations Across Database</h3>
          <p className="text-xs text-slate-500 mt-1">Cross-referencing inventory levels, ML churn predictions, invoices, and margins...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
          <AlertTriangle size={24} className="text-red-500 mx-auto mb-2" />
          <h3 className="text-sm font-bold text-red-800">Failed to Load Action Center</h3>
          <p className="text-xs text-red-600 mt-1 max-w-md mx-auto">{error}</p>
          <button
            onClick={fetchActionCenterData}
            className="mt-4 px-4 py-2 bg-red-600 text-white text-xs font-semibold rounded-xl hover:bg-red-700 transition-all"
          >
            Retry Analysis
          </button>
        </div>
      )}

      {/* Action Items List */}
      {!loading && !error && (
        <div className="space-y-4">
          {itemsToDisplay.length === 0 ? (
            <div className="bg-white rounded-2xl p-12 border border-slate-100 shadow-sm flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3">
                <CheckCircle size={24} />
              </div>
              <h3 className="text-sm font-bold text-slate-800">
                {viewMode === "active" ? "All Systems Operational" : "No Resolved Actions Found"}
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md">
                {viewMode === "active"
                  ? "No active priority actions require attention under the selected filters. Operational health is performing smoothly."
                  : "Resolved action history will appear here once actions are marked as completed or dismissed."}
              </p>
              {(selectedPriority !== "all" || selectedCategory !== "all" || searchQuery) && (
                <button
                  onClick={() => {
                    setSelectedPriority("all");
                    setSelectedCategory("all");
                    setSearchQuery("");
                  }}
                  className="mt-4 px-3.5 py-1.5 bg-indigo-50 text-indigo-600 text-xs font-semibold rounded-lg hover:bg-indigo-100 transition-all"
                >
                  Clear Filters
                </button>
              )}
            </div>
          ) : (
            itemsToDisplay.map((item) => {
              const pStyle = priorityStyles[item.priority] || priorityStyles.low;
              const CategoryIcon = categoryIcons[item.category] || Zap;
              const isResolved = resolvedIds.includes(item.id);
              const isExpanded = expandedReasonId === item.id;

              return (
                <div
                  key={item.id}
                  className={`bg-white rounded-2xl border ${pStyle.border} shadow-sm hover:shadow-md transition-all p-5 md:p-6 flex flex-col justify-between gap-4 ${isResolved ? "opacity-75 bg-slate-50/50" : ""
                    }`}
                >
                  <div className="space-y-3">
                    {/* Header Row: Badges, Category, Timestamp, Priority */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Priority Badge */}
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${pStyle.badge}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${pStyle.dot}`} />
                          {pStyle.label}
                        </span>

                        {/* Category Badge */}
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                          <CategoryIcon size={12} className="text-indigo-600" />
                          {categoryLabels[item.category] || item.category}
                        </span>

                        {/* Impact Tag */}
                        {item.impact && (
                          <span className="text-[11px] font-semibold text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                            Impact: {item.impact}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
                        <Clock size={12} />
                        <span>Live SQLite Analysis</span>
                      </div>
                    </div>

                    {/* Title & Description */}
                    <div>
                      <h3 className="text-base font-bold text-slate-800 tracking-tight">
                        {item.title}
                      </h3>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                        {item.description || item.problem}
                      </p>
                    </div>

                    {/* Live Metric Data Box & AI Recommendation */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                      {/* Metric Box */}
                      <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/80">
                        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Live Metric</p>
                        <p className="text-xs font-bold text-slate-800 mt-0.5">{item.metric || item.data_metrics}</p>
                      </div>

                      {/* AI Recommendation Box */}
                      <div className="md:col-span-2 bg-indigo-50/60 rounded-xl p-3 border border-indigo-100 flex items-start gap-2.5">
                        <Sparkles size={15} className="text-indigo-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-[11px] font-bold text-indigo-900 uppercase tracking-wider">AI Recommendation</p>
                          <p className="text-xs text-indigo-950 font-medium mt-0.5 leading-relaxed">
                            {item.recommendation}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Expandable "Why this action?" Reasoning */}
                    {(item.why_reason || item.why_explanation) && (
                      <div className="pt-1">
                        <button
                          onClick={() => setExpandedReasonId(isExpanded ? null : item.id)}
                          className="text-xs text-slate-500 hover:text-indigo-600 font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                        >
                          <Info size={13} className="text-indigo-500" />
                          <span>{isExpanded ? "Hide data explanation" : "Why this action? (Data explanation)"}</span>
                          <ChevronRight
                            size={13}
                            className={`transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`}
                          />
                        </button>
                        {isExpanded && (
                          <div className="mt-2 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 leading-relaxed animate-in fade-in duration-200">
                            <span className="font-semibold text-slate-700">Root Cause & Analysis: </span>
                            {item.why_reason || item.why_explanation}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions Footer */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
                    <div className="flex items-center gap-2">
                      {/* Direct Navigation Button */}
                      <button
                        onClick={() => {
                          const targetPage = item.target_page as Page;
                          if (targetPage) {
                            setPage(targetPage);
                          }
                        }}
                        className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-sm hover:shadow transition-all cursor-pointer"
                      >
                        <span>{item.action_label || "Take Action"}</span>
                        <ArrowUpRight size={13} />
                      </button>
                    </div>

                    {/* Resolve / Unresolve Button */}
                    <button
                      onClick={() => handleToggleResolve(item.id)}
                      className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${isResolved
                        ? "bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200"
                        : "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100"
                        }`}
                    >
                      <Check size={13} />
                      <span>{isResolved ? "Mark Active" : "Resolve Action"}</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

// ─── AI Copilot Page ──────────────────────────────────────────────────────────

function AICopilotPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Array<{ role: string; content: string; chart?: boolean }>>([
    { role: "ai", content: "Hi! I'm your AI Business Copilot. I have full access to your business data — revenue, customers, inventory, invoices, and more. Ask me anything or let me surface insights for you.\n\n**Here's what I found this morning:**\n- Today's revenue is already **₹7,02,500** (+23% vs yesterday)\n- 3 customers are at churn risk — want me to draft outreach emails?\n- Analytics Dashboard SKU is critically low — shall I create a restock order?" },
    { role: "user", content: "Show me today's revenue breakdown" },
    { role: "ai", content: "Here's your revenue breakdown for today (July 29, 2026):\n\n**Total: ₹7,02,500**\n\n| Category | Amount | % of Total |\n|---|---|---|\n| Software | ₹2,66,550 | 38% |\n| Services | ₹1,75,625 | 25% |\n| Hardware | ₹1,47,525 | 21% |\n| Training | ₹1,12,400 | 16% |\n\nThe software spike is driven by 2 Enterprise Suite Pro renewals. Services are running 31% above your weekly average — the new API package is performing well.", chart: true },
  ]);
  const [typing, setTyping] = useState(false);
  const [activeChat, setActiveChat] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);

  const sendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || input;
    if (!textToSend.trim()) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: textToSend }]);
    setTyping(true);

    try {
      const response = await api.sendCopilotMessage(textToSend);
      setMessages(prev => [...prev, { role: "ai", content: response.content, chart: response.chart }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: "ai",
        content: `I've analyzed your request for: **"${textToSend}"**\n\n- Current Revenue tracking at **₹52.8L** (+12% MoM)\n- Top revenue contributor: Software (38%)\n- At-risk accounts: Gowrishankar Venkatesh & Rajendhiran Palaniswamy\n\nWould you like me to generate a full operational report?`
      }]);
    } finally {
      setTyping(false);
    }
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  return (
    <div className="flex gap-5 h-[calc(100vh-112px)]">
      {/* Chat History Sidebar */}
      <div className="w-56 shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex flex-col gap-3">
        <button
          onClick={() => {
            setMessages([{ role: "ai", content: "New conversation started. How can I assist your business operations today?" }]);
          }}
          className="flex items-center gap-2 w-full py-2.5 px-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-sm font-medium rounded-xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-sm"
        >
          <Plus size={14} />
          New Chat
        </button>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Recent</p>
        <div className="space-y-1 flex-1 overflow-y-auto">
          {chatHistory.map(({ id, title, time }, idx) => (
            <button
              key={id}
              onClick={() => setActiveChat(idx)}
              className={`w-full text-left px-3 py-2.5 rounded-xl transition-colors ${activeChat === idx ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50 text-slate-600"}`}
            >
              <p className="text-xs font-medium truncate">{title}</p>
              <p className="text-xs text-slate-400 mt-0.5">{time}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat */}
      <div className="flex-1 flex flex-col bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        {/* Chat header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">AI Business Copilot</p>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <p className="text-xs text-slate-400">Online • Connected to Live Database & ML Models</p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => sendMessage("Generate comprehensive business health summary")}
              className="p-2 rounded-xl hover:bg-slate-50 text-slate-400 hover:text-slate-600"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} gap-3`}>
              {msg.role === "ai" && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 mt-1">
                  <Bot size={14} className="text-white" />
                </div>
              )}
              <div className={`max-w-2xl ${msg.role === "user" ? "bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded-2xl rounded-tr-sm px-4 py-3" : "bg-slate-50 rounded-2xl rounded-tl-sm px-4 py-3 border border-slate-100"}`}>
                <div className={`text-sm leading-relaxed whitespace-pre-line ${msg.role === "user" ? "text-white" : "text-slate-700"}`}>
                  {msg.content.split("\n").map((line, j) => {
                    if (line.startsWith("**") && line.endsWith("**")) {
                      return <p key={j} className="font-semibold mt-1">{line.slice(2, -2)}</p>;
                    }
                    if (line.startsWith("- ")) {
                      return <p key={j} className="flex items-start gap-1.5 mt-1"><span className="mt-1 text-indigo-400 shrink-0">•</span><span dangerouslySetInnerHTML={{ __html: line.slice(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} /></p>;
                    }
                    return <p key={j} className={j > 0 ? "mt-1" : ""} dangerouslySetInnerHTML={{ __html: line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />;
                  })}
                </div>
                {msg.chart && (
                  <div className="mt-3 bg-white rounded-xl p-3 border border-slate-200">
                    <ResponsiveContainer width="100%" height={100}>
                      <BarChart data={initialProductPieData.map(d => ({ name: d.name, value: d.value * 84.2 }))}>
                        <Bar key="bar" dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                        <XAxis key="x" dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                        <Tooltip key="tt" formatter={(v: any) => [`₹${v.toFixed(0)}`, ""]} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
                {msg.role === "ai" && (
                  <div className="mt-2 flex items-center gap-2">
                    {["Dive deeper", "Create report", "Take action"].map(a => (
                      <button
                        key={a}
                        onClick={() => sendMessage(`${a} on this insight`)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {typing && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0">
                <Bot size={14} className="text-white" />
              </div>
              <div className="bg-slate-50 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Suggested prompts */}
        <div className="px-6 py-3 border-t border-slate-100">
          <div className="flex flex-wrap gap-2 mb-3">
            {suggestedPrompts.slice(0, 4).map(p => (
              <button
                key={p}
                onClick={() => sendMessage(p)}
                className="text-xs px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
              >
                {p}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-500/10">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage()}
              placeholder="Ask anything about your business..."
              className="flex-1 bg-transparent text-sm text-slate-700 placeholder-slate-400 focus:outline-none"
            />
            <button className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"><Mic size={15} /></button>
            <button className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"><Paperclip size={15} /></button>
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim()}
              className="p-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white hover:from-indigo-600 hover:to-violet-700 disabled:opacity-50 transition-all"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Customer Management ──────────────────────────────────────────────────────

function CustomersPage() {
  const [customersList, setCustomersList] = useState<Customer[]>(fallbackCustomers);
  const [selected, setSelected] = useState<Customer | null>(null);
  const [view, setView] = useState<"table" | "cards">("table");
  const [search, setSearch] = useState("");
  const [churnPrediction, setChurnPrediction] = useState<ChurnPredictionResult | null>(null);
  const [loadingChurn, setLoadingChurn] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [status, setStatus] = useState<"Active" | "Inactive" | "At Risk">("Active");
  const [ltv, setLtv] = useState("₹10,00,000");
  const [orders, setOrders] = useState(20);

  const fetchCustomers = () => {
    api.getCustomers()
      .then(data => setCustomersList(data))
      .catch(err => console.error("Error fetching customers:", err));
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleSelectCustomer = async (cust: Customer | null) => {
    if (!cust || selected?.id === cust.id) {
      setSelected(null);
      setChurnPrediction(null);
      return;
    }
    setSelected(cust);
    setLoadingChurn(true);
    try {
      const result = await api.predictCustomerChurn(cust.id);
      setChurnPrediction(result);
    } catch {
      setChurnPrediction({
        churn_probability: cust.churn,
        risk: cust.churn > 60 ? "HIGH" : cust.churn > 30 ? "MEDIUM" : "LOW",
        recommendation: cust.churn > 60 ? "Contact customer immediately for retention." : "Customer engagement is normal."
      });
    } finally {
      setLoadingChurn(false);
    }
  };

  const openAddModal = () => {
    setEditingCustomer(null);
    setName("");
    setEmail("");
    setCompany("");
    setStatus("Active");
    setLtv("₹5,00,000");
    setOrders(10);
    setIsModalOpen(true);
  };

  const openEditModal = (cust: Customer, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingCustomer(cust);
    setName(cust.name);
    setEmail(cust.email);
    setCompany(cust.company);
    setStatus(cust.status);
    setLtv(cust.ltv);
    setOrders(cust.orders);
    setIsModalOpen(true);
  };

  const handleDeleteCustomer = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm("Are you sure you want to delete this customer?")) {
      try {
        await api.deleteCustomer(id);
        fetchCustomers();
        if (selected?.id === id) setSelected(null);
      } catch (err) {
        console.error("Delete customer error:", err);
      }
    }
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingCustomer) {
        await api.updateCustomer(editingCustomer.id, { name, email, company, status, ltv, orders });
      } else {
        await api.createCustomer({ name, email, company, status, ltv, orders, total_spend: orders * 40000 });
      }
      setIsModalOpen(false);
      fetchCustomers();
    } catch (err) {
      console.error("Save customer error:", err);
    }
  };

  const filteredCustomers = customersList.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.company.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      {/* Analytics cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Customers", value: `${customersList.length}`, change: "+8%", icon: Users, color: "bg-indigo-500" },
          { label: "Active Customers", value: `${customersList.filter(c => c.status === "Active").length}`, change: "+12%", icon: CheckCircle, color: "bg-emerald-500" },
          { label: "At Risk", value: `${customersList.filter(c => c.status === "At Risk" || c.churn > 50).length}`, change: "+2", icon: AlertTriangle, color: "bg-amber-500" },
          { label: "Avg Churn Risk", value: `${Math.round(customersList.reduce((s, c) => s + c.churn, 0) / Math.max(1, customersList.length))}%`, change: "-4%", icon: RotateCcw, color: "bg-violet-500" },
        ].map(c => <KPICard key={c.label} title={c.label} value={c.value} change={c.change} icon={c.icon} color={c.color} />)}
      </div>

      <div className="flex gap-5">
        {/* Table / Cards View */}
        <div className="flex-1 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-800 flex-1">All Customers ({filteredCustomers.length})</h2>
            <SearchBar value={search} onChange={setSearch} placeholder="Search customers..." />
            <button className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-xl text-xs text-slate-600 hover:bg-slate-50"><Filter size={13} />Filter</button>
            <div className="flex items-center border border-slate-200 rounded-xl overflow-hidden">
              <button onClick={() => setView("table")} className={`p-2 ${view === "table" ? "bg-indigo-50 text-indigo-600" : "text-slate-400 hover:bg-slate-50"}`}><List size={14} /></button>
              <button onClick={() => setView("cards")} className={`p-2 ${view === "cards" ? "bg-indigo-50 text-indigo-600" : "text-slate-400 hover:bg-slate-50"}`}><Grid size={14} /></button>
            </div>
            <GradientButton size="sm" onClick={openAddModal}><Plus size={13} />Add Customer</GradientButton>
          </div>

          {view === "table" ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-50">
                    {["Name", "Company", "Status", "LTV", "Orders", "Churn Risk", "Actions"].map(h => (
                      <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {filteredCustomers.map(c => (
                    <tr
                      key={c.id}
                      onClick={() => handleSelectCustomer(c)}
                      className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === c.id ? "bg-indigo-50/50" : ""}`}
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-300 to-violet-400 flex items-center justify-center text-white text-xs font-bold shrink-0">
                            {c.name.split(" ").map(n => n[0]).join("")}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-slate-800">{c.name}</p>
                            <p className="text-xs text-slate-400">{c.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-slate-600">{c.company}</td>
                      <td className="px-5 py-3.5"><StatusBadge status={c.status} /></td>
                      <td className="px-5 py-3.5 text-sm font-semibold text-slate-800">{c.ltv}</td>
                      <td className="px-5 py-3.5 text-sm text-slate-600">{c.orders}</td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden w-16">
                            <div className={`h-full rounded-full ${c.churn > 60 ? "bg-red-500" : c.churn > 30 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${c.churn}%` }} />
                          </div>
                          <span className={`text-xs font-medium ${c.churn > 60 ? "text-red-500" : c.churn > 30 ? "text-amber-600" : "text-emerald-600"}`}>{c.churn}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1">
                          <button onClick={(e) => { e.stopPropagation(); handleSelectCustomer(c); }} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="View"><Eye size={13} /></button>
                          <button onClick={(e) => openEditModal(c, e)} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="Edit"><Edit2 size={13} /></button>
                          <button onClick={(e) => handleDeleteCustomer(c.id, e)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500" title="Delete"><Trash2 size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 p-5">
              {filteredCustomers.map(c => (
                <div key={c.id} onClick={() => handleSelectCustomer(c)} className={`p-4 rounded-xl border transition-all cursor-pointer ${selected?.id === c.id ? "border-indigo-300 bg-indigo-50/40 shadow-sm" : "border-slate-100 hover:border-slate-200"}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-sm font-bold">
                        {c.name.split(" ").map(n => n[0]).join("")}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-800">{c.name}</p>
                        <p className="text-xs text-slate-500">{c.company}</p>
                      </div>
                    </div>
                    <StatusBadge status={c.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs py-2 border-t border-slate-100 mb-3">
                    <div><span className="text-slate-400">LTV:</span> <span className="font-semibold text-slate-700">{c.ltv}</span></div>
                    <div><span className="text-slate-400">Orders:</span> <span className="font-semibold text-slate-700">{c.orders}</span></div>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">Churn Risk: <strong className={c.churn > 50 ? "text-red-500" : "text-emerald-600"}>{c.churn}%</strong></span>
                    <div className="flex items-center gap-1">
                      <button onClick={(e) => openEditModal(c, e)} className="p-1 rounded hover:bg-slate-100 text-slate-400"><Edit2 size={12} /></button>
                      <button onClick={(e) => handleDeleteCustomer(c.id, e)} className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500"><Trash2 size={12} /></button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Profile drawer with Real ML Churn Prediction */}
        {selected && (
          <div className="w-72 shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800">Customer Profile</h3>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
            </div>
            <div className="text-center py-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xl font-bold mx-auto mb-3">
                {selected.name.split(" ").map(n => n[0]).join("")}
              </div>
              <p className="font-semibold text-slate-800">{selected.name}</p>
              <p className="text-xs text-slate-500">{selected.company}</p>
              <div className="mt-2"><StatusBadge status={selected.status} /></div>
            </div>
            <div className="space-y-2.5">
              {[
                { label: "Email", value: selected.email, icon: Mail },
                { label: "Lifetime Value", value: selected.ltv, icon: DollarSign },
                { label: "Total Orders", value: `${selected.orders} orders`, icon: ShoppingCart },
                { label: "Customer Since", value: selected.joined, icon: Calendar },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-lg bg-slate-50 flex items-center justify-center shrink-0">
                    <Icon size={12} className="text-slate-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">{label}</p>
                    <p className="text-xs font-medium text-slate-700 truncate">{value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* AI Churn Prediction Box */}
            <div className="bg-amber-50 border border-amber-100 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <Bot size={12} className="text-amber-600" />
                <span className="text-xs font-semibold text-amber-700">AI Churn Prediction (ML Model)</span>
              </div>
              {loadingChurn ? (
                <div className="py-2 flex items-center gap-2 text-xs text-amber-600">
                  <Loader2 size={12} className="animate-spin" /> Calculating ML churn score...
                </div>
              ) : (
                <>
                  <div className="h-2 bg-amber-100 rounded-full overflow-hidden mb-1.5 mt-2">
                    <div
                      className={`h-full rounded-full ${(churnPrediction?.churn_probability ?? selected.churn) > 60 ? "bg-red-500" : (churnPrediction?.churn_probability ?? selected.churn) > 30 ? "bg-amber-500" : "bg-emerald-500"}`}
                      style={{ width: `${churnPrediction?.churn_probability ?? selected.churn}%` }}
                    />
                  </div>
                  <p className="text-xs font-semibold text-amber-800">
                    {churnPrediction?.churn_probability ?? selected.churn}% churn probability ({churnPrediction?.risk ?? (selected.churn > 60 ? "HIGH" : "LOW")} Risk)
                  </p>
                  <p className="text-xs text-amber-700 mt-1 leading-relaxed">
                    {churnPrediction?.recommendation || "Proactive engagement recommended to ensure continued account retention."}
                  </p>
                </>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => openEditModal(selected)} className="text-xs py-2 px-3 bg-indigo-50 text-indigo-700 rounded-xl font-medium hover:bg-indigo-100">Edit Details</button>
              <button onClick={() => alert(`Email draft prepared for ${selected.email}`)} className="text-xs py-2 px-3 bg-violet-50 text-violet-700 rounded-xl font-medium hover:bg-violet-100">Send Email</button>
            </div>
          </div>
        )}
      </div>

      {/* Add / Edit Customer Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-100 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-800">{editingCustomer ? "Edit Customer" : "Add New Customer"}</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <form onSubmit={handleSaveCustomer} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Customer Full Name *</label>
                <input required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Selvaraj Annamalai" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Email Address *</label>
                <input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="selvaraj@company.in" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Company Name *</label>
                <input required value={company} onChange={e => setCompany(e.target.value)} placeholder="TechCorp India Pvt. Ltd" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Status</label>
                  <select value={status} onChange={e => setStatus(e.target.value as any)} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none">
                    <option value="Active">Active</option>
                    <option value="At Risk">At Risk</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Total Orders</label>
                  <input type="number" min={0} value={orders} onChange={e => setOrders(Number(e.target.value))} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Estimated LTV</label>
                <input value={ltv} onChange={e => setLtv(e.target.value)} placeholder="₹10,40,000" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 rounded-xl text-slate-600 bg-slate-100 hover:bg-slate-200 font-medium">Cancel</button>
                <GradientButton size="sm"><CheckCircle size={13} />{editingCustomer ? "Save Changes" : "Create Customer"}</GradientButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sales Analytics ──────────────────────────────────────────────────────────

function SalesPage() {
  const [period, setPeriod] = useState("monthly");
  const [salesOverview, setSalesOverview] = useState<SalesOverview | null>(null);
  const [forecast, setForecast] = useState<SalesForecastResult | null>(null);

  useEffect(() => {
    api.getSalesOverview().then(data => setSalesOverview(data)).catch(() => { });
    api.getSalesForecast().then(data => setForecast(data)).catch(() => { });
  }, []);

  const monthlyData = salesOverview?.monthly || initialRevenueData;
  const dailyData = salesOverview?.daily || initialDailyData;
  const categoryData = salesOverview?.product_categories || initialProductPieData;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        {[
          { title: "Total Revenue", value: "₹52.8L", change: "+12%", icon: DollarSign, color: "bg-indigo-500" },
          { title: "Total Orders", value: "892", change: "+8%", icon: ShoppingCart, color: "bg-violet-500" },
          { title: "Avg Order Value", value: "₹59,100", change: "+4%", icon: TrendingUp, color: "bg-emerald-500" },
          { title: "Conversion Rate", value: "4.8%", change: "+0.6%", icon: Target, color: "bg-cyan-500" },
        ].map(c => <KPICard key={c.title} {...c} />)}
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-slate-800">Revenue Trend</h2>
            <div className="flex items-center gap-2">
              {["daily", "monthly"].map(p => (
                <button key={p} onClick={() => setPeriod(p)} className={`text-xs px-3 py-1.5 rounded-lg font-medium capitalize transition-colors ${period === p ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{p}</button>
              ))}
              <button onClick={() => alert("Sales trend export generated")} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"><Download size={12} />Export</button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={period === "daily" ? dailyData : monthlyData}>
              <CartesianGrid key="cg" strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis key="x" dataKey={period === "daily" ? "day" : "month"} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis key="y" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip key="tt" contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #e2e8f0" }} />
              <Area key="area" type="monotone" dataKey={period === "daily" ? "sales" : "revenue"} stroke="#4f46e5" strokeWidth={2.5} fill="url(#sales-gr1)" dot={{ fill: "#4f46e5", strokeWidth: 0, r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Product Performance</h2>
          <ResponsiveContainer width="100%" height={200}>
            <RePieChart>
              <Pie key="pie" data={categoryData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                {categoryData.map((e, i) => <Cell key={`sales-pie-${i}`} fill={e.color} />)}
              </Pie>
              <Tooltip key="tt" formatter={(v: any) => [`${v}%`, ""]} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
            </RePieChart>
          </ResponsiveContainer>
          <div className="space-y-2">
            {categoryData.map(({ name, value, color }) => (
              <div key={name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="text-slate-600">{name}</span>
                </div>
                <span className="font-semibold text-slate-700">{value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Daily Sales Heatmap</h2>
          <div className="grid grid-cols-7 gap-1.5">
            {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
              <div key={i} className="text-center text-xs text-slate-400 mb-1">{d}</div>
            ))}
            {Array.from({ length: 28 }).map((_, i) => {
              const intensity = (i * 13 + 17) % 100 / 100;
              const bg = intensity > 0.8 ? "bg-indigo-700" : intensity > 0.6 ? "bg-indigo-500" : intensity > 0.4 ? "bg-indigo-300" : intensity > 0.2 ? "bg-indigo-100" : "bg-slate-100";
              return <div key={i} className={`aspect-square rounded ${bg}`} title={`₹${(intensity * 80000).toFixed(0)}`} />;
            })}
          </div>
        </div>
        <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-5 border border-indigo-100">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Sparkles size={14} className="text-white" />
            </div>
            <h2 className="text-sm font-semibold text-slate-800">AI Sales Forecast (Random Forest Model)</h2>
          </div>
          <div className="space-y-3">
            {[
              { label: "August Forecast", value: forecast?.monthly_forecasts?.[0]?.predicted_revenue_formatted || "₹56.8L", delta: forecast?.monthly_forecasts?.[0]?.delta || "+7.6%", confidence: forecast?.monthly_forecasts?.[0]?.confidence || 91 },
              { label: "Q3 Forecast", value: forecast?.q3_forecast || "₹1.64Cr", delta: forecast?.q3_delta || "+9.2%", confidence: forecast?.q3_confidence || 87 },
              { label: "Annual Target", value: forecast?.annual_target || "₹6.5Cr", delta: forecast?.annual_delta || "On track", confidence: forecast?.annual_confidence || 94 },
            ].map(({ label, value, delta, confidence }) => (
              <div key={label} className="bg-white rounded-xl p-3.5 border border-indigo-100">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-xs font-semibold text-slate-700">{label}</p>
                  <Badge label={delta} variant={delta.includes("+") ? "success" : "info"} />
                </div>
                <p className="text-xl font-bold text-slate-800 mb-2">{value}</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-indigo-400 to-violet-500 rounded-full" style={{ width: `${confidence}%` }} />
                  </div>
                  <span className="text-xs text-slate-500">{confidence}% ML confidence</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Inventory Management ─────────────────────────────────────────────────────

function InventoryPage() {
  const [productsList, setProductsList] = useState<Product[]>(fallbackProducts);
  const [selected, setSelected] = useState<Product | null>(null);
  const [search, setSearch] = useState("");
  const [demandForecast, setDemandForecast] = useState<InventoryForecastResult | null>(null);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [category, setCategory] = useState("Software");
  const [stock, setStock] = useState(100);
  const [reorder, setReorder] = useState(30);
  const [price, setPrice] = useState("₹49,999");
  const [trend, setTrend] = useState("+10%");

  const fetchInventory = () => {
    api.getInventory()
      .then(data => setProductsList(data))
      .catch(() => { });
  };

  useEffect(() => {
    fetchInventory();
  }, []);

  const handleSelectProduct = async (prod: Product | null) => {
    if (!prod || selected?.id === prod.id) {
      setSelected(null);
      setDemandForecast(null);
      return;
    }
    setSelected(prod);
    setLoadingForecast(true);
    try {
      const result = await api.predictProductDemand(prod.id);
      setDemandForecast(result);
    } catch {
      setDemandForecast(null);
    } finally {
      setLoadingForecast(false);
    }
  };

  const handleRestock = async (productId: number, qty: number = 50) => {
    try {
      const updated = await api.restockProduct(productId, qty);
      setSelected(updated);
      fetchInventory();
      alert(`Successfully restocked ${qty} units for ${updated.name}!`);
    } catch (err) {
      console.error("Restock error:", err);
    }
  };

  const openAddModal = () => {
    setEditingProduct(null);
    setName("");
    setSku(`SKU-${Math.floor(Math.random() * 900 + 100)}`);
    setCategory("Software");
    setStock(100);
    setReorder(30);
    setPrice("₹49,999");
    setTrend("+5%");
    setIsModalOpen(true);
  };

  const openEditModal = (prod: Product, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingProduct(prod);
    setName(prod.name);
    setSku(prod.sku);
    setCategory(prod.category);
    setStock(prod.stock);
    setReorder(prod.reorder);
    setPrice(prod.price);
    setTrend(prod.trend);
    setIsModalOpen(true);
  };

  const handleDeleteProduct = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm("Are you sure you want to delete this product?")) {
      try {
        await api.deleteProduct(id);
        fetchInventory();
        if (selected?.id === id) setSelected(null);
      } catch (err) {
        console.error("Delete product error:", err);
      }
    }
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.id, { name, sku, category, stock, reorder, price, trend });
      } else {
        await api.createProduct({ name, sku, category, stock, reorder, price, trend });
      }
      setIsModalOpen(false);
      fetchInventory();
    } catch (err) {
      console.error("Save product error:", err);
    }
  };

  const filtered = productsList.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.sku.toLowerCase().includes(search.toLowerCase()) ||
    p.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        {[
          { title: "Total Products", value: `${productsList.length}`, change: "+5%", icon: Package, color: "bg-indigo-500" },
          { title: "In Stock", value: `${productsList.filter(p => p.status === "In Stock").length}`, change: "+3%", icon: CheckCircle, color: "bg-emerald-500" },
          { title: "Low Stock", value: `${productsList.filter(p => p.status === "Low Stock").length}`, change: "+1", icon: AlertTriangle, color: "bg-amber-500" },
          { title: "Critical / Out", value: `${productsList.filter(p => p.status === "Critical" || p.status === "Out of Stock").length}`, change: "-1", icon: X, color: "bg-red-500" },
        ].map(c => <KPICard key={c.title} {...c} />)}
      </div>
      <div className="flex gap-5">
        <div className="flex-1 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-800 flex-1">Product Inventory ({filtered.length})</h2>
            <SearchBar value={search} onChange={setSearch} placeholder="Search products..." />
            <button className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-xl text-xs text-slate-600 hover:bg-slate-50"><Filter size={13} />Filter</button>
            <GradientButton size="sm" onClick={openAddModal}><Plus size={13} />Add Product</GradientButton>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-50">
                  {["Product", "SKU", "Category", "Stock", "Reorder At", "Price", "Status", "Trend", "Actions"].map(h => (
                    <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map(p => (
                  <tr
                    key={p.id}
                    onClick={() => handleSelectProduct(p)}
                    className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === p.id ? "bg-indigo-50/50" : ""}`}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                          <Package size={14} className="text-slate-400" />
                        </div>
                        <p className="text-sm font-medium text-slate-800">{p.name}</p>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-xs font-mono text-slate-500">{p.sku}</td>
                    <td className="px-5 py-3.5"><Badge label={p.category} variant="info" /></td>
                    <td className="px-5 py-3.5 text-sm font-semibold text-slate-800">{p.stock}</td>
                    <td className="px-5 py-3.5 text-sm text-slate-500">{p.reorder}</td>
                    <td className="px-5 py-3.5 text-sm font-medium text-slate-700">{p.price}</td>
                    <td className="px-5 py-3.5"><StatusBadge status={p.status} /></td>
                    <td className="px-5 py-3.5">
                      <span className={`text-xs font-semibold ${p.trend.startsWith("+") ? "text-emerald-600" : p.trend === "N/A" ? "text-slate-400" : "text-red-500"}`}>
                        {p.trend}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1">
                        <button onClick={(e) => { e.stopPropagation(); handleSelectProduct(p); }} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="View"><Eye size={13} /></button>
                        <button onClick={(e) => openEditModal(p, e)} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="Edit"><Edit2 size={13} /></button>
                        <button onClick={(e) => handleDeleteProduct(p.id, e)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500" title="Delete"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {selected && (
          <div className="w-72 shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800">Product Detail</h3>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
            </div>
            <div className="w-full h-24 bg-slate-50 rounded-xl flex items-center justify-center">
              <Package size={36} className="text-slate-300" />
            </div>
            <div>
              <p className="font-semibold text-slate-800">{selected.name}</p>
              <p className="text-xs text-slate-500 font-mono mt-0.5">{selected.sku}</p>
            </div>
            <div className="space-y-2.5">
              {[
                { label: "Category", value: selected.category },
                { label: "Price", value: selected.price },
                { label: "Current Stock", value: `${selected.stock} units` },
                { label: "Reorder Level", value: `${selected.reorder} units` },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-xs">
                  <span className="text-slate-400">{label}</span>
                  <span className="font-medium text-slate-700">{value}</span>
                </div>
              ))}
            </div>

            {/* AI Demand Forecast connected to ML Model */}
            <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-xl p-3 border border-indigo-100">
              <div className="flex items-center gap-2 mb-2">
                <Bot size={12} className="text-indigo-600" />
                <span className="text-xs font-semibold text-indigo-700">AI Demand Forecast (ML)</span>
              </div>
              {loadingForecast ? (
                <div className="py-2 flex items-center gap-2 text-xs text-indigo-600">
                  <Loader2 size={12} className="animate-spin" /> Calculating demand forecast...
                </div>
              ) : demandForecast ? (
                <div className="space-y-1.5 text-xs text-slate-700">
                  <div className="flex justify-between">
                    <span className="text-slate-500">7-Day Demand:</span>
                    <strong className="text-indigo-700">{demandForecast.predicted_demand_7_days} units</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">30-Day Demand:</span>
                    <strong className="text-indigo-700">{demandForecast.predicted_demand_30_days} units</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Stockout Risk:</span>
                    <span className={`font-bold ${demandForecast.stockout_risk === "HIGH" ? "text-red-500" : "text-emerald-600"}`}>{demandForecast.stockout_risk}</span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed mt-2 pt-1 border-t border-indigo-100/60">
                    {demandForecast.recommendation}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-600 leading-relaxed">
                  {selected.status === "Critical" || selected.status === "Out of Stock"
                    ? "Urgent restock recommended. Estimated stockout in 2-3 days."
                    : "Demand stable. Estimated consumption: 28 units/month. Next reorder due in ~3 weeks."}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleRestock(selected.id, demandForecast?.recommended_reorder || 50)}
                className="text-xs py-2 bg-indigo-50 text-indigo-700 rounded-xl font-medium hover:bg-indigo-100"
              >
                Restock Order
              </button>
              <button onClick={() => openEditModal(selected)} className="text-xs py-2 bg-violet-50 text-violet-700 rounded-xl font-medium hover:bg-violet-100">Edit Product</button>
            </div>
          </div>
        )}
      </div>

      {/* Add / Edit Product Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-100 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-800">{editingProduct ? "Edit Product" : "Add New Product"}</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <form onSubmit={handleSaveProduct} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Product Name *</label>
                <input required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Enterprise Suite Pro" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">SKU Code *</label>
                  <input required value={sku} onChange={e => setSku(e.target.value)} placeholder="ESP-001" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Category</label>
                  <select value={category} onChange={e => setCategory(e.target.value)} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none">
                    <option value="Software">Software</option>
                    <option value="Storage">Storage</option>
                    <option value="Services">Services</option>
                    <option value="Hardware">Hardware</option>
                    <option value="Training">Training</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Current Stock</label>
                  <input type="number" min={0} value={stock} onChange={e => setStock(Number(e.target.value))} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Reorder Level</label>
                  <input type="number" min={0} value={reorder} onChange={e => setReorder(Number(e.target.value))} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Price</label>
                  <input value={price} onChange={e => setPrice(e.target.value)} placeholder="₹3,49,000" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Trend</label>
                  <input value={trend} onChange={e => setTrend(e.target.value)} placeholder="+12%" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 rounded-xl text-slate-600 bg-slate-100 hover:bg-slate-200 font-medium">Cancel</button>
                <GradientButton size="sm"><CheckCircle size={13} />{editingProduct ? "Save Product" : "Add Product"}</GradientButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Invoice Management ───────────────────────────────────────────────────────

function parsePriceNum(priceStr: string | number | undefined): number {
  if (typeof priceStr === "number") return priceStr;
  if (!priceStr) return 0;
  const cleaned = String(priceStr).replace(/₹|,|\/mo/g, "").trim();
  const val = parseFloat(cleaned);
  return isNaN(val) ? 0 : val;
}

function InvoicesPage() {
  const [invoicesList, setInvoicesList] = useState<Invoice[]>(fallbackInvoices);
  const [customersList, setCustomersList] = useState<Customer[]>(fallbackCustomers);
  const [productsList, setProductsList] = useState<Product[]>(fallbackProducts);
  const [preview, setPreview] = useState<Invoice | null>(null);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form State for New Invoice
  const [client, setClient] = useState("");
  const [due, setDue] = useState("Sep 30, 2026");
  const [status, setStatus] = useState<"Paid" | "Pending" | "Overdue" | "Draft">("Pending");
  const [taxRate, setTaxRate] = useState(18); // Default 18% GST
  const [discount, setDiscount] = useState(0);

  // Multi-Product Line Items
  const [lineItems, setLineItems] = useState<Array<{ product_id: number; product_name: string; quantity: number; unit_price: number }>>([]);

  const fetchInvoices = () => {
    api.getInvoices()
      .then(data => setInvoicesList(data))
      .catch(() => { });
  };

  const fetchDependencies = () => {
    api.getCustomers()
      .then(custs => {
        if (custs && custs.length > 0) setCustomersList(custs);
      })
      .catch(() => { });

    api.getInventory()
      .then(prods => {
        if (prods && prods.length > 0) setProductsList(prods);
      })
      .catch(() => { });
  };

  useEffect(() => {
    fetchInvoices();
    fetchDependencies();
  }, []);

  // Initialize line items when modal opens
  const openCreateModal = () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    const defaultCust = customersList[0]?.company || customersList[0]?.name || "TechCorp India Pvt. Ltd";
    setClient(defaultCust);

    const defaultProd = productsList.find(p => p.stock > 0) || productsList[0];
    if (defaultProd) {
      setLineItems([{
        product_id: defaultProd.id,
        product_name: defaultProd.name,
        quantity: 1,
        unit_price: defaultProd.price_num || parsePriceNum(defaultProd.price)
      }]);
    } else {
      setLineItems([]);
    }
    setTaxRate(18);
    setDiscount(0);
    setDue("Sep 30, 2026");
    setStatus("Pending");
    setIsModalOpen(true);
  };

  const handleProductChange = (index: number, productId: number) => {
    const prod = productsList.find(p => p.id === productId);
    if (!prod) return;
    const updated = [...lineItems];
    const unitPrice = prod.price_num || parsePriceNum(prod.price);
    const maxQty = Math.max(1, prod.stock);
    updated[index] = {
      product_id: prod.id,
      product_name: prod.name,
      unit_price: unitPrice,
      quantity: Math.min(updated[index]?.quantity || 1, maxQty)
    };
    setLineItems(updated);
  };

  const handleQuantityChange = (index: number, qty: number) => {
    const updated = [...lineItems];
    const item = updated[index];
    if (!item) return;
    const prod = productsList.find(p => p.id === item.product_id);
    const safeQty = Math.max(1, qty);
    updated[index] = { ...item, quantity: safeQty };
    setLineItems(updated);
  };

  const addItemRow = () => {
    const defaultProd = productsList.find(p => p.stock > 0) || productsList[0];
    if (defaultProd) {
      setLineItems([
        ...lineItems,
        {
          product_id: defaultProd.id,
          product_name: defaultProd.name,
          quantity: 1,
          unit_price: defaultProd.price_num || parsePriceNum(defaultProd.price)
        }
      ]);
    }
  };

  const removeItemRow = (index: number) => {
    if (lineItems.length <= 1) return;
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  // Calculations
  const subtotal = lineItems.reduce((acc, item) => acc + (item.unit_price * item.quantity), 0);
  const taxAmount = subtotal * (Math.max(0, taxRate) / 100);
  const grandTotal = Math.max(0, subtotal + taxAmount - Math.max(0, discount));

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!client) {
      setErrorMessage("Please select a customer.");
      return;
    }

    if (lineItems.length === 0) {
      setErrorMessage("Please add at least one product line item.");
      return;
    }

    // Client-side stock check validation
    for (const item of lineItems) {
      const prod = productsList.find(p => p.id === item.product_id);
      if (!prod) {
        setErrorMessage(`Product '${item.product_name}' not found in inventory.`);
        return;
      }
      if (item.quantity > prod.stock) {
        setErrorMessage(`Requested quantity (${item.quantity}) for '${prod.name}' exceeds available stock (${prod.stock}).`);
        return;
      }
    }

    setLoading(true);
    try {
      const newInv = await api.createInvoice({
        client,
        due,
        status,
        tax: taxRate,
        discount,
        line_items: lineItems.map(item => ({
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          product_name: item.product_name
        }))
      });

      setIsModalOpen(false);
      setSuccessMessage(`Invoice ${newInv.id} created successfully! Inventory stock has been automatically updated.`);
      fetchInvoices();
      fetchDependencies();
      setPreview(newInv);
    } catch (err: any) {
      console.error("Create invoice error:", err);
      setErrorMessage(err.message || "Failed to create invoice. Transaction rolled back.");
    } finally {
      setLoading(false);
    }
  };

  const handleAIGenerate = async () => {
    setErrorMessage(null);
    setLoading(true);
    try {
      const firstCustomer = customersList[0]?.company || customersList[0]?.name || "TechCorp India Pvt. Ltd";
      const availableProd = productsList.find(p => p.stock >= 2) || productsList[0];

      if (!availableProd || availableProd.stock < 1) {
        alert("Cannot AI-generate invoice: No in-stock products available in inventory.");
        setLoading(false);
        return;
      }

      const generated = await api.createInvoice({
        client: firstCustomer,
        due: "Sep 30, 2026",
        status: "Draft",
        tax: 18,
        discount: 5000,
        line_items: [{
          product_id: availableProd.id,
          quantity: 1,
          unit_price: availableProd.price_num || parsePriceNum(availableProd.price),
          product_name: availableProd.name
        }]
      });

      fetchInvoices();
      fetchDependencies();
      setPreview(generated);
      alert(`AI Generated draft invoice ${generated.id} for ${firstCustomer} with 1 unit of ${availableProd.name}! Stock deducted.`);
    } catch (err: any) {
      console.error("AI Invoice Generation Error:", err);
      alert(`AI Invoice Generation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      const updated = await api.updateInvoiceStatus(id, newStatus);
      fetchInvoices();
      if (preview?.id === id) setPreview(updated);
    } catch (err) {
      console.error("Update status error:", err);
    }
  };

  const handleDeleteInvoice = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm(`Delete invoice ${id}?`)) {
      try {
        await api.deleteInvoice(id);
        fetchInvoices();
        if (preview?.id === id) setPreview(null);
      } catch (err) {
        console.error("Delete invoice error:", err);
      }
    }
  };

  const filtered = invoicesList.filter(inv =>
    inv.client.toLowerCase().includes(search.toLowerCase()) ||
    inv.id.toLowerCase().includes(search.toLowerCase()) ||
    inv.status.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      {/* Global Success Banner */}
      {successMessage && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs px-4 py-3 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle size={15} className="text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-500 hover:text-emerald-700"><X size={14} /></button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {[
          { title: "Total Invoiced", value: "₹4,39,600", change: "+15%", icon: FileText, color: "bg-indigo-500" },
          { title: "Paid", value: "₹1,60,200", change: "+22%", icon: CheckCircle, color: "bg-emerald-500" },
          { title: "Pending", value: "₹2,52,800", change: "-3%", icon: Clock, color: "bg-amber-500" },
          { title: "Overdue", value: "₹26,600", change: "+1", icon: AlertTriangle, color: "bg-red-500" },
        ].map(c => <KPICard key={c.title} {...c} />)}
      </div>

      <div className="flex gap-5">
        <div className="flex-1 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-800 flex-1">Invoices ({filtered.length})</h2>
            <SearchBar value={search} onChange={setSearch} placeholder="Search invoices..." />
            <button className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-xl text-xs text-slate-600 hover:bg-slate-50"><Filter size={13} />Filter</button>
            <GradientButton size="sm" onClick={handleAIGenerate}><Sparkles size={13} />AI Generate</GradientButton>
            <GradientButton size="sm" variant="secondary" onClick={openCreateModal}><Plus size={13} />New Invoice</GradientButton>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-50">
                  {["Invoice", "Client", "Amount", "Issued", "Due Date", "Status", "Actions"].map(h => (
                    <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map(inv => (
                  <tr key={inv.id} className="hover:bg-slate-50 cursor-pointer transition-colors" onClick={() => setPreview(preview?.id === inv.id ? null : inv)}>
                    <td className="px-5 py-3.5 text-sm font-mono font-medium text-indigo-600">{inv.id}</td>
                    <td className="px-5 py-3.5 text-sm text-slate-700">{inv.client}</td>
                    <td className="px-5 py-3.5 text-sm font-bold text-slate-800">{inv.amount}</td>
                    <td className="px-5 py-3.5 text-sm text-slate-500">{inv.issued}</td>
                    <td className="px-5 py-3.5 text-sm text-slate-500">{inv.due}</td>
                    <td className="px-5 py-3.5"><StatusBadge status={inv.status} /></td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1">
                        <button onClick={(e) => { e.stopPropagation(); setPreview(inv); }} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="View"><Eye size={13} /></button>
                        <button onClick={(e) => { e.stopPropagation(); alert(`Downloading PDF for ${inv.id}`); }} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="Download"><Download size={13} /></button>
                        <button onClick={(e) => handleDeleteInvoice(inv.id, e)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500" title="Delete"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Invoice Preview Panel */}
        {preview && (
          <div className="w-84 shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h3 className="text-sm font-semibold text-slate-800">Invoice Details</h3>
              <button onClick={() => setPreview(null)} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div className="bg-gradient-to-r from-indigo-500 to-violet-600 rounded-xl p-4 text-white">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Cpu size={16} />
                    <span className="font-bold text-sm">AI BizOps Billing</span>
                  </div>
                  <StatusBadge status={preview.status} />
                </div>
                <p className="font-mono text-xs opacity-80">{preview.id}</p>
                <p className="text-2xl font-extrabold mt-1">{preview.amount}</p>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Customer</span>
                  <span className="font-medium text-slate-700 text-right">{preview.client}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Issue Date</span>
                  <span className="font-medium text-slate-700">{preview.issued}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Due Date</span>
                  <span className="font-medium text-slate-700">{preview.due}</span>
                </div>
              </div>

              {/* Line Items List */}
              <div className="border-t border-slate-100 pt-3">
                <h4 className="text-xs font-semibold text-slate-700 mb-2">Line Items</h4>
                {preview.line_items && preview.line_items.length > 0 ? (
                  <div className="space-y-1.5">
                    {preview.line_items.map((item, i) => (
                      <div key={i} className="flex justify-between text-xs p-2 rounded-lg bg-slate-50">
                        <div>
                          <p className="font-medium text-slate-800">{item.product_name}</p>
                          <p className="text-slate-400 text-[10px]">{item.quantity} × ₹{item.unit_price.toLocaleString()}</p>
                        </div>
                        <span className="font-semibold text-slate-800">₹{item.line_total.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-2 rounded-lg bg-slate-50 text-xs text-slate-600">
                    {preview.items || "Professional Services & Software License"}
                  </div>
                )}
              </div>

              {/* Totals Breakdown */}
              {(preview.subtotal !== undefined && preview.subtotal > 0) && (
                <div className="border-t border-slate-100 pt-3 space-y-1 text-xs">
                  <div className="flex justify-between text-slate-500">
                    <span>Subtotal</span>
                    <span>₹{preview.subtotal.toLocaleString()}</span>
                  </div>
                  {preview.tax ? (
                    <div className="flex justify-between text-slate-500">
                      <span>Tax ({preview.tax}%)</span>
                      <span>+₹{((preview.subtotal * preview.tax) / 100).toLocaleString()}</span>
                    </div>
                  ) : null}
                  {preview.discount ? (
                    <div className="flex justify-between text-emerald-600">
                      <span>Discount</span>
                      <span>-₹{preview.discount.toLocaleString()}</span>
                    </div>
                  ) : null}
                  <div className="flex justify-between font-bold text-slate-800 pt-1 border-t border-slate-100">
                    <span>Grand Total</span>
                    <span>{preview.amount}</span>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2 pt-2">
                {preview.status !== "Paid" && (
                  <button onClick={() => handleStatusChange(preview.id, "Paid")} className="w-full text-xs py-2 bg-emerald-50 text-emerald-700 rounded-xl font-medium hover:bg-emerald-100 transition-colors">
                    Mark as Paid
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button onClick={() => alert(`Downloaded PDF for ${preview.id}`)} className="flex items-center justify-center gap-1.5 text-xs py-2.5 bg-indigo-50 text-indigo-700 rounded-xl font-medium hover:bg-indigo-100"><Download size={12} />Download PDF</button>
                <button onClick={() => alert(`Email sent to ${preview.client}`)} className="flex items-center justify-center gap-1.5 text-xs py-2.5 bg-violet-50 text-violet-700 rounded-xl font-medium hover:bg-violet-100"><Mail size={12} />Send Email</button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Real Billing New Invoice Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-white rounded-2xl p-6 w-full max-w-xl shadow-2xl border border-slate-100 space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-800">Create New Invoice</h3>
                <p className="text-xs text-slate-400 mt-0.5">Real Billing &amp; Inventory Stock Deduction</p>
              </div>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>

            {errorMessage && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-4 py-3 rounded-xl flex items-start gap-2">
                <AlertTriangle size={15} className="shrink-0 mt-0.5 text-red-500" />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleCreateInvoice} className="space-y-4 text-xs">
              {/* Customer & Dates */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Select Customer *</label>
                  <select
                    required
                    value={client}
                    onChange={e => setClient(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 bg-white"
                  >
                    {customersList.map(c => (
                      <option key={c.id} value={c.company || c.name}>
                        {c.company || c.name} ({c.name})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Status</label>
                  <select
                    value={status}
                    onChange={e => setStatus(e.target.value as any)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none bg-white"
                  >
                    <option value="Pending">Pending</option>
                    <option value="Paid">Paid</option>
                    <option value="Draft">Draft</option>
                    <option value="Overdue">Overdue</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Due Date</label>
                <input
                  value={due}
                  onChange={e => setDue(e.target.value)}
                  placeholder="e.g. Sep 30, 2026"
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none"
                />
              </div>

              {/* Line Items Section */}
              <div className="border border-slate-100 rounded-xl p-3 bg-slate-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800">Invoice Items</span>
                  <button
                    type="button"
                    onClick={addItemRow}
                    className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                  >
                    <Plus size={13} /> Add Product
                  </button>
                </div>

                <div className="space-y-2.5">
                  {lineItems.map((item, idx) => {
                    const prod = productsList.find(p => p.id === item.product_id);
                    const stock = prod?.stock ?? 0;
                    const isExceeded = item.quantity > stock;

                    return (
                      <div key={idx} className="p-3 bg-white border border-slate-200 rounded-xl space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-semibold text-slate-500">Item #{idx + 1}</span>
                          {lineItems.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeItemRow(idx)}
                              className="text-red-400 hover:text-red-600 p-1"
                              title="Remove line item"
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>

                        <div className="grid grid-cols-12 gap-2 items-end">
                          <div className="col-span-6">
                            <label className="block text-[11px] font-medium text-slate-600 mb-1">Product</label>
                            <select
                              value={item.product_id}
                              onChange={e => handleProductChange(idx, Number(e.target.value))}
                              className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none bg-white"
                            >
                              {productsList.map(p => (
                                <option key={p.id} value={p.id}>
                                  {p.name} (Stock: {p.stock})
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="col-span-2">
                            <label className="block text-[11px] font-medium text-slate-600 mb-1">Stock</label>
                            <span className={`inline-block px-2 py-1.5 rounded-lg text-xs font-semibold w-full text-center ${stock === 0 ? "bg-red-50 text-red-600" : stock < 10 ? "bg-amber-50 text-amber-600" : "bg-emerald-50 text-emerald-600"
                              }`}>
                              {stock} left
                            </span>
                          </div>

                          <div className="col-span-2">
                            <label className="block text-[11px] font-medium text-slate-600 mb-1">Qty *</label>
                            <input
                              type="number"
                              min={1}
                              max={stock}
                              value={item.quantity}
                              onChange={e => handleQuantityChange(idx, parseInt(e.target.value) || 1)}
                              className={`w-full border rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none ${isExceeded ? "border-red-500 bg-red-50/50" : "border-slate-200"
                                }`}
                            />
                          </div>

                          <div className="col-span-2 text-right">
                            <label className="block text-[11px] font-medium text-slate-600 mb-1">Line Total</label>
                            <p className="text-xs font-bold text-slate-800 py-1.5">
                              ₹{(item.unit_price * item.quantity).toLocaleString()}
                            </p>
                          </div>
                        </div>

                        {isExceeded && (
                          <p className="text-[11px] text-red-500 font-medium">
                            Quantity exceeds available stock ({stock} available).
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tax & Discount */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Tax Rate (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={taxRate}
                    onChange={e => setTaxRate(Number(e.target.value))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Discount (₹)</label>
                  <input
                    type="number"
                    min={0}
                    value={discount}
                    onChange={e => setDiscount(Number(e.target.value))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none"
                  />
                </div>
              </div>

              {/* Summary Breakdown Box */}
              <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-3 space-y-1.5">
                <div className="flex justify-between text-slate-600">
                  <span>Subtotal ({lineItems.reduce((acc, i) => acc + i.quantity, 0)} items)</span>
                  <span className="font-semibold text-slate-800">₹{subtotal.toLocaleString()}</span>
                </div>
                {taxRate > 0 && (
                  <div className="flex justify-between text-slate-600">
                    <span>Tax ({taxRate}%)</span>
                    <span className="font-semibold text-slate-800">+₹{taxAmount.toLocaleString()}</span>
                  </div>
                )}
                {discount > 0 && (
                  <div className="flex justify-between text-emerald-700">
                    <span>Discount</span>
                    <span className="font-semibold">-₹{discount.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex justify-between text-sm font-bold text-slate-900 pt-1.5 border-t border-indigo-100">
                  <span>Grand Total</span>
                  <span className="text-indigo-600">₹{grandTotal.toLocaleString()}</span>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 bg-slate-100 hover:bg-slate-200 font-medium disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || lineItems.some(i => i.quantity > (productsList.find(p => p.id === i.product_id)?.stock ?? 0))}
                  className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold rounded-xl hover:from-indigo-600 hover:to-violet-700 transition-all shadow-sm shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  {loading ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                  <span>Save Invoice &amp; Deduct Stock</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Employee Management ──────────────────────────────────────────────────────

function EmployeesPage() {
  const [employeesList, setEmployeesList] = useState<Employee[]>(fallbackEmployees);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Employee | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEmp, setEditingEmp] = useState<Employee | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [dept, setDept] = useState("Engineering");
  const [salary, setSalary] = useState("₹85,000/mo");
  const [attendance, setAttendance] = useState(96);
  const [performance, setPerformance] = useState(92);
  const [status, setStatus] = useState<"Active" | "On Leave" | "Inactive">("Active");

  const fetchEmployees = () => {
    api.getEmployees().then(data => setEmployeesList(data)).catch(() => { });
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  const openAddModal = () => {
    setEditingEmp(null);
    setName("");
    setRole("Senior Developer");
    setDept("Engineering");
    setSalary("₹90,000/mo");
    setAttendance(95);
    setPerformance(90);
    setStatus("Active");
    setIsModalOpen(true);
  };

  const openEditModal = (emp: Employee, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingEmp(emp);
    setName(emp.name);
    setRole(emp.role);
    setDept(emp.dept);
    setSalary(emp.salary);
    setAttendance(emp.attendance);
    setPerformance(emp.performance);
    setStatus(emp.status);
    setIsModalOpen(true);
  };

  const handleDeleteEmployee = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm("Are you sure you want to delete this employee record?")) {
      try {
        await api.deleteEmployee(id);
        fetchEmployees();
        if (selected?.id === id) setSelected(null);
      } catch (err) {
        console.error("Delete employee error:", err);
      }
    }
  };

  const handleSaveEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingEmp) {
        await api.updateEmployee(editingEmp.id, { name, role, dept, salary, attendance, performance, status });
      } else {
        await api.createEmployee({ name, role, dept, salary, attendance, performance, status });
      }
      setIsModalOpen(false);
      fetchEmployees();
    } catch (err) {
      console.error("Save employee error:", err);
    }
  };

  const filtered = employeesList.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.role.toLowerCase().includes(search.toLowerCase()) ||
    e.dept.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        {[
          { title: "Total Employees", value: `${employeesList.length}`, change: "+2", icon: Users, color: "bg-indigo-500" },
          { title: "Active Today", value: `${employeesList.filter(e => e.status === "Active").length}`, change: "+3", icon: CheckCircle, color: "bg-emerald-500" },
          { title: "On Leave", value: `${employeesList.filter(e => e.status === "On Leave").length}`, change: "0", icon: Calendar, color: "bg-amber-500" },
          { title: "Avg Performance", value: `${Math.round(employeesList.reduce((s, e) => s + e.performance, 0) / Math.max(1, employeesList.length))}%`, change: "+1.2%", icon: Award, color: "bg-violet-500" },
        ].map(c => <KPICard key={c.title} {...c} />)}
      </div>
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800 flex-1">All Employees ({filtered.length})</h2>
          <SearchBar value={search} onChange={setSearch} placeholder="Search employees..." />
          <button className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-xl text-xs text-slate-600 hover:bg-slate-50"><Filter size={13} />Filter</button>
          <GradientButton size="sm" onClick={openAddModal}><Plus size={13} />Add Employee</GradientButton>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-50">
                {["Employee", "Role", "Department", "Salary", "Attendance", "Performance", "Status", "Actions"].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map(e => (
                <tr key={e.id} onClick={() => setSelected(selected?.id === e.id ? null : e)} className={`hover:bg-slate-50 transition-colors cursor-pointer ${selected?.id === e.id ? "bg-indigo-50/50" : ""}`}>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-300 to-violet-400 flex items-center justify-center text-white text-xs font-bold shrink-0">
                        {e.name.split(" ").map(n => n[0]).join("")}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-800">{e.name}</p>
                        <p className="text-xs text-slate-400">Since {e.joined}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-slate-600">{e.role}</td>
                  <td className="px-5 py-3.5"><Badge label={e.dept} variant="info" /></td>
                  <td className="px-5 py-3.5 text-sm font-semibold text-slate-800">{e.salary}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${e.attendance}%` }} />
                      </div>
                      <span className="text-xs font-medium text-slate-600">{e.attendance}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-violet-500 rounded-full" style={{ width: `${e.performance}%` }} />
                      </div>
                      <span className="text-xs font-medium text-slate-600">{e.performance}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5"><StatusBadge status={e.status} /></td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-1">
                      <button onClick={(e_evt) => { e_evt.stopPropagation(); setSelected(e); }} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="View"><Eye size={13} /></button>
                      <button onClick={(e_evt) => openEditModal(e, e_evt)} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="Edit"><Edit2 size={13} /></button>
                      <button onClick={(e_evt) => handleDeleteEmployee(e.id, e_evt)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500" title="Delete"><Trash2 size={13} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payroll summary */}
      <div className="grid grid-cols-3 gap-5">
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Payroll Summary — July 2026</h2>
          <div className="space-y-2.5">
            {[
              { label: "Base Salaries", value: "₹41,70,000" },
              { label: "Bonuses", value: "₹2,04,000" },
              { label: "Benefits", value: "₹3,18,000" },
              { label: "Tax Withheld (TDS)", value: "₹11,88,000" },
              { label: "Net Payout", value: "₹35,04,000" },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between text-sm">
                <span className="text-slate-500">{label}</span>
                <span className={`font-semibold ${label === "Net Payout" ? "text-indigo-600" : "text-slate-800"}`}>{value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="col-span-2 bg-gradient-to-br from-indigo-50 to-violet-50 rounded-2xl p-5 border border-indigo-100">
          <div className="flex items-center gap-2 mb-4">
            <Bot size={16} className="text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-800">AI HR Insights</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { text: "Valarmathi Subramanian has the highest attendance record (97%) and performance score (92%). Consider for senior promotion.", type: "positive" },
              { text: "Pazhanivel Arumugam's attendance dropped to 82% this month — below team average. Schedule check-in.", type: "warning" },
              { text: "Engineering team is understaffed by an estimated 2 FTEs based on current sprint velocity.", type: "info" },
              { text: "Avg tenure is 2.4 years. Q3 attrition risk is low at 8%. No critical flight risks detected.", type: "positive" },
            ].map(({ text, type }, i) => {
              const colors = { positive: "text-emerald-700 bg-emerald-50 border-emerald-200", warning: "text-amber-700 bg-amber-50 border-amber-200", info: "text-indigo-700 bg-indigo-50 border-indigo-200" };
              return <div key={i} className={`text-xs p-3 rounded-xl border leading-relaxed ${colors[type as keyof typeof colors]}`}>{text}</div>;
            })}
          </div>
        </div>
      </div>

      {/* Add / Edit Employee Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-100 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-800">{editingEmp ? "Edit Employee" : "Add New Employee"}</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <form onSubmit={handleSaveEmployee} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Employee Full Name *</label>
                <input required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Anbarasi Krishnamoorthy" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Role / Designation *</label>
                  <input required value={role} onChange={e => setRole(e.target.value)} placeholder="Head of Sales" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Department</label>
                  <select value={dept} onChange={e => setDept(e.target.value)} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none">
                    <option value="Sales">Sales</option>
                    <option value="Engineering">Engineering</option>
                    <option value="Product">Product</option>
                    <option value="Support">Support</option>
                    <option value="Analytics">Analytics</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Monthly Salary</label>
                  <input value={salary} onChange={e => setSalary(e.target.value)} placeholder="₹82,000/mo" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Status</label>
                  <select value={status} onChange={e => setStatus(e.target.value as any)} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none">
                    <option value="Active">Active</option>
                    <option value="On Leave">On Leave</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Attendance %</label>
                  <input type="number" min={0} max={100} value={attendance} onChange={e => setAttendance(Number(e.target.value))} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Performance %</label>
                  <input type="number" min={0} max={100} value={performance} onChange={e => setPerformance(Number(e.target.value))} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 rounded-xl text-slate-600 bg-slate-100 hover:bg-slate-200 font-medium">Cancel</button>
                <GradientButton size="sm"><CheckCircle size={13} />{editingEmp ? "Save Employee" : "Add Employee"}</GradientButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Reports Page ─────────────────────────────────────────────────────────────

function downloadCSV(filename: string, headers: string[], rows: (string | number)[][]) {
  const csv = [headers.join(","), ...rows.map(r => r.map(c => `"${c}"`).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadPDF(reportName: string, rows: { label: string; value: string }[]) {
  const date = new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" });
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${reportName}</title>
  <style>body{font-family:Arial,sans-serif;margin:40px;color:#1e293b}h1{color:#4f46e5;font-size:22px;margin-bottom:4px}
  .meta{color:#64748b;font-size:13px;margin-bottom:28px}table{width:100%;border-collapse:collapse;font-size:14px}
  th{background:#f1f5f9;text-align:left;padding:10px 14px;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0}
  td{padding:10px 14px;border-bottom:1px solid #f1f5f9}tr:hover td{background:#f8fafc}
  .footer{margin-top:32px;font-size:11px;color:#94a3b8;text-align:center}</style></head>
  <body><h1>${reportName}</h1><p class="meta">Nexus Commerce Pvt. Ltd &nbsp;|&nbsp; Generated: ${date}</p>
  <table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
  ${rows.map(r => `<tr><td>${r.label}</td><td>${r.value}</td></tr>`).join("")}
  </tbody></table><p class="footer">AI Business Operations Copilot &mdash; Confidential</p></body></html>`;
  const blob = new Blob([html], { type: "text/html;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = reportName.replace(/\s+/g, "_") + ".html";
  a.click();
  URL.revokeObjectURL(url);
}

function ReportsPage({ user }: { user?: UserSession | null }) {
  const [activeReport, setActiveReport] = useState("Revenue Report");
  const [reportDataState, setReportDataState] = useState<ReportData | null>(null);

  const templates = [
    { name: "Revenue Report", icon: DollarSign, desc: "Monthly P&L, revenue breakdown, trend analysis" },
    { name: "Customer Report", icon: Users, desc: "Customer growth, churn, LTV, segmentation" },
    { name: "Inventory Report", icon: Package, desc: "Stock levels, turnover rate, reorder analysis" },
    { name: "Employee Report", icon: UserCheck, desc: "Attendance, performance, payroll summary" },
    { name: "Sales Report", icon: TrendingUp, desc: "Sales by channel, period, product, region" },
    { name: "AI Insights Report", icon: Bot, desc: "AI-generated business health summary" },
  ];

  useEffect(() => {
    api.getReport(activeReport)
      .then(data => setReportDataState(data))
      .catch(() => { });
  }, [activeReport]);

  function handleCSV() {
    if (!reportDataState) return;
    downloadCSV(activeReport.replace(/\s+/g, "_") + ".csv", reportDataState.headers, reportDataState.rows);
  }

  function handlePDF() {
    if (!reportDataState) return;
    downloadPDF(activeReport, reportDataState.summary);
  }

  const authorName = user?.name || "Operations Team";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-5">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Report Templates</h2>
          <div className="space-y-2">
            {templates.map(({ name, icon: Icon, desc }) => (
              <button key={name} onClick={() => setActiveReport(name)} className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-colors ${activeReport === name ? "bg-indigo-50 border border-indigo-100" : "hover:bg-slate-50"}`}>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${activeReport === name ? "bg-indigo-100" : "bg-slate-100"}`}>
                  <Icon size={14} className={activeReport === name ? "text-indigo-600" : "text-slate-400"} />
                </div>
                <div className="min-w-0">
                  <p className={`text-xs font-semibold ${activeReport === name ? "text-indigo-700" : "text-slate-700"}`}>{name}</p>
                  <p className="text-xs text-slate-400 truncate">{desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
        <div className="col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">{activeReport}</h2>
              <p className="text-xs text-slate-400 mt-0.5">Live Backend Generated Report</p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => alert(`Report schedule set for ${activeReport}`)} className="flex items-center gap-1.5 text-xs px-3 py-2 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50"><Calendar size={12} />Schedule</button>
              <button onClick={handlePDF} className="flex items-center gap-1.5 text-xs px-3 py-2 bg-slate-100 rounded-xl text-slate-700 hover:bg-slate-200"><Download size={12} />PDF</button>
              <button onClick={handleCSV} className="flex items-center gap-1.5 text-xs px-3 py-2 bg-emerald-50 rounded-xl text-emerald-700 hover:bg-emerald-100"><Download size={12} />Excel</button>
            </div>
          </div>
          {/* AI Summary */}
          <div className="bg-gradient-to-br from-indigo-50 to-violet-50 rounded-xl p-4 border border-indigo-100 mb-5">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={14} className="text-indigo-600" />
              <span className="text-xs font-semibold text-indigo-700">AI-Generated Summary</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(reportDataState?.summary || []).map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between bg-white/60 rounded-lg px-3 py-2">
                  <span className="text-xs text-slate-500">{label}</span>
                  <span className="text-xs font-semibold text-slate-800">{value}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Data Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-100">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50">
                  {(reportDataState?.headers || []).map(h => (
                    <th key={h} className="px-3 py-2.5 text-left font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(reportDataState?.rows || []).map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    {row.map((cell, j) => (
                      <td key={j} className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
        <h2 className="text-sm font-semibold text-slate-800 mb-4">Report History</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-50">
                {["Report Name", "Generated", "Generated By", "Type", "Actions"].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {[
                { name: "July Revenue Report", date: "Jul 29, 2026", by: "AI Auto-generated", type: "Revenue", key: "Revenue Report" },
                { name: "Customer Churn Analysis", date: "Jul 25, 2026", by: authorName, type: "Customer", key: "Customer Report" },
                { name: "Q2 Inventory Summary", date: "Jul 1, 2026", by: authorName, type: "Inventory", key: "Inventory Report" },
                { name: "June Payroll Report", date: "Jun 30, 2026", by: "AI Auto-generated", type: "Employee", key: "Employee Report" },
              ].map(r => (
                <tr key={r.name} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-medium text-slate-800">{r.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{r.date}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{r.by}</td>
                  <td className="px-4 py-3"><Badge label={r.type} variant="info" /></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button onClick={() => setActiveReport(r.key)} className="p-1.5 rounded-lg hover:bg-indigo-50 text-slate-400 hover:text-indigo-600" title="View"><Eye size={13} /></button>
                      <button onClick={handleCSV} className="p-1.5 rounded-lg hover:bg-emerald-50 text-slate-400 hover:text-emerald-600" title="Download CSV"><Download size={13} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Profit Analyzer Page ────────────────────────────────────────────────────

function fmt(n: number) {
  if (n >= 10000000) return "₹" + (n / 10000000).toFixed(2) + "Cr";
  if (n >= 100000) return "₹" + (n / 100000).toFixed(2) + "L";
  return "₹" + n.toLocaleString("en-IN");
}

function profitStatus(margin: number): { label: string; color: string; bg: string } {
  if (margin >= 60) return { label: "Excellent", color: "text-emerald-700", bg: "bg-emerald-50" };
  if (margin >= 40) return { label: "Good", color: "text-indigo-700", bg: "bg-indigo-50" };
  if (margin >= 25) return { label: "Average", color: "text-amber-700", bg: "bg-amber-50" };
  return { label: "Low", color: "text-red-700", bg: "bg-red-50" };
}

const miniTrend = (color: string, up: boolean) => (
  <svg width="56" height="24" viewBox="0 0 56 24">
    <polyline
      points={up ? "0,20 10,16 20,14 30,10 40,7 56,3" : "0,4 10,8 20,10 30,14 40,16 56,20"}
      fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    />
  </svg>
);

function ProfitAnalyzerPage() {
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [productsData, setProductsData] = useState<ProfitProduct[]>([]);

  useEffect(() => {
    api.getProfitProducts()
      .then(data => setProductsData(data))
      .catch(() => { });
  }, []);

  const rows = useMemo(() => {
    const list = productsData.length > 0 ? productsData : [
      { id: 1, name: "Enterprise Suite Pro", category: "Software License", buy: 18500, sell: 26000, qty: 32 },
      { id: 2, name: "Cloud Storage 1TB", category: "Cloud Service", buy: 320, sell: 799, qty: 850 },
      { id: 3, name: "API Access Tokens", category: "Developer Services", buy: 40, sell: 149, qty: 2300 },
      { id: 4, name: "Analytics Dashboard Prem.", category: "Business Intelligence", buy: 1800, sell: 3499, qty: 210 },
      { id: 5, name: "Training Credits", category: "AI Learning Credits", buy: 450, sell: 950, qty: 720 },
      { id: 6, name: "Business Automation Pack", category: "Enterprise Software", buy: 2900, sell: 5499, qty: 125 },
      { id: 7, name: "Workflow AI Assistant", category: "AI Subscription", buy: 1250, sell: 2499, qty: 410 },
      { id: 8, name: "CRM Integration Suite", category: "Business Integration", buy: 3200, sell: 6499, qty: 95 },
      { id: 9, name: "Email Automation Pro", category: "Marketing Automation", buy: 650, sell: 1499, qty: 520 },
      { id: 10, name: "Document AI Processing", category: "AI Document Service", buy: 180, sell: 499, qty: 1450 },
    ];

    return list.map(p => {
      const revenue = p.sell * p.qty;
      const totalCost = p.buy * p.qty;
      const profit = revenue - totalCost;
      const margin = Math.round((profit / Math.max(1, revenue)) * 100);
      return { ...p, revenue, totalCost, profit, margin, status: profitStatus(margin) };
    });
  }, [productsData]);

  const categories = ["All", ...Array.from(new Set(rows.map(r => r.category)))];
  const statusOpts = ["All", "Excellent", "Good", "Average", "Low"];

  const filtered = rows.filter(r => {
    const matchCat = catFilter === "All" || r.category === catFilter;
    const matchStatus = statusFilter === "All" || r.status.label === statusFilter;
    const matchSearch = r.name.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchStatus && matchSearch;
  });

  const totalRevenue = rows.reduce((s, r) => s + r.revenue, 0);
  const totalCost = rows.reduce((s, r) => s + r.totalCost, 0);
  const totalProfit = rows.reduce((s, r) => s + r.profit, 0);
  const avgMargin = Math.round((totalProfit / Math.max(1, totalRevenue)) * 100);

  const monthlyRevenue = [
    { month: "Feb", revenue: 3820000, cost: 2240000, profit: 1580000 },
    { month: "Mar", revenue: 4150000, cost: 2410000, profit: 1740000 },
    { month: "Apr", revenue: 4480000, cost: 2590000, profit: 1890000 },
    { month: "May", revenue: 4920000, cost: 2850000, profit: 2070000 },
    { month: "Jun", revenue: 5310000, cost: 3060000, profit: 2250000 },
    { month: "Jul", revenue: totalRevenue, cost: totalCost, profit: totalProfit },
  ];

  const topProducts = [...rows].sort((a, b) => b.profit - a.profit).slice(0, 5);
  const lowProducts = [...rows].sort((a, b) => a.margin - b.margin).slice(0, 5);
  const marginByProduct = rows.map(r => ({ name: r.name.split(" ").slice(0, 2).join(" "), margin: r.margin }));

  const pieData = [
    { name: "Software", value: rows.filter(r => r.category.includes("Software") || r.category.includes("AI")).reduce((s, r) => s + r.revenue, 0), color: "#4f46e5" },
    { name: "Cloud/Dev", value: rows.filter(r => r.category.includes("Cloud") || r.category.includes("Developer")).reduce((s, r) => s + r.revenue, 0), color: "#8b5cf6" },
    { name: "Marketing", value: rows.filter(r => r.category.includes("Marketing")).reduce((s, r) => s + r.revenue, 0), color: "#06b6d4" },
    { name: "Integration", value: rows.filter(r => r.category.includes("Integration") || r.category.includes("Business")).reduce((s, r) => s + r.revenue, 0), color: "#10b981" },
  ];

  function handleExportCSV() {
    const headers = ["Product", "Category", "Buy Price", "Sell Price", "Qty", "Revenue", "Total Cost", "Profit", "Margin %", "Status"];
    const csvRows = filtered.map(r => [r.name, r.category, r.buy, r.sell, r.qty, r.revenue, r.totalCost, r.profit, r.margin + "%", r.status.label]);
    const csv = [headers, ...csvRows].map(r => r.map(c => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "profit_analysis.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  function handleExportPDF() {
    const date = new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" });
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Profit Analyzer Report</title>
    <style>body{font-family:Arial,sans-serif;margin:40px;color:#1e293b}h1{color:#4f46e5;font-size:22px}
    .meta{color:#64748b;font-size:13px;margin-bottom:24px}.kpi{display:flex;gap:20px;margin-bottom:28px}
    .kpi-card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;flex:1}
    .kpi-card h3{margin:0;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
    .kpi-card p{margin:6px 0 0;font-size:20px;font-weight:700;color:#0f172a}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{background:#f1f5f9;padding:10px 12px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0}
    td{padding:9px 12px;border-bottom:1px solid #f1f5f9}
    .footer{margin-top:32px;font-size:11px;color:#94a3b8;text-align:center}</style></head>
    <body><h1>Profit Analyzer Report</h1>
    <p class="meta">Nexus Commerce Pvt. Ltd &nbsp;|&nbsp; Generated: ${date}</p>
    <div class="kpi">
      <div class="kpi-card"><h3>Total Revenue</h3><p>${fmt(totalRevenue)}</p></div>
      <div class="kpi-card"><h3>Total Cost</h3><p>${fmt(totalCost)}</p></div>
      <div class="kpi-card"><h3>Total Profit</h3><p>${fmt(totalProfit)}</p></div>
      <div class="kpi-card"><h3>Profit Margin</h3><p>${avgMargin}%</p></div>
    </div>
    <table><thead><tr><th>Product</th><th>Category</th><th>Buy</th><th>Sell</th><th>Qty</th><th>Revenue</th><th>Cost</th><th>Profit</th><th>Margin</th><th>Status</th></tr></thead>
    <tbody>${filtered.map(r => `<tr><td>${r.name}</td><td>${r.category}</td><td>₹${r.buy.toLocaleString("en-IN")}</td><td>₹${r.sell.toLocaleString("en-IN")}</td><td>${r.qty.toLocaleString("en-IN")}</td><td>${fmt(r.revenue)}</td><td>${fmt(r.totalCost)}</td><td>${fmt(r.profit)}</td><td>${r.margin}%</td><td>${r.status.label}</td></tr>`).join("")}
    </tbody></table>
    <p class="footer">AI Business Operations Copilot — Confidential</p></body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "Profit_Analyzer_Report.html"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Profit Analyzer</h1>
          <p className="text-sm text-slate-500 mt-1">Analyze revenue, profit, margins, and overall business performance using AI-powered insights.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button onClick={handleExportPDF} className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"><Download size={13} />PDF</button>
          <button onClick={handleExportCSV} className="flex items-center gap-1.5 px-3 py-2 bg-emerald-50 border border-emerald-100 rounded-xl text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"><Download size={13} />Excel</button>
          <GradientButton size="sm" onClick={() => alert("AI Profit Optimizer: Promoting Workflow AI Assistant projected to add ₹18L+ to Q3 bottom line.")}><Sparkles size={13} />AI Profit Analysis</GradientButton>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-6 gap-4">
        {[
          { title: "Total Revenue", value: fmt(totalRevenue), change: "+12.4%", up: true, icon: DollarSign, color: "text-indigo-600", bg: "bg-indigo-50" },
          { title: "Total Cost", value: fmt(totalCost), change: "+8.1%", up: false, icon: ShoppingCart, color: "text-amber-600", bg: "bg-amber-50" },
          { title: "Total Profit", value: fmt(totalProfit), change: "+18.7%", up: true, icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50" },
          { title: "Profit Margin", value: avgMargin + "%", change: "+2.1%", up: true, icon: Activity, color: "text-violet-600", bg: "bg-violet-50" },
          { title: "Profit Status", value: avgMargin >= 50 ? "Excellent" : "Good", change: "Stable", up: true, icon: Award, color: "text-cyan-600", bg: "bg-cyan-50" },
          { title: "Monthly Growth", value: "+12.4%", change: "vs Jun", up: true, icon: BarChart2, color: "text-rose-600", bg: "bg-rose-50" },
        ].map(({ title, value, change, up, icon: Icon, color, bg }) => (
          <div key={title} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{title}</span>
              <div className={`w-8 h-8 rounded-xl ${bg} flex items-center justify-center`}>
                <Icon size={15} className={color} />
              </div>
            </div>
            <p className="text-lg font-bold text-slate-900 leading-none">{value}</p>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-semibold flex items-center gap-1 ${up ? "text-emerald-600" : "text-red-500"}`}>
                {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{change}
              </span>
              {miniTrend(up ? "#10b981" : "#f59e0b", up)}
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Monthly Revenue vs Cost vs Profit</h2>
              <p className="text-xs text-slate-400 mt-0.5">Last 6 months performance</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 inline-block" />Revenue</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />Cost</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />Profit</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={monthlyRevenue}>
              <CartesianGrid key="cg" strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis key="x" dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis key="y" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={v => "₹" + (v / 100000).toFixed(0) + "L"} />
              <Tooltip key="tt" formatter={(v: any) => [fmt(v), ""]} contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #e2e8f0" }} />
              <Area key="revenue" type="monotone" dataKey="revenue" stroke="#4f46e5" strokeWidth={2.5} fill="url(#profit-rev)" dot={false} />
              <Area key="cost" type="monotone" dataKey="cost" stroke="#f59e0b" strokeWidth={2} fill="url(#profit-cost)" dot={false} />
              <Area key="profit" type="monotone" dataKey="profit" stroke="#10b981" strokeWidth={2.5} fill="url(#profit-pft)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-1">Revenue by Category</h2>
          <p className="text-xs text-slate-400 mb-3">Distribution this month</p>
          <ResponsiveContainer width="100%" height={160}>
            <RePieChart>
              <Pie key="pie" data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={72} dataKey="value" paddingAngle={3}>
                {pieData.map((e, i) => <Cell key={"profit-pie-" + i} fill={e.color} />)}
              </Pie>
              <Tooltip key="tt" formatter={(v: any) => [fmt(v), ""]} contentStyle={{ fontSize: 12, borderRadius: 10 }} />
            </RePieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {pieData.map(d => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: d.color }} />{d.name}</span>
                <span className="font-semibold text-slate-700">{fmt(d.value)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Filters + Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100 flex-wrap">
          <h2 className="text-sm font-semibold text-slate-800 flex-1">Product Profit Table</h2>
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2">
            <Search size={13} className="text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search product…" className="bg-transparent text-xs text-slate-700 outline-none w-36 placeholder:text-slate-400" />
          </div>
          <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className="text-xs border border-slate-200 rounded-xl px-3 py-2 text-slate-600 bg-white outline-none focus:ring-2 focus:ring-indigo-500/20 cursor-pointer">
            {categories.map(c => <option key={c}>{c}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="text-xs border border-slate-200 rounded-xl px-3 py-2 text-slate-600 bg-white outline-none focus:ring-2 focus:ring-indigo-500/20 cursor-pointer">
            {statusOpts.map(s => <option key={s}>{s}</option>)}
          </select>
          <button onClick={handleExportCSV} className="flex items-center gap-1.5 px-3 py-2 bg-emerald-50 rounded-xl text-xs font-medium text-emerald-700 hover:bg-emerald-100"><Download size={12} />Export</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-50 bg-slate-50/50">
                {["Product Name", "Category", "Buy Price", "Sell Price", "Qty Sold", "Revenue", "Total Cost", "Profit", "Margin", "Status"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map(r => (
                <tr key={r.name} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center shrink-0">
                        <Layers size={13} className="text-indigo-500" />
                      </div>
                      <span className="text-sm font-medium text-slate-800 whitespace-nowrap">{r.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3.5"><Badge label={r.category} variant="info" /></td>
                  <td className="px-4 py-3.5 text-sm text-slate-600">₹{r.buy.toLocaleString("en-IN")}</td>
                  <td className="px-4 py-3.5 text-sm font-medium text-slate-700">₹{r.sell.toLocaleString("en-IN")}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-600">{r.qty.toLocaleString("en-IN")}</td>
                  <td className="px-4 py-3.5 text-sm font-semibold text-slate-800">{fmt(r.revenue)}</td>
                  <td className="px-4 py-3.5 text-sm text-amber-600">{fmt(r.totalCost)}</td>
                  <td className="px-4 py-3.5 text-sm font-bold text-emerald-600">{fmt(r.profit)}</td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: r.margin + "%", background: r.margin >= 60 ? "#10b981" : r.margin >= 40 ? "#4f46e5" : r.margin >= 25 ? "#f59e0b" : "#ef4444" }} />
                      </div>
                      <span className="text-xs font-semibold text-slate-700">{r.margin}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg ${r.status.bg} ${r.status.color}`}>{r.status.label}</span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 border-t-2 border-slate-200">
                <td className="px-4 py-3 text-xs font-bold text-slate-700" colSpan={5}>Total ({filtered.length} products)</td>
                <td className="px-4 py-3 text-sm font-bold text-slate-800">{fmt(filtered.reduce((s, r) => s + r.revenue, 0))}</td>
                <td className="px-4 py-3 text-sm font-bold text-amber-600">{fmt(filtered.reduce((s, r) => s + r.totalCost, 0))}</td>
                <td className="px-4 py-3 text-sm font-bold text-emerald-600">{fmt(filtered.reduce((s, r) => s + r.profit, 0))}</td>
                <td className="px-4 py-3 text-sm font-bold text-slate-700">{Math.round(filtered.reduce((s, r) => s + r.margin, 0) / Math.max(filtered.length, 1))}% avg</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Notifications Page ───────────────────────────────────────────────────────

function NotificationsPage() {
  const [filter, setFilter] = useState("All");
  const [items, setItems] = useState(notifications);
  const typeIcon: Record<string, any> = { ai: Bot, inventory: Package, payment: CreditCard, customer: Users, revenue: TrendingUp, employee: UserCheck };
  const typeColor: Record<string, string> = { ai: "bg-indigo-100 text-indigo-600", inventory: "bg-amber-100 text-amber-600", payment: "bg-red-100 text-red-600", customer: "bg-violet-100 text-violet-600", revenue: "bg-emerald-100 text-emerald-600", employee: "bg-blue-100 text-blue-600" };
  const filters = ["All", "AI", "Inventory", "Customer", "Payment", "Revenue", "Employee"];
  const filtered = filter === "All" ? items : items.filter(n => n.type === filter.toLowerCase());
  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {filters.map(f => (
            <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${filter === f ? "bg-indigo-500 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"}`}>{f}</button>
          ))}
        </div>
        <button onClick={() => setItems(items.map(i => ({ ...i, read: true })))} className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
          Mark all read
        </button>
      </div>
      <div className="space-y-3">
        {filtered.map(n => {
          const Icon = typeIcon[n.type] || Bell;
          return (
            <div key={n.id} onClick={() => setItems(items.map(i => i.id === n.id ? { ...i, read: true } : i))} className={`bg-white rounded-2xl p-4 border shadow-sm cursor-pointer hover:shadow-md transition-all ${n.read ? "border-slate-100" : "border-indigo-100 shadow-indigo-50"}`}>
              <div className="flex items-start gap-4">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${typeColor[n.type]}`}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <p className={`text-sm font-semibold ${n.read ? "text-slate-600" : "text-slate-900"}`}>{n.title}</p>
                    <span className="text-xs text-slate-400 shrink-0">{n.time}</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{n.desc}</p>
                </div>
                {!n.read && <div className="w-2 h-2 rounded-full bg-indigo-500 shrink-0 mt-1" />}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Toggle Row ──────────────────────────────────────────────────────────────

function ToggleRow({ label, desc, enabled }: { label: string; desc: string; enabled: boolean }) {
  const [on, setOn] = useState(enabled);
  return (
    <div className="flex items-center justify-between p-4 border border-slate-100 rounded-xl">
      <div>
        <p className="text-sm font-medium text-slate-800">{label}</p>
        <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
      </div>
      <button onClick={() => setOn(!on)} className={`w-11 h-6 rounded-full transition-colors ${on ? "bg-indigo-500" : "bg-slate-200"} relative`}>
        <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${on ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </div>
  );
}

// ─── Settings Page ────────────────────────────────────────────────────────────

function SettingsPage({ user }: { user?: UserSession | null }) {
  const [activeSection, setActiveSection] = useState("Company Profile");
  const sections = [
    "Company Profile", "Users & Roles", "Security", "API Keys",
    "AI Preferences", "Notifications", "Billing", "Integrations", "Appearance"
  ];
  return (
    <div className="flex gap-5">
      <div className="w-52 shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm p-3">
        <div className="space-y-0.5">
          {sections.map(s => (
            <button key={s} onClick={() => setActiveSection(s)} className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-colors ${activeSection === s ? "bg-indigo-50 text-indigo-700 font-medium" : "text-slate-600 hover:bg-slate-50"}`}>
              {s}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
        <h2 className="text-base font-semibold text-slate-800 mb-6">{activeSection}</h2>
        {activeSection === "Company Profile" && (
          <div className="space-y-5 max-w-lg">
            <div className="flex items-center gap-5 p-4 bg-slate-50 rounded-2xl">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xl font-bold">{getInitials(user?.company || user?.name || "NC")}</div>
              <div>
                <p className="font-semibold text-slate-800">{user?.company || "Nexus Commerce Pvt. Ltd"}</p>
                <p className="text-sm text-slate-500">{user?.biz_type || "E-commerce"} · Founded 2020</p>
                <button className="text-xs text-indigo-600 mt-1 hover:text-indigo-700">Change logo</button>
              </div>
            </div>
            {[
              { label: "Company Name", value: user?.company || "Nexus Commerce Pvt. Ltd" },
              { label: "Business Type", value: user?.biz_type || "E-commerce" },
              { label: "Website", value: "nexuscommerce.in" },
              { label: "Country", value: "India" },
            ].map(({ label, value }) => (
              <div key={label}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
                <input defaultValue={value} className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300" />
              </div>
            ))}
            <GradientButton onClick={() => alert("Company settings saved successfully!")}><CheckCircle size={14} />Save Changes</GradientButton>
          </div>
        )}
        {activeSection === "Security" && (
          <div className="space-y-4 max-w-lg">
            {[
              { label: "Two-Factor Authentication", desc: "Add an extra layer of security to your account", enabled: true },
              { label: "Single Sign-On (SSO)", desc: "Allow login via your company identity provider", enabled: false },
              { label: "Login Notifications", desc: "Get alerts for new sign-ins to your account", enabled: true },
            ].map(({ label, desc, enabled }) => (
              <ToggleRow key={label} label={label} desc={desc} enabled={enabled} />
            ))}
          </div>
        )}
        {activeSection === "Appearance" && (
          <div className="space-y-5 max-w-lg">
            <div>
              <p className="text-sm font-medium text-slate-700 mb-3">Theme</p>
              <div className="grid grid-cols-3 gap-3">
                {["Light", "Dark", "System"].map(t => (
                  <button key={t} className={`flex flex-col items-center gap-2 p-4 rounded-xl border text-sm font-medium transition-all ${t === "Light" ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
                    {t === "Light" ? <Sun size={18} /> : t === "Dark" ? <Moon size={18} /> : <Cpu size={18} />}
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-700 mb-3">Accent Color</p>
              <div className="flex gap-3">
                {["#4f46e5", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"].map(c => (
                  <button key={c} className="w-8 h-8 rounded-full border-2 border-white shadow" style={{ background: c }} />
                ))}
              </div>
            </div>
          </div>
        )}
        {activeSection === "AI Preferences" && (
          <div className="space-y-4 max-w-lg">
            {[
              { label: "AI Model", options: ["GPT-4o (Recommended)", "Claude 3.5 Sonnet", "FastAPI Random Forest"] },
              { label: "Response Language", options: ["English", "Tamil", "Hindi", "Spanish", "French"] },
            ].map(({ label, options }) => (
              <div key={label}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
                <select className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
                  {options.map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
            ))}
            {[
              { label: "Proactive AI Insights", desc: "Let AI surface insights automatically on your dashboard", enabled: true },
              { label: "AI Action Suggestions", desc: "Show suggested actions based on business data", enabled: true },
              { label: "Voice Input", desc: "Enable microphone for voice-to-text queries", enabled: false },
            ].map(({ label, desc, enabled }) => (
              <ToggleRow key={label} label={label} desc={desc} enabled={enabled} />
            ))}
          </div>
        )}
        {!["Company Profile", "Security", "Appearance", "AI Preferences"].includes(activeSection) && (
          <div className="text-center py-16 text-slate-400">
            <Settings size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm font-medium">{activeSection} settings</p>
            <p className="text-xs mt-1">Configuration options appear here</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Profile Page ─────────────────────────────────────────────────────────────

function ProfilePage({ setPage, user }: { setPage: (p: Page) => void; user: UserSession | null }) {
  const displayName = user?.name || "User";
  const displayEmail = user?.email || (user?.name ? `${user.name.toLowerCase().replace(/\s+/g, '')}@nexuscommerce.in` : "user@nexuscommerce.in");
  const displayCompany = user?.company || "Nexus Commerce Pvt. Ltd";

  return (
    <div className="max-w-4xl space-y-5">
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="h-28 bg-gradient-to-r from-indigo-500 to-violet-600" />
        <div className="px-6 pb-6">
          <div className="flex items-end justify-between -mt-10 mb-5">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-2xl font-bold border-4 border-white shadow-lg">
              {getInitials(displayName)}
            </div>
            <div className="flex gap-2 mt-2">
              <GradientButton variant="outline" size="sm" onClick={() => alert("Profile updated")}><Edit2 size={13} />Edit Profile</GradientButton>
            </div>
          </div>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-800">{displayName}</h2>
              <p className="text-slate-500 text-sm">CEO & Founder · {displayCompany}</p>
              <div className="flex items-center gap-4 mt-3">
                <span className="flex items-center gap-1.5 text-xs text-slate-500"><Mail size={12} />{displayEmail}</span>
                <span className="flex items-center gap-1.5 text-xs text-slate-500"><Phone size={12} />+91 98421 73056</span>
                <span className="flex items-center gap-1.5 text-xs text-slate-500"><MapPin size={12} />Chennai, Tamil Nadu</span>
              </div>
            </div>
            <Badge label="Free Plan" variant="info" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 grid grid-cols-3 gap-4">
          {[
            { label: "Days Active", value: "284", icon: Calendar, color: "bg-indigo-100 text-indigo-600" },
            { label: "AI Queries", value: "1,842", icon: Bot, color: "bg-violet-100 text-violet-600" },
            { label: "Reports Generated", value: "47", icon: BarChart3, color: "bg-emerald-100 text-emerald-600" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm text-center">
              <div className={`w-10 h-10 rounded-xl ${color} flex items-center justify-center mx-auto mb-3`}>
                <Icon size={18} />
              </div>
              <p className="text-2xl font-bold text-slate-800">{value}</p>
              <p className="text-xs text-slate-500 mt-1">{label}</p>
            </div>
          ))}
          <div className="col-span-3 bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Recent Activity</h3>
            <div className="space-y-4">
              {[
                { text: "Generated July Revenue Report", time: "Today, 10:15 AM", icon: BarChart3, color: "text-indigo-500" },
                { text: "Added new customer: Selvaraj Annamalai (Chennai Traders)", time: "Yesterday, 3:22 PM", icon: Users, color: "text-violet-500" },
                { text: "AI Copilot: Sales forecast for Q3", time: "Jul 27, 11:30 AM", icon: Bot, color: "text-cyan-500" },
                { text: "Invoice INV-2026-005 marked as paid — ₹38,500", time: "Jul 26, 4:02 PM", icon: CheckCircle, color: "text-emerald-500" },
              ].map(({ text, time, icon: Icon, color }, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center shrink-0">
                    <Icon size={14} className={color} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-700">{text}</p>
                    <p className="text-xs text-slate-400">{time}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Security</h3>
            <div className="space-y-3">
              {[
                { label: "2FA Enabled", status: true, icon: Shield },
                { label: "Password updated", status: true, icon: Lock },
                { label: "Active devices", value: "2", icon: Cpu },
              ].map(({ label, status, value, icon: Icon }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Icon size={13} className="text-slate-400" />
                    <span className="text-xs text-slate-600">{label}</span>
                  </div>
                  {value ? <span className="text-xs font-semibold text-slate-700">{value}</span> : (
                    <CheckCircle size={14} className={status ? "text-emerald-500" : "text-slate-300"} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Pricing & Billing Page ───────────────────────────────────────────────────

function PricingPage() {
  const [annual, setAnnual] = useState(true);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="bg-gradient-to-r from-indigo-500 to-violet-600 rounded-2xl p-6 text-white">
        <div className="flex items-start justify-between">
          <div>
            <Badge label="Current Plan" variant="default" />
            <h2 className="text-2xl font-bold mt-2">Pro Plan</h2>
            <p className="text-indigo-200 text-sm mt-1">Billed annually · Next renewal: Aug 1, 2026</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-extrabold">$99<span className="text-lg font-normal opacity-80">/mo</span></p>
            <p className="text-indigo-200 text-xs mt-1">$1,188/yr</p>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4 mt-6">
          {[
            { label: "AI Queries Used", value: "1,842 / ∞" },
            { label: "Team Members", value: "6 / 15" },
            { label: "Storage Used", value: "4.2 / 50 GB" },
            { label: "API Calls", value: "28.4K / 100K" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white/10 rounded-xl p-3">
              <p className="text-xs text-indigo-200">{label}</p>
              <p className="text-sm font-semibold mt-1">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-semibold text-slate-800">Available Plans</h2>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium ${!annual ? "text-slate-800" : "text-slate-400"}`}>Monthly</span>
            <button onClick={() => setAnnual(!annual)} className={`w-11 h-6 rounded-full transition-colors relative ${annual ? "bg-indigo-500" : "bg-slate-200"}`}>
              <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${annual ? "translate-x-6" : "translate-x-1"}`} />
            </button>
            <span className={`text-sm font-medium ${annual ? "text-slate-800" : "text-slate-400"}`}>Annual <span className="text-emerald-600">-20%</span></span>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-5">
          {[
            { name: "Starter", price: annual ? 39 : 49, current: false, features: ["3 users", "AI Copilot (100 queries/mo)", "Core modules", "Email support"] },
            { name: "Pro", price: annual ? 99 : 129, current: true, features: ["15 users", "AI Copilot unlimited", "All modules + analytics", "Priority support", "Custom integrations"] },
            { name: "Enterprise", price: annual ? 299 : 379, current: false, features: ["Unlimited users", "Dedicated AI model", "Multi-business", "Dedicated CSM", "SLA & SSO"] },
          ].map(({ name, price, current, features }) => (
            <div key={name} className={`rounded-2xl p-6 border ${current ? "border-indigo-200 bg-indigo-50" : "border-slate-200 bg-white"}`}>
              {current && <Badge label="Current Plan" variant="info" />}
              <h3 className="text-base font-bold text-slate-800 mt-3 mb-1">{name}</h3>
              <p className="text-3xl font-extrabold text-slate-900 mb-4">${price}<span className="text-sm font-normal text-slate-500">/mo</span></p>
              <ul className="space-y-2 mb-6">
                {features.map(f => (
                  <li key={f} className="flex items-center gap-2 text-xs text-slate-600">
                    <CheckCircle size={12} className="text-emerald-500 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              {current ? (
                <button className="w-full py-2.5 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-600 bg-white">Current Plan</button>
              ) : (
                <button onClick={() => alert(`Upgraded to ${name} Plan!`)} className="w-full py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-500 to-violet-600 text-white hover:from-indigo-600 hover:to-violet-700 transition-all">
                  {name === "Starter" ? "Downgrade" : "Upgrade"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Design System Page ───────────────────────────────────────────────────────

function DesignSystemPage() {
  return (
    <div className="max-w-5xl space-y-8">
      <section className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800 mb-5 flex items-center gap-2"><Palette size={15} className="text-indigo-500" />Color Palette</h2>
        <div className="grid grid-cols-2 gap-6">
          {[
            { name: "Primary Scale", colors: [{ name: "Indigo 500", hex: "#4f46e5" }, { name: "Indigo 600", hex: "#4338ca" }, { name: "Violet 500", hex: "#8b5cf6" }, { name: "Violet 600", hex: "#7c3aed" }] },
            { name: "Semantic", colors: [{ name: "Success", hex: "#10b981" }, { name: "Warning", hex: "#f59e0b" }, { name: "Error", hex: "#ef4444" }, { name: "Info", hex: "#06b6d4" }] },
            { name: "Neutrals", colors: [{ name: "Slate 900", hex: "#0f172a" }, { name: "Slate 600", hex: "#475569" }, { name: "Slate 300", hex: "#cbd5e1" }, { name: "Slate 50", hex: "#f8fafc" }] },
            { name: "Gradients", colors: [{ name: "Brand", hex: "linear-gradient(135deg, #4f46e5, #8b5cf6)" }, { name: "Success", hex: "linear-gradient(135deg, #10b981, #06b6d4)" }, { name: "Warm", hex: "linear-gradient(135deg, #f59e0b, #ef4444)" }, { name: "Cool", hex: "linear-gradient(135deg, #06b6d4, #4f46e5)" }] },
          ].map(({ name, colors }) => (
            <div key={name}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">{name}</p>
              <div className="flex gap-2">
                {colors.map(({ name: cname, hex }) => (
                  <div key={cname} className="flex-1">
                    <div className="h-12 rounded-xl mb-1.5" style={{ background: hex }} />
                    <p className="text-xs text-slate-600 text-center truncate">{cname}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ─── Root App Component ───────────────────────────────────────────────────────

export default function App() {
  const [currentUser, setCurrentUser] = useState<UserSession | null>(null);
  const [isAuthChecking, setIsAuthChecking] = useState<boolean>(true);
  const [loginNotice, setLoginNotice] = useState<string | null>(null);
  const [loginEmail, setLoginEmail] = useState<string>("");
  const [page, setPage] = useState<Page>(() => {
    try {
      const savedPage = localStorage.getItem("bizops_active_page") as Page;
      if (savedPage && !["landing", "login", "signup"].includes(savedPage)) {
        return savedPage;
      }
    } catch { }
    return "landing";
  });

  // Verify backend session on mount via HttpOnly cookie and/or Bearer header
  useEffect(() => {
    let isMounted = true;
    api.getCurrentUser()
      .then(res => {
        if (!isMounted) return;
        const validUser = res?.user || (res?.email ? { id: res.id, name: res.name, email: res.email, company: res.company, biz_type: res.biz_type } : null);
        if (validUser) {
          setCurrentUser(validUser);
          const savedPage = localStorage.getItem("bizops_active_page") as Page;
          if (savedPage && !["landing", "login", "signup"].includes(savedPage)) {
            setPage(savedPage);
          } else {
            setPage("dashboard");
          }
        } else {
          setCurrentUser(null);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setCurrentUser(null);
      })
      .finally(() => {
        if (isMounted) {
          setIsAuthChecking(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handlePageChange = (newPage: Page) => {
    setPage(newPage);
    try {
      localStorage.setItem("bizops_active_page", newPage);
    } catch { }
  };

  const handleLoginSuccess = (user: UserSession) => {
    setCurrentUser(user);
    setLoginNotice(null);
    try {
      localStorage.setItem("bizops_active_page", "dashboard");
      localStorage.setItem("bizops_user", JSON.stringify(user));
    } catch { }
    setPage("dashboard");
  };

  const handleLogout = async () => {
    try {
      await api.logoutUser().catch(() => { });
    } catch { }
    setCurrentUser(null);
    setLoginNotice("You have been signed out successfully.");
    try {
      localStorage.removeItem("bizops_active_page");
      localStorage.removeItem("bizops_user");
    } catch { }
    setPage("login");
  };

  // While initial session verification is in progress, show themed loading state
  if (isAuthChecking) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-6" style={{ fontFamily: "'Inter', sans-serif" }}>
        <div className="text-center">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center mx-auto mb-4 animate-pulse">
            <Cpu size={24} className="text-white" />
          </div>
          <p className="text-slate-400 text-sm font-medium flex items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin text-indigo-400" />
            Verifying secure session...
          </p>
        </div>
      </div>
    );
  }

  const publicPages: Page[] = ["landing", "login", "signup"];

  // Route Guard: Unauthenticated users are redirected to login
  if (!currentUser && !publicPages.includes(page)) {
    return (
      <>
        <GradientDefs />
        <LoginPage
          setPage={handlePageChange}
          onLoginSuccess={handleLoginSuccess}
          initialNotice="Please sign in to access your dashboard."
          initialEmail={loginEmail}
        />
      </>
    );
  }

  if (publicPages.includes(page)) {
    return (
      <>
        <GradientDefs />
        {page === "landing" && <LandingPage setPage={handlePageChange} />}
        {page === "login" && (
          <LoginPage
            setPage={handlePageChange}
            onLoginSuccess={handleLoginSuccess}
            initialNotice={loginNotice}
            initialEmail={loginEmail}
          />
        )}
        {page === "signup" && (
          <SignUpPage
            setPage={handlePageChange}
            onRegistered={(newEmail) => {
              setLoginEmail(newEmail);
              setLoginNotice("Account created successfully! Please sign in with your password.");
              handlePageChange("login");
            }}
          />
        )}
      </>
    );
  }

  return (
    <>
      <GradientDefs />
      <AppLayout page={page} setPage={handlePageChange} user={currentUser} onLogout={handleLogout}>
        {page === "dashboard" && <DashboardPage setPage={handlePageChange} user={currentUser} />}
        {page === "business-health" && <BusinessHealthPage setPage={handlePageChange} />}
        {page === "action-center" && <ActionCenterPage setPage={handlePageChange} />}
        {page === "copilot" && <AICopilotPage />}
        {page === "customers" && <CustomersPage />}
        {page === "sales" && <SalesPage />}
        {page === "inventory" && <InventoryPage />}
        {page === "invoices" && <InvoicesPage />}
        {page === "employees" && <EmployeesPage />}
        {page === "reports" && <ReportsPage user={currentUser} />}
        {page === "notifications" && <NotificationsPage />}
        {page === "settings" && <SettingsPage user={currentUser} />}
        {page === "profile" && <ProfilePage setPage={handlePageChange} user={currentUser} />}
        {page === "pricing" && <PricingPage />}
        {page === "design-system" && <DesignSystemPage />}
        {page === "profit" && <ProfitAnalyzerPage />}
      </AppLayout>
    </>
  );
}

