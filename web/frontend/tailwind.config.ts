import type { Config } from "tailwindcss";

// One theme for the whole app — the Kestrel palette. The landing page keeps its
// own *layout* CSS (components/landing/styles.ts) but shares these tokens, so
// landing and dashboard read as one product.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#07090D",
        panel: "#10151C",
        panel2: "#141B24",
        border: "#1C232D",
        fg: "#E8EFF6",
        muted: "#9AA7B8",
        axis: "#7D8A9C",
        accent: "#26D9E4",
        accentDim: "#0E7C86",
        pos: "#34D399",
        neg: "#F87171",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
