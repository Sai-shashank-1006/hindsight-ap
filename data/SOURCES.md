# Data sources

| File | Source | Real or made up |
|---|---|---|
| `demo_scenario.json`, `test_invoices.json`, `vendors.json`, `purchase_orders.json` | Written for this project | Illustrative: vendor names, prices and dates are invented for the demo story |
| `real/invoices.json`, `real/purchase_orders.json`, `real/vendors.json` | Built by `download_real_data.py` from the dataset below | Real purchase lines; see "What is derived" |

## External datasets

### Supply Chain Shipment Pricing Data (USAID SCMS Delivery History)

- **Name:** Supply Chain Shipment Pricing Dataset (Supply Chain Management System delivery history, 2006-2015)
- **Publisher:** USAID, from the PEPFAR-funded Supply Chain Management System (SCMS) project
- **Original URL:** https://data.usaid.gov/HIV-AIDS/Supply-Chain-Shipment-Pricing-Dataset/a3rc-nmf6/data
- **License:** CC BY, with attribution to the partner (as stated on USAID's Development Data Library listing).
  Attribution: *USAID / Partnership for Supply Chain Management, SCMS Delivery History Dataset.*
- **Mirrors the script downloads from** (they add no rights of their own; the original's license governs):
  - Kaggle `apoorvwatsky/supply-chain-shipment-pricing-data`: https://www.kaggle.com/datasets/apoorvwatsky/supply-chain-shipment-pricing-data
    (Kaggle license field: "Data files © Original Authors")
  - Kaggle `divyeshardeshana/supply-chain-shipment-pricing-data`: https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data
    (Kaggle license field: "Unknown")
  - GitHub `jrcinco/supply-chain-shipment-price-data`: https://github.com/jrcinco/supply-chain-shipment-price-data
    (no license file)

What is real: vendor, item, price per pack, quantity and delivery date of each line, traceable through
`source_ref`. What is derived: the dataset has one price per line, so each PO record's price is the
vendor's contract price for that item (the price it billed most often in the period); prices are
converted from USD at ₹83/USD. Only lines sold directly by Indian manufacturers are kept.
