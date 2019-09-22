window.addEventListener("load", function() {                                                                      
  if (window._noVNC_has_module_support) return;
  var loader = document.createElement("script");
  loader.src = "vendor/browser-es-module-loader/dist/browser-es-module-loader.js";
  document.head.appendChild(loader);
});
