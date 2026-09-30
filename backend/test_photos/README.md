# test_photos — OCR test dataset

## How to fill ground_truth.csv

Each row corresponds to one medicine pack photo in this folder.

| Column   | Example        | Notes                                  |
|----------|----------------|----------------------------------------|
| filename | dolo_front.jpg | Exact filename in this folder          |
| name     | Dolo 650       | Brand name as printed on the strip     |
| batch    | 24B901         | Batch number exactly as printed        |
| expiry   | 11/2026        | MM/YYYY as printed (or MM/YY → MM/YYYY)|

## Steps
1. Copy medicine pack photos into this folder.
2. Open ground_truth.csv in a spreadsheet.
3. Add one row per photo with what is printed on the pack.
4. Run: python scripts/ocr_test.py --photos test_photos/ --gt test_photos/ground_truth.csv
5. Review ocr_report.csv for mismatches.

## Goal
Aim for ≥ 85% accuracy on batch and expiry fields.
