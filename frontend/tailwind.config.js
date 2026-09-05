/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'Avenir Next', 'sans-serif'],
        display: ['Space Grotesk', 'Avenir Next', 'sans-serif']
      },
      colors: {
        ink: '#172a3a',
        teal: { 50: '#edfafa', 600: '#0f8b8d', 700: '#087f82', 800: '#076669' }
      },
      boxShadow: {
        panel: '0 14px 34px rgba(37, 66, 76, 0.08)'
      }
    }
  },
  plugins: []
};
