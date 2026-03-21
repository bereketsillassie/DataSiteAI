import MapView from "./MapView";
import "./index.css";

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>DataSiteAI</h1>
          <p>Data Center Impact Analysis Dashboard</p>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <h2>Overlays</h2>

          <div className="sidebar-section">
            <label>
              <input type="checkbox" /> Carbon Emissions
            </label>
            <label>
              <input type="checkbox" /> Wildfire Risk
            </label>
            <label>
              <input type="checkbox" /> Flood & Drought
            </label>
            <label>
              <input type="checkbox" /> Deforestation
            </label>
            <label>
              <input type="checkbox" /> Urban Heat
            </label>
          </div>

          <h2>Analysis</h2>
          <div className="sidebar-section">
            <p>Select a location on the map to view:</p>
            <ul>
              <li>Land score</li>
              <li>Wildlife impact</li>
              <li>Utility/community impact</li>
              <li>Mock ROI</li>
            </ul>
          </div>
        </aside>

        <main className="app-main">
          <div className="map-panel">
            <MapView />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;