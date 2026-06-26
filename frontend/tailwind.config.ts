import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class", // selalu mode terang (tak ikut dark mode OS)
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tema utama: mint hijau. Warna khas brand-200 = #ADF7B6.
        brand: {
          50: "#effef4",
          100: "#d7fce2",
          200: "#adf7b6",
          300: "#7eec93",
          400: "#42d869",
          500: "#1bbf4c",
          600: "#0f9d3d",
          700: "#0f7c34",
          800: "#11622d",
          900: "#0f5028",
        },
      },
      boxShadow: {
        glow: "0 10px 30px -8px rgba(27, 191, 76, 0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
