import { useState } from "react";
import MapView from "./MapView";
import "./index.css";

export interface SelectedLocation {
  lat: number;
  lng: number;
  address: string;
}

function App() {
  const [searchValue, setSearchValue] = useState("");
  const [selectedLocation, setSelectedLocation] =
    useState<SelectedLocation | null>(null);

  const handleMapLocationSelect = (location: SelectedLocation) => {
    setSelectedLocation(location);
    setSearchValue(location.address);
  };

  const handleSearch = async () => {
    if (!searchValue.trim()) return;

    try {
      const query = encodeURIComponent(searchValue.trim());

      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${query}&format=json&limit=1`
      );
      const data = await res.json();

      if (!data || data.length === 0) {
        alert("Address not found.");
        return;
      }

      const result = data[0];
      const lat = parseFloat(result.lat);
      const lng = parseFloat(result.lon);

      setSelectedLocation({
        lat,
        lng,
        address: result.display_name,
      });

      setSearchValue(result.display_name);
    } catch (error) {
      console.error("Geocoding error:", error);
      alert("Failed to search address.");
    }
  };

  const handleReset = () => {
    setSelectedLocation(null);
    setSearchValue("");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-badge">DS</div>
          <div>
            <h1>DataSiteAI</h1>
            <p>Data Center Siting & Environmental Impact Intelligence</p>
          </div>
        </div>

        <div className="topbar-actions">
          <div className="search-wrap">
            <input
              type="text"
              placeholder="Search address, city, or coordinates..."
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearch();
                }
              }}
            />
          </div>

          <button className="secondary-btn" onClick={handleReset}>
            Reset View
          </button>
          <button className="primary-btn" onClick={handleSearch}>
            Analyze Site
          </button>
        </div>
      </header>

      <div className="dashboard-layout">
        <aside className="left-panel">
          <div className="panel-card">
            <div className="panel-card-header">
              <h2>Environmental Overlays</h2>
              <span className="panel-pill">Live Mock</span>
            </div>

            <div className="toggle-list">
              <label className="toggle-row">
                <input type="checkbox" defaultChecked />
                <span>Flood &amp; Drought</span>
              </label>

              <label className="toggle-row">
                <input type="checkbox" />
                <span>Carbon Emissions</span>
              </label>

              <label className="toggle-row">
                <input type="checkbox" />
                <span>Wildfire Risk</span>
              </label>

              <label className="toggle-row">
                <input type="checkbox" />
                <span>Deforestation</span>
              </label>

              <label className="toggle-row">
                <input type="checkbox" />
                <span>Urban Heat</span>
              </label>
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-card-header">
              <h2>Analysis Mode</h2>
            </div>

            <div className="stack-sm">
              <button className="mode-btn active">Site Selection</button>
              <button className="mode-btn">Regional Comparison</button>
              <button className="mode-btn">Weighted Scoring</button>
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-card-header">
              <h2>Scoring Inputs</h2>
            </div>

            <div className="metric-preview">
              <div className="metric-row">
                <span>Environmental Risk</span>
                <strong>Pending</strong>
              </div>
              <div className="metric-row">
                <span>Community Utility Impact</span>
                <strong>Pending</strong>
              </div>
              <div className="metric-row">
                <span>Economic Potential</span>
                <strong>Pending</strong>
              </div>
              <div className="metric-row">
                <span>Land Score Metric</span>
                <strong>—</strong>
              </div>
            </div>
          </div>
        </aside>

        <main className="center-panel">
          <div className="map-card">
            <div className="map-card-header">
              <div>
                <h2>National Site Analysis Map</h2>
                <p>
                  Explore environmental risk layers and evaluate potential data
                  center locations.
                </p>
              </div>

              <div className="legend-mini">
                <span className="legend-dot low"></span>
                <span>Low</span>
                <span className="legend-dot med"></span>
                <span>Medium</span>
                <span className="legend-dot high"></span>
                <span>High</span>
              </div>
            </div>

            <div className="map-stage">
              <MapView
                selectedLocation={selectedLocation}
                onLocationSelect={handleMapLocationSelect}
              />
            </div>
          </div>
        </main>

        <aside className="right-panel">
          <div className="panel-card">
            <div className="panel-card-header">
              <h2>Selected Site</h2>
              <span className="panel-pill muted">
                {selectedLocation ? "Selected" : "No Selection"}
              </span>
            </div>

            <div className="empty-state">
              {selectedLocation ? (
                <>
                  <h3>{selectedLocation.address}</h3>
                  <p>
                    Lat: {selectedLocation.lat.toFixed(4)}, Lng:{" "}
                    {selectedLocation.lng.toFixed(4)}
                  </p>
                </>
              ) : (
                <>
                  <h3>Click a location to begin</h3>
                  <p>
                    Site metrics, weighted analysis, and projected land score
                    will appear here after selection.
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="panel-card score-card">
            <div className="panel-card-header">
              <h2>Land Score Metric</h2>
            </div>

            <div className="score-ring">
              <div className="score-ring-inner">
                <span className="score-value">--</span>
                <span className="score-label">Pending</span>
              </div>
            </div>

            <div className="score-breakdown">
              <div className="score-item">
                <span>Wildlife Impact</span>
                <strong>--</strong>
              </div>
              <div className="score-item">
                <span>Utility Impact</span>
                <strong>--</strong>
              </div>
              <div className="score-item">
                <span>Economic Outlook</span>
                <strong>--</strong>
              </div>
              <div className="score-item">
                <span>Company Image</span>
                <strong>AI Pending</strong>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;