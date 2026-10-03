import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart, ReferenceLine } from "recharts";

// ─── Config ───────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

// ─── Helpers ─────────────────────────────────────────────────────────────────
const INR = (val) =>
  val != null
    ? `₹${Number(val).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
    : "—";

const PLATFORM_COLORS = {
  amazon:   { bg: "#ff9900", text: "#111" },
  flipkart: { bg: "#2874f0", text: "#fff" },
  meesho:   { bg: "#f43397", text: "#fff" },
  myntra:   { bg: "#ff3f6c", text: "#fff" },
  snapdeal: { bg: "#e40000", text: "#fff" },
  jiomart:  { bg: "#0073e6", text: "#fff" },
  croma:    { bg: "#67b346", text: "#fff" },
  tatacliq: { bg: "#993366", text: "#fff" },
  unknown:  { bg: "#475569", text: "#fff" },
};

// ─── Sub-Components ───────────────────────────────────────────────────────────
function PlatformBadge({ platform, small }) {
  const c = PLATFORM_COLORS[platform] || PLATFORM_COLORS.unknown;
  return (
    <span style={{ background: c.bg, color: c.text, fontSize: small ? 9 : 10, fontWeight: 800, padding: small ? "2px 6px" : "3px 9px", borderRadius: 4, textTransform: "uppercase", letterSpacing: 1 }}>
      {platform}
    </span>
  );
}

function Stars({ rating }) {
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5;
  return (
    <span style={{ color: "#fbbf24", fontSize: 13 }}>
      {"★".repeat(full)}{half ? "½" : ""}{"☆".repeat(5 - full - (half ? 1 : 0))}
    </span>
  );
}

function LoadingDots() {
  return (
    <>
      <style>{`@keyframes ptBounce{0%,100%{opacity:.2;transform:scale(.7)}50%{opacity:1;transform:scale(1)}}`}</style>
      <div style={{ display: "flex", justifyContent: "center", gap: 6, marginTop: 16 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ width: 9, height: 9, borderRadius: "50%", background: "#14b8a6", animation: `ptBounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />
        ))}
      </div>
    </>
  );
}

