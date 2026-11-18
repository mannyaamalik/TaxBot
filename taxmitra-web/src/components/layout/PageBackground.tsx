"use client";
import { useEffect, useRef } from "react";

export function PageBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf: number;
    let w = window.innerWidth;
    let h = window.innerHeight;

    // Simple floating particle system
    const particles = Array.from({ length: 40 }, () => ({
      x:  Math.random() * w,
      y:  Math.random() * h,
      r:  Math.random() * 2 + 0.5,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      a:  Math.random() * 0.4 + 0.1,
    }));

    function resize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas!.width  = w;
      canvas!.height = h;
    }
    resize();
    window.addEventListener("resize", resize);

    let t = 0;
    function draw() {
      ctx!.clearRect(0, 0, w, h);
      t += 0.004;

      // Soft gradient mesh
      const grd = ctx!.createRadialGradient(
        w * (0.3 + 0.1 * Math.sin(t)),
        h * (0.3 + 0.1 * Math.cos(t)),
        0,
        w * 0.5, h * 0.5, w * 0.8
      );
      grd.addColorStop(0,   "rgba(255,153,51,0.06)");
      grd.addColorStop(0.5, "rgba(19,136,8,0.04)");
      grd.addColorStop(1,   "rgba(11,16,32,0)");
      ctx!.fillStyle = grd;
      ctx!.fillRect(0, 0, w, h);

      // Second gradient moving opposite direction
      const grd2 = ctx!.createRadialGradient(
        w * (0.7 + 0.1 * Math.cos(t * 0.7)),
        h * (0.6 + 0.1 * Math.sin(t * 0.7)),
        0,
        w * 0.5, h * 0.5, w * 0.9
      );
      grd2.addColorStop(0,   "rgba(59,130,246,0.05)");
      grd2.addColorStop(1,   "rgba(11,16,32,0)");
      ctx!.fillStyle = grd2;
      ctx!.fillRect(0, 0, w, h);

      // Particles
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(255,153,51,${p.a * (0.5 + 0.5 * Math.sin(t + p.x))})`;
        ctx!.fill();
      });

      raf = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      id="particle-canvas"
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}
    />
  );
}
