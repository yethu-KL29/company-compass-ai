import { App } from "./App";
import { PublicPage } from "./features/public/PublicPage";

/** Two entry pages share the existing API; admin writes stay server-authorized. */
export function Application() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  return path === "/admin" ? <App /> : <PublicPage />;
}
