import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "pulse-slow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "orb-breathe": {
          "0%, 100%": { transform: "scale(1)", boxShadow: "0 0 0 0 rgba(99, 102, 241, 0.35)" },
          "50%": { transform: "scale(1.04)", boxShadow: "0 0 0 0 rgba(99, 102, 241, 0.15)" },
        },
        "orb-listen": {
          "0%, 100%": { transform: "scale(1)", filter: "drop-shadow(0 0 12px rgba(34, 211, 238, 0.5))" },
          "50%": { transform: "scale(1.06)", filter: "drop-shadow(0 0 18px rgba(34, 211, 238, 0.75))" },
        },
        "orb-wobble": {
          "0%, 100%": { transform: "rotate(-2deg)" },
          "50%": { transform: "rotate(2deg)" },
        },
        "orb-speak": {
          "0%, 100%": { transform: "scale(1)", filter: "drop-shadow(0 0 14px rgba(217, 70, 239, 0.55))" },
          "50%": { transform: "scale(1.08)", filter: "drop-shadow(0 0 22px rgba(217, 70, 239, 0.85))" },
        },
        "orb-ring-spin": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pulse-slow": "pulse-slow 2s ease-in-out infinite",
        "orb-breathe": "orb-breathe 3s ease-in-out infinite",
        "orb-listen": "orb-listen 1.2s ease-in-out infinite",
        "orb-wobble": "orb-wobble 0.35s ease-in-out infinite",
        "orb-speak": "orb-speak 0.55s ease-in-out infinite",
        "orb-ring-spin": "orb-ring-spin 8s linear infinite",
        "orb-ring-spin-fast": "orb-ring-spin 1.2s linear infinite",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
