from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
raw=pd.read_csv(ROOT/"data/jobs_in_data.csv")
us=raw.loc[raw.company_location.eq("United States") & raw.employee_residence.eq("United States")]
audit=json.loads((ROOT/"results/data_quality.json").read_text())
assert audit["us_records"]==len(us)
assert audit["us_records_without_exact_repeats"]==len(us.drop_duplicates())
years=pd.read_csv(ROOT/"results/tables/year_summary.csv")
assert years.records.sum()==len(us)
exp=pd.read_csv(ROOT/"results/tables/experience_summary.csv")
for row in exp.itertuples():
    subset=us.loc[us.experience_level.eq(row.experience_level)].salary_in_usd
    assert row.records==len(subset) and row.median==subset.median()
comparison=pd.read_csv(ROOT/"results/tables/year_over_year.csv")
for row in comparison.itertuples():
    for year in [2022,2023]:
        subset=us.loc[us.employment_type.eq("Full-time") & us.work_year.eq(year) & us.experience_level.eq(row.experience_level) & us.work_setting.eq(row.work_setting)]
        value=getattr(row,f"median_{year}")
        assert (pd.isna(value) and len(subset)==0) or value==subset.salary_in_usd.median()
assert len(list((ROOT/"results/plots").glob("*.png")))==8
for p in (ROOT/"results/plots").glob("*.png"): assert p.read_bytes().startswith(b"\x89PNG")
assert "Plotly.newPlot" in (ROOT/"results/job_distribution.html").read_text()
assert len(list((ROOT/"results/tables").glob("*.csv")))==8
print("Verified summaries against source data, unavailable groups, 8 tables, 8 PNG charts, and interactive HTML.")
