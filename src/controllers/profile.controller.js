exports.getProfile = (req, res) => {
  res.json({
    message: "Profile data fetched successfully",
    user: req.user
  });
};
