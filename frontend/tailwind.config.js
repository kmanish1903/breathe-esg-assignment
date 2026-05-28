/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#f7f8f6",
        line: "#d8ded8",
        moss: "#496f5d",
        coral: "#bf5b4b",
        amber: "#b7791f",
      },
      boxShadow: {
        soft: "0 18px 45px rgba(23, 32, 38, 0.08)",
      },
    },
  },
  plugins: [],
};