function PriceHistoryChart({ history, currentPrice }) {
  if (!history || history.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "24px 0", color: "#475569", fontSize: 13 }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📊</div>
        <div>No price history yet.</div>
        <div style={{ fontSize: 11, marginTop: 4, color: "#334155" }}>
          Each time you track this product, the price is saved. Come back later to see the trend!
        </div>
      </div>
    );
  }

  // Format data for the chart
  const chartData = history.map((point) => {
    const d = new Date(point.scraped_at);
    return {
      date: d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
      time: d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
      fullDate: d.toLocaleString("en-IN"),
      price: point.price,
      original_price: point.original_price,
    };
  });

  const prices = chartData.map((d) => d.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;
  const priceRange = maxPrice - minPrice;
  const yMin = Math.floor((minPrice - Math.max(priceRange * 0.15, 100)) / 100) * 100;
  const yMax = Math.ceil((maxPrice + Math.max(priceRange * 0.15, 100)) / 100) * 100;

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const data = payload[0].payload;
    return (
      <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 8, padding: "10px 14px", fontSize: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}>
        <div style={{ color: "#64748b", marginBottom: 4 }}>{data.fullDate}</div>
        <div style={{ color: "#14b8a6", fontWeight: 800, fontSize: 16 }}>₹{data.price.toLocaleString("en-IN")}</div>
        {data.original_price && (
          <div style={{ color: "#475569", textDecoration: "line-through", fontSize: 11, marginTop: 2 }}>
            MRP: ₹{data.original_price.toLocaleString("en-IN")}
          </div>
        )}
      </div>
    );
  };

  return (
    <div>
      {/* Stats row */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        {[
          { label: "Lowest", value: `₹${minPrice.toLocaleString("en-IN")}`, color: "#34d399" },
          { label: "Highest", value: `₹${maxPrice.toLocaleString("en-IN")}`, color: "#f87171" },
          { label: "Average", value: `₹${Math.round(avgPrice).toLocaleString("en-IN")}`, color: "#818cf8" },
          { label: "Data Points", value: history.length, color: "#fbbf24" },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, minWidth: 90, background: "#030b18", borderRadius: 8, padding: "10px 12px", border: "1px solid #1e293b", textAlign: "center" }}>
            <div style={{ fontSize: 10, color: "#475569", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8 }}>{s.label}</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: s.color, marginTop: 4 }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div style={{ width: "100%", height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey={history.length > 10 ? "date" : "time"}
              stroke="#334155"
              tick={{ fill: "#475569", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "#1e293b" }}
            />
            <YAxis
              domain={[yMin, yMax]}
              stroke="#334155"
              tick={{ fill: "#475569", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "#1e293b" }}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(v >= 1000 ? 1 : 0)}k`}
              width={52}
            />
            <Tooltip content={<CustomTooltip />} />
            {history.length > 1 && (
              <ReferenceLine y={avgPrice} stroke="#818cf840" strokeDasharray="5 5" label="" />
            )}
            <Area
              type="monotone"
              dataKey="price"
              stroke="#14b8a6"
              strokeWidth={2.5}
              fill="url(#priceGradient)"
              dot={{ fill: "#14b8a6", stroke: "#0d1526", strokeWidth: 2, r: history.length <= 15 ? 4 : 0 }}
              activeDot={{ r: 6, fill: "#14b8a6", stroke: "#030b18", strokeWidth: 3 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Trend info */}
      {history.length >= 2 && (
        <div style={{ marginTop: 12, background: "#030b18", borderRadius: 8, padding: "10px 14px", border: "1px solid #1e293b", fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>
          <strong style={{ color: "#94a3b8" }}>Trend: </strong>
          {(() => {
            const first = history[0].price;
            const last = history[history.length - 1].price;
            const diff = last - first;
            const pct = ((diff / first) * 100).toFixed(1);
            if (diff < 0) return <span style={{ color: "#34d399" }}>Price dropped ₹{Math.abs(diff).toLocaleString("en-IN")} ({pct}%) since first tracked 📉</span>;
            if (diff > 0) return <span style={{ color: "#f87171" }}>Price increased ₹{diff.toLocaleString("en-IN")} (+{pct}%) since first tracked 📈</span>;
            return <span>Price has stayed the same since first tracked</span>;
          })()}
        </div>
      )}

      <div style={{ marginTop: 8, fontSize: 10, color: "#1e293b", textAlign: "center" }}>
        Every data point is a real scrape — no simulated or predicted data
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function PriceTracker() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [product, setProduct] = useState(null);
  const [error, setError] = useState("");
  const [backendOnline, setBackendOnline] = useState(null);
  const [showWatchForm, setShowWatchForm] = useState(false);
  const [watchEmail, setWatchEmail] = useState("");
  const [watchPrice, setWatchPrice] = useState("");
  const [watchLoading, setWatchLoading] = useState(false);
  const [watchMessage, setWatchMessage] = useState("");

  // Check if backend is running
  useEffect(() => {
    fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) })
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  const handleTrack = async () => {
    const trimmed = url.trim();
    if (!trimmed) { setError("Please paste a product URL first."); return; }
    if (!trimmed.startsWith("http")) { setError("URL must start with https://"); return; }

    setError("");
    setLoading(true);
    setProduct(null);

    if (!backendOnline) {
      setError("⚠️ Backend is not running. Start it with: cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/fetch-product`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Server error ${res.status}`);
      }

      setProduct(data);

    } catch (e) {
      if (e.name === "TypeError" && e.message.includes("fetch")) {
        setError("Cannot connect to backend. Make sure it's running on port 8000.");
      } else {
        setError(e.message || "Failed to fetch product. Try a different URL.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWatch = async () => {
    const trimmed = url.trim();
    const price = parseFloat(watchPrice);

    if (!trimmed || !validate_url(trimmed)) { setWatchMessage("❌ Invalid product URL."); return; }
    if (isNaN(price) || price <= 0) { setWatchMessage("❌ Target price must be a positive number."); return; }
    if (!watchEmail || !watchEmail.includes("@")) { setWatchMessage("❌ Invalid email address."); return; }

    setWatchLoading(true);
    setWatchMessage("");

    try {
      const res = await fetch(`${API_BASE}/api/watches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed, target_price: price, email: watchEmail }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Server error ${res.status}`);
      }

      setWatchMessage(`✅ ${data.message}`);
      setWatchEmail("");
      setWatchPrice("");
      setTimeout(() => setShowWatchForm(false), 2000);

    } catch (e) {
      setWatchMessage(`❌ ${e.message || "Failed to create watch."}`);
    } finally {
      setWatchLoading(false);
    }
  };

  const validate_url = (u) => {
    try {
      new URL(u);
      return true;
    } catch {
      return false;
    }
  };

  const C = {
    card: { background: "#0d1526", border: "1px solid #1e293b", borderRadius: 14, padding: 20 },
    sec: { fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 14 },
  };

  // Build sorted price list: current product + comparison results
  const allPrices = [];
  if (product) {
    allPrices.push({
      platform: product.platform,
      title: product.title,
      price: product.current_price,
      image_url: product.image_url,
      product_url: url,
      rating: product.rating,
      isCurrent: true,
    });
    if (product.comparison && product.comparison.length > 0) {
      product.comparison.forEach((r) => {
        allPrices.push({ ...r, isCurrent: false });
      });
    }
  }
  allPrices.sort((a, b) => a.price - b.price);
  const cheapest = allPrices.length > 1 ? allPrices[0].price : 0;

  return (
    <div style={{ minHeight: "100vh", background: "#030b18", color: "#e2e8f0", fontFamily: "'Segoe UI', system-ui, sans-serif" }}>

      {/* ── HEADER ── */}
      <div style={{ background: "linear-gradient(135deg,#0a1628,#0d1f3c)", borderBottom: "1px solid #1e293b", padding: "16px 0" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 28px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 900, letterSpacing: -0.5, background: "linear-gradient(90deg,#14b8a6,#818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              ⚡ PriceTracker
            </div>
            <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>Real-time price scraping & comparison · Amazon, Flipkart, Myntra, Snapdeal · Prices in ₹</div>
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            {["Amazon.in", "Flipkart", "Myntra", "Snapdeal"].map((p) => (
              <span key={p} style={{ fontSize: 11, color: "#64748b", background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, padding: "3px 8px" }}>{p}</span>
            ))}
            <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 6, background: backendOnline === null ? "#1e293b" : backendOnline ? "#14532d" : "#7f1d1d", color: backendOnline === null ? "#64748b" : backendOnline ? "#86efac" : "#fca5a5" }}>
              {backendOnline === null ? "⟳ Checking..." : backendOnline ? "● API Online" : "● API Offline"}
            </span>
          </div>
        </div>
      </div>

      {/* ── BACKEND OFFLINE BANNER ── */}
      {backendOnline === false && (
        <div style={{ background: "#1c0a0a", borderBottom: "1px solid #7f1d1d", padding: "10px 28px" }}>
          <div style={{ maxWidth: 1280, margin: "0 auto", fontSize: 12, color: "#fca5a5" }}>
            ⚠️ <strong>Backend is offline.</strong> Start it:{" "}
            <code style={{ background: "#030b18", padding: "2px 6px", borderRadius: 4 }}>
              cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
            </code>
          </div>
        </div>
      )}

      {/* ── SEARCH BAR ── */}
      <div style={{ background: "#0a1628", borderBottom: "1px solid #1e293b", padding: "20px 0" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 28px" }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input
              style={{ flex: 1, minWidth: 240, background: "#0f172a", border: "1.5px solid #1e293b", borderRadius: 10, padding: "13px 18px", color: "#e2e8f0", fontSize: 14, outline: "none" }}
              placeholder="Paste a product URL from Amazon, Flipkart, Myntra, or Snapdeal..."
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(""); }}
              onKeyDown={(e) => e.key === "Enter" && handleTrack()}
              onFocus={(e) => (e.target.style.borderColor = "#14b8a6")}
              onBlur={(e) => (e.target.style.borderColor = "#1e293b")}
            />
            <button onClick={handleTrack} disabled={loading}
              style={{ background: loading ? "#1e293b" : "linear-gradient(135deg,#14b8a6,#0d9488)", color: loading ? "#475569" : "#fff", border: "none", borderRadius: 10, padding: "13px 28px", fontWeight: 700, fontSize: 14, cursor: loading ? "not-allowed" : "pointer", boxShadow: loading ? "none" : "0 4px 16px rgba(20,184,166,0.35)", whiteSpace: "nowrap" }}>
              {loading ? "⟳ Scraping..." : "🔍 Track & Compare"}
            </button>
            <button onClick={() => setShowWatchForm(!showWatchForm)}
              style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #1e293b", borderRadius: 10, padding: "13px 20px", fontWeight: 700, fontSize: 14, cursor: "pointer", whiteSpace: "nowrap", transition: "all 0.2s" }}>
              ⏰ Set Price Watch
            </button>
          </div>

          {/* Watch form (collapsed by default) */}
          {showWatchForm && product && (
            <div style={{ marginTop: 12, background: "#030b18", border: "1px solid #14b8a640", borderRadius: 10, padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: 8 }}>📍 Watching: {product.title.substring(0, 50)}...</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div>
                    <label style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>Target Price</label>
                    <input
                      type="number"
                      placeholder={`e.g. ${Math.max(product.current_price - 5000, 1)}`}
                      value={watchPrice}
                      onChange={(e) => setWatchPrice(e.target.value)}
                      style={{ width: "100%", background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, padding: "10px", color: "#e2e8f0", fontSize: 13 }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>Email</label>
                    <input
                      type="email"
                      placeholder="your@email.com"
                      value={watchEmail}
                      onChange={(e) => setWatchEmail(e.target.value)}
                      style={{ width: "100%", background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, padding: "10px", color: "#e2e8f0", fontSize: 13 }}
                    />
                  </div>
                </div>
                <button onClick={handleCreateWatch} disabled={watchLoading}
                  style={{ marginTop: 12, width: "100%", background: watchLoading ? "#1e293b" : "#818cf8", color: "#fff", border: "none", borderRadius: 6, padding: "10px", fontWeight: 700, cursor: watchLoading ? "not-allowed" : "pointer" }}>
                  {watchLoading ? "⟳ Creating..." : "✓ Create Watch"}
                </button>
                {watchMessage && (
                  <div style={{ marginTop: 10, padding: "10px", borderRadius: 6, fontSize: 12, background: watchMessage.includes("✅") ? "#14532d" : "#7f1d1d", color: watchMessage.includes("✅") ? "#86efac" : "#fca5a5" }}>
                    {watchMessage}
                  </div>
                )}
              </div>
            </div>
          )}

          {error && (
            <div style={{ marginTop: 10, background: "#1c0a0a", border: "1px solid #7f1d1d", borderRadius: 8, padding: "10px 14px", color: "#fca5a5", fontSize: 13, lineHeight: 1.5 }}>
              {error}
            </div>
          )}
        </div>
      </div>

      {/* ── LOADING ── */}
      {loading && (
        <div style={{ maxWidth: 1280, margin: "40px auto", padding: "0 28px" }}>
          <div style={{ ...C.card, textAlign: "center", padding: "52px 24px" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
            <div style={{ fontSize: 16, color: "#94a3b8", fontWeight: 700 }}>Scraping product & comparing prices...</div>
            <div style={{ fontSize: 13, color: "#475569", marginTop: 6 }}>
              Fetching from the product page, then searching other platforms. This may take 20-40 seconds.
            </div>
            <LoadingDots />
          </div>
        </div>
      )}

      {/* ── PRODUCT DASHBOARD ── */}
      {product && !loading && (
        <div style={{ maxWidth: 1100, margin: "24px auto", padding: "0 28px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 340px) 1fr", gap: 24, alignItems: "start" }}>

            {/* ── LEFT COLUMN ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={C.card}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <PlatformBadge platform={product.platform} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: product.seller_verified ? "#14b8a6" : "#f87171" }}>
                    {product.seller_verified ? "✓ Verified Seller" : "⚠ Unverified"}
                  </span>
                </div>
                <div style={{ textAlign: "center", marginBottom: 14, background: "#030b18", borderRadius: 10, padding: 12 }}>
                  <img src={product.image_url} alt={product.title}
                    style={{ maxWidth: "100%", maxHeight: 200, objectFit: "contain", borderRadius: 6 }}
                    onError={(e) => { e.target.src = "https://placehold.co/200x200/0d1526/475569?text=No+Image"; }} />
                </div>
                <div style={{ fontSize: 10, color: "#475569", textAlign: "center" }}>
                  Scraped at {new Date(product.scraped_at).toLocaleString("en-IN")}
                </div>
              </div>

              {/* Listing Checks */}
              <div style={C.card}>
                <div style={C.sec}>Listing Details</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  {[
                    { label: "Seller Verified",  pass: product.seller_verified },
                    { label: "Trusted Platform", pass: ["amazon","flipkart","myntra","meesho","snapdeal","jiomart","croma","tatacliq"].includes(product.platform) },
                    { label: "Price Realistic",  pass: !product.discount_percent || Number(product.discount_percent) < 75 },
                    { label: "In Stock",         pass: product.availability === "In Stock" },
                  ].map((check) => (
                    <div key={check.label} style={{ display: "flex", alignItems: "center", gap: 10, background: "#030b18", borderRadius: 8, padding: "10px 12px", border: `1px solid ${check.pass ? "#14532d" : "#7f1d1d"}` }}>
                      <span style={{ fontSize: 16 }}>{check.pass ? "✅" : "❌"}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0" }}>{check.label}</div>
                        <div style={{ fontSize: 10, color: check.pass ? "#14b8a6" : "#f87171" }}>{check.pass ? "Passed" : "Warning"}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ── RIGHT COLUMN ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

              {/* Title, Rating & Price */}
              <div style={C.card}>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", lineHeight: 1.5, marginBottom: 12 }}>
                  {product.title}
                </div>
                {product.rating && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 16 }}>
                    <Stars rating={product.rating} />
                    <span style={{ fontSize: 12, color: "#64748b" }}>
                      {product.rating} ({product.review_count?.toLocaleString("en-IN") || "—"} ratings)
                    </span>
                  </div>
                )}
                <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: "#f0f9ff" }}>{INR(product.current_price)}</span>
                  {product.original_price && (
                    <span style={{ fontSize: 16, color: "#64748b", textDecoration: "line-through" }}>{INR(product.original_price)}</span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
                  {product.discount_percent && (
                    <span style={{ background: "#14532d", color: "#86efac", fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 6 }}>
                      ↓ {Number(product.discount_percent).toFixed(1)}% OFF
                    </span>
                  )}
                  {product.original_price && product.current_price && (
                    <span style={{ color: "#14b8a6", fontSize: 12, fontWeight: 600 }}>
                      Save {INR(product.original_price - product.current_price)}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: product.availability === "In Stock" ? "#14b8a6" : "#ef4444" }}>
                  {product.availability === "In Stock" ? "✓ In Stock" : "✗ Out of Stock"}
                </div>
              </div>

              {/* ── Price History Chart (genuine data from DB) ── */}
              <div style={C.card}>
                <div style={C.sec}>📈 Price History (Real Data)</div>
                <PriceHistoryChart history={product.price_history} currentPrice={product.current_price} />
              </div>

              {/* ── Price Comparison (auto-scraped) ── */}
              <div style={C.card}>
                <div style={C.sec}>🔄 Price Comparison (Live Scraped)</div>

                {allPrices.length <= 1 && (
                  <div style={{ textAlign: "center", padding: "16px 0", color: "#475569", fontSize: 13 }}>
                    No matching products found on other platforms. It may be exclusive to {product.platform}.
                  </div>
                )}

                {allPrices.length > 1 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {allPrices.map((item, i) => {
                      const isCheapest = item.price === cheapest;
                      const diff = item.isCurrent ? 0 : item.price - product.current_price;
                      const diffPct = product.current_price > 0 ? ((diff / product.current_price) * 100).toFixed(1) : 0;

                      return (
                        <div
                          key={`${item.platform}-${i}`}
                          style={{
                            background: "#030b18",
                            border: `1.5px solid ${isCheapest ? "#14b8a640" : item.isCurrent ? "#818cf840" : "#1e293b"}`,
                            borderRadius: 10,
                            padding: "14px 16px",
                            display: "flex",
                            alignItems: "center",
                            gap: 14,
                          }}
                        >
                          {/* Rank */}
                          <div style={{
                            width: 28, height: 28, borderRadius: "50%",
                            background: isCheapest ? "#14532d" : "#1e293b",
                            color: isCheapest ? "#86efac" : "#64748b",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 13, fontWeight: 800, flexShrink: 0,
                          }}>
                            {i + 1}
                          </div>

                          {/* Image */}
                          {item.image_url && (
                            <img
                              src={item.image_url}
                              alt=""
                              style={{ width: 48, height: 48, objectFit: "contain", borderRadius: 6, background: "#0d1526", flexShrink: 0 }}
                              onError={(e) => { e.target.style.display = "none"; }}
                            />
                          )}

                          {/* Info */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                              <PlatformBadge platform={item.platform} small />
                              {item.isCurrent && (
                                <span style={{ fontSize: 10, color: "#818cf8", fontWeight: 700 }}>CURRENT</span>
                              )}
                              {isCheapest && (
                                <span style={{ fontSize: 10, color: "#86efac", fontWeight: 700, background: "#14532d", padding: "1px 6px", borderRadius: 4 }}>
                                  BEST PRICE
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: 12, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {item.title}
                            </div>
                            {item.rating && (
                              <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>★ {item.rating}</div>
                            )}
                          </div>

                          {/* Price */}
                          <div style={{ textAlign: "right", flexShrink: 0 }}>
                            <div style={{ fontSize: 18, fontWeight: 900, color: isCheapest ? "#86efac" : "#f0f9ff" }}>
                              {INR(item.price)}
                            </div>
                            {!item.isCurrent && diff !== 0 && (
                              <div style={{ fontSize: 11, fontWeight: 700, color: diff < 0 ? "#34d399" : "#f87171", marginTop: 2 }}>
                                {diff < 0 ? "▼" : "▲"} {INR(Math.abs(diff))} ({diff < 0 ? "" : "+"}{diffPct}%)
                              </div>
                            )}
                          </div>

                          {/* Link */}
                          {item.product_url && !item.isCurrent && (
                            <a
                              href={item.product_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                background: "#1e293b", color: "#94a3b8",
                                border: "none", borderRadius: 6,
                                padding: "6px 10px", fontSize: 11, fontWeight: 600,
                                textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0,
                              }}
                            >
                              View →
                            </a>
                          )}
                        </div>
                      );
                    })}

                    {/* Summary */}
                    <div style={{ marginTop: 6, background: "#030b18", borderRadius: 8, padding: "10px 14px", border: "1px solid #1e293b", fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>
                      <strong style={{ color: "#94a3b8" }}>Summary: </strong>
                      {allPrices[0].isCurrent
                        ? `You already have the best price on ${product.platform}! 🎉`
                        : `${allPrices[0].platform} has it cheaper by ${INR(product.current_price - allPrices[0].price)}. Consider switching!`
                      }
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 10, fontSize: 10, color: "#1e293b", textAlign: "center" }}>
                  All prices scraped live from each platform at {new Date(product.scraped_at).toLocaleTimeString("en-IN")}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* ── EMPTY STATE ── */}
      {!product && !loading && (
        <div style={{ maxWidth: 560, margin: "80px auto", textAlign: "center", padding: "0 24px" }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>🛒</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: "#e2e8f0", marginBottom: 10 }}>Track & Compare Product Prices</div>
          <div style={{ fontSize: 14, color: "#475569", lineHeight: 1.7 }}>
            Paste a product URL from Amazon, Flipkart, Myntra, or Snapdeal.<br />
            We'll scrape the price and automatically compare it across other platforms — all live.
          </div>
        </div>
      )}

      {/* ── FOOTER ── */}
      <div style={{ borderTop: "1px solid #1e293b", marginTop: 48, padding: "20px 28px", textAlign: "center" }}>
        <div style={{ fontSize: 12, color: "#334155" }}>
          ⚡ PriceTracker · All prices scraped live · Selenium + BeautifulSoup · No fake data
        </div>
      </div>
    </div>
  );
}
