(function () {
  if (window.localStorage && window.localStorage.getItem("adminTheme") === null) {
    window.localStorage.setItem("adminTheme", JSON.stringify("light"));
  }
})();
