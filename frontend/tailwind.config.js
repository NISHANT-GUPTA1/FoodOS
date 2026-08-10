/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        prevent: '#4ade80',
        preserve: '#f59e0b',
        recover: '#fb7185',
      },
    },
  },
  plugins: [],
}