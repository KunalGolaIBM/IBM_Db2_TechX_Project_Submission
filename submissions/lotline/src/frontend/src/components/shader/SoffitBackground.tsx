import React, { useEffect, useRef, useState } from 'react';

// Soffit 002 Calibrated Palette:
// Deep marine navy upper -> rich ocean blue -> radiant cyan -> luminous turquoise -> seafoam highlight
const COLOR_CONFIG = {
  bgColor: [3 / 255, 12 / 255, 26 / 255],     // #030c1a: Deep velvety marine navy upper
  colorA: [8 / 255, 32 / 255, 60 / 255],      // #08203c: Ocean shadow with deep blue returning bounce
  colorB: [16 / 255, 78 / 255, 120 / 255],    // #104e78: Rich marine twilight cyan
  colorC: [24 / 255, 140 / 255, 168 / 255],   // #188ca8: Soft luminous turquoise
  colorD: [64 / 255, 205 / 255, 200 / 255],   // #40cdc8: Gentle seafoam highlight (no white glare)
};

// Soffit 002 Calibrated Shader Parameters:
// Directional falloff from broad luminous lower region into deep marine upper atmosphere
const SHADER_PARAMS = {
  ambient: 0.10,
  amount: 0.28,
  bounce: 0.26,
  bounceCurve: 2.8,
  breathe: 0.12,
  contrast: 1.60,
  curve: 2.85,
  direct: 0.72,
  dither: 0.85,
  flow: 0.20,
  glow: 0.12,
  grain: 0.02,
  grainAnim: 0.0,
  horizon: -0.42,
  lacunarity: 2.02,
  lift: 0.10,
  midpoint: 0.54,
  moteScale: 6.5,
  motes: 0.03,
  parallax: 0.003,
  rock: 0.08,
  roughness: 0.45,
  scale: 0.75,
  sink: 0.20,
  speed: 0.20,
  spillCentre: 0.12,
  spillFloor: 0.18,
  spillWidth: 1.80,
  spread: 0.95,
  steer: 0.15,
  sweep: 0.25,
  tilt: -1.38,
  vignette: 0.30,
  warp: 2.20,
  warpScale: 0.80,
};

