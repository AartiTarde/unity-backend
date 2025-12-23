require("dotenv").config();

const connectDB = require("./config/db");
connectDB(); // 🔴 THIS WAS MISSING

const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.send("Unity Backend API is running");
});

app.use("/api/auth", require("./routes/auth.routes"));
app.use("/api", require("./routes/profile.routes"));

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`API running on port ${PORT}`);
});
