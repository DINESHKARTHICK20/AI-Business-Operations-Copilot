import os
import re

APP_FILE = r"d:\My Projects\AI Business Operations Copilot\src\app\App.tsx"

with open(APP_FILE, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Clear top-level fallback constants
old_fallbacks_start = "// ─── Fallback Initial Data ───────────────────────────────────────────────────"
old_fallbacks_end = "// ─── Shared Components ───────────────────────────────────────────────────────"

new_fallbacks = """// ─── Initial Dynamic Defaults ────────────────────────────────────────────────

const initialRevenueData: Array<{ month: string; revenue: number; expenses: number; profit: number }> = [];
const initialDailyData: Array<{ day: string; sales: number; orders: number }> = [];
const initialCustomerGrowth: Array<{ month: string; new: number; returning: number }> = [];
const initialProductPieData: Array<{ name: string; value: number; color: string }> = [];

const fallbackCustomers: Customer[] = [];
const fallbackProducts: Product[] = [];
const fallbackInvoices: Invoice[] = [];
const fallbackEmployees: Employee[] = [];
const notifications: Array<{ id: number; type: string; title: string; desc: string; time: string; read: boolean }> = [];

const chatHistory = [
  { id: 1, title: "Operations Overview", time: "Today" },
  { id: 2, title: "Inventory Restock Planning", time: "Yesterday" },
  { id: 3, title: "Customer Churn Analysis", time: "This week" }
];

const suggestedPrompts = [
  "Show today's revenue breakdown",
  "Predict customer churn risks",
  "Which products need restocking?",
  "Show employee team performance",
  "Summarize active invoices"
];

"""

if old_fallbacks_start in text and old_fallbacks_end in text:
    p1 = text.split(old_fallbacks_start)[0]
    p2 = text.split(old_fallbacks_end)[1]
    text = p1 + old_fallbacks_start + "\n\n" + new_fallbacks + old_fallbacks_end + p2
    print("Replaced top-level fallback constants.")
else:
    print("WARNING: Top-level fallback marker not matched!")

# 2. Fix DashboardPage: fallback KPIs, fallbackActivity, lowStockItems, insights
text = re.sub(
    r'const fallbackKpis = \{[^}]+\};',
    '''const fallbackKpis = {
    today_revenue: "₹0", today_revenue_change: "0%",
    monthly_revenue: "₹0", monthly_revenue_change: "0%",
    active_customers: "0", active_customers_change: "0%",
    pending_orders: "0", pending_orders_change: "0",
    inventory_health: "0%", inventory_health_change: "0%",
    business_health: "0/100",
    business_health_change: "No Data"
  };''',
    text
)

text = text.replace(
    '''  const lowStockItems = stats?.low_stock_alerts && stats.low_stock_alerts.length > 0
    ? stats.low_stock_alerts.slice(0, 3)
    : fallbackProducts.filter(p => p.status !== "In Stock").slice(0, 3);''',
    '''  const lowStockItems = stats?.low_stock_alerts || [];'''
)

text = text.replace(
    '''            {(activity.length > 0 ? activity : fallbackActivity).map(({ text, time, color }, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-slate-50 flex items-center justify-center shrink-0">
                  <Activity size={13} className={color} />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-slate-700 leading-relaxed">{text}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{time}</p>
                </div>
              </div>
            ))}''',
    '''            {activity.length > 0 ? (
              activity.map(({ text, time, color }, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-slate-50 flex items-center justify-center shrink-0">
                    <Activity size={13} className={color} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-700 leading-relaxed">{text}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{time}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-slate-400">
                <Activity size={22} className="mx-auto mb-2 text-slate-300" />
                <p className="text-xs">No recent activity recorded.</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Actions you take will be logged here.</p>
              </div>
            )}'''
)

text = text.replace(
    '''            {(insights.length > 0 ? insights : [
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
            })}''',
    '''            {insights.length > 0 ? (
              insights.map(({ text, type }, i) => {
                const colors: Record<string, string> = {
                  positive: "text-emerald-700 bg-emerald-50 border-emerald-200",
                  warning: "text-amber-700 bg-amber-50 border-amber-200",
                  danger: "text-red-600 bg-red-50 border-red-200",
                  info: "text-indigo-700 bg-indigo-50 border-indigo-200"
                };
                return (
                  <div key={i} className={`text-xs p-3 rounded-xl border ${colors[type] || colors.info} leading-relaxed`}>
                    {text}
                  </div>
                );
              })
            ) : (
              <div className="text-xs p-4 rounded-xl border border-indigo-200 bg-white/70 text-slate-500 text-center">
                <Sparkles size={20} className="mx-auto mb-2 text-indigo-400" />
                Add your business records to unlock automated AI insights.
              </div>
            )}'''
)

# 3. Fix AICopilotPage initial messages and error catch
text = text.replace(
    '''  const [messages, setMessages] = useState<Array<{ role: string; content: string; chart?: boolean }>>([
    { role: "ai", content: "Hi! I'm your AI Business Copilot. I have full access to your business data — revenue, customers, inventory, invoices, and more. Ask me anything or let me surface insights for you.\\n\\n**Here's what I found this morning:**\\n- Today's revenue is already **₹7,02,500** (+23% vs yesterday)\\n- 3 customers are at churn risk — want me to draft outreach emails?\\n- Analytics Dashboard SKU is critically low — shall I create a restock order?" },
    { role: "user", content: "Show me today's revenue breakdown" },
    { role: "ai", content: "Here's your revenue breakdown for today (July 29, 2026):\\n\\n**Total: ₹7,02,500**\\n\\n| Category | Amount | % of Total |\\n|---|---|---|\\n| Software | ₹2,66,550 | 38% |\\n| Services | ₹1,75,625 | 25% |\\n| Hardware | ₹1,47,525 | 21% |\\n| Training | ₹1,12,400 | 16% |\\n\\nThe software spike is driven by 2 Enterprise Suite Pro renewals. Services are running 31% above your weekly average — the new API package is performing well.", chart: true },
  ]);''',
    '''  const [messages, setMessages] = useState<Array<{ role: string; content: string; chart?: boolean }>>([
    {
      role: "ai",
      content: "Hello! I am your AI Business Operations Copilot. I have real-time access to your private database — customers, inventory, invoices, and performance.\\n\\nAsk me about your current revenue, customer churn risk, inventory restocking, or team performance."
    }
  ]);'''
)

text = text.replace(
    '''      setMessages(prev => [...prev, {
        role: "ai",
        content: `I've analyzed your request for: **"${textToSend}"**\\n\\n- Current Revenue tracking at **₹52.8L** (+12% MoM)\\n- Top revenue contributor: Software (38%)\\n- At-risk accounts: Gowrishankar Venkatesh & Rajendhiran Palaniswamy\\n\\nWould you like me to generate a full operational report?`
      }]);''',
    '''      setMessages(prev => [...prev, {
        role: "ai",
        content: `Unable to complete query for "${textToSend}". Please ensure the backend server is reachable.`
      }]);'''
)

# 4. Fix CustomersPage state initialization & default form values
text = text.replace(
    'const [customersList, setCustomersList] = useState<Customer[]>(fallbackCustomers);',
    'const [customersList, setCustomersList] = useState<Customer[]>([]);'
)
text = text.replace(
    '''  const [ltv, setLtv] = useState("₹10,00,000");
  const [orders, setOrders] = useState(20);''',
    '''  const [ltv, setLtv] = useState("₹0");
  const [orders, setOrders] = useState(0);'''
)

# 5. Fix InventoryPage state initialization
text = text.replace(
    'const [productsList, setProductsList] = useState<Product[]>(fallbackProducts);',
    'const [productsList, setProductsList] = useState<Product[]>([]);'
)

# 6. Fix InvoicesPage state initialization & dependencies
text = text.replace(
    '''  const [invoicesList, setInvoicesList] = useState<Invoice[]>(fallbackInvoices);
  const [customersList, setCustomersList] = useState<Customer[]>(fallbackCustomers);
  const [productsList, setProductsList] = useState<Product[]>(fallbackProducts);''',
    '''  const [invoicesList, setInvoicesList] = useState<Invoice[]>([]);
  const [customersList, setCustomersList] = useState<Customer[]>([]);
  const [productsList, setProductsList] = useState<Product[]>([]);'''
)

text = text.replace(
    '''    api.getCustomers()
      .then(custs => {
        if (custs && custs.length > 0) setCustomersList(custs);
      })
      .catch(() => { });

    api.getInventory()
      .then(prods => {
        if (prods && prods.length > 0) setProductsList(prods);
      })
      .catch(() => { });''',
    '''    api.getCustomers()
      .then(custs => setCustomersList(custs || []))
      .catch(() => setCustomersList([]));

    api.getInventory()
      .then(prods => setProductsList(prods || []))
      .catch(() => setProductsList([]));'''
)

text = text.replace(
    'const defaultCust = customersList[0]?.company || customersList[0]?.name || "TechCorp India Pvt. Ltd";',
    'const defaultCust = customersList[0]?.company || customersList[0]?.name || "";'
)

# 7. Fix InvoicesPage hardcoded KPI values
text = text.replace(
    '''      <div className="grid grid-cols-4 gap-4">
        {[
          { title: "Total Invoiced", value: "₹4,39,600", change: "+15%", icon: FileText, color: "bg-indigo-500" },
          { title: "Paid", value: "₹1,60,200", change: "+22%", icon: CheckCircle, color: "bg-emerald-500" },
          { title: "Pending", value: "₹2,52,800", change: "-3%", icon: Clock, color: "bg-amber-500" },
          { title: "Overdue", value: "₹26,600", change: "+1", icon: AlertTriangle, color: "bg-red-500" },
        ].map(c => <KPICard key={c.title} {...c} />)}
      </div>''',
    '''      <div className="grid grid-cols-4 gap-4">
        {(() => {
          const totalInvoiced = invoicesList.reduce((s, i) => s + (i.amount_num || parsePriceNum(i.amount)), 0);
          const totalPaid = invoicesList.filter(i => i.status === "Paid").reduce((s, i) => s + (i.amount_num || parsePriceNum(i.amount)), 0);
          const totalPending = invoicesList.filter(i => i.status === "Pending").reduce((s, i) => s + (i.amount_num || parsePriceNum(i.amount)), 0);
          const totalOverdue = invoicesList.filter(i => i.status === "Overdue").reduce((s, i) => s + (i.amount_num || parsePriceNum(i.amount)), 0);
          return [
            { title: "Total Invoiced", value: `₹${totalInvoiced.toLocaleString("en-IN")}`, change: `${invoicesList.length} total`, icon: FileText, color: "bg-indigo-500" },
            { title: "Paid", value: `₹${totalPaid.toLocaleString("en-IN")}`, change: `${invoicesList.filter(i => i.status === "Paid").length} paid`, icon: CheckCircle, color: "bg-emerald-500" },
            { title: "Pending", value: `₹${totalPending.toLocaleString("en-IN")}`, change: `${invoicesList.filter(i => i.status === "Pending").length} pending`, icon: Clock, color: "bg-amber-500" },
            { title: "Overdue", value: `₹${totalOverdue.toLocaleString("en-IN")}`, change: `${invoicesList.filter(i => i.status === "Overdue").length} overdue`, icon: AlertTriangle, color: "bg-red-500" },
          ];
        })().map(c => <KPICard key={c.title} {...c} />)}
      </div>'''
)

# 8. Fix EmployeesPage state initialization
text = text.replace(
    'const [employeesList, setEmployeesList] = useState<Employee[]>(fallbackEmployees);',
    'const [employeesList, setEmployeesList] = useState<Employee[]>([]);'
)

# 9. Fix ProfitAnalyzerPage fallback to fake items
text = text.replace(
    '''    const list = productsData.length > 0 ? productsData : [
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
    ];''',
    '''    const list = productsData;'''
)

# 10. Fix NotificationsPage to connect to real API
text = text.replace(
    '''function NotificationsPage() {
  const [filter, setFilter] = useState("All");
  const [items, setItems] = useState(notifications);''',
    '''function NotificationsPage() {
  const [filter, setFilter] = useState("All");
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    api.getNotifications()
      .then(data => setItems(data || []))
      .catch(() => setItems([]));
  }, []);'''
)

text = text.replace(
    '''        <button onClick={() => setItems(items.map(i => ({ ...i, read: true })))} className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
          Mark all read
        </button>''',
    '''        <button onClick={async () => {
          try {
            await api.markAllNotificationsRead();
            setItems(items.map(i => ({ ...i, read: true })));
          } catch {}
        }} className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
          Mark all read
        </button>'''
)

text = text.replace(
    '''            <div key={n.id} onClick={() => setItems(items.map(i => i.id === n.id ? { ...i, read: true } : i))} className={`bg-white rounded-2xl p-4 border shadow-sm cursor-pointer hover:shadow-md transition-all ${n.read ? "border-slate-100" : "border-indigo-100 shadow-indigo-50"}`}>''',
    '''            <div key={n.id} onClick={async () => {
              try {
                await api.markNotificationRead(n.id);
                setItems(items.map(i => i.id === n.id ? { ...i, read: true } : i));
              } catch {}
            }} className={`bg-white rounded-2xl p-4 border shadow-sm cursor-pointer hover:shadow-md transition-all ${n.read ? "border-slate-100" : "border-indigo-100 shadow-indigo-50"}`}>'''
)

with open(APP_FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated src/app/App.tsx successfully!")

