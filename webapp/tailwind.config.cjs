/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:  ['Geist', 'Inter', 'Arial', 'Apple Color Emoji', 'Segoe UI Emoji', 'sans-serif'],
        mono:  ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'Roboto Mono', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
        /* keep display alias pointing to same sans stack */
        display: ['Geist', 'Inter', 'Arial', 'sans-serif'],
      },
      colors: {
        /* ── Surfaces ── */
        'surface-page':   'var(--surface-page)',
        'surface-card':   'var(--surface-card)',
        'surface-input':  'var(--surface-input)',
        'surface-soft':   'var(--surface-soft)',
        'surface-strong': 'var(--surface-strong)',

        /* ── Legacy component surfaces ── */
        'c-base':   'var(--c-base)',
        'c-deep':   'var(--c-deep)',
        'c-float':  'var(--c-float)',
        'c-raised': 'var(--c-raised)',

        /* ── Text ── */
        't-primary':    'var(--t-primary)',
        't-secondary':  'var(--t-secondary)',
        't-label':      'var(--t-secondary)',    /* alias */
        't-muted':      'var(--t-muted)',
        't-placeholder':'var(--t-placeholder)',
        't-on-primary': 'var(--t-on-primary)',

        /* ── Borders ── */
        'b-subtle':  'var(--b-subtle)',
        'b-medium':  'var(--b-medium)',
        'b-strong':  'var(--b-strong)',
        'b-divider': 'var(--b-divider)',

        /* ── Neutral scale ── */
        'vos-black': 'var(--vos-black)',
        'vos-600':   'var(--vos-600)',
        'vos-500':   'var(--vos-500)',
        'vos-400':   'var(--vos-400)',
        'vos-200':   'var(--vos-200)',
        'vos-50':    'var(--vos-50)',

        /* ── Ink aliases ── */
        'ink':         'var(--vos-black)',
        'ink-primary': 'var(--btn-primary-bg)',

        /* ── Workflow accents ── */
        'ship-red':     'var(--ship-red)',
        'preview-pink': 'var(--preview-pink)',
        'dev-blue':     'var(--dev-blue)',
        'link-blue':    'var(--link-blue)',

        /* ── Badge ── */
        'badge-bg':   'var(--badge-bg)',
        'badge-text': 'var(--badge-text)',

        /* ── Semantic ── */
        'semantic-success': 'var(--semantic-success)',
        'semantic-error':   'var(--semantic-error)',
        'semantic-warning': 'var(--semantic-warning)',
      },
      boxShadow: {
        'border':  'var(--shadow-border)',
        'ring':    'var(--shadow-ring)',
        'card':    'var(--shadow-card)',
        'soft':    'var(--shadow-soft)',
        'focus':   'var(--focus-ring)',
      },
      borderRadius: {
        'none':  '0px',
        'xs':    '2px',
        'sm':    '4px',
        DEFAULT: '6px',
        'md':    '6px',
        'lg':    '8px',
        'xl':    '12px',
        '2xl':   '16px',
        '3xl':   '24px',
        'pill':  '64px',
        'full':  '9999px',
      },
      letterSpacing: {
        /* Geist compression scale */
        'display-xl':   '-2.88px',
        'display-lg':   '-2.4px',
        'display-md':   '-1.28px',
        'display-sm':   '-0.96px',
        'display-xs':   '-0.32px',
        'editorial':    '0px',
      },
      fontSize: {
        'display-hero': ['48px', { lineHeight: '1.08', fontWeight: '600', letterSpacing: '-2.4px' }],
        'display-xl':   ['40px', { lineHeight: '1.20', fontWeight: '600', letterSpacing: '-2.4px' }],
        'display-lg':   ['32px', { lineHeight: '1.25', fontWeight: '600', letterSpacing: '-1.28px' }],
        'display-md':   ['24px', { lineHeight: '1.33', fontWeight: '600', letterSpacing: '-0.96px' }],
        'display-sm':   ['20px', { lineHeight: '1.40', fontWeight: '400', letterSpacing: 'normal' }],
        'body-lg':      ['18px', { lineHeight: '1.56', fontWeight: '400' }],
        'body':         ['16px', { lineHeight: '1.50', fontWeight: '400' }],
        'body-sm':      ['14px', { lineHeight: '1.43', fontWeight: '400' }],
        'caption':      ['12px', { lineHeight: '1.33', fontWeight: '500' }],
        'mono-sm':      ['12px', { lineHeight: '1.00', fontWeight: '500' }],
        'micro':        ['7px',  { lineHeight: '1.00', fontWeight: '700' }],
      },
    },
  },
  plugins: [],
}
