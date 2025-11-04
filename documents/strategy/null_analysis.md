## 🧩 1. **Understand What “Null Analysis” Means**

Null analysis = **systematically identifying, quantifying, and deciding what to do with missing data** in each column.

You’re looking to answer:

* Where are missing values concentrated?
* Are they *random* or *systematic*?
* Should you **drop, fill, or leave** them?

---

## 🧮 2. **Run Null Summary**

In Python (Pandas):

```python
import pandas as pd

df = pd.read_csv("synosales_cleaned.csv")

# Basic null count and percentage
null_summary = df.isna().sum().sort_values(ascending=False)
percent_null = (df.isna().sum() / len(df) * 100).sort_values(ascending=False)

null_df = pd.DataFrame({
    'Missing_Count': null_summary,
    'Missing_Percent': percent_null
})
print(null_df)
```

➡️ This gives you a ranked view: which columns have the most missing data and whether they’re acceptable or critical.

---

## 🧭 3. **Decide Strategy Per Column**

| Column                                   | Missing% | Role                | Recommended Action                                                  |
| ---------------------------------------- | -------- | ------------------- | ------------------------------------------------------------------- |
| `Capacity`, `Unit`, `Bays`, `total_bays` | 65–85%   | Hardware attributes | Likely drop or keep only for hardware SKUs                          |
| `exchange_rate_to_usd`, `usd_adjusted_*` | ~6%      | Monetary metric     | Fill with default or average rate                                   |
| `ItemCode`, `ShipTo`                     | ~15%     | Identifier          | Don’t drop whole row; fill with placeholder or infer from `Product` |
| `Comments`                               | ~97%     | Non-essential note  | Safe to drop entirely                                               |
| `Region`, `Country`                      | <1%      | Key feature         | Fill using lookup or mode                                           |
| `Currency`                               | <0.5%    | Important           | Fill with mode or infer from region                                 |
| `Total`, `Price`, `Quantity`             | 0%       | Core metrics        | Keep — perfect condition                                            |

---

## 🧰 4. **Fixing / Filling Techniques**

### 🧹 A. **Drop Columns with Excessive Nulls**

If a column is **>90% missing** or **not analytically meaningful**:

```python
df = df.drop(columns=['Comments', 'Unit'])  # example
```

### 🗑️ B. **Drop Rows with Critical Nulls**

If a row is missing values that are **essential** (e.g., `Customer`, `Product`, `Total`):

```python
df = df.dropna(subset=['Customer', 'Product', 'Total'])
```

### 🔄 C. **Fill (Imputation)**

When a field can be **safely inferred or standardized**:

#### 1. Fill by mode (most frequent value)

```python
df['Currency'].fillna(df['Currency'].mode()[0], inplace=True)
df['Region'].fillna(df['Region'].mode()[0], inplace=True)
```

#### 2. Fill numeric by mean/median

```python
df['exchange_rate_to_usd'].fillna(df['exchange_rate_to_usd'].mean(), inplace=True)
```

#### 3. Fill based on logic or mapping

```python
# Fill region based on country
region_map = df.groupby('Country')['Region'].agg(pd.Series.mode).to_dict()
df['Region'] = df.apply(lambda x: region_map.get(x['Country'], x['Region']), axis=1)
```

#### 4. Fill date with previous value (forward fill)

```python
df['ShipDate'] = pd.to_datetime(df['ShipDate'])
df['ShipDate'] = df['ShipDate'].fillna(method='ffill')
```

---

## 🧪 5. **Amputation (Optional)**

If you want to simulate missing data (for testing model robustness), you can *amputate*:

```python
import numpy as np

# Randomly set 5% of rows in 'Price' to NaN
df.loc[df.sample(frac=0.05).index, 'Price'] = np.nan
```

Useful for validating imputation pipelines or evaluating how models handle nulls.

---

## 🧾 6. **Post-Imputation Validation**

Always re-run a quick check:

```python
df.isna().sum().sum()  # total remaining missing values
```

or visualize missingness:

```python
import seaborn as sns
import matplotlib.pyplot as plt

plt.figure(figsize=(12,6))
sns.heatmap(df.isna(), cbar=False)
plt.title("Missing Value Heatmap")
plt.show()
```

This lets you visually confirm patterns (e.g., are missing values clustered in certain products or timeframes?).

---

## 🧭 7. **Rule of Thumb Summary**

| Situation                       | Strategy                                          |
| ------------------------------- | ------------------------------------------------- |
| <5% missing and random          | Fill (mean/median/mode)                           |
| >50% missing but not crucial    | Drop                                              |
| Missing but logically derivable | Fill using mapping logic                          |
| Critical to model but sparse    | Advanced imputation (KNN, regression)             |
| Missing due to product category | Conditional fill (e.g., hardware vs subscription) |

---

## ⚙️ In Your Case (BI Forecast Context)

| Data Role                                | Suggested Handling                                                |
| ---------------------------------------- | ----------------------------------------------------------------- |
| **Numerical (Price, Total, Rate)**       | Fill with mean or mapped conversion rate                          |
| **Categorical (Type, Region, Currency)** | Fill with mode or rule-based logic                                |
| **Non-essential (Comments, Unit)**       | Drop                                                              |
| **Derived metrics (usd_adjusted_total)** | Recompute from `Total × exchange_rate_to_usd` instead of imputing |


