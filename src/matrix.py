import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

INPUT_FILE = os.path.join("output", "master_appendix.csv")

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(
        f"[MISSING INPUT] {INPUT_FILE} not found. Run merge.py first."
    )

df = pd.read_csv(INPUT_FILE)

# Normalize casing so 'Critical'/'critical' etc. don't split into separate columns
df["Severity_Impact"] = df["Severity_Impact"].str.capitalize()

pivot = df.pivot_table(
    index="GovTech_Vendor",
    columns="Severity_Impact",
    values="Defect_Node_Count",
    aggfunc="sum",
    fill_value=0
)

# --- DATA PREPARATION FOR PURE MATPLOTLIB CHARTING ---
tiers = pivot.index.tolist()[::-1]  # Invert order so the last vendor sits at the base
critical_counts = pivot.get("Critical", pd.Series(0, index=pivot.index)).loc[tiers].values
serious_counts = pivot.get("Serious", pd.Series(0, index=pivot.index)).loc[tiers].values

y_positions = np.arange(len(tiers))
bar_thickness = 0.35

fig, ax = plt.subplots(figsize=(11, 6))
ax.grid(True, axis="x", linestyle="-", color="#EAEAEA", zorder=0)
ax.set_facecolor("white")

critical_bars = ax.barh(y_positions + bar_thickness/2, critical_counts, bar_thickness, label="Critical", color="#d9534f", zorder=3)
serious_bars = ax.barh(y_positions - bar_thickness/2, serious_counts, bar_thickness, label="Serious", color="#f0ad4e", zorder=3)

ax.set_title("NJ Digital Public Governance: Programmatic WCAG Defect Density Profile (2026)", fontsize=12, pad=15, weight="bold")
ax.set_xlabel("Detected Failure Nodes (Defect Count)", fontsize=10, labelpad=10)
ax.set_ylabel("Audited GovTech Vendor", fontsize=10, labelpad=10)
ax.set_yticks(y_positions)
ax.set_yticklabels(tiers, fontsize=9)

ax.legend(title="WCAG Violation Severity", loc="lower right", frameon=True, facecolor="white", edgecolor="#EAEAEA")

plt.tight_layout()
plt.show()