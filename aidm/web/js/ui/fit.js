// Keeps the phone controller exactly as tall as the visible page (mobile browsers with a bottom toolbar make
// 100dvh taller than what is on screen). Sets --app-h on the root element.
export function fitViewport(win = window) {
  const root = win.document.documentElement;
  const apply = () => {
    const height = win.visualViewport?.height || win.innerHeight;
    root.style.setProperty('--app-h', `${Math.round(height)}px`);
  };
  apply();
  win.addEventListener('resize', apply);
  win.addEventListener('orientationchange', apply);
  win.visualViewport?.addEventListener('resize', apply);
}
