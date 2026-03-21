import express from "express";

const app = express();

app.use(express.json());

app.get("/", (_req, res) => {
  res.send("Backend running");
});

app.listen(5000, () => {
  console.log("Server running on port 5000");
});