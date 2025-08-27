#!/usr/bin/env python3
import sys
import csv
import os

def process_csv(input_file):
    output_file = os.path.join(os.path.dirname(input_file), "meta_audience_whametrics.csv")

    with open(input_file, newline='', encoding='utf-8-sig') as infile, \
         open(output_file, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        fieldnames = ['phone', 'country', 'fn', 'ln']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in reader:
            phone = row.get('phone', '')
            country = row.get('country', '')
            name = row.get('name', '')

            if name:
                parts = name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
            else:
                first_name, last_name = "", ""

            writer.writerow({
                'phone': phone,
                'country': country,
                'fn': first_name,
                'ln': last_name
            })

    print(f"✅ Processed file saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ~/twist/scripts/process_whametrics.py <whametrics_file.csv>")
        sys.exit(1)

    process_csv(sys.argv[1])
