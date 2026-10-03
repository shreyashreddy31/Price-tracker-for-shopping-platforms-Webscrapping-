"""
Smart Price Tracker — ML Engine
Deal Score Algorithm + Linear Regression Price Prediction
Uses: Scikit-learn, NumPy, Pandas
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: DEAL SCORE ALGORITHM
# ══════════════════════════════════════════════════════════════════════════════

def calculate_deal_score(
    current_price: float,
    avg_30d: float,
    avg_90d: float,
    historical_low: float,
    historical_high: float,
    discount_from_original: float = 0.0,
) -> dict:
    """
    Calculates a Deal Score from 0–100 using a weighted multi-factor model.

    Scoring Components:
    ┌─────────────────────────────────────────────────────────────┐
    │  Factor                          │ Weight │ Max Points      │
    ├─────────────────────────────────────────────────────────────┤
    │  Price vs. 30-day average        │  35%   │  35 pts         │
    │  Price vs. historical range      │  30%   │  30 pts         │
    │  Closeness to all-time low       │  20%   │  20 pts         │
    │  Discount from original price    │  15%   │  15 pts         │
    └─────────────────────────────────────────────────────────────┘

    Args:
        current_price: Today's scraped price
        avg_30d: 30-day average price
        avg_90d: 90-day average price
        historical_low: All-time lowest price
        historical_high: All-time highest price
        discount_from_original: Percentage discount from listed MRP (0–1)

    Returns:
        dict with score, grade, label, and component breakdown
    """

    if current_price <= 0:
        return _build_result(0, {})

    scores = {}

    # ── Component 1: vs. 30-day average (35 pts) ──────────────────────────────
    if avg_30d > 0:
        savings_pct = (avg_30d - current_price) / avg_30d
        # Sigmoid-like scaling: every 5% below avg = ~10 pts
        comp1 = min(35, max(0, savings_pct * 200))
    else:
        comp1 = 17.5  # Neutral

    scores["vs_30d_avg"] = round(comp1, 2)

    # ── Component 2: Position in historical range (30 pts) ────────────────────
    price_range = historical_high - historical_low
    if price_range > 0:
        # 0 = at all-time high (0 pts), 1 = at all-time low (30 pts)
        position = (historical_high - current_price) / price_range
        comp2 = position * 30
    else:
        comp2 = 15.0  # Neutral

    scores["historical_position"] = round(comp2, 2)

    # ── Component 3: Closeness to all-time low (20 pts) ───────────────────────
    if historical_low > 0 and historical_high > 0:
        if current_price <= historical_low * 1.01:
            comp3 = 20.0  # AT or BELOW all-time low — perfect score
        else:
            pct_above_low = (current_price - historical_low) / historical_low
            comp3 = max(0, 20 - (pct_above_low * 80))
    else:
        comp3 = 10.0

    scores["near_all_time_low"] = round(comp3, 2)

    # ── Component 4: Discount from original/MRP (15 pts) ─────────────────────
    comp4 = min(15, discount_from_original * 30)  # 50% discount = max score
    scores["mrp_discount"] = round(comp4, 2)

    # ── Total Score ───────────────────────────────────────────────────────────
    total = comp1 + comp2 + comp3 + comp4
    total = max(0, min(100, round(total)))

    return _build_result(total, scores)


def _build_result(score: int, components: dict) -> dict:
    """Attaches grade, label, and emoji to a score."""
    if score >= 85:
        grade, label, emoji = "A+", "Exceptional Deal", "🔥"
    elif score >= 70:
        grade, label, emoji = "A", "Great Deal", "✅"
    elif score >= 55:
        grade, label, emoji = "B", "Good Deal", "👍"
    elif score >= 40:
        grade, label, emoji = "C", "Fair Price", "😐"
    elif score >= 25:
        grade, label, emoji = "D", "Slightly Overpriced", "⚠️"
    else:
        grade, label, emoji = "F", "Bad Deal — Wait for Sale", "❌"

    return {
        "score": score,
        "grade": grade,
        "label": label,
        "emoji": emoji,
        "components": components,
        "recommendation": _get_recommendation(score),
    }


def _get_recommendation(score: int) -> str:
    if score >= 75:
        return "Buy now! This is a strong deal based on historical prices."
    elif score >= 50:
        return "Decent price. Consider buying if you need it soon."
    elif score >= 30:
        return "Not the best deal. Set a price alert and wait."
    else:
        return "Poor deal. Historical data shows much lower prices. Hold off."


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: PRICE TREND PREDICTION (Linear & Polynomial Regression)
# ══════════════════════════════════════════════════════════════════════════════

class PriceTrendPredictor:
    """
    Predicts future price trends using Linear Regression with optional
    polynomial features for capturing non-linear seasonal price patterns.

    Training features:
    - Day index (time step)
    - Day of week (0=Mon, 6=Sun) — captures weekend sale patterns
    - Day of month — captures end-of-month promotions
    - Rolling 7-day average — smoothed trend signal
    """

    def __init__(self, degree: int = 2):
        """
        Args:
            degree: Polynomial degree (1=linear, 2=quadratic for curves)
        """
        self.degree = degree
        self.model = Pipeline([
            ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
            ("lr", LinearRegression())
        ])
        self.is_trained = False
        self.feature_names = ["day_index", "day_of_week", "day_of_month", "rolling_avg_7d"]

    def _build_features(self, dates: list, prices: list) -> np.ndarray:
        """Constructs a feature matrix from raw date+price data."""
        df = pd.DataFrame({"date": pd.to_datetime(dates), "price": prices})
        df = df.sort_values("date").reset_index(drop=True)

        features = pd.DataFrame({
            "day_index": df.index,
            "day_of_week": df["date"].dt.dayofweek,
            "day_of_month": df["date"].dt.day,
            "rolling_avg_7d": df["price"].rolling(window=7, min_periods=1).mean(),
        })

        return features.values, df["price"].values, df["date"].tolist()

    def train(self, dates: list, prices: list) -> dict:
        """
        Trains the regression model on historical price data.

        Returns:
            dict with training metrics (MAE, R², coefficients)
        """
        if len(prices) < 14:
            raise ValueError("Need at least 14 data points to train the model.")

        X, y, _ = self._build_features(dates, prices)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False  # Time series: no shuffle
        )

        self.model.fit(X_train, y_train)
        self.is_trained = True

        y_pred_test = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred_test)
        r2 = r2_score(y_test, y_pred_test)

        return {
            "mae": round(mae, 2),
            "r2_score": round(r2, 4),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "model_degree": self.degree,
        }

    def predict(self, historical_dates: list, historical_prices: list, days_ahead: int = 7) -> list:
        """
        Predicts prices for the next N days.

        Returns:
            list of {"date": str, "price": float, "is_prediction": True}
        """
        if not self.is_trained:
            self.train(historical_dates, historical_prices)

        last_date = pd.to_datetime(historical_dates[-1])
        last_idx = len(historical_prices)
        rolling_avg = np.mean(historical_prices[-7:])

        predictions = []
        for i in range(1, days_ahead + 1):
            future_date = last_date + timedelta(days=i)
            features = np.array([[
                last_idx + i,
                future_date.dayofweek,
                future_date.day,
                rolling_avg,
            ]])
            predicted_price = self.model.predict(features)[0]
            predicted_price = max(0, round(predicted_price, 2))

            # Update rolling avg for next step
            rolling_avg = (rolling_avg * 6 + predicted_price) / 7

            predictions.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "price": predicted_price,
                "is_prediction": True,
            })

        return predictions


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: DUMMY DATA GENERATION + DEMO
# ══════════════════════════════════════════════════════════════════════════════

def generate_realistic_price_history(
    base_price: float = 999.99,
    days: int = 90,
    seed: int = 42
) -> tuple:
    """
    Generates realistic historical price data with:
    - Long-term trend (slight deflation over time)
    - Weekly patterns (slight discount on weekends)
    - Monthly sale events (e.g., end-of-month drops)
    - Random noise
    """
    np.random.seed(seed)
    start_date = datetime.now() - timedelta(days=days)

    dates = []
    prices = []
    price = base_price * 1.20  # Start 20% above current

    for i in range(days):
        date = start_date + timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))

        # Long-term downward trend
        trend = -0.05 * (i / days) * base_price

        # Weekend dip (small)
        weekend_factor = -base_price * 0.02 if date.weekday() >= 5 else 0

        # Monthly flash sale (day 28-30 of month)
        sale_factor = -base_price * 0.10 if date.day >= 28 else 0

        # Random noise (±2%)
        noise = np.random.normal(0, base_price * 0.02)

        price = base_price + trend + weekend_factor + sale_factor + noise
        price = max(base_price * 0.65, price)  # Floor at 65% of base
        prices.append(round(price, 2))

    return dates, prices


def run_demo():
    """End-to-end demonstration of the ML engine."""

    print("=" * 65)
    print("  SMART PRICE TRACKER — ML ENGINE DEMO")
    print("=" * 65)

    # ── Generate dummy data ────────────────────────────────────────────────
    print("\n📊 Generating 90 days of simulated price history...")
    current_price = 849.99
    dates, prices = generate_realistic_price_history(
        base_price=current_price, days=90, seed=7
    )

    avg_30d = np.mean(prices[-30:])
    avg_90d = np.mean(prices)
    hist_low = min(prices)
    hist_high = max(prices)

    print(f"   Current Price  : ${current_price:>8.2f}")
    print(f"   30-Day Average : ${avg_30d:>8.2f}")
    print(f"   90-Day Average : ${avg_90d:>8.2f}")
    print(f"   All-Time Low   : ${hist_low:>8.2f}")
    print(f"   All-Time High  : ${hist_high:>8.2f}")

    # ── Deal Score ────────────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("  DEAL SCORE ANALYSIS")
    print("─" * 65)

    result = calculate_deal_score(
        current_price=current_price,
        avg_30d=avg_30d,
        avg_90d=avg_90d,
        historical_low=hist_low,
        historical_high=hist_high,
        discount_from_original=0.15,  # 15% discount from MRP
    )

    print(f"\n  {result['emoji']}  Deal Score  : {result['score']} / 100")
    print(f"  Grade         : {result['grade']}  ({result['label']})")
    print(f"  Recommendation: {result['recommendation']}")
    print("\n  Score Breakdown:")
    for key, val in result["components"].items():
        bar = "█" * int(val) + "░" * max(0, 35 - int(val))
        print(f"    {key:<25} {bar[:20]}  {val:.1f} pts")

    # ── Price Prediction ──────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("  PRICE TREND PREDICTION (Next 7 Days)")
    print("─" * 65)

    predictor = PriceTrendPredictor(degree=2)
    metrics = predictor.train(dates, prices)

    print(f"\n  Model Training Metrics:")
    print(f"    Mean Absolute Error : ±${metrics['mae']:.2f}")
    print(f"    R² Score            :  {metrics['r2_score']:.4f}  {'(good fit ✅)' if metrics['r2_score'] > 0.7 else '(weak fit ⚠️)'}")
    print(f"    Training Samples    :  {metrics['train_samples']}")
    print(f"    Polynomial Degree   :  {metrics['model_degree']}")

    predictions = predictor.predict(dates, prices, days_ahead=7)

    print(f"\n  Predicted Prices:")
    print(f"  {'Date':<14} {'Price':>10}  {'vs Current':>12}  {'Signal':>10}")
    print(f"  {'─'*14}  {'─'*10}  {'─'*12}  {'─'*10}")
    for p in predictions:
        diff = p["price"] - current_price
        diff_pct = (diff / current_price) * 100
        arrow = "📈" if diff > 0 else "📉"
        signal = "Hold" if diff > 0 else "Buy soon"
        print(f"  {p['date']:<14} ${p['price']:>9.2f}  {diff_pct:>+10.1f}%  {arrow} {signal}")

    # ── Summary ───────────────────────────────────────────────────────────
    avg_predicted = np.mean([p["price"] for p in predictions])
    trend = "rising 📈" if avg_predicted > current_price else "falling 📉"
    print(f"\n  Trend Outlook: Prices are {trend} over the next 7 days.")
    print(f"  Avg predicted price: ${avg_predicted:.2f} vs current ${current_price:.2f}\n")
    print("=" * 65)
    print("  ✅  ML Engine demo complete.")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
