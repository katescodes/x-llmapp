import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";

const toNumber = (value?: string, fallback?: number): number | undefined => {
  if (value === undefined || value === "") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? fallback : parsed;
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "", "");

  const devPort = toNumber(env.VITE_DEV_SERVER_PORT, 6173) ?? 6173;

  const backendProtocol = env.VITE_BACKEND_PROTOCOL || "http";
  const backendHost = env.VITE_BACKEND_HOST || "127.0.0.1";
  const backendPort = toNumber(
    env.VITE_BACKEND_PORT,
    toNumber(env.VITE_API_PORT, 9001)
  ) ?? 9001;

  const publicHost = env.VITE_DEV_SERVER_PUBLIC_HOST || undefined;
  const publicPort = toNumber(env.VITE_DEV_SERVER_PUBLIC_PORT);
  const publicProtocol = env.VITE_DEV_SERVER_PUBLIC_PROTOCOL || undefined;

  const hmrHost = env.VITE_DEV_SERVER_HMR_HOST || publicHost;
  const hmrPort = toNumber(
    env.VITE_DEV_SERVER_HMR_PORT,
    toNumber(env.VITE_DEV_SERVER_PORT, devPort)
  );
  const hmrProtocol =
    env.VITE_DEV_SERVER_HMR_PROTOCOL || publicProtocol || undefined;
  const hmrClientPort = toNumber(
    env.VITE_DEV_SERVER_HMR_CLIENT_PORT,
    publicPort ?? hmrPort ?? devPort
  );

  const shouldConfigureHmr = Boolean(
    hmrHost ||
      env.VITE_DEV_SERVER_HMR_PORT ||
      env.VITE_DEV_SERVER_HMR_PROTOCOL ||
      env.VITE_DEV_SERVER_HMR_CLIENT_PORT ||
      publicHost ||
      publicPort ||
      publicProtocol
  );

  const resolvedHmr = shouldConfigureHmr
    ? {
        host: hmrHost,
        port: hmrPort ?? devPort,
        protocol: hmrProtocol,
        clientPort: hmrClientPort
      }
    : undefined;

  const proxyTarget =
    env.VITE_DEV_PROXY_TARGET ||
    `${backendProtocol}://${backendHost}:${backendPort}`;

  const shouldDisableProxy =
    env.VITE_DISABLE_DEV_PROXY === "1" ||
    env.VITE_DISABLE_DEV_PROXY?.toLowerCase() === "true";

  const proxy = shouldDisableProxy
    ? undefined
    : {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false
        },
        "/health": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false
        },
        "/docs": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false
        }
      };

  return {
    base: "/ylAI/",
    plugins: [react()],
    server: {
      port: devPort,
      host: "0.0.0.0",
      allowedHosts: true,
      hmr: {
        protocol: "wss",
        host: "ai.yglinker.com",
        clientPort: 6399,
        path: "/ylAI/"
      },
      proxy
    }
  };
});
