"""Reproduce the U.S. salary analysis and exported outputs."""
from pathlib import Path
import json, hashlib
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results/tables"
PLOTS = ROOT / "results/plots"
ORDER = ["Entry-level", "Mid-level", "Senior", "Executive"]

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(ROOT / "data/jobs_in_data.csv")
    required = {"work_year", "salary_in_usd", "company_location", "employee_residence", "experience_level", "work_setting", "job_category", "employment_type"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Missing columns: {required - set(raw.columns)}")
    if raw[list(required)].isna().any().any():
        raise ValueError("Required fields contain missing values")
    if not pd.api.types.is_numeric_dtype(raw.salary_in_usd) or (raw.salary_in_usd <= 0).any():
        raise ValueError("USD salaries must be positive numeric values")
    if not set(raw.experience_level).issubset(ORDER):
        raise ValueError("Unrecognized experience level")
    us = raw.loc[raw.company_location.eq("United States") & raw.employee_residence.eq("United States")].copy()
    dedup = us.drop_duplicates(subset=raw.columns)
    if us.empty: raise ValueError("No U.S. records")
    audit = {"input_sha256": hashlib.sha256((ROOT / "data/jobs_in_data.csv").read_bytes()).hexdigest(), "raw_records": len(raw), "columns": len(raw.columns), "missing_values": int(raw.isna().sum().sum()), "global_exact_repeats": int(raw.duplicated().sum()), "us_records": len(us), "us_exact_repeats": int(us.duplicated().sum()), "us_records_without_exact_repeats": len(dedup), "years": sorted(map(int,us.work_year.unique())), "us_salary_currency_counts": us.salary_currency.value_counts().to_dict(), "us_salary_vs_usd_mismatches": int(us.salary.ne(us.salary_in_usd).sum())}
    (ROOT / "results/data_quality.json").write_text(json.dumps(audit,indent=2)+"\n")
    def summary(frame, group):
        return frame.groupby(group).salary_in_usd.agg(records="size", median="median", mean="mean").reset_index()
    years = summary(us,"work_year")
    years["share_percent"] = years.records / len(us)*100
    experience = summary(us,"experience_level").set_index("experience_level").reindex(ORDER).reset_index()
    settings = summary(us,"work_setting")
    categories = summary(us,"job_category").sort_values("median",ascending=False)
    cs = summary(us,["job_category","work_setting"])
    full = us.loc[us.employment_type.eq("Full-time") & us.work_year.isin([2022,2023])]
    comparison = summary(full,["experience_level","work_setting","work_year"]).pivot(index=["experience_level","work_setting"],columns="work_year",values=["records","median"])
    comparison.columns = [f"{a}_{b}" for a,b in comparison.columns]
    comparison = comparison.reset_index()
    comparison["change_percent"] = (comparison.median_2023 / comparison.median_2022-1)*100
    comparison["small_sample"] = comparison.records_2022.fillna(0).lt(30) | comparison.records_2023.fillna(0).lt(30)
    sensitivity = []
    for label,frame in [("all_records",us),("exact_repeats_removed",dedup)]:
        sensitivity.append({"sample":label,"group_type":"overall","group":"All","records":len(frame),"median":frame.salary_in_usd.median(),"mean":frame.salary_in_usd.mean()})
        for group in ["experience_level","work_setting","job_category","work_year"]:
            for row in summary(frame,group).to_dict("records"):
                sensitivity.append({"sample":label,"group_type":group,"group":str(row.pop(group)),**row})
    sens = pd.DataFrame(sensitivity)
    overall = us.salary_in_usd.describe().rename_axis("statistic").reset_index(name="value")
    for name,table in {"year_summary":years,"experience_summary":experience,"work_setting_summary":settings,"category_summary":categories,"category_work_setting_summary":cs,"year_over_year":comparison,"duplicate_sensitivity":sens,"overall_summary":overall}.items():
        table.to_csv(TABLES / f"{name}.csv",index=False)
    sns.set_theme(style="whitegrid",palette="colorblind")
    def save(name):
        plt.tight_layout(); plt.savefig(PLOTS / name,dpi=160,bbox_inches="tight"); plt.close()
    plt.figure(figsize=(9,4)); sns.barplot(data=years,x="work_year",y="records",color="#2878a0")
    plt.title("U.S. sample is concentrated in 2023"); plt.xlabel("Year"); plt.ylabel("Records"); save("records_by_year.png")
    plt.figure(figsize=(10,5)); sns.boxplot(data=us,x="experience_level",y="salary_in_usd",order=ORDER,color="#75b7c8")
    plt.title("Salary distributions by experience level"); plt.xlabel("Experience level"); plt.ylabel("Annual salary (nominal USD)"); save("salary_by_experience.png")
    plt.figure(figsize=(9,5)); sns.boxplot(data=us,x="work_setting",y="salary_in_usd",order=["Hybrid","In-person","Remote"],color="#75b7c8")
    plt.title("Salary distributions by work setting | Hybrid n=38"); plt.xlabel("Work setting"); plt.ylabel("Annual salary (nominal USD)"); save("salary_by_work_setting.png")
    plt.figure(figsize=(11,6)); sns.barplot(data=categories,x="median",y="job_category",color="#2878a0")
    plt.title("Median salary by job category | Cloud and Database n=5"); plt.xlabel("Annual salary (nominal USD)"); plt.ylabel(""); save("median_by_category.png")
    matrix=cs.pivot(index="job_category",columns="work_setting",values="median").reindex(categories.job_category)
    plt.figure(figsize=(10,7)); sns.heatmap(matrix,annot=True,fmt=".0f",cmap="Blues",mask=matrix.isna(),cbar_kws={"label":"Nominal USD"})
    plt.title("Median salary by category and work setting\nBlank cells have no records; group counts are in the CSV"); plt.xlabel("Work setting"); plt.ylabel(""); save("category_work_setting.png")
    fig,axes=plt.subplots(1,2,figsize=(14,5),sharey=True)
    for ax,year in zip(axes,[2022,2023]):
        sns.boxplot(data=full.loc[full.work_year.eq(year)],x="experience_level",y="salary_in_usd",hue="work_setting",order=ORDER,ax=ax)
        ax.set_title(f"{year}: full-time records"); ax.set_xlabel("Experience level"); ax.set_ylabel("Nominal USD"); ax.tick_params(axis="x",rotation=15)
    save("full_time_year_comparison.png")
    comp=comparison.dropna(subset=["change_percent"]).copy()
    comp["label"]=comp.apply(lambda r:f"{r.experience_level} / {r.work_setting} (n={int(r.records_2022)}→{int(r.records_2023)})",axis=1)
    plt.figure(figsize=(12,6)); plt.barh(comp.label,comp.change_percent,color=["#d89036" if s else "#2878a0" for s in comp.small_sample]); plt.axvline(0,color="black",lw=1)
    plt.title("2022–2023 median salary differences\nOrange: fewer than 30 records in either year (display flag)"); plt.xlabel("Change (%) | Different yearly samples"); save("year_over_year_change.png")
    se=sens.loc[sens.group_type.eq("experience_level")]
    plt.figure(figsize=(10,5)); sns.barplot(data=se,x="group",y="median",hue="sample",order=ORDER)
    plt.title("Experience medians remain ordered after removing exact repeats"); plt.xlabel("Experience level"); plt.ylabel("Median annual salary (nominal USD)"); save("duplicate_sensitivity.png")
    sun=us.groupby(["work_year","work_setting","experience_level"]).size().reset_index(name="records")
    sun["work_year"]=sun.work_year.astype(str)
    fig=px.sunburst(sun,path=["work_year","work_setting","experience_level"],values="records",title="U.S. record composition: year, work setting, experience")
    fig.write_html(ROOT / "results/job_distribution.html",include_plotlyjs=True,full_html=True)
    print(json.dumps(audit,indent=2))
    print(experience.to_string(index=False))
    print("Generated 8 CSV tables, 8 PNG charts, an interactive HTML chart, and the data-quality summary.")
    return {"us":us,"years":years,"experience":experience,"settings":settings,"categories":categories,"comparison":comparison,"sensitivity":sens,"audit":audit}

if __name__ == "__main__":
    main()
