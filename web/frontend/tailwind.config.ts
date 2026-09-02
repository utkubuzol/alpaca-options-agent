import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0e14",
        panel: "#141922",
        border: "#232a36",
        accent: "#4f9cf9",
      },
    },
  },
  plugins: [],
};
export default config;
