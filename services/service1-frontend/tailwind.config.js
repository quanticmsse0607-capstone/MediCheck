/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        // MediCheck brand colours — to be finalised in Sprint 2 design pass
        brand: {
          primary: '#2B6CB0',
          dark: '#1A365D',
          light: '#EBF8FF',
        },
        severity: {
          high: '#E53E3E',
          'high-bg': '#FFF5F5',
          medium: '#DD6B20',
          'medium-bg': '#FFFAF0',
          info: '#38A169',
          'info-bg': '#F0FFF4',
        },
      },
    },
  },
  plugins: [],
};
