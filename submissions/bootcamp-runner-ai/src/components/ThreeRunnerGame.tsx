import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { Character, GameSettings } from '../types/game';
import { soundEngine } from '../utils/audio';

interface ThreeRunnerGameProps {
  selectedCharacter: Character;
  settings: GameSettings;
  isPaused: boolean;
  onScoreUpdate: (score: number, distance: number, coins: number, multiplier: number) => void;
  onDamage: (newHealth: number) => void;
  onGameOver: (finalScore: number, distance: number, coins: number, obstaclesAvoided: number) => void;
  onPowerUpCollect: (type: 'shield' | 'magnet' | 'multiplier') => void;
  activePowerUps: { type: string; durationRemaining: number }[];
}

export const ThreeRunnerGame: React.FC<ThreeRunnerGameProps> = ({
  selectedCharacter,
  settings,
  isPaused,
  onScoreUpdate,
  onDamage,
  onGameOver,
  onPowerUpCollect,
  activePowerUps,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const gameStateRef = useRef({
    score: 0,
    distance: 0,
    coins: 0,
    multiplier: 1,
    health: 100,
    obstaclesAvoided: 0,
    isGameOver: false,
    speed: 26, // units per second
    lane: 0, // -1: Left, 0: Center, 1: Right
    targetLaneX: 0,
    currentX: 0,
    isJumping: false,
    jumpVelocity: 0,
    jumpY: 0,
    isSliding: false,
    slideTimer: 0,
    runCycle: 0,
  });

  // Keep references to mutable props
  const propsRef = useRef({
    selectedCharacter,
    settings,
    isPaused,
    onScoreUpdate,
    onDamage,
    onGameOver,
    onPowerUpCollect,
    activePowerUps,
  });

  useEffect(() => {
    propsRef.current = {
      selectedCharacter,
      settings,
      isPaused,
      onScoreUpdate,
      onDamage,
      onGameOver,
      onPowerUpCollect,
      activePowerUps,
    };
  }, [selectedCharacter, settings, isPaused, onScoreUpdate, onDamage, onGameOver, onPowerUpCollect, activePowerUps]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Detect software WebGL guard from skill
    const isSoftwareGl = (() => {
      try {
        const gl = document.createElement('canvas').getContext('webgl2');
        if (!gl) return true;
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        const param = ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER;
        const gpu = String(gl.getParameter(param));
        gl.getExtension('WEBGL_lose_context')?.loseContext();
        return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
      } catch {
        return false;
      }
    })();

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080b12);
    scene.fog = new THREE.FogExp2(0x080b12, 0.018);

    // 2. Camera setup (third-person chase cam)
    const camera = new THREE.PerspectiveCamera(
      65,
      container.clientWidth / container.clientHeight,
      0.1,
      200
    );
    camera.position.set(0, 3.4, 6.2);
    camera.lookAt(0, 1.4, -6);

    // 3. Renderer setup
    const renderer = new THREE.WebGLRenderer({
      antialias: !isSoftwareGl,
      powerPreference: 'high-performance',
      alpha: false,
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    // 4. Studio Lighting
    const ambientLight = new THREE.AmbientLight(0x1a243b, 1.8);
    scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(0x00e5ff, 0x8b5cf6, 1.2);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 2.5);
    dirLight.position.set(5, 12, 6);
    scene.add(dirLight);

    // Point lights for cyber track glow
    const playerGlowLight = new THREE.PointLight(
      new THREE.Color(propsRef.current.selectedCharacter.accentColor || 0x00e5ff),
      3,
      12
    );
    playerGlowLight.position.set(0, 2, 0);
    scene.add(playerGlowLight);

    // 5. Track construction (3 Lanes: Left: -2.3, Center: 0, Right: +2.3)
    const LANE_WIDTH = 2.3;
    const TRACK_LENGTH = 160;

    // Road Plane with glowing cyber grid
    const roadGeo = new THREE.PlaneGeometry(8, TRACK_LENGTH, 1, 40);
    const roadMat = new THREE.MeshStandardMaterial({
      color: 0x0c1322,
      roughness: 0.35,
      metalness: 0.7,
    });
    const roadMesh = new THREE.Mesh(roadGeo, roadMat);
    roadMesh.rotation.x = -Math.PI / 2;
    roadMesh.position.set(0, 0, -TRACK_LENGTH / 2 + 10);
    scene.add(roadMesh);

    // Glowing Lane Dividers
    const laneDividerMat = new THREE.MeshBasicMaterial({
      color: 0x00e5ff,
      transparent: true,
      opacity: 0.6,
    });
    const dividerGeo = new THREE.BoxGeometry(0.08, 0.02, TRACK_LENGTH);
    const leftDivider = new THREE.Mesh(dividerGeo, laneDividerMat);
    leftDivider.position.set(-LANE_WIDTH / 2, 0.01, -TRACK_LENGTH / 2 + 10);
    scene.add(leftDivider);

    const rightDivider = new THREE.Mesh(dividerGeo, laneDividerMat);
    rightDivider.position.set(LANE_WIDTH / 2, 0.01, -TRACK_LENGTH / 2 + 10);
    scene.add(rightDivider);

    // Outer Track Guardrails with pulse glow
    const railMat = new THREE.MeshStandardMaterial({
      color: 0x8b5cf6,
      emissive: 0x8b5cf6,
      emissiveIntensity: 0.4,
      metalness: 0.9,
      roughness: 0.2,
    });
    const railGeo = new THREE.BoxGeometry(0.2, 0.4, TRACK_LENGTH);
    const leftRail = new THREE.Mesh(railGeo, railMat);
    leftRail.position.set(-4, 0.2, -TRACK_LENGTH / 2 + 10);
    scene.add(leftRail);

    const rightRail = new THREE.Mesh(railGeo, railMat);
    rightRail.position.set(4, 0.2, -TRACK_LENGTH / 2 + 10);
    scene.add(rightRail);

    // Decorative Flanking Server Towers along the sides
    const serverTowers: THREE.Mesh[] = [];
    const serverGeo = new THREE.BoxGeometry(1.5, 9, 2);
    const serverMat = new THREE.MeshStandardMaterial({
      color: 0x090e17,
      roughness: 0.4,
      metalness: 0.8,
    });
    for (let i = 0; i < 16; i++) {
      const zPos = -i * 12 + 10;
      const leftServer = new THREE.Mesh(serverGeo, serverMat);
      leftServer.position.set(-6, 4.5, zPos);
      scene.add(leftServer);
      serverTowers.push(leftServer);

      const rightServer = new THREE.Mesh(serverGeo, serverMat);
      rightServer.position.set(6, 4.5, zPos);
      scene.add(rightServer);
      serverTowers.push(rightServer);
    }

    // Overhead Arch Gates (Neon Portal Arches)
    const archGates: THREE.Group[] = [];
    const archMat = new THREE.MeshStandardMaterial({
      color: 0x00e5ff,
      emissive: 0x00e5ff,
      emissiveIntensity: 0.8,
      roughness: 0.2,
    });
    for (let i = 0; i < 6; i++) {
      const arch = new THREE.Group();
      const topBar = new THREE.Mesh(new THREE.BoxGeometry(9, 0.3, 0.3), archMat);
      topBar.position.y = 5;
      const leftCol = new THREE.Mesh(new THREE.BoxGeometry(0.3, 5, 0.3), archMat);
      leftCol.position.set(-4.5, 2.5, 0);
      const rightCol = new THREE.Mesh(new THREE.BoxGeometry(0.3, 5, 0.3), archMat);
      rightCol.position.set(4.5, 2.5, 0);
      arch.add(topBar, leftCol, rightCol);
      arch.position.set(0, 0, -i * 30);
      scene.add(arch);
      archGates.push(arch);
    }

    // 6. BUILD THE 3D RUNNER CHARACTER (Multi-Part Procedural Model)
    // As per Three.js guidelines: composite 3-12 part procedural model with distinct parts
    const characterColor = new THREE.Color(propsRef.current.selectedCharacter.accentColor || '#00E5FF');
    const runnerGroup = new THREE.Group();

    // Grounding Contact Shadow
    const shadowGeo = new THREE.PlaneGeometry(1.2, 1.2);
    const shadowMat = new THREE.MeshBasicMaterial({
      color: 0x000000,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    });
    const shadowMesh = new THREE.Mesh(shadowGeo, shadowMat);
    shadowMesh.rotation.x = -Math.PI / 2;
    shadowMesh.position.y = 0.02;
    runnerGroup.add(shadowMesh);

    // Torso / Exosuit Armor
    const torsoGeo = new THREE.BoxGeometry(0.68, 0.85, 0.42);
    const suitMat = new THREE.MeshStandardMaterial({
      color: 0x111827,
      metalness: 0.8,
      roughness: 0.25,
    });
    const torsoMesh = new THREE.Mesh(torsoGeo, suitMat);
    torsoMesh.position.y = 1.35;
    runnerGroup.add(torsoMesh);

    // Glowing Core Reactor on Torso (Neon Accent)
    const coreGeo = new THREE.BoxGeometry(0.35, 0.45, 0.08);
    const coreMat = new THREE.MeshStandardMaterial({
      color: characterColor,
      emissive: characterColor,
      emissiveIntensity: 1.2,
      roughness: 0.1,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    coreMesh.position.set(0, 1.35, -0.22); // Facing running direction (z-)
    runnerGroup.add(coreMesh);

    // Back Jetpack Thrusters
    const jetpackGeo = new THREE.BoxGeometry(0.48, 0.6, 0.22);
    const jetpackMat = new THREE.MeshStandardMaterial({
      color: 0x1f2937,
      metalness: 0.9,
      roughness: 0.2,
    });
    const jetpackMesh = new THREE.Mesh(jetpackGeo, jetpackMat);
    jetpackMesh.position.set(0, 1.4, 0.26);
    runnerGroup.add(jetpackMesh);

    // Jetpack Thruster Flame Nozzles
    const nozzleMat = new THREE.MeshBasicMaterial({ color: characterColor });
    const leftNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.04, 0.2), nozzleMat);
    leftNozzle.position.set(-0.16, 1.05, 0.26);
    const rightNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.04, 0.2), nozzleMat);
    rightNozzle.position.set(0.16, 1.05, 0.26);
    runnerGroup.add(leftNozzle, rightNozzle);

    // Cyber Helmet & Visor
    const headGeo = new THREE.BoxGeometry(0.44, 0.44, 0.44);
    const headMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.85,
      roughness: 0.2,
    });
    const headMesh = new THREE.Mesh(headGeo, headMat);
    headMesh.position.y = 2.05;
    runnerGroup.add(headMesh);

    // Visor HUD Strip
    const visorGeo = new THREE.BoxGeometry(0.36, 0.14, 0.08);
    const visorMat = new THREE.MeshStandardMaterial({
      color: characterColor,
      emissive: characterColor,
      emissiveIntensity: 1.8,
    });
    const visorMesh = new THREE.Mesh(visorGeo, visorMat);
    visorMesh.position.set(0, 2.05, -0.23);
    runnerGroup.add(visorMesh);

    // Left Arm Hierarchy
    const leftArmGroup = new THREE.Group();
    leftArmGroup.position.set(-0.46, 1.65, 0);
    const armGeo = new THREE.BoxGeometry(0.2, 0.65, 0.22);
    const armMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.7,
      roughness: 0.3,
    });
    const leftArmMesh = new THREE.Mesh(armGeo, armMat);
    leftArmMesh.position.y = -0.3;
    leftArmGroup.add(leftArmMesh);
    runnerGroup.add(leftArmGroup);

    // Right Arm Hierarchy
    const rightArmGroup = new THREE.Group();
    rightArmGroup.position.set(0.46, 1.65, 0);
    const rightArmMesh = new THREE.Mesh(armGeo, armMat);
    rightArmMesh.position.y = -0.3;
    rightArmGroup.add(rightArmMesh);
    runnerGroup.add(rightArmGroup);

    // Left Leg Hierarchy
    const leftLegGroup = new THREE.Group();
    leftLegGroup.position.set(-0.22, 0.95, 0);
    const legGeo = new THREE.BoxGeometry(0.22, 0.85, 0.24);
    const legMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.8,
      roughness: 0.3,
    });
    const leftLegMesh = new THREE.Mesh(legGeo, legMat);
    leftLegMesh.position.y = -0.42;
    leftLegGroup.add(leftLegMesh);

    // Left Boot
    const bootGeo = new THREE.BoxGeometry(0.24, 0.2, 0.38);
    const bootMat = new THREE.MeshStandardMaterial({
      color: characterColor,
      emissive: characterColor,
      emissiveIntensity: 0.4,
      metalness: 0.5,
    });
    const leftBootMesh = new THREE.Mesh(bootGeo, bootMat);
    leftBootMesh.position.set(0, -0.8, -0.06);
    leftLegGroup.add(leftBootMesh);
    runnerGroup.add(leftLegGroup);

    // Right Leg Hierarchy
    const rightLegGroup = new THREE.Group();
    rightLegGroup.position.set(0.22, 0.95, 0);
    const rightLegMesh = new THREE.Mesh(legGeo, legMat);
    rightLegMesh.position.y = -0.42;
    rightLegGroup.add(rightLegMesh);

    // Right Boot
    const rightBootMesh = new THREE.Mesh(bootGeo, bootMat);
    rightBootMesh.position.set(0, -0.8, -0.06);
    rightLegGroup.add(rightBootMesh);
    runnerGroup.add(rightLegGroup);

    // Active Shield Sphere Hologram around Runner
    const shieldSphereGeo = new THREE.SphereGeometry(1.6, 24, 24);
    const shieldSphereMat = new THREE.MeshBasicMaterial({
      color: 0x00e5ff,
      wireframe: true,
      transparent: true,
      opacity: 0,
    });
    const shieldSphereMesh = new THREE.Mesh(shieldSphereGeo, shieldSphereMat);
    shieldSphereMesh.position.y = 1.3;
    runnerGroup.add(shieldSphereMesh);

    scene.add(runnerGroup);

    // 7. DYNAMIC OBSTACLES & COLLECTIBLES ARRAYS
    interface ActiveObstacle {
      mesh: THREE.Group;
      lane: number;
      z: number;
      type: 'BUG' | 'LASER_GATE';
      collided: boolean;
      avoided: boolean;
    }

    interface ActiveCoin {
      mesh: THREE.Group;
      lane: number;
      z: number;
      collected: boolean;
    }

    const obstacles: ActiveObstacle[] = [];
    const coins: ActiveCoin[] = [];

    // Helper to spawn a bug / firewall obstacle
    const spawnObstacle = (zPos: number) => {
      const lane = Math.floor(Math.random() * 3) - 1; // -1, 0, 1
      const isLaser = Math.random() > 0.65;
      const group = new THREE.Group();

      if (isLaser) {
        // High laser barrier: player must SLIDE under!
        const postMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8 });
        const leftPost = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 3), postMat);
        leftPost.position.set(-LANE_WIDTH / 2.2, 1.5, 0);
        const rightPost = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 3), postMat);
        rightPost.position.set(LANE_WIDTH / 2.2, 1.5, 0);

        const beamMat = new THREE.MeshBasicMaterial({ color: 0xec4899 });
        const beam = new THREE.Mesh(new THREE.BoxGeometry(LANE_WIDTH, 0.35, 0.2), beamMat);
        beam.position.set(0, 1.7, 0); // High beam: must slide under!

        group.add(leftPost, rightPost, beam);
        group.position.set(lane * LANE_WIDTH, 0, zPos);
        scene.add(group);
        obstacles.push({ mesh: group, lane, z: zPos, type: 'LASER_GATE', collided: false, avoided: false });
      } else {
        // Red Glitch Firewall Bug: player must JUMP over or switch lanes!
        const bugMat = new THREE.MeshStandardMaterial({
          color: 0xef4444,
          emissive: 0xef4444,
          emissiveIntensity: 0.8,
          roughness: 0.2,
        });
        const barrier = new THREE.Mesh(new THREE.BoxGeometry(LANE_WIDTH * 0.85, 0.9, 0.6), bugMat);
        barrier.position.y = 0.45;

        // Glitch antenna / spikes
        const spike = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.5, 4), bugMat);
        spike.position.set(0, 1.1, 0);
        group.add(barrier, spike);

        group.position.set(lane * LANE_WIDTH, 0, zPos);
        scene.add(group);
        obstacles.push({ mesh: group, lane, z: zPos, type: 'BUG', collided: false, avoided: false });
      }
    };

    // Helper to spawn ByteCoins
    const coinGeo = new THREE.OctahedronGeometry(0.35, 0);
    const coinMat = new THREE.MeshStandardMaterial({
      color: 0xa3ff12,
      emissive: 0xa3ff12,
      emissiveIntensity: 0.9,
      metalness: 0.4,
      roughness: 0.1,
    });

    const spawnCoinsCluster = (startZ: number) => {
      const lane = Math.floor(Math.random() * 3) - 1;
      for (let i = 0; i < 4; i++) {
        const coinGroup = new THREE.Group();
        const mesh = new THREE.Mesh(coinGeo, coinMat);
        coinGroup.add(mesh);
        coinGroup.position.set(lane * LANE_WIDTH, 0.9, startZ - i * 3.5);
        scene.add(coinGroup);
        coins.push({ mesh: coinGroup, lane, z: startZ - i * 3.5, collected: false });
      }
    };

    // Initial Spawns ahead of player
    for (let i = 1; i <= 6; i++) {
      spawnObstacle(-i * 24);
      spawnCoinsCluster(-i * 24 - 10);
    }

    // 8. CONTROLS INPUT DISPATCHER
    const moveLeft = () => {
      if (gameStateRef.current.isGameOver) return;
      if (gameStateRef.current.lane > -1) {
        gameStateRef.current.lane -= 1;
        gameStateRef.current.targetLaneX = gameStateRef.current.lane * LANE_WIDTH;
        soundEngine.playClick();
      }
    };

    const moveRight = () => {
      if (gameStateRef.current.isGameOver) return;
      if (gameStateRef.current.lane < 1) {
        gameStateRef.current.lane += 1;
        gameStateRef.current.targetLaneX = gameStateRef.current.lane * LANE_WIDTH;
        soundEngine.playClick();
      }
    };

    const jump = () => {
      if (gameStateRef.current.isGameOver) return;
      if (!gameStateRef.current.isJumping && !gameStateRef.current.isSliding) {
        gameStateRef.current.isJumping = true;
        gameStateRef.current.jumpVelocity = 14;
        soundEngine.playHover();
      }
    };

    const slide = () => {
      if (gameStateRef.current.isGameOver) return;
      if (!gameStateRef.current.isSliding && !gameStateRef.current.isJumping) {
        gameStateRef.current.isSliding = true;
        gameStateRef.current.slideTimer = 0.65; // seconds
        soundEngine.playHover();
      }
    };

    // Keyboard listener
    const onKeyDown = (e: KeyboardEvent) => {
      if (propsRef.current.isPaused || gameStateRef.current.isGameOver) return;
      if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') moveLeft();
      if (e.key === 'd' || e.key === 'D' || e.key === 'ArrowRight') moveRight();
      if (e.key === 'w' || e.key === 'W' || e.key === ' ' || e.key === 'ArrowUp') jump();
      if (e.key === 's' || e.key === 'S' || e.key === 'ArrowDown') slide();
    };

    window.addEventListener('keydown', onKeyDown);

    // Touch gesture swipe support
    let touchStartX = 0;
    let touchStartY = 0;
    const onTouchStart = (e: TouchEvent) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    };
    const onTouchEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].screenX - touchStartX;
      const dy = e.changedTouches[0].screenY - touchStartY;
      if (Math.abs(dx) > Math.abs(dy)) {
        if (dx > 30) moveRight();
        else if (dx < -30) moveLeft();
      } else {
        if (dy < -30) jump();
        else if (dy > 30) slide();
      }
    };

    window.addEventListener('touchstart', onTouchStart);
    window.addEventListener('touchend', onTouchEnd);

    // 9. ANIMATION & GAME LOOP
    const clock = new THREE.Clock();
    let frameId = 0;

    const tick = () => {
      frameId = requestAnimationFrame(tick);

      const delta = Math.min(clock.getDelta(), 0.1);
      if (propsRef.current.isPaused || gameStateRef.current.isGameOver) {
        renderer.render(scene, camera);
        return;
      }

      const state = gameStateRef.current;
      const forwardMove = state.speed * delta;

      // Advance distance & score
      state.distance += forwardMove;
      state.score += Math.round(forwardMove * 3 * state.multiplier);
      propsRef.current.onScoreUpdate(
        state.score,
        Math.floor(state.distance),
        state.coins,
        state.multiplier
      );

      // 10. Update Character Running Kinematics & Animation
      state.runCycle += delta * 14;

      // Lateral smooth lane interpolation (smooth lerp)
      state.currentX = THREE.MathUtils.damp(state.currentX, state.targetLaneX, 16, delta);
      runnerGroup.position.x = state.currentX;

      // Slight banking tilt when switching lanes
      const targetRoll = (state.targetLaneX - state.currentX) * -0.15;
      runnerGroup.rotation.z = THREE.MathUtils.damp(runnerGroup.rotation.z, targetRoll, 10, delta);

      // Jump Physics
      if (state.isJumping) {
        state.jumpVelocity -= 36 * delta; // gravity
        state.jumpY += state.jumpVelocity * delta;
        if (state.jumpY <= 0) {
          state.jumpY = 0;
          state.isJumping = false;
          state.jumpVelocity = 0;
        }
      }

      // Slide Physics
      if (state.isSliding) {
        state.slideTimer -= delta;
        if (state.slideTimer <= 0) {
          state.isSliding = false;
        }
      }

      // Position runner vertical Y
      runnerGroup.position.y = state.jumpY;

      // Scale shadow based on jump height
      const shadowScale = Math.max(0.4, 1 - state.jumpY * 0.35);
      shadowMesh.scale.set(shadowScale, shadowScale, shadowScale);
      shadowMat.opacity = 0.6 * shadowScale;

      // Leg & Arm Running Gait Animation
      if (state.isSliding) {
        // Duck down low
        torsoMesh.position.y = 0.7;
        torsoMesh.rotation.x = 0.5;
        headMesh.position.y = 1.15;
        leftLegGroup.rotation.x = -1.2;
        rightLegGroup.rotation.x = -1.2;
        leftArmGroup.rotation.x = 0.9;
        rightArmGroup.rotation.x = 0.9;
      } else if (state.isJumping) {
        // Tuck knees in air
        torsoMesh.position.y = 1.35;
        torsoMesh.rotation.x = 0.1;
        headMesh.position.y = 2.05;
        leftLegGroup.rotation.x = -0.6;
        rightLegGroup.rotation.x = -0.3;
        leftArmGroup.rotation.x = -1.2;
        rightArmGroup.rotation.x = -1.2;
      } else {
        // Normal Running Cycle: rhythmic arm & leg swings
        torsoMesh.position.y = 1.35 + Math.sin(state.runCycle * 2) * 0.05; // torso bounce
        torsoMesh.rotation.x = 0.12; // slight forward run lean
        headMesh.position.y = 2.05 + Math.sin(state.runCycle * 2) * 0.05;

        const legSwing = Math.sin(state.runCycle) * 0.85;
        leftLegGroup.rotation.x = legSwing;
        rightLegGroup.rotation.x = -legSwing;

        const armSwing = Math.sin(state.runCycle) * 0.75;
        leftArmGroup.rotation.x = -armSwing;
        rightArmGroup.rotation.x = armSwing;
      }

      // Check Shield Active from props
      const hasShield = propsRef.current.activePowerUps.some((p) => p.type === 'shield');
      shieldSphereMat.opacity = hasShield ? 0.45 + Math.sin(state.runCycle * 4) * 0.15 : 0;
      shieldSphereMesh.rotation.y += delta * 2;

      // Dynamic light follows player
      playerGlowLight.position.x = runnerGroup.position.x;
      playerGlowLight.position.y = runnerGroup.position.y + 2;

      // Camera dynamic follow with slight damping
      camera.position.x = THREE.MathUtils.damp(camera.position.x, runnerGroup.position.x * 0.6, 8, delta);

      // 11. Move Track & Scenery to create continuous illusion of velocity
      // Move obstacles towards player (+Z direction)
      for (let i = obstacles.length - 1; i >= 0; i--) {
        const obs = obstacles[i];
        obs.z += forwardMove;
        obs.mesh.position.z = obs.z;

        // Collision Check with player (player is at z=0, width ≈ 1.0)
        const inLane = Math.abs(obs.lane * LANE_WIDTH - runnerGroup.position.x) < 1.0;
        const inZ = obs.z > -1.2 && obs.z < 1.0;

        if (inLane && inZ && !obs.collided) {
          // Check evasion mechanics:
          let evaded = false;
          if (obs.type === 'BUG' && state.jumpY > 1.0) {
            evaded = true; // jumped over bug!
          }
          if (obs.type === 'LASER_GATE' && state.isSliding) {
            evaded = true; // slid under laser!
          }

          if (!evaded) {
            obs.collided = true;
            if (hasShield) {
              // Shield absorbs the bug!
              soundEngine.playPowerUp();
              obs.mesh.position.y = -20; // vaporize
            } else {
              // Direct hit!
              soundEngine.playClick();
              state.health = Math.max(0, state.health - 25);
              propsRef.current.onDamage(state.health);

              // Screen shake cue
              camera.position.y += (Math.random() - 0.5) * 0.4;

              if (state.health <= 0) {
                state.isGameOver = true;
                soundEngine.playPause();
                propsRef.current.onGameOver(
                  state.score,
                  Math.floor(state.distance),
                  state.coins,
                  state.obstaclesAvoided
                );
                return;
              }
            }
          }
        }

        // Obstacle passed behind player
        if (obs.z > 10) {
          if (!obs.collided && !obs.avoided) {
            obs.avoided = true;
            state.obstaclesAvoided += 1;
          }
          scene.remove(obs.mesh);
          obstacles.splice(i, 1);
          // Spawn new obstacle far ahead
          const furthestZ = obstacles.reduce((min, o) => Math.min(min, o.z), 0);
          spawnObstacle(furthestZ - 26);
        }
      }

      // Move Coins
      const hasMagnet = propsRef.current.activePowerUps.some((p) => p.type === 'magnet');
      for (let i = coins.length - 1; i >= 0; i--) {
        const c = coins[i];
        c.z += forwardMove;
        c.mesh.position.z = c.z;
        c.mesh.rotation.y += delta * 4;

        // Magnet attraction effect
        if (hasMagnet && Math.abs(c.z) < 16) {
          c.mesh.position.x = THREE.MathUtils.damp(c.mesh.position.x, runnerGroup.position.x, 8, delta);
          c.mesh.position.y = THREE.MathUtils.damp(c.mesh.position.y, runnerGroup.position.y + 1, 8, delta);
        }

        // Collection collision
        const inLane = Math.abs(c.mesh.position.x - runnerGroup.position.x) < 1.1;
        const inZ = c.z > -1.2 && c.z < 1.2;
        const inY = Math.abs(c.mesh.position.y - (runnerGroup.position.y + 1)) < 1.4;

        if (inLane && inZ && inY && !c.collected) {
          c.collected = true;
          state.coins += 1;
          state.score += 50 * state.multiplier;
          soundEngine.playCoin();
          scene.remove(c.mesh);
          coins.splice(i, 1);
          continue;
        }

        // Coin passed behind player
        if (c.z > 10) {
          scene.remove(c.mesh);
          coins.splice(i, 1);
          if (coins.length < 12) {
            const furthestZ = coins.reduce((min, o) => Math.min(min, o.z), 0);
            spawnCoinsCluster(furthestZ - 22);
          }
        }
      }

      // Move Overhead Arches
      archGates.forEach((arch) => {
        arch.position.z += forwardMove;
        if (arch.position.z > 15) {
          arch.position.z -= 180;
        }
      });

      // Move Side Server Towers
      serverTowers.forEach((tower) => {
        tower.position.z += forwardMove;
        if (tower.position.z > 15) {
          tower.position.z -= 192;
        }
      });

      renderer.render(scene, camera);
    };

    tick();

    // 12. Window Resize Handler
    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    // Clean disposal
    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchend', onTouchEnd);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className="absolute inset-0 w-full h-full z-0 overflow-hidden"
    />
  );
};
