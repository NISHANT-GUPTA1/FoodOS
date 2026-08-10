/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // Mirrors the horizon tokens in src/index.css :root. Keep the two in
      // step — §7 H0-3 asks for one colour per horizon, and this file and
      // that one previously disagreed on all three.
      colors: {
        prevent: { DEFAULT: '#10b981', ink: '#047857' },
        preserve: { DEFAULT: '#f59e0b', ink: '#9a6700' },
        recover: { DEFAULT: '#ef4444', ink: '#ba1a1a' },
      },
    },
  },
  plugins: [],
}