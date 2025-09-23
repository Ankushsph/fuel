module.exports = {
  content: [
    './templates/**/*.html',
    './assets/src/**/*.css'
  ],
  theme: {
    extend: {
      colors: {
        'fuel-orange': '#FF6B35',
        'fuel-black': '#1A1A1A',
        'fuel-gray': '#2D2D2D',
        'fuel-green': '#22C55E',
        'fuel-red': '#EF4444',
      },
    },
  },
  safelist: [
    'bg-fuel-green',
    'bg-fuel-black',
    'text-white',
  ],
}