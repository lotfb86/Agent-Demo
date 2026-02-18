# Financial Reporting Agent — Skills

## Report Types
- **P&L Reports**: Division-level or company-wide profit & loss with revenue, COGS breakdown, gross profit, operating expenses, and net income
- **Period Comparisons**: Year-over-year or quarter-over-quarter with dollar and percentage variance
- **Expense Analysis**: Drill into specific cost lines (fuel, labor, materials, subcontractor) across divisions
- **Job Costing**: Project-level cost reports showing contract value, costs-to-date, percent complete, and margin
- **AR Aging Analysis**: Accounts receivable aging buckets, DSO calculation, collections priority
- **Backlog Reports**: Contracted backlog by division, 12-month burn rate, pipeline analysis
- **Cash Flow**: Operating cash in/out, capital expenditures, net cash flow trend, ending balance
- **Margin Analysis**: Quarterly gross and net margin trends, division-level margin comparison
- **Budget Variance**: Actual vs. budget by GL line, highlighting over/under items
- **KPI Dashboard**: Executive overview with key metrics, targets, and trend indicators

## Chart Types
- Bar charts for division comparisons and budget variance
- Line charts for trend analysis (margins, revenue, cash flow)
- Pie charts for composition analysis (AR aging buckets, revenue mix)
- Stacked bar for multi-dimensional breakdowns

## Quality Standards
- All numbers are computed deterministically in Python — never hallucinated
- Reports include 2-4 sections (mix of kpi_grid, table, chart, narrative)
- Executive narratives highlight actionable insights and anomalies
- Currency values are raw numbers; formatting handled by the frontend
