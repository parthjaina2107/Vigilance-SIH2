import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // Command Center palette
        "vc-bg": "#090d16",
        "vc-panel": "rgba(15, 23, 42, 0.45)",
        "vc-border": "rgba(255, 255, 255, 0.09)",
        // Neon accent system
        "neon-cyan": "#22d3ee",
        "neon-green": "#4ade80",
        "neon-amber": "#fbbf24",
        "neon-red": "#f87171",
        "neon-blue": "#60a5fa",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        display: ["Geist", "Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        "neon-cyan": "0 0 20px rgba(34, 211, 238, 0.3), 0 0 60px rgba(34, 211, 238, 0.1)",
        "neon-green": "0 0 20px rgba(74, 222, 128, 0.3), 0 0 60px rgba(74, 222, 128, 0.1)",
        "neon-amber": "0 0 20px rgba(251, 191, 36, 0.3), 0 0 60px rgba(251, 191, 36, 0.1)",
        "neon-red": "0 0 20px rgba(248, 113, 113, 0.3), 0 0 60px rgba(248, 113, 113, 0.1)",
        "glass-inset": "inset 0 1px 0 0 rgba(255, 255, 255, 0.1)",
        "command-glow": "0 4px 30px rgba(0, 0, 0, 0.5), 0 0 50px rgba(34, 211, 238, 0.05)",
      },
      animation: {
        "radar-ping": "radar-ping 2s cubic-bezier(0, 0, 0.2, 1) infinite",
        "neon-pulse": "neon-pulse 2.5s ease-in-out infinite",
        "gauge-fill": "gauge-fill 1.5s ease-out forwards",
        "slide-up": "slide-up 0.5s ease-out",
        "glow-breathe": "glow-breathe 3s ease-in-out infinite",
      },
      keyframes: {
        "radar-ping": {
          "0%": { transform: "scale(0.5)", opacity: "1" },
          "100%": { transform: "scale(2.5)", opacity: "0" },
        },
        "neon-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "gauge-fill": {
          "0%": { width: "0%" },
          "100%": { width: "var(--gauge-target)" },
        },
        "slide-up": {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "glow-breathe": {
          "0%, 100%": { boxShadow: "0 0 15px rgba(34, 211, 238, 0.2)" },
          "50%": { boxShadow: "0 0 30px rgba(34, 211, 238, 0.5)" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
export default config;
