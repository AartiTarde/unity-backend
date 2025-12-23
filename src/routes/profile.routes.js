const router = require("express").Router();
const authMiddleware = require("../middleware/auth.middleware");
const controller = require("../controllers/profile.controller");

router.get("/profile", authMiddleware, controller.getProfile);

module.exports = router;
