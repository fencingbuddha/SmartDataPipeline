import MetricDailyCard from "./components/MetricDailyCard";

function App() {
  return (
    <div style={{ maxWidth: 720, margin: "32px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginTop: 0 }}>Smart Data Pipeline – Dashboard (Seed)</h1>
      <MetricDailyCard />
    </div>
  );
}

export default App;
