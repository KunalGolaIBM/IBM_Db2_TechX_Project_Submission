/**
 * Futuristic Web Audio Synthesizer for AAA Cyberpunk UI
 * Generates instant crisp SFX without external audio asset downloads.
 */

class SoundEngine {
  private ctx: AudioContext | null = null;
  private sfxVolume: number = 0.8;
  private masterVolume: number = 0.8;

  private initContext() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
  }

  public updateVolumes(master: number, sfx: number) {
    this.masterVolume = Math.max(0, Math.min(1, master / 100));
    this.sfxVolume = Math.max(0, Math.min(1, sfx / 100));
  }

  private getEffectiveVolume(): number {
    return this.masterVolume * this.sfxVolume;
  }

  /** Subtle futuristic cyber hover tick */
  public playHover() {
    try {
      // Hover sounds must not create or resume an AudioContext.
      if (!this.ctx || this.ctx.state !== 'running') return;
      const vol = this.getEffectiveVolume() * 0.15;
      if (vol <= 0.001) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1800, this.ctx.currentTime + 0.04);

      gain.gain.setValueAtTime(vol, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.04);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + 0.05);
    } catch {
      // Audio autoplay policy fallback
    }
  }

  /** High-impact cybernetic button click */
  public playClick() {
    try {
      this.initContext();
      if (!this.ctx) return;
      const vol = this.getEffectiveVolume() * 0.25;
      if (vol <= 0.001) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(440, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880, this.ctx.currentTime + 0.08);

      gain.gain.setValueAtTime(vol, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.09);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + 0.1);
    } catch {}
  }

  /** Cyberpunk menu select / start game chord */
  public playLaunch() {
    try {
      this.initContext();
      if (!this.ctx) return;
      const vol = this.getEffectiveVolume() * 0.3;
      if (vol <= 0.001) return;

      const notes = [440, 554.37, 659.25, 880]; // A major cyber chord
      notes.forEach((freq, idx) => {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime + idx * 0.03);

        const startTime = this.ctx.currentTime + idx * 0.03;
        gain.gain.setValueAtTime(0.001, startTime);
        gain.gain.linearRampToValueAtTime(vol * 0.3, startTime + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.35);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(startTime);
        osc.stop(startTime + 0.36);
      });
    } catch {}
  }

  /** Power-up pickup chime */
  public playPowerUp() {
    try {
      this.initContext();
      if (!this.ctx) return;
      const vol = this.getEffectiveVolume() * 0.25;
      if (vol <= 0.001) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, this.ctx.currentTime); // C5
      osc.frequency.exponentialRampToValueAtTime(1046.5, this.ctx.currentTime + 0.15); // C6

      gain.gain.setValueAtTime(vol, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.2);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + 0.22);
    } catch {}
  }

  /** Coin / ByteCoin collect blip */
  public playCoin() {
    try {
      this.initContext();
      if (!this.ctx) return;
      const vol = this.getEffectiveVolume() * 0.18;
      if (vol <= 0.001) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(987.77, this.ctx.currentTime); // B5
      osc.frequency.setValueAtTime(1318.51, this.ctx.currentTime + 0.06); // E6

      gain.gain.setValueAtTime(vol, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.12);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + 0.13);
    } catch {}
  }

  /** Game pause audio cue */
  public playPause() {
    try {
      this.initContext();
      if (!this.ctx) return;
      const vol = this.getEffectiveVolume() * 0.2;
      if (vol <= 0.001) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(700, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(350, this.ctx.currentTime + 0.1);

      gain.gain.setValueAtTime(vol, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.12);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + 0.13);
    } catch {}
  }
}

export const soundEngine = new SoundEngine();
