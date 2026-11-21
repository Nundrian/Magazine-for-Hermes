(function () {
  'use strict';
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React } = SDK;
  function Magazine() {
    const ref = React.useRef(null);
    React.useEffect(() => {
      let cleanup, disposed = false;
      import((window.__HERMES_BASE_PATH__ || '') + '/dashboard-plugins/magazine/dist/entry.mjs').then(module => {
        if (!disposed) cleanup = module.default.mount(ref.current);
      }).catch(error => { if (ref.current) ref.current.textContent = 'Magazine failed to load: ' + error.message; });
      return () => { disposed = true; if (cleanup) cleanup(); };
    }, []);
    return React.createElement('div', { ref });
  }
  window.__HERMES_PLUGINS__.register('magazine', Magazine);
})();
