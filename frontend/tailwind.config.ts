import type { Config } from "tailwindcss";
import colors from "tailwindcss/colors";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        brand: {
          50: "#eef9ff",
          100: "#d8f0ff",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
        },
        surface: {
          DEFAULT: "var(--surface)",
          elevated: "var(--surface-elevated)",
          card: "var(--surface-card)",
        },
        "app-border": "var(--app-border)",
        muted: "var(--muted)",
        // Neutros zinc alinhados à landing (substitui o slate azulado)
        slate: {
          50: colors.zinc[50],
          100: colors.zinc[100],
          200: colors.zinc[200],
          300: colors.zinc[300],
          400: colors.zinc[400],
          500: colors.zinc[500],
          600: colors.zinc[600],
          700: "#27272a",
          800: "#161618",
          900: "#111113",
          950: "#0a0a0b",
        },
        // Accent sky = brand da landing (propaga para todos os cyan-* existentes)
        cyan: { ...colors.sky },
      },
      boxShadow: {
        glow: "0 0 80px rgba(14, 165, 233, 0.15)",
        "brand-sm": "0 10px 40px rgba(14, 165, 233, 0.2)",
      },
    },
  },
  plugins: [],
};
export default config;
