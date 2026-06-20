# 🎨 Fashion Trend Analytics with PySpark

A PySpark project for fashion trend analysis with two pipelines:

1. **Synthetic Trend Generator + Analytics Dashboard**  
   Generates a realistic two-year dataset (10,000+ records) and produces trend insights and dashboards.

2. **Zara-Style Catalog Analytics (Scraping-Ready Template)**  
   Builds a Zara-like product catalog dataset and analyzes category, color, style, price, stock, and regional patterns.

---

## 🌟 Capabilities

### Synthetic Pipeline
- Generate 10,000+ fashion records across categories, styles, colors, seasons, and regions
- Identify top categories by revenue and units sold
- Rank top seasonal colors (Spark window functions)
- Analyze style popularity and social engagement
- Detect regional preferences (top style per region)
- Segment performance by price range
- Export datasets and insights for downstream work
- Create dashboards and detailed analysis charts

### Zara-Style Pipeline
- Build a product catalog dataset with Zara-like attributes (category, style, color, price, stock status, bestseller flag)
- Analyze:
  - Top categories by revenue, units, average price, and SKU count
  - Top colors per season (ranked)
  - Style popularity vs engagement and price
  - Price band performance
  - Bestseller patterns
  - Stock status distribution
  - Regional performance
- Export results and generate a dedicated Zara dashboard and detailed figures

---

## 📦 Requirements

### System
- Python 3.8+
- Java 8 or 11 (required for PySpark)

### Python Packages
```bash
pip install pyspark pandas matplotlib seaborn requests beautifulsoup4
```

> Note: Charts use a serif font stack that includes “Sabon”. If unavailable, Matplotlib falls back to Georgia / Times New Roman.

---

## 🚀 Running

### 1) Synthetic Trend Generator + Analytics Dashboard

```bash
python fashion_trend_analyzer.py
```

**Outputs**
- `fashion_data.csv` — full synthetic dataset
- `fashion_insights.json` — curated findings
- `fashion_dashboard.png` — 6-panel dashboard
- `fashion_detailed_analysis.png` — additional figures (monthly trend, heatmap, scatter, top combos)

---

### 2) Zara-Style Catalog Analytics

```bash
python zara_fashion_analyzer.py
```

**Notes on data collection**
- The included function produces a realistic Zara-style dataset by default.
- Live scraping typically requires additional engineering (headers, rate limiting, anti-bot handling, and site-specific parsing). The script is structured to support this extension without changing the analytics steps.

**Outputs**
- `zara_products.csv` — product catalog dataset
- `zara_insights.json` — curated findings (categories, seasonal colors, styles, bestsellers)
- `zara_dashboard.png` — Zara analytics dashboard
- `zara_detailed_analysis.png` — detailed figures (heatmap, scatter, stock status, top combos)

---

## 🧠 Key Metrics Produced

- Revenue and units by category, season, and region
- Top-N ranking (colors by season, style by region) using Spark window functions
- Engagement signals (average social engagement per style)
- Price segmentation performance (budget → luxury)
- Cross-dimension patterns (category × color combinations)

---

## 🛠️ Technical Notes

- Spark DataFrame caching is used for performance
- Aggregations: `sum`, `avg`, `count`
- Window functions: `row_number()` over partitions
- Plotting is performed via Pandas + Matplotlib/Seaborn

All artifacts are written to the working directory (CSV, JSON, PNG).

---


##  Sample Insights

The analysis reveals patterns like:
- **Black, White, and Navy** are consistently top-selling colors
- **Casual and Streetwear** styles dominate sales
- **Dresses and Outerwear** see seasonal revenue spikes
- **Mid-range pricing** ($50-150) has the highest sales volume
- Regional preferences vary significantly

## 🛠️ Technical Details

### PySpark Features Used
- **DataFrame API** - For data manipulation
- **Aggregations** - Complex groupBy operations
- **Window Functions** - For ranking and partitioning
- **ML Features** - Vector assemblers (ready for ML extension)
- **Caching** - For performance optimization

### Data Generation
- Realistic fashion data with 10,000+ records
- 9 categories, 10 styles, 13 colors
- 2 years of temporal data
- 5 global regions
- Seasonal patterns built in

## 🎨 Visualizations

The project creates:
1. **Bar charts** - Top categories, styles, colors
2. **Pie charts** - Seasonal revenue distribution
3. **Heatmaps** - Category-season correlations
4. **Scatter plots** - Price vs popularity
5. **Line graphs** - Monthly trends
6. **Horizontal bars** - Regional comparisons

