const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const users = require("../models/user.model");

exports.signup = async (req, res) => {
  const { email, password } = req.body;

  if (!email || !password)
    return res.status(400).json({ message: "Missing fields" });

  const exists = users.find(u => u.email === email);
  if (exists)
    return res.status(409).json({ message: "User already exists" });

  const hash = await bcrypt.hash(password, 10);

  users.push({
    id: users.length + 1,
    email,
    password: hash
  });

  res.status(201).json({ message: "User created" });
};

exports.login = async (req, res) => {
  const { email, password } = req.body;

  const user = users.find(u => u.email === email);
  if (!user)
    return res.status(401).json({ message: "Invalid credentials" });

  const valid = await bcrypt.compare(password, user.password);
  if (!valid)
    return res.status(401).json({ message: "Invalid credentials" });

  const token = jwt.sign(
    { userId: user.id, email: user.email },
    process.env.JWT_SECRET,
    { expiresIn: "1h" }
  );

  res.json({
    accessToken: token,
    expiresIn: 3600
  });
};