const VERTEX_SHADER = `#version 300 es
in vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

out vec4 fragColor;

uniform vec2 iResolution;
uniform float iTime;
uniform vec2 iMouse;
uniform float uScale;

uniform vec3 uBg, uColorA, uColorB, uColorC, uColorD;

uniform float uSpeed, uTilt, uRock, uHorizon;
uniform float uBreathe, uSpread, uCurve, uDirect;
uniform float uBounce, uBounceCurve;

uniform float uSpillCentre, uSpillWidth, uSpillFloor;

uniform float uAmount, uWarp, uWarpScale, uFlow;
uniform float uRoughness, uLacunarity, uMotes, uMoteScale;

uniform float uAmbient, uContrast, uMidpoint;
uniform float uSink, uGlow;

uniform float uGrain, uGrainAnim, uDither, uVignette;

uniform float uSteer, uLift, uSweep, uParallax;

#define OCTAVES 4

vec2 hash2(vec2 p) {
    p = vec2(
        dot(p, vec2(127.1, 311.7)),
        dot(p, vec2(269.5, 183.3))
    );
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

float snoise(vec2 p) {
    const float K1 = 0.366025404;
    const float K2 = 0.211324865;

    vec2 i = floor(p + (p.x + p.y) * K1);
    vec2 a = p - i + (i.x + i.y) * K2;

    float m = step(a.y, a.x);
    vec2 o = vec2(m, 1.0 - m);

    vec2 b = a - o + K2;
    vec2 c = a - 1.0 + 2.0 * K2;

    vec3 h = max(
        0.5 - vec3(dot(a,a), dot(b,b), dot(c,c)),
        0.0
    );

    vec3 n = h*h*h*h * vec3(
        dot(a,hash2(i)),
        dot(b,hash2(i+o)),
        dot(c,hash2(i+1.0))
    );

    return dot(n,vec3(70.0));
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;

    for (int i = 0; i < OCTAVES; i++) {
        v += amp * snoise(p);
        p *= uLacunarity;
        amp *= uRoughness;
    }

    return v;
}

vec3 ramp4(float t) {
    vec3 c = mix(
        uColorA,
        uColorB,
        smoothstep(0.00, 0.42, t)
    );

    c = mix(
        c,
        uColorC,
        smoothstep(0.36, 0.80, t)
    );

    c = mix(
        c,
        uColorD,
        smoothstep(0.75, 1.00, t)
    );

    return c;
}

float triDither(vec2 fc) {
    float a = fract(
        sin(dot(fc, vec2(12.9898, 78.233))) *
        43758.5453
    );

    float b = fract(
        sin(dot(fc + 17.0, vec2(12.9898, 78.233))) *
        43758.5453
    );

    return (a + b - 1.0) / 255.0;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * iResolution) / iResolution.y;
    uv *= uScale;

    vec2 iM = iMouse * uScale;
    float t = iTime * uSpeed;

    vec2 p = uv - iM * uParallax;

    float tilt = uTilt + sin(t * 0.13) * uRock + iM.x * uSteer;
    vec2 dir = vec2(cos(tilt), sin(tilt));

    float axis = dot(p, dir);
    float across = dot(p, vec2(-dir.y, dir.x));

    vec2 q = vec2(
        fbm(p * uWarpScale + vec2(0.0, t * uFlow)),
        fbm(p * uWarpScale + vec2(5.2, 1.3) - t * uFlow * 0.7)
    );

    float air = fbm(p + uWarp * q + vec2(t * 0.12, -t * 0.09)) * 0.5 + 0.5;

    float horizon = uHorizon + sin(t * 0.09 + 2.1) * uBreathe - iM.y * uLift;

    float alt = clamp(
        0.5 + (axis - horizon) * uSpread + (air - 0.5) * uAmount,
        0.0,
        1.0
    );

    float ac = (across - uSpillCentre - iM.x * uSweep) / max(0.05, uSpillWidth);

    float spill = mix(
        uSpillFloor,
        1.0,
        exp(-ac * ac)
    );

    float direct = pow(alt, max(0.05, uCurve)) * uDirect * spill;
    float bounce = uBounce * pow(1.0 - alt, max(0.05, uBounceCurve));

    float f = uAmbient + direct + bounce;

    f += uMotes * snoise(p * uMoteScale + vec2(-t * 0.5, t * 0.35)) * 0.5 * alt;

    f = clamp(
        (f - uMidpoint) * uContrast + 0.5,
        0.0,
        1.0
    );

    vec3 col = ramp4(f);
    col += uColorD * uGlow * pow(f, 4.0);

    col = mix(
        uBg,
        col,
        smoothstep(0.0, max(0.01, uSink), f) * 0.90 + 0.10
    );

    col *= 1.0 - uVignette * dot(uv, uv);
    col += triDither(gl_FragCoord.xy) * uDither;

    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`;

interface SoffitBackgroundProps {
  containerRef?: React.RefObject<HTMLElement | null>;
}

