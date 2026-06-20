# 🎨 Fashion Trend Analytics with PySpark

A creative PySpark project that analyzes fashion trends, predicts hot items, and provides actionable insights for the fashion industry

## 🌟 What This Does

This project uses PySpark's big data processing power to:
-  Analyze 10,000+ fashion items across categories, styles, and colors
-  Identify trending styles and colors by season
-  Discover regional fashion preferences
-  Analyze price points and revenue patterns
-  Track year-over-year growth
-  Generate actionable recommendations
-  Create beautiful visualizations

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- Java 8 or 11 (required for PySpark)

### Installation

1. **Install Java** (if you don't have it):
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install openjdk-11-jdk
   
   # On Mac
   brew install openjdk@11
   
   # On Windows - download from Oracle or use Chocolatey
   choco install openjdk11
   ```

2. **Install Python packages**:
   ```bash
   pip install pyspark pandas matplotlib seaborn
   ```

### Running the Project

1. **Run the main analytics**:
   ```bash
   python fashion_trend_analyzer.py
   ```
   
   This will:
   - Generate fashion trend data
   - Run comprehensive analytics
   - Export insights to JSON
   - Save full dataset as CSV
   
2. **Create visualizations**:
   ```bash
   python fashion_visualizer.py
   ```
   
   This generates beautiful charts and dashboards!

## 📁 Output Files

After running, we'll get:
- `fashion_insights.json` - Key findings in JSON format
- `fashion_data.csv` - Full dataset (10,000 records)
- `fashion_dashboard.png` - Main dashboard with 6 visualizations
- `fashion_detailed_analysis.png` - Detailed trend analysis

## 🎯 What we Discover

### 1. Category Performance
See which fashion categories generate the most revenue:
- Dresses, Tops, Pants, Shoes, Accessories, etc.
- Average prices per category
- Total units sold

### 2. Color Trends
Discover the hottest colors for each season:
- Spring: Bright and pastels
- Summer: Light and vibrant
- Fall: Earth tones
- Winter: Dark and rich

### 3. Style Analysis
Identify trending styles:
- Casual, Streetwear, Minimalist
- Vintage, Bohemian, Formal
- Social media engagement metrics

### 4. Regional Preferences
See what styles are popular in different regions:
- North America
- Europe
- Asia
- South America
- Australia

### 5. Price Point Analysis
Understand which price ranges perform best:
- Budget (<$50)
- Mid-Range ($50-150)
- Premium ($150-300)
- Luxury (>$300)

### 6. Seasonal Insights
Get recommendations on what to stock for each season

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