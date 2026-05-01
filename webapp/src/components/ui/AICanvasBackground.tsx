import { useEffect, useRef } from 'react';
import { useUiStore } from '@/store/uiStore';

/* ── Aurora canvas — dark: vivid purple/blue/teal blobs + breathing dot grid
                     light: barely-visible grey tones
──────────────────────────────────────────────────────────────────────────── */

export function AICanvasBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const theme = useUiStore((s) => s.theme);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let w = canvas.width  = window.innerWidth;
    let h = canvas.height = window.innerHeight;
    let frame = 0;

    const onResize = () => {
      w = canvas.width  = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', onResize);

    const isDark = theme === 'dark';

    type Blob = {
      x: number; y: number;
      rx: number; ry: number;
      angle: number;
      vx: number; vy: number; va: number;
      colors: [string, string];
    };

    const blobs: Blob[] = isDark
      ? [
          /* blob 1 — deep purple */
          {
            x: w * 0.18, y: h * 0.72,
            rx: w * 0.48, ry: h * 0.30,
            angle: -0.35, vx: 0.18, vy: -0.08, va: 0.00018,
            colors: ['rgba(120, 40, 220, 0.72)', 'rgba(120, 40, 220, 0)'],
          },
          /* blob 2 — indigo/blue */
          {
            x: w * 0.82, y: h * 0.68,
            rx: w * 0.42, ry: h * 0.26,
            angle: 0.28, vx: -0.14, vy: -0.06, va: -0.00014,
            colors: ['rgba(70, 60, 200, 0.60)', 'rgba(70, 60, 200, 0)'],
          },
          /* blob 3 — dark violet accent */
          {
            x: w * 0.50, y: h * 0.90,
            rx: w * 0.32, ry: h * 0.14,
            angle: 0.10, vx: 0.08, vy: -0.04, va: 0.00010,
            colors: ['rgba(90, 20, 180, 0.45)', 'rgba(90, 20, 180, 0)'],
          },
          /* blob 4 — teal edge ribbon for depth */
          {
            x: w * 0.90, y: h * 0.20,
            rx: w * 0.28, ry: h * 0.18,
            angle: -0.55, vx: -0.10, vy: 0.06, va: 0.00008,
            colors: ['rgba(0, 190, 190, 0.28)', 'rgba(0, 190, 190, 0)'],
          },
        ]
      : [
          /* light mode: barely-there warm greys */
          {
            x: w * 0.20, y: h * 0.75,
            rx: w * 0.45, ry: h * 0.28,
            angle: -0.30, vx: 0.12, vy: -0.06, va: 0.00012,
            colors: ['rgba(0,0,0,0.055)', 'rgba(0,0,0,0)'],
          },
          {
            x: w * 0.80, y: h * 0.70,
            rx: w * 0.40, ry: h * 0.22,
            angle: 0.25, vx: -0.10, vy: -0.05, va: -0.00010,
            colors: ['rgba(0,0,0,0.040)', 'rgba(0,0,0,0)'],
          },
          {
            x: w * 0.50, y: h * 0.88,
            rx: w * 0.30, ry: h * 0.12,
            angle: 0.08, vx: 0.06, vy: -0.03, va: 0.00008,
            colors: ['rgba(0,0,0,0.030)', 'rgba(0,0,0,0)'],
          },
          {
            x: w * 0.85, y: h * 0.18,
            rx: w * 0.22, ry: h * 0.14,
            angle: -0.45, vx: -0.07, vy: 0.04, va: 0.00006,
            colors: ['rgba(0,0,0,0.025)', 'rgba(0,0,0,0)'],
          },
        ];

    /* dot-grid config */
    const DOT_GAP    = 24;
    const DOT_R      = 0.9;
    const DOT_ALPHA  = isDark ? 0.18 : 0.13;

    function drawBlobsOffscreen(): HTMLCanvasElement {
      const off = document.createElement('canvas');
      off.width  = w;
      off.height = h;
      const octx = off.getContext('2d')!;

      blobs.forEach(b => {
        octx.save();
        octx.translate(b.x, b.y);
        octx.rotate(b.angle);

        const grad = octx.createRadialGradient(0, 0, 0, 0, 0, Math.max(b.rx, b.ry));
        grad.addColorStop(0,   b.colors[0]);
        grad.addColorStop(0.5, b.colors[0].replace(/[\d.]+\)$/, '0.25)'));
        grad.addColorStop(1,   b.colors[1]);

        octx.scale(b.rx / Math.max(b.rx, b.ry), b.ry / Math.max(b.rx, b.ry));
        octx.beginPath();
        octx.arc(0, 0, Math.max(b.rx, b.ry), 0, Math.PI * 2);
        octx.fillStyle = grad;
        octx.fill();
        octx.restore();
      });

      return off;
    }

    function draw() {
      if (!ctx) return;
      frame++;

      /* Background */
      ctx.fillStyle = isDark ? '#0a0a0a' : '#f5f5f5';
      ctx.fillRect(0, 0, w, h);

      /* Aurora blobs */
      ctx.save();
      ctx.filter = isDark ? 'blur(80px)' : 'blur(60px)';
      ctx.drawImage(drawBlobsOffscreen(), 0, 0);
      ctx.filter = 'none';
      ctx.restore();

      /* Breathing dot grid — dots near blob centres glow brighter */
      const breathe = 0.5 + 0.5 * Math.sin(frame * 0.012);

      for (let x = DOT_GAP / 2; x < w; x += DOT_GAP) {
        for (let y = DOT_GAP / 2; y < h; y += DOT_GAP) {
          /* proximity boost from nearest blob */
          let boost = 0;
          if (isDark) {
            for (const b of blobs) {
              const dx = x - b.x;
              const dy = y - b.y;
              const d  = Math.sqrt(dx * dx + dy * dy);
              const influence = Math.max(0, 1 - d / (b.rx * 1.4));
              boost = Math.max(boost, influence * 0.22 * breathe);
            }
          }
          const alpha = Math.min(0.55, DOT_ALPHA + boost);
          ctx.fillStyle = isDark
            ? `rgba(255,255,255,${alpha})`
            : `rgba(0,0,0,${alpha})`;
          ctx.beginPath();
          ctx.arc(x, y, DOT_R, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      /* Drift blobs */
      blobs.forEach(b => {
        b.x     += b.vx;
        b.y     += b.vy;
        b.angle += b.va;
        if (b.x < -b.rx * 0.5) b.vx =  Math.abs(b.vx);
        if (b.x >  w + b.rx * 0.5) b.vx = -Math.abs(b.vx);
        if (b.y < -b.ry * 0.5) b.vy =  Math.abs(b.vy);
        if (b.y >  h + b.ry * 0.5) b.vy = -Math.abs(b.vy);
      });

      animId = requestAnimationFrame(draw);
    }

    draw();
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0 block pointer-events-none"
    />
  );
}
