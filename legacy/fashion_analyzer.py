"""
Fashion Trend Analytics with PySpark + Visualizations
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window
import random
from datetime import datetime, timedelta
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set style for visualizations with Sabon font and pastels
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Sabon', 'Georgia', 'Times New Roman']
plt.rcParams['axes.facecolor'] = '#FFF9F5'
plt.rcParams['figure.facecolor'] = '#FFFFFF'

# Initialize Spark Session
spark = SparkSession.builder \
    .appName("FashionTrendAnalyzer") \
    .master("local[*]") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

print("🎨 Fashion Trend Analyzer - Powered by PySpark")
print("=" * 60)

# ============================================================================
# SECTION 1: GENERATE FASHION DATA
# ============================================================================

def generate_fashion_data(num_records=10000):
    """Generate realistic fashion trend data"""
    
    categories = ['Dresses', 'Tops', 'Pants', 'Shoes', 'Accessories', 
                  'Outerwear', 'Skirts', 'Bags', 'Jewelry']
    
    styles = ['Casual', 'Formal', 'Streetwear', 'Bohemian', 'Minimalist', 
              'Vintage', 'Athletic', 'Punk', 'Preppy', 'Grunge']
    
    colors = ['Black', 'White', 'Navy', 'Beige', 'Red', 'Pink', 'Green', 
              'Blue', 'Yellow', 'Purple', 'Orange', 'Brown', 'Gray']
    
    seasons = ['Spring', 'Summer', 'Fall', 'Winter']
    
    regions = ['North America', 'Europe', 'Asia', 'South America', 'Australia']
    
    data = []
    base_date = datetime(2023, 1, 1)
    
    for i in range(num_records):
        date = base_date + timedelta(days=random.randint(0, 730))
        month = date.month
        
        if month in [3, 4, 5]:
            season = 'Spring'
        elif month in [6, 7, 8]:
            season = 'Summer'
        elif month in [9, 10, 11]:
            season = 'Fall'
        else:
            season = 'Winter'
        
        category = random.choice(categories)
        style = random.choice(styles)
        color = random.choice(colors)
        region = random.choice(regions)
        
        base_sales = random.randint(100, 1000)
        
        if (season == 'Summer' and category in ['Dresses', 'Tops']) or \
           (season == 'Winter' and category == 'Outerwear'):
            base_sales *= 1.5
        
        if (color in ['Black', 'White', 'Navy']):
            base_sales *= 1.2
        
        if style in ['Casual', 'Streetwear', 'Minimalist']:
            base_sales *= 1.3
        
        sales = int(base_sales)
        price = random.randint(20, 500)
        revenue = sales * price
        social_engagement = random.randint(1000, 50000)
        
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'year': date.year,
            'month': date.month,
            'season': season,
            'category': category,
            'style': style,
            'color': color,
            'region': region,
            'sales_units': sales,
            'price': price,
            'revenue': revenue,
            'social_engagement': social_engagement
        })
    
    return data

# Generate the data
print("\n📊 Generating fashion trend data...")
fashion_data = generate_fashion_data(10000)

# Create Spark DataFrame
df = spark.createDataFrame(fashion_data)
df.cache()

print(f"✅ Generated {df.count()} fashion records")
print("\n📋 Sample Data:")
df.show(5, truncate=False)

# ============================================================================
# SECTION 2: TREND ANALYSIS
# ============================================================================

print("\n" + "="*60)
print("🔥 TREND ANALYSIS")
print("="*60)

# 1. Most Popular Categories
print("\n1️⃣ TOP SELLING CATEGORIES BY REVENUE:")
top_categories = df.groupBy('category') \
    .agg(
        sum('revenue').alias('total_revenue'),
        sum('sales_units').alias('total_units'),
        avg('price').alias('avg_price')
    ) \
    .orderBy(desc('total_revenue'))

top_categories.show(truncate=False)

# 2. Color Trends by Season
print("\n2️⃣ HOTTEST COLORS BY SEASON:")
color_trends = df.groupBy('season', 'color') \
    .agg(sum('sales_units').alias('total_sales')) \
    .orderBy('season', desc('total_sales'))

window_spec = Window.partitionBy('season').orderBy(desc('total_sales'))
top_colors_season = color_trends.withColumn('rank', row_number().over(window_spec)) \
    .filter(col('rank') <= 3) \
    .drop('rank')

top_colors_season.show(20, truncate=False)

# 3. Style Popularity Trends
print("\n3️⃣ TRENDING STYLES:")
style_trends = df.groupBy('style') \
    .agg(
        sum('sales_units').alias('total_sales'),
        avg('social_engagement').alias('avg_engagement'),
        count('*').alias('num_items')
    ) \
    .orderBy(desc('total_sales'))

style_trends.show(truncate=False)

# 4. Regional Preferences
print("\n4️⃣ REGIONAL FASHION PREFERENCES:")
regional_prefs = df.groupBy('region', 'style') \
    .agg(sum('sales_units').alias('total_sales')) \
    .orderBy('region', desc('total_sales'))

window_spec = Window.partitionBy('region').orderBy(desc('total_sales'))
top_style_region = regional_prefs.withColumn('rank', row_number().over(window_spec)) \
    .filter(col('rank') == 1) \
    .drop('rank')

print("Top Style by Region:")
top_style_region.show(truncate=False)

# 5. Seasonal Revenue Analysis
print("\n5️⃣ SEASONAL REVENUE BREAKDOWN:")
seasonal_revenue = df.groupBy('season') \
    .agg(
        sum('revenue').alias('total_revenue'),
        avg('revenue').alias('avg_revenue'),
        sum('sales_units').alias('total_units')
    ) \
    .orderBy(desc('total_revenue'))

seasonal_revenue.show(truncate=False)

# 6. Price Point Analysis
print("\n6️⃣ PRICE POINT ANALYSIS:")
price_analysis = df.withColumn('price_range', 
    when(col('price') < 50, 'Budget')
    .when((col('price') >= 50) & (col('price') < 150), 'Mid-Range')
    .when((col('price') >= 150) & (col('price') < 300), 'Premium')
    .otherwise('Luxury')
)

price_range_sales = price_analysis.groupBy('price_range') \
    .agg(
        sum('sales_units').alias('total_sales'),
        sum('revenue').alias('total_revenue'),
        avg('price').alias('avg_price')
    ) \
    .orderBy(desc('total_revenue'))

price_range_sales.show(truncate=False)

# ============================================================================
# SECTION 3: EXPORT DATA FOR VISUALIZATION
# ============================================================================

print("\n💾 Preparing data for visualization...")

# Convert to pandas for easier plotting
df_pandas = df.toPandas()

# Save insights
insights = {
    'top_categories': top_categories.limit(5).toPandas().to_dict('records'),
    'seasonal_colors': top_colors_season.toPandas().to_dict('records'),
    'trending_styles': style_trends.limit(5).toPandas().to_dict('records'),
    'regional_preferences': top_style_region.toPandas().to_dict('records'),
}

with open('./fashion_insights.json', 'w') as f:
    json.dump(insights, f, indent=2)

df_pandas.to_csv('./fashion_data.csv', index=False)
print("✅ Data exported successfully!")

# ============================================================================
# SECTION 4: CREATE VISUALIZATIONS
# ============================================================================

print("\n🎨 Creating visualizations...")

# Create main dashboard
fig = plt.figure(figsize=(20, 12))

# 1. Top Categories by Revenue
ax1 = plt.subplot(2, 3, 1)
top_cat_df = pd.DataFrame(insights['top_categories'][:5])
colors_palette = ['#FFB5C5', '#B5E7A0', '#A8D8EA', '#FFCCB6', '#E0BBE4']
bars = ax1.barh(top_cat_df['category'], top_cat_df['total_revenue'], color=colors_palette)
ax1.set_xlabel('Revenue ($)', fontweight='bold')
ax1.set_title('💰 Top 5 Categories by Revenue', fontweight='bold', fontsize=12)
ax1.ticklabel_format(style='plain', axis='x')
for i, bar in enumerate(bars):
    width = bar.get_width()
    ax1.text(width, bar.get_y() + bar.get_height()/2, 
             f'${width/1e6:.1f}M', ha='left', va='center', fontweight='bold')

# 2. Seasonal Revenue
ax2 = plt.subplot(2, 3, 2)
seasonal_rev = df_pandas.groupby('season')['revenue'].sum().sort_values(ascending=False)
colors_season = ['#FFD6E8', '#C7CEEA', '#B5EAD7', '#FFDAC1']
explode = (0.1, 0, 0, 0)
ax2.pie(seasonal_rev.values, labels=seasonal_rev.index, autopct='%1.1f%%',
        colors=colors_season, explode=explode, shadow=True, startangle=90)
ax2.set_title('🍂 Revenue by Season', fontweight='bold', fontsize=12)

# 3. Style Popularity
ax3 = plt.subplot(2, 3, 3)
style_df = pd.DataFrame(insights['trending_styles'][:7])
ax3.bar(range(len(style_df)), style_df['total_sales'], 
        color=['#E8C1C5', '#C5E1A5', '#B3E5FC', '#FFCCBC', '#D1C4E9', '#F8BBD0', '#C5CAE9'])
ax3.set_xticks(range(len(style_df)))
ax3.set_xticklabels(style_df['style'], rotation=45, ha='right')
ax3.set_ylabel('Total Sales (Units)', fontweight='bold')
ax3.set_title('✨ Top Styles by Sales Volume', fontweight='bold', fontsize=12)
ax3.ticklabel_format(style='plain', axis='y')

# 4. Color Trends
ax4 = plt.subplot(2, 3, 4)
color_sales = df_pandas.groupby('color')['sales_units'].sum().sort_values(ascending=False)[:8]
colors_map = {
    'Black': '#000000', 'White': '#FFFFFF', 'Navy': '#000080',
    'Beige': '#F5F5DC', 'Red': '#FF0000', 'Pink': '#FFC0CB',
    'Green': '#008000', 'Blue': '#0000FF', 'Yellow': '#FFFF00',
    'Purple': '#800080', 'Orange': '#FFA500', 'Brown': '#8B4513',
    'Gray': '#808080'
}
actual_colors = [colors_map.get(c, '#555555') for c in color_sales.index]
bars = ax4.bar(range(len(color_sales)), color_sales.values, color=actual_colors, 
               edgecolor='black', linewidth=1.5)
ax4.set_xticks(range(len(color_sales)))
ax4.set_xticklabels(color_sales.index, rotation=45, ha='right')
ax4.set_ylabel('Sales (Units)', fontweight='bold')
ax4.set_title('🎨 Most Popular Colors', fontweight='bold', fontsize=12)
ax4.ticklabel_format(style='plain', axis='y')

# 5. Regional Preferences
ax5 = plt.subplot(2, 3, 5)
regional_df = pd.DataFrame(insights['regional_preferences'])
y_pos = range(len(regional_df))
ax5.barh(y_pos, regional_df['total_sales'], color=sns.color_palette("muted"))
ax5.set_yticks(y_pos)
ax5.set_yticklabels([f"{row['region']}\n({row['style']})" for _, row in regional_df.iterrows()])
ax5.set_xlabel('Sales (Units)', fontweight='bold')
ax5.set_title('🌍 Top Style by Region', fontweight='bold', fontsize=12)
ax5.ticklabel_format(style='plain', axis='x')

# 6. Price Range Distribution
ax6 = plt.subplot(2, 3, 6)
price_ranges = pd.cut(df_pandas['price'], bins=[0, 50, 150, 300, 600], 
                      labels=['Budget', 'Mid-Range', 'Premium', 'Luxury'])
price_dist = price_ranges.value_counts().sort_index()
colors_price = ['#B5E7A0', '#FFD3B6', '#FFAAA5', '#D4A5A5']
ax6.bar(price_dist.index, price_dist.values, color=colors_price, alpha=0.7, edgecolor='black')
ax6.set_ylabel('Number of Items', fontweight='bold')
ax6.set_title('💵 Price Range Distribution', fontweight='bold', fontsize=12)
ax6.ticklabel_format(style='plain', axis='y')

plt.suptitle('🛍️ Fashion Trend Analytics Dashboard 🛍️', 
             fontsize=18, fontweight='bold', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('./fashion_dashboard.png', dpi=300, bbox_inches='tight')
print("✅ Dashboard saved as fashion_dashboard.png")

# Create detailed analysis charts
fig2, axes = plt.subplots(2, 2, figsize=(16, 10))

# Monthly Revenue Trend
monthly_revenue = df_pandas.groupby('month')['revenue'].sum()
axes[0, 0].plot(monthly_revenue.index, monthly_revenue.values, 
                marker='o', linewidth=3, markersize=8, color='#FF9AA2')
axes[0, 0].fill_between(monthly_revenue.index, monthly_revenue.values, alpha=0.3, color='#FFB7B2')
axes[0, 0].set_xlabel('Month', fontweight='bold')
axes[0, 0].set_ylabel('Revenue ($)', fontweight='bold')
axes[0, 0].set_title('📈 Monthly Revenue Trend', fontweight='bold', fontsize=12)
axes[0, 0].grid(True, alpha=0.3)
axes[0, 0].ticklabel_format(style='plain', axis='y')

# Category Sales Heatmap by Season
pivot_data = df_pandas.groupby(['season', 'category'])['sales_units'].sum().unstack(fill_value=0)
sns.heatmap(pivot_data, annot=True, fmt=',.0f', cmap='YlOrRd', 
            cbar_kws={'label': 'Sales Units'}, ax=axes[0, 1])
axes[0, 1].set_title('🔥 Category Sales by Season Heatmap', fontweight='bold', fontsize=12)

# Style vs Price Analysis
style_price = df_pandas.groupby('style').agg({'price': 'mean', 'sales_units': 'sum'})
scatter = axes[1, 0].scatter(style_price['price'], style_price['sales_units'], 
                            s=500, alpha=0.6, c=range(len(style_price)), 
                            cmap='viridis', edgecolors='black', linewidth=2)
for idx, style in enumerate(style_price.index):
    axes[1, 0].annotate(style, (style_price.iloc[idx]['price'], 
                                style_price.iloc[idx]['sales_units']),
                       fontsize=9, fontweight='bold')
axes[1, 0].set_xlabel('Average Price ($)', fontweight='bold')
axes[1, 0].set_ylabel('Total Sales (Units)', fontweight='bold')
axes[1, 0].set_title('💎 Style: Price vs Popularity', fontweight='bold', fontsize=12)
axes[1, 0].grid(True, alpha=0.3)
axes[1, 0].ticklabel_format(style='plain', axis='y')

# Top 10 Combinations
combo_sales = df_pandas.groupby(['category', 'color'])['sales_units'].sum().sort_values(ascending=False)[:10]
combo_labels = [f"{cat}\n{col}" for cat, col in combo_sales.index]
axes[1, 1].barh(range(len(combo_sales)), combo_sales.values, 
               color=['#FFD3B6', '#FFAAA5', '#FF8B94', '#C7CEEA', '#B5EAD7', '#E2F0CB', '#FFDAC1', '#E0BBE4', '#D4A5A5', '#FEC8D8'])
axes[1, 1].set_yticks(range(len(combo_sales)))
axes[1, 1].set_yticklabels(combo_labels, fontsize=9)
axes[1, 1].set_xlabel('Sales (Units)', fontweight='bold')
axes[1, 1].set_title('🏆 Top 10 Category-Color Combinations', fontweight='bold', fontsize=12)
axes[1, 1].ticklabel_format(style='plain', axis='x')

plt.suptitle('📊 Fashion Analytics 📊', fontsize=16, fontweight='bold', y=0.995)
plt.tight_layout(rect=[0, 0, 1, 0.98])
plt.savefig('./fashion_detailed_analysis.png', dpi=300, bbox_inches='tight')
print("✅ Analysis saved as fashion_detailed_analysis.png")

# ============================================================================
# SECTION 5: SUMMARY
# ============================================================================

print("\n" + "="*60)
print("📊 SUMMARY STATISTICS")
print("="*60)

total_revenue = df.agg(sum('revenue')).collect()[0][0]
total_sales = df.agg(sum('sales_units')).collect()[0][0]
avg_price = df.agg(avg('price')).collect()[0][0]
num_categories = df.select('category').distinct().count()
num_styles = df.select('style').distinct().count()

print(f"\n💰 Total Revenue: ${total_revenue:,.2f}")
print(f"📦 Total Units Sold: {total_sales:,}")
print(f"💵 Average Price: ${avg_price:.2f}")
print(f"🏷️ Number of Categories: {num_categories}")
print(f"✨ Number of Styles: {num_styles}")

print("\n" + "="*60)
print("🎉 Analysis Complete!")
print("="*60)
print("\nGenerated Files:")
print("  📊 fashion_dashboard.png")
print("  📈 fashion_detailed_analysis.png")
print("  📁 fashion_data.csv")
print("  📄 fashion_insights.json")

# Stop Spark
spark.stop()

print("\n✨ All done!")
