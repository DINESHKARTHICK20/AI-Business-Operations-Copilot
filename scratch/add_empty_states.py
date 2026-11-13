import os

APP_FILE = r"d:\My Projects\AI Business Operations Copilot\src\app\App.tsx"

with open(APP_FILE, "r", encoding="utf-8") as f:
    text = f.read()

# 1. CustomersPage table view empty state
target_cust_table = """                <tbody className="divide-y divide-slate-50">
                  {filteredCustomers.map(c => (
                    <tr
                      key={c.id}
                      onClick={() => handleSelectCustomer(c)}
                      className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === c.id ? "bg-indigo-50/50" : ""}`}
                    >"""

replacement_cust_table = """                <tbody className="divide-y divide-slate-50">
                  {filteredCustomers.length > 0 ? (
                    filteredCustomers.map(c => (
                      <tr
                        key={c.id}
                        onClick={() => handleSelectCustomer(c)}
                        className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === c.id ? "bg-indigo-50/50" : ""}`}
                      >"""

text = text.replace(target_cust_table, replacement_cust_table)

target_cust_table_end = """                      </td>
                    </tr>
                  ))}
                </tbody>"""

replacement_cust_table_end = """                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                      <Users size={32} className="mx-auto mb-2 text-slate-300" />
                      <p className="text-sm font-medium text-slate-600">No customers found</p>
                      <p className="text-xs text-slate-400 mt-1">Get started by adding your first business customer.</p>
                      <button onClick={openAddModal} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                        <Plus size={14} /> Add Customer
                      </button>
                    </td>
                  </tr>
                )}
                </tbody>"""

text = text.replace(target_cust_table_end, replacement_cust_table_end)

# 2. CustomersPage cards view empty state
target_cust_cards = """          ) : (
            <div className="grid grid-cols-2 gap-4 p-5">
              {filteredCustomers.map(c => ("""

replacement_cust_cards = """          ) : (
            <div className="grid grid-cols-2 gap-4 p-5">
              {filteredCustomers.length > 0 ? (
                filteredCustomers.map(c => ("""

text = text.replace(target_cust_cards, replacement_cust_cards)

target_cust_cards_end = """                  </div>
                </div>
              ))}
            </div>
          )}"""

replacement_cust_cards_end = """                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-2 py-12 text-center text-slate-400">
                <Users size={32} className="mx-auto mb-2 text-slate-300" />
                <p className="text-sm font-medium text-slate-600">No customers found</p>
                <p className="text-xs text-slate-400 mt-1">Get started by adding your first business customer.</p>
                <button onClick={openAddModal} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                  <Plus size={14} /> Add Customer
                </button>
              </div>
            )}
            </div>
          )}"""

text = text.replace(target_cust_cards_end, replacement_cust_cards_end)

# 3. InventoryPage table empty state
target_inv_table = """              <tbody className="divide-y divide-slate-50">
                {filtered.map(p => (
                  <tr
                    key={p.id}
                    onClick={() => handleSelectProduct(p)}
                    className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === p.id ? "bg-indigo-50/50" : ""}`}
                  >"""

replacement_inv_table = """              <tbody className="divide-y divide-slate-50">
                {filtered.length > 0 ? (
                  filtered.map(p => (
                    <tr
                      key={p.id}
                      onClick={() => handleSelectProduct(p)}
                      className={`hover:bg-slate-50 cursor-pointer transition-colors ${selected?.id === p.id ? "bg-indigo-50/50" : ""}`}
                    >"""

text = text.replace(target_inv_table, replacement_inv_table)

target_inv_table_end = """                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>"""

replacement_inv_table_end = """                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="px-5 py-12 text-center text-slate-400">
                    <Package size={32} className="mx-auto mb-2 text-slate-300" />
                    <p className="text-sm font-medium text-slate-600">No products cataloged</p>
                    <p className="text-xs text-slate-400 mt-1">Add catalog items to manage stock and forecast demand.</p>
                    <button onClick={openAddModal} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                      <Plus size={14} /> Add Product
                    </button>
                  </td>
                </tr>
              )}
              </tbody>"""

text = text.replace(target_inv_table_end, replacement_inv_table_end)

# 4. InvoicesPage table empty state
target_invoice_table = """              <tbody className="divide-y divide-slate-50">
                {filtered.map(inv => (
                  <tr
                    key={inv.id}
                    onClick={() => setPreview(inv)}
                    className={`hover:bg-slate-50 cursor-pointer transition-colors ${preview?.id === inv.id ? "bg-indigo-50/50" : ""}`}
                  >"""

replacement_invoice_table = """              <tbody className="divide-y divide-slate-50">
                {filtered.length > 0 ? (
                  filtered.map(inv => (
                    <tr
                      key={inv.id}
                      onClick={() => setPreview(inv)}
                      className={`hover:bg-slate-50 cursor-pointer transition-colors ${preview?.id === inv.id ? "bg-indigo-50/50" : ""}`}
                    >"""

text = text.replace(target_invoice_table, replacement_invoice_table)

target_invoice_table_end = """                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>"""

replacement_invoice_table_end = """                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                    <FileText size={32} className="mx-auto mb-2 text-slate-300" />
                    <p className="text-sm font-medium text-slate-600">No invoices issued</p>
                    <p className="text-xs text-slate-400 mt-1">Create an invoice to bill clients and automatically decrement stock.</p>
                    <button onClick={openCreateModal} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                      <Plus size={14} /> New Invoice
                    </button>
                  </td>
                </tr>
              )}
              </tbody>"""

text = text.replace(target_invoice_table_end, replacement_invoice_table_end)

# 5. EmployeesPage table empty state
target_emp_table = """            <tbody className="divide-y divide-slate-50">
              {filtered.map(e => (
                <tr key={e.id} onClick={() => setSelected(selected?.id === e.id ? null : e)} className={`hover:bg-slate-50 transition-colors cursor-pointer ${selected?.id === e.id ? "bg-indigo-50/50" : ""}`}>"""

replacement_emp_table = """            <tbody className="divide-y divide-slate-50">
              {filtered.length > 0 ? (
                filtered.map(e => (
                  <tr key={e.id} onClick={() => setSelected(selected?.id === e.id ? null : e)} className={`hover:bg-slate-50 transition-colors cursor-pointer ${selected?.id === e.id ? "bg-indigo-50/50" : ""}`}>"""

text = text.replace(target_emp_table, replacement_emp_table)

target_emp_table_end = """                    </div>
                  </td>
                </tr>
              ))}
            </tbody>"""

replacement_emp_table_end = """                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="px-5 py-12 text-center text-slate-400">
                  <UserCheck size={32} className="mx-auto mb-2 text-slate-300" />
                  <p className="text-sm font-medium text-slate-600">No employees listed</p>
                  <p className="text-xs text-slate-400 mt-1">Onboard employees to track attendance and team performance.</p>
                  <button onClick={openAddModal} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                    <Plus size={14} /> Add Employee
                  </button>
                </td>
              </tr>
            )}
            </tbody>"""

text = text.replace(target_emp_table_end, replacement_emp_table_end)

with open(APP_FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("Added clean empty states to Customers, Inventory, Invoices, and Employees!")

