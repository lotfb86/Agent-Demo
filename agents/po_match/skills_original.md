# PO Match Agent - Skills & Procedures

## Core Matching Process
For each invoice in queue:
1. Read the invoice PDF and extract vendor, amount, PO reference, and line items.
2. If PO reference exists, search purchase orders by exact number.
3. If no PO reference, fuzzy match using vendor name + exact amount.
4. If PO match is found, compare invoice amount to PO amount.
5. If variance is <= 2%, assign coding and mark complete.
6. If variance is > 2%, create a price variance exception.
7. Check for duplicate usage of the same PO before completion.
8. Post approved invoices to Vista.

## Exception Handling
- Price variance: route to review queue with variance amount and percentage.
- No PO found: route to Randy Eisenhardt for review.
- Duplicate detected: route to review queue as potential duplicate.

## Notifications
Send a daily summary to AP manager after queue completion.
