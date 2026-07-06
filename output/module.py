import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# FIX: INPUT_FILE/OUTPUT_IMAGE previously used a bare relative "output"
# folder name, same drift risk as merge.py's old local OUTPUT_DIR
# redefinition. Now anchored to pipeline_config.OUTPUT_DIR
# (<PROJECT_ROOT>/output/) so this script finds master_appendix.csv
# regardless of the cwd it's launched from.
from pipeline_config import OUTPUT_DIR, output_path

INPUT_FILE = output_path("master_appendix.csv")
OUTPUT_IMAGE = output_path("final_thesis_risk_chart.png")

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(
        f"[MISSING INPUT] {INPUT_FILE} not found. Run merge.py first."
    )

df = pd.read_csv(INPUT_FILE)
df["Severity_Impact"] = df["Severity_Impact"].str.capitalize()

pivot = df.pivot_table(
    index="GovTech_Vendor",
    columns="Severity_Impact",
    values="Defect_Node_Count",
    aggfunc="sum",
    fill_value=0
)

tiers = pivot.index.tolist()[::-1]
critical_counts = pivot.get("Critical", pd.Series(0, index=pivot.index)).loc[tiers].values
serious_counts = pivot.get("Serious", pd.Series(0, index=pivot.index)).loc[tiers].values

y_positions = np.arange(len(tiers))
bar_thickness = 0.35

fig, ax = plt.subplots(figsize=(11, 6))
ax.grid(True, axis="x", linestyle="-", color="#EAEAEA", zorder=0)
ax.set_facecolor("white")

critical_bars = ax.barh(y_positions + bar_thickness/2, critical_counts, bar_thickness, label="Critical", color="#d9534f", zorder=3)
serious_bars = ax.barh(y_positions - bar_thickness/2, serious_counts, bar_thickness, label="Serious", color="#f0ad4e", zorder=3)

def apply_value_labels(bars):
    for bar in bars:
        width = bar.get_width()
        if width > 0:
            ax.annotate(f" {int(width)}",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(3, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9, color="#333333", weight="bold")

apply_value_labels(critical_bars)
apply_value_labels(serious_bars)

ax.set_title("NJ Digital Public Governance: Programmatic WCAG Defect Density Profile (2026)", fontsize=12, pad=15, weight="bold")
ax.set_xlabel("Detected Failure Nodes (Defect Count)", fontsize=10, labelpad=10)
ax.set_ylabel("Audited GovTech Vendor", fontsize=10, labelpad=10)
ax.set_yticks(y_positions)
ax.set_yticklabels(tiers, fontsize=9)

max_count = max(critical_counts.max(), serious_counts.max())
ax.set_xlim(0, max_count * 1.15)  # Dynamic headroom instead of a hardcoded 220

ax.legend(title="WCAG Violation Severity", loc="lower right", frameon=True, facecolor="white", edgecolor="#EAEAEA")

# FIX: os.makedirs("output", ...) removed — it pointed at the same stale
# bare relative folder as INPUT_FILE/OUTPUT_IMAGE used to, and is redundant
# anyway since output_path() (used above) already creates OUTPUT_DIR.
plt.tight_layout()
plt.savefig(OUTPUT_IMAGE, dpi=300, bbox_inches="tight")
print(f"[FILE OUTPUT SUCCESS] High-resolution graphic compiled to '{OUTPUT_IMAGE}'.")
plt.show()


# ------------------------------------------------------------------
# REPORT SUMMARY
# ------------------------------------------------------------------

total_records = len(df)
total_defects = df["Defect_Node_Count"].sum()

severity_summary = (
    df.groupby("Severity_Impact")["Defect_Node_Count"]
      .sum()
      .sort_values(ascending=False)
)

vendor_summary = (
    df.groupby("GovTech_Vendor")["Defect_Node_Count"]
      .sum()
      .sort_values(ascending=False)
)

worst_vendor = vendor_summary.index[0]
worst_count = vendor_summary.iloc[0]

REPORT_FILE = output_path("pipeline_summary_report.txt")

with open(REPORT_FILE, "w", encoding="utf-8") as report:

    report.write("=" * 70 + "\n")
    report.write("NJ GOVTECH WCAG COMPLIANCE PIPELINE SUMMARY\n")
    report.write("=" * 70 + "\n\n")

    report.write(f"Audit Date: {pd.Timestamp.now()}\n\n")

    report.write(f"Total observations : {total_records:,}\n")
    report.write(f"Total defect nodes : {total_defects:,}\n\n")

    report.write("Severity Distribution\n")
    report.write("---------------------\n")

    for severity, count in severity_summary.items():
        report.write(f"{severity:<12} {count:>8}\n")

    report.write("\n")

    report.write("Vendor Totals\n")
    report.write("-------------\n")

    for vendor, count in vendor_summary.items():
        report.write(f"{vendor:<35} {count:>8}\n")

    report.write("\n")

    report.write("Highest Defect Density\n")
    report.write("----------------------\n")
    report.write(f"{worst_vendor}: {worst_count:,} detected failure nodes\n\n")

    report.write("Summary\n")
    report.write("----------------------\n")

    report.write(
        f"This audit identified {total_defects:,} accessibility "
        f"failure nodes across {total_records:,} observations. "
        f"The highest observed defect density occurred in "
        f"{worst_vendor}, with {worst_count:,} detected failure nodes. "
        "Counts reflect automated and cross-validated findings "
        "generated by the WCAG GovTech pipeline.\n"
    )

print(f"[REPORT GENERATED] {REPORT_FILE}")