export const SoffitBackground: React.FC<SoffitBackgroundProps> = ({ containerRef }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Initialize WebGL2 context with alpha disabled for optimal performance
    const gl = canvas.getContext('webgl2', {
      alpha: false,
      depth: false,
      stencil: false,
      antialias: false,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: false,
    });

    if (!gl) {
      console.warn('WebGL2 not supported on this device. Using CSS fallback gradient.');
      setHasError(true);
      return;
    }

    const compileShader = (type: number, source: string): WebGLShader | null => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compilation error:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    };

    const vs = compileShader(gl.VERTEX_SHADER, VERTEX_SHADER);
    const fs = compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);

    if (!vs || !fs) {
      setHasError(true);
      return;
    }

    const program = gl.createProgram();
    if (!program) {
      setHasError(true);
      return;
    }
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      setHasError(true);
      return;
    }

    gl.useProgram(program);

    // Fullscreen single triangle in NDC: (-1, -1), (3, -1), (-1, 3)
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    const positions = new Float32Array([
      -1.0, -1.0,
       3.0, -1.0,
      -1.0,  3.0,
    ]);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const posLocation = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(posLocation);
    gl.vertexAttribPointer(posLocation, 2, gl.FLOAT, false, 0, 0);

    // Uniform Locations
    const uResLoc = gl.getUniformLocation(program, 'iResolution');
    const uTimeLoc = gl.getUniformLocation(program, 'iTime');
    const uMouseLoc = gl.getUniformLocation(program, 'iMouse');
    const uScaleLoc = gl.getUniformLocation(program, 'uScale');

    const uBgLoc = gl.getUniformLocation(program, 'uBg');
    const uColorALoc = gl.getUniformLocation(program, 'uColorA');
    const uColorBLoc = gl.getUniformLocation(program, 'uColorB');
    const uColorCLoc = gl.getUniformLocation(program, 'uColorC');
    const uColorDLoc = gl.getUniformLocation(program, 'uColorD');

    const paramLocs: Record<string, WebGLUniformLocation | null> = {};
    for (const key of Object.keys(SHADER_PARAMS)) {
      const uniformName = 'u' + key.charAt(0).toUpperCase() + key.slice(1);
      paramLocs[key] = gl.getUniformLocation(program, uniformName);
    }

    // Set colors & parameters
    gl.uniform3fv(uBgLoc, COLOR_CONFIG.bgColor);
    gl.uniform3fv(uColorALoc, COLOR_CONFIG.colorA);
    gl.uniform3fv(uColorBLoc, COLOR_CONFIG.colorB);
    gl.uniform3fv(uColorCLoc, COLOR_CONFIG.colorC);
    gl.uniform3fv(uColorDLoc, COLOR_CONFIG.colorD);
    gl.uniform1f(uScaleLoc, SHADER_PARAMS.scale);

    for (const [key, val] of Object.entries(SHADER_PARAMS)) {
      const loc = paramLocs[key];
      if (loc) {
        gl.uniform1f(loc, val);
      }
    }

    // Responsive Canvas Resize using ResizeObserver
    const updateDimensions = () => {
      const targetElement = containerRef?.current || canvas.parentElement || document.body;
      const width = Math.max(targetElement.clientWidth, 320);
      const height = Math.max(targetElement.clientHeight, 400);

      // DPR capped at 1.0 for low-frequency atmospheric gradient performance
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
      gl.uniform2f(uResLoc, width, height);
    };

    updateDimensions();

    const targetElement = containerRef?.current || canvas.parentElement;
    let resizeObserver: ResizeObserver | null = null;
    if (targetElement && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        updateDimensions();
      });
      resizeObserver.observe(targetElement);
    }

    window.addEventListener('resize', updateDimensions);

    // Two-stage pointer physics tracking
    let rawMouseX = 0;
    let rawMouseY = 0;
    let leadX = 0;
    let leadY = 0;
    let bodyX = 0;
    let bodyY = 0;

    const onPointerMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const relX = (e.clientX - rect.left) / rect.width;
      const relY = (e.clientY - rect.top) / rect.height;
      rawMouseX = relX * 2 - 1;
      rawMouseY = -(relY * 2 - 1);
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });

    // Accumulated shader clock with delta clamping (4.17ms - 50ms)
    let accumulatedTime = 0;
    let lastTimestamp = performance.now();
    let animId = 0;
    let isDocumentVisible = !document.hidden;

    const onVisibilityChange = () => {
      isDocumentVisible = !document.hidden;
      if (isDocumentVisible) {
        lastTimestamp = performance.now();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    const onContextLost = (e: Event) => {
      e.preventDefault();
      cancelAnimationFrame(animId);
      setHasError(true);
    };
    canvas.addEventListener('webglcontextlost', onContextLost, false);

    const render = (now: number) => {
      if (!isDocumentVisible) {
        animId = requestAnimationFrame(render);
        return;
      }

      const rawDt = (now - lastTimestamp) / 1000;
      lastTimestamp = now;
      const dt = Math.min(Math.max(rawDt, 0.00417), 0.050);

      if (!prefersReducedMotion) {
        accumulatedTime += dt;
        leadX += (rawMouseX - leadX) * 0.105;
        leadY += (rawMouseY - leadY) * 0.105;
        bodyX += (leadX - bodyX) * 0.043;
        bodyY += (leadY - bodyY) * 0.043;
      } else {
        bodyX = 0;
        bodyY = 0;
      }

      gl.uniform1f(uTimeLoc, accumulatedTime);
      gl.uniform2f(uMouseLoc, bodyX, bodyY);

      gl.drawArrays(gl.TRIANGLES, 0, 3);
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', updateDimensions);
      window.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }

      gl.deleteBuffer(positionBuffer);
      gl.deleteVertexArray(vao);
      gl.deleteProgram(program);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    };
  }, [containerRef]);

  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-hidden" aria-hidden="true">
      {hasError ? (
        // Soffit 002 High-Fidelity CSS fallback
        <div
          className="w-full h-full"
          style={{
            background: 'linear-gradient(175deg, #041222 0%, #0c365a 45%, #1680ac 75%, #23cad2 100%)',
          }}
        />
      ) : (
        <canvas
          ref={canvasRef}
          className="w-full h-full block"
          style={{ width: '100%', height: '100%' }}
        />
      )}
    </div>
  );
};
